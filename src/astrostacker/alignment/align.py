"""Star-based frame alignment using astroalign.

Uses multiprocessing to align frames in parallel across CPU cores.
On Apple Silicon, targets performance cores for optimal throughput.
"""

from __future__ import annotations

import warnings
from concurrent.futures import ProcessPoolExecutor
from typing import Callable

import astroalign as aa
import numpy as np

from astrostacker.utils.parallel import optimal_workers


def _align_single_frame(args: tuple) -> tuple[int, np.ndarray | None]:
    """Align a single frame to the reference (runs in worker process).

    Args:
        args: Tuple of (index, frame, ref_lum, ref_channels_or_none, is_color).

    Returns:
        Tuple of (original_index, aligned_frame_or_None).
    """
    idx, frame, ref_lum, reference, is_color = args

    try:
        if is_color:
            src_lum = np.mean(frame, axis=2)
            transform, _ = aa.find_transform(src_lum, ref_lum)

            channels = []
            for c in range(frame.shape[2]):
                registered, footprint = aa.apply_transform(
                    transform, frame[:, :, c], reference[:, :, c]
                )
                registered = registered.astype(np.float32)
                registered[footprint] = np.nan
                channels.append(registered)
            return idx, np.stack(channels, axis=2)
        else:
            registered, footprint = aa.register(frame, ref_lum)
            registered = registered.astype(np.float32)
            registered[footprint] = np.nan
            return idx, registered

    except (aa.MaxIterError, ValueError, Exception) as e:
        warnings.warn(
            f"Alignment failed for frame {idx}: {e}. Skipping.",
            stacklevel=2,
        )
        return idx, None


def align_frames(
    frames: list[np.ndarray],
    reference_index: int = 0,
    progress_callback: Callable[[int, int], None] | None = None,
) -> list[np.ndarray]:
    """Align all frames to a reference frame using star pattern matching.

    Uses multiprocessing to align frames in parallel across CPU cores.
    On Apple Silicon, targets performance cores for optimal throughput.

    Pixels outside the overlap region are set to NaN so stacking methods
    using nanmean/nanmedian will naturally exclude them.

    Frames where alignment fails are skipped with a warning.

    Args:
        frames: List of float32 ndarrays (all same shape).
        reference_index: Index of the reference frame to align to.
        progress_callback: Optional callback(current, total) for progress.

    Returns:
        List of aligned frames (may be shorter than input if some fail).
    """
    if not frames:
        raise ValueError("No frames to align")

    reference = frames[reference_index]
    is_color = reference.ndim == 3

    if is_color:
        ref_lum = np.mean(reference, axis=2)
    else:
        ref_lum = reference

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

    if progress_callback:
        progress_callback(completed, total)

    if workers <= 1 or len(work_items) <= 1:
        # Sequential fallback for single frame or single core
        for item in work_items:
            idx, aligned = _align_single_frame(item)
            if aligned is not None:
                results[idx] = aligned
            completed += 1
            if progress_callback:
                progress_callback(completed, total)
    else:
        # Parallel alignment across CPU cores
        with ProcessPoolExecutor(max_workers=workers) as pool:
            for idx, aligned in pool.map(_align_single_frame, work_items):
                if aligned is not None:
                    results[idx] = aligned
                completed += 1
                if progress_callback:
                    progress_callback(completed, total)

    # Return in original order, excluding failed frames
    return [results[i] for i in sorted(results.keys())]
