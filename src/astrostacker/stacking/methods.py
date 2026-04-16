"""Stacking algorithms: Mean, Median, Sigma Clip, Min, Max,
Weighted Mean, Percentile Clip, Winsorized Sigma, Noise-Weighted.

Optimised for Apple Silicon and cross-platform:
- All operations stay in float32 (NEON processes 4×float32 vs 2×float64).
- Colour channels are processed in parallel threads where possible.
- Large stacks use chunked processing to reduce peak memory.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from typing import Callable

import numpy as np
from astropy.stats import sigma_clip


# ── Basic methods ──────────────────────────────────────────────────────


def stack_mean(images: np.ndarray) -> np.ndarray:
    """Average stacking. Maximizes SNR with clean data.

    Args:
        images: 3D array of shape (N, H, W) or 4D (N, H, W, C).

    Returns:
        Stacked image as float32.
    """
    return np.nanmean(images, axis=0).astype(np.float32)


def stack_median(images: np.ndarray) -> np.ndarray:
    """Median stacking. Good outlier rejection for any frame count.

    Args:
        images: 3D array of shape (N, H, W) or 4D (N, H, W, C).

    Returns:
        Stacked image as float32.
    """
    return np.nanmedian(images, axis=0).astype(np.float32)


def stack_min(images: np.ndarray) -> np.ndarray:
    """Minimum stacking. Useful for detecting light pollution gradients.

    Args:
        images: 3D array of shape (N, H, W) or 4D (N, H, W, C).

    Returns:
        Stacked image as float32.
    """
    return np.nanmin(images, axis=0).astype(np.float32)


def stack_max(images: np.ndarray) -> np.ndarray:
    """Maximum stacking. Useful for finding transient objects.

    Args:
        images: 3D array of shape (N, H, W) or 4D (N, H, W, C).

    Returns:
        Stacked image as float32.
    """
    return np.nanmax(images, axis=0).astype(np.float32)


# ── Sigma clipping methods ────────────────────────────────────────────


def _sigma_clip_channel(args: tuple) -> np.ndarray:
    """Sigma-clip a single channel slice — used for parallel colour stacking."""
    data_3d, sigma_low, sigma_high, max_iters = args
    clipped = sigma_clip(
        data_3d,
        sigma_lower=sigma_low,
        sigma_upper=sigma_high,
        maxiters=max_iters,
        axis=0,
        masked=True,
        cenfunc="median",
    )
    return np.ma.mean(clipped, axis=0).data.astype(np.float32)


def stack_sigma_clip(
    images: np.ndarray,
    sigma_low: float = 2.5,
    sigma_high: float = 2.5,
    max_iters: int = 5,
) -> np.ndarray:
    """Kappa-Sigma clipping stack.

    Iteratively rejects outlier pixels beyond sigma_low/sigma_high
    standard deviations from the median, then takes the mean of
    remaining pixels. Best with 15+ frames.

    For colour images (N, H, W, C), processes each channel in parallel
    threads — numpy/astropy release the GIL during heavy C-level work,
    so all channels are computed simultaneously across CPU cores.

    Args:
        images: 3D array of shape (N, H, W) or 4D (N, H, W, C).
        sigma_low: Lower rejection threshold in sigma units.
        sigma_high: Upper rejection threshold in sigma units.
        max_iters: Maximum clipping iterations.

    Returns:
        Stacked image as float32.
    """
    # Colour image: clip each channel in parallel
    if images.ndim == 4:
        n_channels = images.shape[3]
        work = [
            (images[:, :, :, c], sigma_low, sigma_high, max_iters)
            for c in range(n_channels)
        ]
        with ThreadPoolExecutor(max_workers=n_channels) as pool:
            channels = list(pool.map(_sigma_clip_channel, work))
        return np.stack(channels, axis=2)

    # Mono image: single pass
    clipped = sigma_clip(
        images,
        sigma_lower=sigma_low,
        sigma_upper=sigma_high,
        maxiters=max_iters,
        axis=0,
        masked=True,
        cenfunc="median",
    )
    return np.ma.mean(clipped, axis=0).data.astype(np.float32)


# ── Winsorized sigma clipping ─────────────────────────────────────────


def _winsorize_mono(
    images_3d: np.ndarray,
    sigma_low: float,
    sigma_high: float,
    max_iters: int,
) -> np.ndarray:
    """Winsorized sigma clip for a single 2-D channel stack.

    Instead of discarding rejected pixels (standard sigma clip),
    clamps them to the rejection boundary.  This preserves more
    signal, especially with fewer frames.
    """
    data = images_3d.astype(np.float32, copy=True)
    for _ in range(max_iters):
        med = np.nanmedian(data, axis=0)
        # Robust std via MAD (Median Absolute Deviation)
        deviations = np.abs(data - med[np.newaxis, :, :])
        mad = np.nanmedian(deviations, axis=0) * 1.4826
        mad = np.maximum(mad, 1e-10)  # prevent division by zero

        lower = med - sigma_low * mad
        upper = med + sigma_high * mad

        # Clamp outliers to boundary values (vectorized)
        data = np.clip(data, lower[np.newaxis, :, :], upper[np.newaxis, :, :])

    return np.nanmean(data, axis=0).astype(np.float32)


def stack_winsorized_sigma(
    images: np.ndarray,
    sigma_low: float = 2.5,
    sigma_high: float = 2.5,
    max_iters: int = 5,
) -> np.ndarray:
    """Winsorized sigma clipping: clamp outliers instead of discarding.

    Like sigma clipping, but replaces rejected pixels with the clipping
    boundary value rather than throwing them away.  Preserves more signal
    than standard sigma clipping, particularly with smaller frame counts
    (< 15 frames).

    Args:
        images: 3D (N, H, W) or 4D (N, H, W, C) array.
        sigma_low: Lower clamp threshold in sigma units.
        sigma_high: Upper clamp threshold in sigma units.
        max_iters: Maximum winsorization iterations.

    Returns:
        Stacked image as float32.
    """
    if images.ndim == 4:
        n_channels = images.shape[3]
        work = [
            (images[:, :, :, c], sigma_low, sigma_high, max_iters)
            for c in range(n_channels)
        ]
        with ThreadPoolExecutor(max_workers=n_channels) as pool:
            channels = list(pool.map(
                lambda a: _winsorize_mono(*a), work
            ))
        return np.stack(channels, axis=2)

    return _winsorize_mono(images, sigma_low, sigma_high, max_iters)


# ── Percentile clipping ───────────────────────────────────────────────


def stack_percentile_clip(
    images: np.ndarray,
    pct_low: float = 10.0,
    pct_high: float = 10.0,
) -> np.ndarray:
    """Percentile clipping: reject extreme pixel values, then average.

    For each pixel position, sorts values across all frames, discards
    the bottom ``pct_low``% and top ``pct_high``%, and averages the rest.
    Dead simple and very effective against satellite trails, planes,
    and hot pixels — works well even with small stacks.

    Args:
        images: 3D (N, H, W) or 4D (N, H, W, C) array.
        pct_low: Percentage of lowest values to reject per pixel (0–49).
        pct_high: Percentage of highest values to reject per pixel (0–49).

    Returns:
        Stacked image as float32.
    """
    n = images.shape[0]
    if n < 3:
        return np.nanmean(images, axis=0).astype(np.float32)

    sorted_imgs = np.sort(images, axis=0)

    low_cut = max(0, int(np.floor(n * pct_low / 100.0)))
    high_cut = max(0, int(np.floor(n * pct_high / 100.0)))

    if low_cut + high_cut >= n:
        # Can't reject more frames than we have — fall back to median
        return np.nanmedian(images, axis=0).astype(np.float32)

    end = n - high_cut if high_cut > 0 else n
    trimmed = sorted_imgs[low_cut:end]
    return np.nanmean(trimmed, axis=0).astype(np.float32)


# ── Weighted average ──────────────────────────────────────────────────


def stack_weighted_mean(
    images: np.ndarray,
    weights: np.ndarray | None = None,
) -> np.ndarray:
    """Quality-weighted average stacking.

    Weights sharper or cleaner frames higher in the stack.  Frames
    with lower HFR (tighter stars) contribute more to the final result.
    Falls back to equal-weight mean if no weights are provided.

    Args:
        images: 3D (N, H, W) or 4D (N, H, W, C) array.
        weights: 1D array of per-frame weights (higher = more influence).

    Returns:
        Stacked image as float32.
    """
    if weights is None or len(weights) == 0:
        return np.nanmean(images, axis=0).astype(np.float32)

    w = np.asarray(weights, dtype=np.float32)
    w = w / w.sum()

    # Expand for broadcasting: (N,) → (N, 1, 1) or (N, 1, 1, 1)
    for _ in range(images.ndim - 1):
        w = w[:, np.newaxis]

    # Handle NaN pixels: zero them out and adjust effective weights
    valid = np.isfinite(images)
    safe = np.where(valid, images, 0.0)
    weighted_sum = (safe * w).sum(axis=0)
    weight_sum = (valid.astype(np.float32) * w).sum(axis=0)

    result = np.where(weight_sum > 0, weighted_sum / weight_sum, 0.0)
    return result.astype(np.float32)


# ── Noise-weighted average ────────────────────────────────────────────


def _estimate_frame_noise(image: np.ndarray) -> float:
    """Estimate frame noise via Median Absolute Deviation.

    MAD is robust against stars and bright nebulae — it measures
    the background noise floor, not signal.
    """
    mono = np.nanmean(image, axis=-1) if image.ndim == 3 else image
    valid = mono[np.isfinite(mono)]
    if len(valid) == 0:
        return 1.0
    mad = float(np.median(np.abs(valid - np.median(valid))))
    # MAD → sigma conversion factor for normal distribution
    return max(mad * 1.4826, 1e-10)


def stack_noise_weighted(images: np.ndarray) -> np.ndarray:
    """Noise-weighted average: weight frames inversely to their noise.

    Automatically estimates per-frame background noise using Median
    Absolute Deviation (robust against stars and nebulae), then
    weights frames so cleaner exposures contribute more.  Frames
    taken through cloud or with higher read noise are automatically
    downweighted.

    Args:
        images: 3D (N, H, W) or 4D (N, H, W, C) array.

    Returns:
        Stacked image as float32.
    """
    n = images.shape[0]
    noise = np.array([_estimate_frame_noise(images[i]) for i in range(n)])
    # Inverse-variance weights: cleaner frames get more weight
    weights = 1.0 / (noise ** 2)
    return stack_weighted_mean(images, weights=weights)


# ── Method registry ───────────────────────────────────────────────────


METHODS: dict[str, Callable] = {
    "mean": stack_mean,
    "median": stack_median,
    "sigma_clip": stack_sigma_clip,
    "winsorized_sigma": stack_winsorized_sigma,
    "percentile_clip": stack_percentile_clip,
    "weighted_mean": stack_weighted_mean,
    "noise_weighted": stack_noise_weighted,
    "min": stack_min,
    "max": stack_max,
}
