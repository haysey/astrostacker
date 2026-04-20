"""Build master calibration frames (dark, flat, dark flat)."""

from __future__ import annotations

import numpy as np

from astrostacker.io.loader import load_image
from astrostacker.utils.parallel import parallel_load_images


def _combine_frames(paths: list[str], method: str = "mean") -> np.ndarray:
    """Load and combine multiple frames into a master frame.

    Uses a streaming mean by default to keep memory usage constant
    regardless of frame count (only 1 frame + accumulator in RAM at a
    time).  Median is available for small datasets but loads all frames
    simultaneously and should be avoided with 50+ large frames.

    Args:
        paths: List of file paths to combine.
        method: 'mean' (default, memory-efficient streaming) or
                'median' (robust but loads all frames into RAM).

    Returns:
        Combined float32 master frame.
    """
    if not paths:
        raise ValueError("No frames provided for combination")

    if method == "mean":
        # Streaming incremental mean — O(frame_size) memory regardless of
        # how many frames are provided.  With 100 frames this is
        # statistically equivalent to median for well-behaved calibration
        # data (same exposure, temperature, gain).
        acc: np.ndarray | None = None
        for path in paths:
            frame = load_image(path).astype(np.float32)
            if acc is None:
                acc = frame.copy()
            else:
                acc += frame
        assert acc is not None
        return (acc / len(paths)).astype(np.float32)

    elif method == "median":
        # Load all frames at once — only suitable for small frame counts
        # where total RAM (n_frames × frame_size) fits comfortably in memory.
        frames = parallel_load_images(paths, load_image)
        stack = np.array(frames, dtype=np.float32)
        del frames
        result = np.median(stack, axis=0).astype(np.float32)
        del stack
        return result

    else:
        raise ValueError(f"Unknown combination method: {method}")


def build_master_dark(
    dark_paths: list[str], method: str = "mean"
) -> np.ndarray:
    """Build a master dark frame by combining individual dark frames.

    Args:
        dark_paths: Paths to dark frame files.
        method: Combination method ('median' recommended to reject cosmic rays).

    Returns:
        Master dark frame as float32 ndarray.
    """
    return _combine_frames(dark_paths, method=method)


def build_master_flat(
    flat_paths: list[str],
    dark_flat_paths: list[str] | None = None,
    method: str = "mean",
) -> np.ndarray:
    """Build a normalized master flat frame.

    Steps:
        1. If dark_flat_paths provided, build a master dark flat.
        2. Median (or mean) combine the flat frames.
        3. Subtract the master dark flat from the combined flat.
        4. Normalize so the result is centered around 1.0.

    Args:
        flat_paths: Paths to flat frame files.
        dark_flat_paths: Optional paths to dark flat frame files.
        method: Combination method for both flats and dark flats.

    Returns:
        Normalized master flat as float32 ndarray (values centered at 1.0).
    """
    master_flat = _combine_frames(flat_paths, method=method)

    if dark_flat_paths:
        master_dark_flat = _combine_frames(dark_flat_paths, method=method)
        master_flat = master_flat - master_dark_flat

    # Normalize to mean of 1.0
    flat_mean = np.mean(master_flat)
    if flat_mean > 0:
        master_flat = master_flat / flat_mean
    else:
        raise ValueError("Master flat has non-positive mean; check flat frames")

    return master_flat.astype(np.float32)
