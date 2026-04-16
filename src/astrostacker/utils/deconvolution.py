"""Damped Richardson-Lucy deconvolution for sharpening stacked images.

Uses the measured PSF (from star fitting) to reverse the blurring
caused by atmospheric seeing, optical aberrations, and tracking
error.  Applied to the stacked result *before* denoising so the
denoiser can clean up any amplified noise.

Key improvements over naive RL:
  - **Damping** — each correction step is raised to a power < 1,
    preventing the dark-halo "ringing" around bright stars that
    standard RL is notorious for.
  - **Normalisation** — the image is scaled to [0, 1] before
    deconvolution for numerical stability, then scaled back.

Works with both mono (H, W) and colour (H, W, C) images.
Colour channels are processed in parallel for speed.

References:
    Richardson, W.H., 1972, "Bayesian-Based Iterative Method of
    Image Restoration", JOSA 62(1).
    Lucy, L.B., 1974, "An iterative technique for the rectification
    of observed distributions", Astronomical Journal 79(6).
    White, R.L., 1994, "Image restoration using the damped
    Richardson-Lucy method", Proc. SPIE 2198.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

import numpy as np
from scipy.signal import fftconvolve


def richardson_lucy(
    image: np.ndarray,
    psf: np.ndarray,
    iterations: int = 10,
    damping: float = 0.75,
) -> np.ndarray:
    """Damped Richardson-Lucy deconvolution of a 2-D image.

    The damping parameter (0 < d ≤ 1) controls how aggressively
    each iteration corrects.  Lower values are gentler and prevent
    the dark-halo ringing artifacts around bright stars.

    Args:
        image: 2-D image (float).
        psf: 2-D PSF kernel (should sum to 1).
        iterations: Number of RL iterations.
        damping: Correction damping (0.5–1.0).  Lower = gentler.

    Returns:
        Deconvolved image as float32, same shape as input.
    """
    # Normalise to [0, 1] for numerical stability
    img = np.maximum(image.astype(np.float64), 0.0)
    peak = img.max()
    if peak <= 0:
        return image.astype(np.float32)
    img /= peak

    psf64 = psf.astype(np.float64)
    psf_mirror = psf64[::-1, ::-1]

    estimate = img.copy()

    for _ in range(iterations):
        blurred = fftconvolve(estimate, psf64, mode="same")
        blurred = np.maximum(blurred, 1e-12)
        ratio = img / blurred
        correction = fftconvolve(ratio, psf_mirror, mode="same")
        # Damped update: correction^damping instead of correction
        # This prevents ringing/dark halos around bright stars
        correction = np.maximum(correction, 1e-12)
        estimate *= correction ** damping
        estimate = np.maximum(estimate, 0.0)

    # Scale back to original range
    estimate *= peak
    return estimate.astype(np.float32)


# ── Colour helpers ──

def _deconvolve_channel(args: tuple) -> np.ndarray:
    """Deconvolve a single colour channel (for parallel map)."""
    channel, psf, iterations, damping = args
    return richardson_lucy(channel, psf, iterations, damping)


def deconvolve_image(
    data: np.ndarray,
    psf: np.ndarray,
    iterations: int = 10,
    damping: float = 0.75,
) -> np.ndarray:
    """Deconvolve a mono or colour image.

    Args:
        data: 2-D (H, W) or 3-D (H, W, C) stacked image.
        psf: 2-D PSF kernel (from :func:`psf.build_moffat_kernel`).
        iterations: RL iterations.
        damping: Correction damping (0.5–1.0).

    Returns:
        Deconvolved image as float32, same shape as input.
    """
    if data.ndim == 3:
        n_ch = data.shape[2]
        work = [(data[:, :, c], psf, iterations, damping) for c in range(n_ch)]
        with ThreadPoolExecutor(max_workers=n_ch) as pool:
            channels = list(pool.map(_deconvolve_channel, work))
        return np.stack(channels, axis=2).astype(np.float32)

    return richardson_lucy(data, psf, iterations, damping)
