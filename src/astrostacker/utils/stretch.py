"""Auto-stretch functions for displaying astronomical images.

Implements a Midtone Transfer Function (MTF) similar to PixInsight's
Screen Transfer Function (STF) for mapping high dynamic range float
data to displayable 8-bit images.

Uses thread-parallel channel processing for color images.
"""

from concurrent.futures import ThreadPoolExecutor

import numpy as np


def midtone_transfer(x: np.ndarray, midtone: float) -> np.ndarray:
    """Apply the midtone transfer function.

    MTF(x, m) = (m - 1) * x / ((2m - 1) * x - m)

    This maps 0->0, 1->1, and places the midtone at 0.5.
    """
    # Avoid division by zero
    denom = (2.0 * midtone - 1.0) * x - midtone
    denom = np.where(np.abs(denom) < 1e-10, -1e-10, denom)
    result = (midtone - 1.0) * x / denom
    return np.clip(result, 0.0, 1.0)


def auto_stretch(
    data: np.ndarray,
    target_background: float = 0.25,
) -> np.ndarray:
    """Auto-stretch astronomical image data to uint8 for display.

    Uses a Midtone Transfer Function approach:
    1. Compute median and MAD (median absolute deviation) of the data.
    2. Clip shadows at ~2.8 sigma below median.
    3. Normalize to [0, 1].
    4. Apply MTF to map the background to target_background.
    5. Scale to [0, 255] uint8.

    Args:
        data: float32 image data, shape (H, W) or (H, W, C).
        target_background: Where the median background should map to (0-1).

    Returns:
        uint8 ndarray suitable for display.
    """
    if data.size == 0:
        return data.astype(np.uint8)

    result = data.astype(np.float64)

    if result.ndim == 3:
        # Process channels in parallel (numpy releases GIL during computation)
        def _stretch_c(c: int) -> np.ndarray:
            return _stretch_channel(result[:, :, c], target_background)

        with ThreadPoolExecutor(max_workers=result.shape[2]) as pool:
            channels = list(pool.map(_stretch_c, range(result.shape[2])))
        return np.stack(channels, axis=2)
    else:
        return _stretch_channel(result, target_background)


def _stretch_channel(
    channel: np.ndarray, target_background: float
) -> np.ndarray:
    """Stretch a single 2D channel to uint8."""
    valid = channel[np.isfinite(channel)]
    if valid.size == 0:
        return np.zeros_like(channel, dtype=np.uint8)

    median_val = np.median(valid)
    mad = np.median(np.abs(valid - median_val))

    # Shadow clipping point: ~2.8 sigma below median
    # MAD to sigma conversion: sigma ~= MAD * 1.4826
    sigma_est = mad * 1.4826
    shadow_clip = median_val - 2.8 * sigma_est
    shadow_clip = max(shadow_clip, float(np.min(valid)))

    highlight = float(np.max(valid))

    # Normalize to [0, 1]
    data_range = highlight - shadow_clip
    if data_range <= 0:
        return np.zeros_like(channel, dtype=np.uint8)

    normalized = (channel - shadow_clip) / data_range
    normalized = np.clip(normalized, 0.0, 1.0)

    # Compute midtone balance parameter from the normalized median
    norm_median = (median_val - shadow_clip) / data_range
    norm_median = np.clip(norm_median, 0.001, 0.999)

    # Solve for midtone parameter that maps norm_median -> target_background
    # MTF(norm_median, m) = target_background
    # Solving: m = (target * (2*norm_median - 1) - norm_median) / ((2*target - 1) * norm_median - target)  -- actually it's a known formula
    # Simplified: use target_background as the midtone directly
    # for the region below the median
    midtone = midtone_balance(norm_median, target_background)

    stretched = midtone_transfer(normalized, midtone)

    # Handle NaN pixels (from alignment footprint)
    stretched = np.nan_to_num(stretched, nan=0.0)

    return (stretched * 255).astype(np.uint8)


def midtone_balance(median_norm: float, target: float) -> float:
    """Compute the midtone balance parameter.

    Finds m such that MTF(median_norm, m) ~ target.
    """
    if median_norm <= 0:
        return 0.5
    if median_norm >= 1:
        return 0.5

    # Analytical solution
    m = (
        (median_norm - 1.0) * target
    ) / (
        (2.0 * target - 1.0) * median_norm - target
    )
    return float(np.clip(m, 0.001, 0.999))


def linear_stretch(data: np.ndarray) -> np.ndarray:
    """Simple linear stretch to uint8. Maps min->0, max->255."""
    valid = data[np.isfinite(data)]
    if valid.size == 0:
        return np.zeros_like(data, dtype=np.uint8)

    lo = float(np.percentile(valid, 0.5))
    hi = float(np.percentile(valid, 99.5))

    if hi <= lo:
        return np.zeros_like(data, dtype=np.uint8)

    normalized = (data - lo) / (hi - lo)
    normalized = np.clip(normalized, 0.0, 1.0)
    normalized = np.nan_to_num(normalized, nan=0.0)
    return (normalized * 255).astype(np.uint8)
