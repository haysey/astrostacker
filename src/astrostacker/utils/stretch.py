"""Auto-stretch functions for displaying astronomical images.

Implements a Midtone Transfer Function (MTF) similar to PixInsight's
Screen Transfer Function (STF) for mapping high dynamic range float
data to displayable 8-bit images.

Colour images are stretched using *luminance-linked* parameters: shadow,
highlight, and midtone are computed from the image luminance (weighted
average of R/G/B) and the **same** normalisation is applied to every
channel.  This preserves colour ratios so that manual colour-balance
adjustments (R×, G×, B× multipliers) remain visible in the preview.

The old per-channel independent stretch compensated for any channel
multiplier — boosting Red by 2× simply resulted in a smaller stretch
factor for Red — making colour controls appear to have no effect.
"""

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


def _compute_stretch_params(
    channel: np.ndarray, target_background: float
) -> tuple[float, float, float]:
    """Compute (shadow_clip, highlight, midtone) stretch parameters.

    Args:
        channel: 2D float64 array.
        target_background: Desired display value for the background median.

    Returns:
        (shadow_clip, highlight, midtone) tuple.
    """
    valid = channel[np.isfinite(channel)]
    if valid.size == 0:
        return 0.0, 1.0, target_background

    median_val = float(np.median(valid))
    mad = float(np.median(np.abs(valid - median_val)))

    # Shadow clipping point: ~2.8 sigma below median
    sigma_est = mad * 1.4826
    shadow_clip = float(max(median_val - 2.8 * sigma_est, np.min(valid)))
    highlight = float(np.percentile(valid, 99.9))

    data_range = highlight - shadow_clip
    if data_range <= 0:
        return shadow_clip, highlight, target_background

    norm_median = float(np.clip((median_val - shadow_clip) / data_range, 0.001, 0.999))
    midtone = midtone_balance(norm_median, target_background)
    return shadow_clip, highlight, midtone


def _apply_stretch_params(
    channel: np.ndarray, shadow_clip: float, highlight: float, midtone: float
) -> np.ndarray:
    """Apply precomputed stretch parameters to a 2D channel, returning uint8."""
    data_range = highlight - shadow_clip
    if data_range <= 0:
        return np.zeros_like(channel, dtype=np.uint8)

    normalized = np.clip((channel - shadow_clip) / data_range, 0.0, 1.0)
    stretched = midtone_transfer(normalized, midtone)
    stretched = np.nan_to_num(stretched, nan=0.0)
    return (stretched * 255).astype(np.uint8)


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

    For **colour images** the stretch parameters are derived from the
    luminance channel (0.299 R + 0.587 G + 0.114 B) and the *same*
    shadow/highlight/midtone values are applied to every channel.  This
    ensures that colour-balance multipliers remain visible in the preview
    instead of being silently cancelled by per-channel renormalisation.

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
        # Derive stretch parameters from luminance so that any colour-balance
        # multipliers applied to individual channels remain visible.
        lum = (
            0.299 * result[:, :, 0]
            + 0.587 * result[:, :, 1]
            + 0.114 * result[:, :, 2]
        )
        shadow_clip, highlight, midtone = _compute_stretch_params(lum, target_background)
        channels = [
            _apply_stretch_params(result[:, :, c], shadow_clip, highlight, midtone)
            for c in range(result.shape[2])
        ]
        return np.stack(channels, axis=2)
    else:
        return _stretch_channel(result, target_background)


def _stretch_channel(
    channel: np.ndarray, target_background: float
) -> np.ndarray:
    """Stretch a single 2D channel to uint8."""
    shadow_clip, highlight, midtone = _compute_stretch_params(channel, target_background)
    return _apply_stretch_params(channel, shadow_clip, highlight, midtone)


def midtone_balance(median_norm: float, target: float) -> float:
    """Compute the midtone balance parameter.

    Finds m such that MTF(median_norm, m) = target.

    Derived by solving MTF(x, m) = t for m:
        m = x * (t - 1) / (2*t*x - t - x)
    """
    if median_norm <= 0:
        return 0.5
    if median_norm >= 1:
        return 0.5

    denom = 2.0 * target * median_norm - target - median_norm
    if abs(denom) < 1e-10:
        return 0.5

    m = median_norm * (target - 1.0) / denom
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
