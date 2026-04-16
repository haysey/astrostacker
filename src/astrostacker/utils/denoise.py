"""Non-Local Means denoising for stacked astrophotography images.

NLM works by finding similar patches across the image and averaging
them, weighted by how similar they are.  Unlike simple blurring it
preserves sharp edges (star profiles, nebula structure) while
smoothing noisy background regions.

Uses scikit-image's optimised Cython implementation — no model files,
no GPU, no external downloads.

Reference: Buades, Coll & Morel 2005, "A Non-Local Algorithm for
Image Denoising", CVPR.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

import numpy as np
from skimage.restoration import denoise_nl_means

# Named strength presets mapping to a multiplier on the estimated
# noise sigma.  Higher multiplier = more aggressive smoothing.
STRENGTH_PRESETS = {
    "light": 0.6,
    "medium": 1.0,
    "strong": 1.5,
}


def denoise_image(
    data: np.ndarray,
    strength: str = "medium",
) -> np.ndarray:
    """Denoise a stacked image using Non-Local Means.

    Automatically estimates the background noise level and applies
    NLM filtering scaled by the chosen strength preset.

    Works with both mono (H, W) and colour (H, W, C) images.
    Colour channels are denoised in parallel for speed.

    Args:
        data: Stacked image as float32 ndarray.
        strength: One of "light", "medium", "strong".

    Returns:
        Denoised image as float32, same shape as input.
    """
    multiplier = STRENGTH_PRESETS.get(strength, 1.0)

    if data.ndim == 3:
        return _denoise_colour(data, multiplier)
    else:
        return _denoise_mono(data, multiplier)


def _estimate_noise_mad(img: np.ndarray) -> float:
    """Estimate noise sigma via Median Absolute Deviation.

    MAD is robust against stars and nebulae — it measures the
    background noise floor, not the signal.  The 1.4826 factor
    converts MAD to an equivalent Gaussian standard deviation.
    """
    valid = img[np.isfinite(img)]
    if len(valid) == 0:
        return 0.0
    mad = float(np.median(np.abs(valid - np.median(valid))))
    return mad * 1.4826


def _denoise_mono(data: np.ndarray, multiplier: float) -> np.ndarray:
    """NLM denoise a single 2-D image."""
    img = data.astype(np.float32)

    # Estimate noise standard deviation using MAD (no PyWavelets needed)
    sigma = _estimate_noise_mad(img)
    if sigma < 1e-10:
        return img  # essentially noiseless — nothing to do

    h = sigma * multiplier

    denoised = denoise_nl_means(
        img,
        h=h,
        patch_size=5,       # 5×5 comparison patches
        patch_distance=6,   # search within 6 px radius
        fast_mode=True,     # use the fast algorithm
    )
    return denoised.astype(np.float32)


def _denoise_channel(args: tuple) -> np.ndarray:
    """Denoise a single colour channel (for parallel execution)."""
    channel, multiplier = args
    return _denoise_mono(channel, multiplier)


def _denoise_colour(data: np.ndarray, multiplier: float) -> np.ndarray:
    """NLM denoise a colour image, processing channels in parallel."""
    n_channels = data.shape[2]
    work = [(data[:, :, c], multiplier) for c in range(n_channels)]

    with ThreadPoolExecutor(max_workers=n_channels) as pool:
        channels = list(pool.map(_denoise_channel, work))

    return np.stack(channels, axis=2).astype(np.float32)
