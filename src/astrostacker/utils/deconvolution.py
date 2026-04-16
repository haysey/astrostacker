"""Richardson-Lucy deconvolution for sharpening stacked images.

Uses the measured PSF (from star fitting) to reverse the blurring
caused by atmospheric seeing, optical aberrations, and tracking
error.  Applied to the stacked result *before* denoising so the
denoiser can clean up any amplified noise.

Works with both mono (H, W) and colour (H, W, C) images.
Colour channels are processed in parallel for speed.

References:
    Richardson, W.H., 1972, "Bayesian-Based Iterative Method of
    Image Restoration", JOSA 62(1).
    Lucy, L.B., 1974, "An iterative technique for the rectification
    of observed distributions", Astronomical Journal 79(6).
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

import numpy as np
from scipy.signal import fftconvolve


def richardson_lucy(
    image: np.ndarray,
    psf: np.ndarray,
    iterations: int = 15,
) -> np.ndarray:
    """Richardson-Lucy deconvolution of a 2-D image.

    Args:
        image: 2-D image (float).
        psf: 2-D PSF kernel (should sum to 1).
        iterations: Number of RL iterations (10–30 typical).

    Returns:
        Deconvolved image as float32, same shape as input.
    """
    img = np.maximum(image.astype(np.float64), 0.0)
    psf64 = psf.astype(np.float64)
    psf_mirror = psf64[::-1, ::-1]

    estimate = img.copy()

    for _ in range(iterations):
        blurred = fftconvolve(estimate, psf64, mode="same")
        blurred = np.maximum(blurred, 1e-12)
        ratio = img / blurred
        correction = fftconvolve(ratio, psf_mirror, mode="same")
        estimate *= correction
        estimate = np.maximum(estimate, 0.0)

    return estimate.astype(np.float32)


# ── Colour helpers ──

def _deconvolve_channel(args: tuple) -> np.ndarray:
    """Deconvolve a single colour channel (for parallel map)."""
    channel, psf, iterations = args
    return richardson_lucy(channel, psf, iterations)


def deconvolve_image(
    data: np.ndarray,
    psf: np.ndarray,
    iterations: int = 15,
) -> np.ndarray:
    """Deconvolve a mono or colour image.

    Args:
        data: 2-D (H, W) or 3-D (H, W, C) stacked image.
        psf: 2-D PSF kernel (from :func:`psf.build_moffat_kernel`).
        iterations: RL iterations.

    Returns:
        Deconvolved image as float32, same shape as input.
    """
    if data.ndim == 3:
        n_ch = data.shape[2]
        work = [(data[:, :, c], psf, iterations) for c in range(n_ch)]
        with ThreadPoolExecutor(max_workers=n_ch) as pool:
            channels = list(pool.map(_deconvolve_channel, work))
        return np.stack(channels, axis=2).astype(np.float32)

    return richardson_lucy(data, psf, iterations)
