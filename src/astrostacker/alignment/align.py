"""Star-based frame alignment using astroalign.

Uses thread-parallel alignment across CPU cores. Threading works well
here because numpy, scipy and astroalign release the GIL during their
heavy C-level computations, allowing true parallel execution.

Includes progressively relaxed detection parameters to handle a wide
range of image quality (bright narrowband, faint broadband, etc).
"""

from __future__ import annotations

import sys
import warnings
from concurrent.futures import ThreadPoolExecutor
from typing import Callable

import numpy as np
from skimage.feature import peak_local_max
from skimage.filters import gaussian

import astroalign as aa

from astrostacker.utils.parallel import optimal_workers


def _find_sources_skimage(img, detection_sigma=5, min_area=5, mask=None):
    """Detect star sources using scikit-image (no sep dependency).

    Replaces astroalign's built-in _find_sources which relies on sep_pjw,
    a library that breaks in PyInstaller bundles.
    """
    # Normalise to float64 [0, 1] for scikit-image
    image = np.ascontiguousarray(img, dtype=np.float64)
    image = np.nan_to_num(image, nan=0.0)
    lo, hi = image.min(), image.max()
    if hi > lo:
        image = (image - lo) / (hi - lo)

    # Apply mask if provided
    if mask is not None:
        image[mask] = 0.0

    # Smooth to reduce noise, then find bright peaks (stars)
    smoothed = gaussian(image, sigma=max(1.0, min_area / 2.0))

    # Threshold based on detection_sigma above the median
    median = np.median(smoothed)
    std = np.std(smoothed)
    threshold = median + (detection_sigma * std * 0.3)

    coords = peak_local_max(
        smoothed,
        min_distance=max(3, min_area),
        threshold_abs=max(threshold, 0.01),
        num_peaks=200,
    )

    if len(coords) == 0:
        return np.array([]).reshape(0, 2)

    # Sort by brightness (brightest first) and return as (x, y)
    brightness = [image[r, c] for r, c in coords]
    order = np.argsort(brightness)[::-1]
    coords = coords[order]

    return np.array([[c[1], c[0]] for c in coords], dtype=np.float64)


# Replace astroalign's source detection with our scikit-image version
aa._find_sources = _find_sources_skimage

# Detection parameter sets, tried in order from strict to relaxed.
# Each tuple: (detection_sigma, min_area, max_control_points)
_DETECTION_PROFILES = [
    (5, 5, 50),    # Default - works for most images
    (3, 3, 80),    # More sensitive - picks up fainter stars
    (2, 2, 100),   # Very sensitive - noisy images, few bright stars
]


def _normalise_for_alignment(data: np.ndarray) -> np.ndarray:
    """Normalise image data for astroalign/sep compatibility.

    sep (Source Extractor) requires:
    - Native byte order (FITS files are big-endian, ARM Macs are little-endian)
    - C-contiguous memory layout
    - float32 or float64 dtype

    Normalises to [0, 1] float64 range.
    """
    # Clean non-finite values
    arr = np.nan_to_num(data, nan=0.0, posinf=0.0, neginf=0.0)
    # Force native byte order, float64, C-contiguous in one step
    arr = np.array(arr, dtype=np.float64, order='C')
    # Ensure native byte order explicitly
    if arr.dtype.byteorder not in ('=', '|', '<' if np.little_endian else '>'):
        arr = arr.byteswap().view(arr.dtype.newbyteorder('='))
        arr = np.ascontiguousarray(arr)
    # Normalise to [0, 1]
    lo = arr.min()
    hi = arr.max()
    if hi > lo:
        arr = (arr - lo) / (hi - lo)
    return arr


def _try_find_transform(src_lum, ref_lum):
    """Try progressively more sensitive detection to find a transform.

    Returns the transform and match list, or raises if all profiles fail.
    """
    last_error = None
    for det_sigma, min_area, max_ctrl in _DETECTION_PROFILES:
        try:
            transform, (src_match, ref_match) = aa.find_transform(
                src_lum,
                ref_lum,
                detection_sigma=det_sigma,
                min_area=min_area,
                max_control_points=max_ctrl,
            )
            return transform
        except Exception as e:
            last_error = e
            continue

    raise last_error


def _try_register(src, ref_lum):
    """Try progressively more sensitive detection to register a frame."""
    last_error = None
    for det_sigma, min_area, max_ctrl in _DETECTION_PROFILES:
        try:
            registered, footprint = aa.register(
                src,
                ref_lum,
                detection_sigma=det_sigma,
                min_area=min_area,
                max_control_points=max_ctrl,
            )
            return registered, footprint
        except Exception as e:
            last_error = e
            continue

    raise last_error


def _align_single_frame(args: tuple) -> tuple[int, np.ndarray | None, str]:
    """Align a single frame to the reference.

    Args:
        args: Tuple of (index, frame, ref_lum, reference, is_color).

    Returns:
        Tuple of (original_index, aligned_frame_or_None, error_message).
    """
    idx, frame, ref_lum, reference, is_color = args

    try:
        if is_color:
            src_lum = _normalise_for_alignment(np.mean(frame, axis=2))
            transform = _try_find_transform(src_lum, ref_lum)

            channels = []
            for c in range(frame.shape[2]):
                src_ch = _normalise_for_alignment(frame[:, :, c])
                ref_ch = _normalise_for_alignment(reference[:, :, c])
                registered, footprint = aa.apply_transform(
                    transform, src_ch, ref_ch
                )
                # Scale back to original range of this channel
                ch_lo = np.nanmin(frame[:, :, c])
                ch_hi = np.nanmax(frame[:, :, c])
                registered = (registered * (ch_hi - ch_lo) + ch_lo).astype(np.float32)
                registered[footprint] = np.nan
                channels.append(registered)
            return idx, np.stack(channels, axis=2), ""
        else:
            src_norm = _normalise_for_alignment(frame)
            registered, footprint = _try_register(src_norm, ref_lum)
            # Scale back to original range
            f_lo = np.nanmin(frame)
            f_hi = np.nanmax(frame)
            registered = (registered * (f_hi - f_lo) + f_lo).astype(np.float32)
            registered[footprint] = np.nan
            return idx, registered, ""

    except Exception as e:
        import traceback
        shape = frame.shape
        dtype = frame.dtype
        tb = traceback.format_exc()
        return idx, None, f"{e} [shape={shape}, dtype={dtype}, byteorder={dtype.byteorder}]\n{tb}"


def align_frames(
    frames: list[np.ndarray],
    reference_index: int = 0,
    progress_callback: Callable[[int, int], None] | None = None,
    status_callback: Callable[[str], None] | None = None,
) -> list[np.ndarray]:
    """Align all frames to a reference frame using star pattern matching.

    Uses threads to align frames in parallel across CPU cores.
    Tries progressively more sensitive star detection if initial
    settings fail, to handle a wide range of image types.

    Pixels outside the overlap region are set to NaN so stacking methods
    using nanmean/nanmedian will naturally exclude them.

    Frames where alignment fails are skipped with a warning.

    Args:
        frames: List of float32 ndarrays (all same shape).
        reference_index: Index of the reference frame to align to.
        progress_callback: Optional callback(current, total) for progress.
        status_callback: Optional callback(message) for status messages.

    Returns:
        List of aligned frames (may be shorter than input if some fail).
    """
    if not frames:
        raise ValueError("No frames to align")

    reference = frames[reference_index]
    is_color = reference.ndim == 3

    if is_color:
        ref_lum = _normalise_for_alignment(np.mean(reference, axis=2))
    else:
        ref_lum = _normalise_for_alignment(reference)

    total = len(frames)

    # Build work items for non-reference frames
    work_items = []
    for i, frame in enumerate(frames):
        if i != reference_index:
            work_items.append((i, frame, ref_lum, reference, is_color))

    workers = min(optimal_workers(io_bound=False), len(work_items)) if work_items else 1

    # Collect results keyed by original index
    results: dict[int, np.ndarray] = {reference_index: reference}
    completed = 1  # reference frame counts as done
    failed = 0

    if progress_callback:
        progress_callback(completed, total)

    def _process_result(idx, aligned, error_msg):
        nonlocal completed, failed
        if aligned is not None:
            results[idx] = aligned
        else:
            failed += 1
            msg = f"Frame {idx} failed: {error_msg}"
            if status_callback:
                status_callback(msg)
            warnings.warn(msg, stacklevel=2)
        completed += 1
        if progress_callback:
            progress_callback(completed, total)

    if workers <= 1 or len(work_items) <= 1:
        # Sequential fallback for single frame or single core
        for item in work_items:
            idx, aligned, error_msg = _align_single_frame(item)
            _process_result(idx, aligned, error_msg)
    else:
        # Parallel alignment across CPU cores using threads
        with ThreadPoolExecutor(max_workers=workers) as pool:
            for idx, aligned, error_msg in pool.map(_align_single_frame, work_items):
                _process_result(idx, aligned, error_msg)

    if status_callback:
        ok = len(results)
        status_callback(f"Alignment: {ok}/{total} succeeded, {failed} failed")

    # Return in original order, excluding failed frames
    return [results[i] for i in sorted(results.keys())]
