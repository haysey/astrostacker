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
