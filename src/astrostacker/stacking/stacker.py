"""High-level stacking interface."""

import inspect

import numpy as np

from astrostacker.stacking.methods import METHODS


# Row strip height used by _chunked_stack.  Larger values run slightly
# faster (fewer passes) but use proportionally more RAM per strip.
# At 128 rows, 36 ASI294MC colour frames = 128 × 4144 × 3 × 36 × 4 B
# ≈ 144 MB per strip — comfortably under the old np.array() approach
# which needed a full extra ~5 GB copy of all frames simultaneously.
_CHUNK_ROWS = 128


def _normalise_frame_shapes(images: list[np.ndarray]) -> list[np.ndarray]:
    """Trim all frames to the smallest common H × W.

    astroalign uses scipy.ndimage.affine_transform internally.  The output
    shape of the affine transform is determined by the *target* (reference)
    frame shape, but floating-point rounding in the transform matrix can
    occasionally produce a frame that is 1 pixel larger or smaller in one
    dimension.  When that happens np.stack raises:

        ValueError: all input arrays must have the same shape

    This function detects the mismatch and crops every frame to the minimum
    height and width found across the list.  For a 1-pixel discrepancy the
    lost edge region is negligible — it is all NaN (the alignment footprint)
    anyway.

    Args:
        images: List of float32 ndarrays (may have slightly different H/W).

    Returns:
        List where every frame has identical H and W.
    """
    if not images:
        return images

    min_h = min(img.shape[0] for img in images)
    min_w = min(img.shape[1] for img in images)

    # Fast path — all shapes already match
    if all(img.shape[0] == min_h and img.shape[1] == min_w for img in images):
        return images

    if images[0].ndim == 3:
        return [img[:min_h, :min_w, :] for img in images]
    return [img[:min_h, :min_w] for img in images]


def _reject_outlier_pixels(strip: np.ndarray, threshold: float = 10.0) -> np.ndarray:
    """Flag extreme per-pixel outliers as NaN before stacking.

    For each pixel position, computes the median and MAD (Median Absolute
    Deviation) across all N frames.  Any frame whose value at that position
    exceeds median + threshold * MAD_sigma is replaced with NaN so that
    downstream stacking functions (nanmean, nanmedian, sigma_clip) skip it.

    Using MAD rather than std is critical: a single hot pixel inflates the
    regular std dramatically, potentially allowing the outlier to survive a
    2.5-sigma rejection.  MAD is derived from the non-outlier frames and is
    therefore insensitive to the hot pixel value.

    A 10-sigma MAD threshold is intentionally conservative so that genuine
    bright stars and nebula peaks are never masked — only truly extreme
    isolated pixels (hot pixels, cosmic rays, dithered satellite trail
    segments) are removed.

    This pass runs for every stacking method, so hot/cosmic-ray pixels
    cannot sneak through Mean, Weighted Mean, or Noise-Weighted stacks.

    Args:
        strip: (N, H, W) or (N, H, W, C) float32 array.
        threshold: Rejection threshold in MAD-sigma units (default 10).

    Returns:
        Copy of strip with outlier pixels set to NaN.
    """
    if strip.shape[0] < 3:
        return strip  # need at least 3 frames to compute a meaningful MAD

    strip = strip.astype(np.float32, copy=True)
    med = np.nanmedian(strip, axis=0, keepdims=True)          # (1, H, W[, C])
    mad = np.nanmedian(np.abs(strip - med), axis=0, keepdims=True) * 1.4826
    np.maximum(mad, 1e-10, out=mad)                           # avoid /0

    hot = strip > (med + threshold * mad)
    strip[hot] = np.nan
    return strip


def _chunked_stack(
    images: list[np.ndarray],
    method_fn,
    chunk_rows: int = _CHUNK_ROWS,
    **valid_kwargs,
) -> np.ndarray:
    """Stack frames in row strips to avoid creating the full 4-D array.

    ``np.array(images)`` converts the list into one contiguous block that
    is as large as the entire frame list — for 36 ASI294MC colour frames
    that is ~5 GB of extra allocation on top of the list itself.  This
    function instead reads ``chunk_rows`` rows from each frame, stacks
    and reduces them, then moves to the next strip, keeping the extra
    allocation to O(N × chunk_rows × W × C × 4 bytes) ≈ 144 MB.

    A pre-rejection pass (_reject_outlier_pixels) flags hot pixels and
    cosmic rays as NaN before the chosen stacking method runs.

    Args:
        images: List of float32 ndarrays, all the same shape.
        method_fn: Stacking function that accepts an (N, H, W[, C]) array.
        chunk_rows: Row strip height.  Larger = faster, more RAM.
        **valid_kwargs: Pre-filtered kwargs forwarded to the method.

    Returns:
        Stacked result as float32 ndarray, same H×W[×C] shape as inputs.
    """
    first = images[0]
    H, W = first.shape[:2]
    is_colour = first.ndim == 3
    out_shape = (H, W, first.shape[2]) if is_colour else (H, W)
    result = np.empty(out_shape, dtype=np.float32)

    for r0 in range(0, H, chunk_rows):
        r1 = min(r0 + chunk_rows, H)
        # Build strip: (N, strip_H, W) or (N, strip_H, W, C)
        strip = np.stack(
            [img[r0:r1].astype(np.float32) for img in images],
            axis=0,
        )
        # Pre-reject hot pixels / cosmic rays before the stacking method
        strip = _reject_outlier_pixels(strip)
        result[r0:r1] = method_fn(strip, **valid_kwargs)
        del strip  # free immediately before the next strip

    return result


def stack_images(
    images: list[np.ndarray],
    method: str = "median",
    **kwargs,
) -> np.ndarray:
    """Stack a list of aligned images using the specified method.

    Args:
        images: List of aligned float32 ndarrays, all same shape.
        method: Stacking method name (see METHODS registry).
        **kwargs: Extra arguments forwarded to the stacking function.
                  Only parameters that the chosen method accepts are
                  passed through; the rest are silently ignored.

    Returns:
        Stacked result as float32 ndarray.
    """
    if not images:
        raise ValueError("No images to stack")

    if method not in METHODS:
        raise ValueError(f"Unknown method '{method}'. Available: {list(METHODS.keys())}")

    # Trim any 1-pixel shape discrepancies from astroalign's affine transform
    # rounding before we try to np.stack them into a strip.
    images = _normalise_frame_shapes(images)

    method_fn = METHODS[method]

    # Only forward kwargs that the method's signature actually accepts,
    # so callers can pass a superset without triggering TypeErrors.
    sig = inspect.signature(method_fn)
    valid_kwargs = {
        k: v for k, v in kwargs.items()
        if k in sig.parameters
    }

    # Use chunked row-strip stacking to avoid a full N×H×W×C copy of
    # all frames.  For 36 full-resolution colour frames, np.array(images)
    # would need ~5 GB of extra RAM on top of the frame list already in
    # memory.  Chunked processing caps the extra allocation at ~144 MB
    # per strip regardless of frame count or image resolution.
    return _chunked_stack(images, method_fn, **valid_kwargs)
