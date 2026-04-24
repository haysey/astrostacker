"""PSF-informed sharpening for stacked astrophotography images.

Uses unsharp masking with the blur radius set from the measured
star PSF (FWHM).  This is safe and predictable — it never creates
the dark-halo ringing artifacts that Richardson-Lucy deconvolution
causes on high dynamic range astro images.

Works with both mono (H, W) and colour (H, W, C) images.
Colour channels are processed in parallel for speed.

The PSF fitting module measures the star FWHM, which is converted
to a Gaussian sigma for the blur kernel.  The sharpening amount
(Light/Medium/Strong) controls how much of the detail layer is
added back to the image.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

import numpy as np
from scipy.ndimage import gaussian_filter

# FWHM → sigma conversion factor
_FWHM_TO_SIGMA = 1.0 / (2.0 * np.sqrt(2.0 * np.log(2.0)))  # ≈ 0.4247

# Strength presets — amount of the detail layer added back.
# Values are intentionally conservative: high-contrast astro images
# (nebulae with dark dust lanes, galaxies) show false ringing in the
# auto-stretched view when USM is too aggressive, because brightening
# the nebula peaks increases local contrast and makes adjacent dark
# lanes appear darker after stretching.
SHARPEN_PRESETS = {
    "light":  0.12,
    "medium": 0.22,
    "strong": 0.38,
}


def sharpen_image(
    data: np.ndarray,
    fwhm: float,
    strength: str = "medium",
) -> np.ndarray:
    """Sharpen an image using PSF-informed unsharp masking.

    The blur radius is derived from the measured star FWHM, so the
    sharpening targets the correct spatial scale.  The strength
    preset controls how aggressive the sharpening is.

    Args:
        data: 2-D (H, W) or 3-D (H, W, C) stacked image.
        fwhm: Measured star FWHM in pixels (from PSF fitting).
        strength: ``"light"``, ``"medium"``, or ``"strong"``.

    Returns:
        Sharpened image as float32, same shape as input.
    """
    amount = SHARPEN_PRESETS.get(strength, 0.5)

    if data.ndim == 3:
        return _sharpen_colour(data, fwhm, amount)
    return _sharpen_mono(data, fwhm, amount)


def _sharpen_mono(
    image: np.ndarray,
    fwhm: float,
    amount: float,
) -> np.ndarray:
    """Unsharp-mask a single 2-D image."""
    img = image.astype(np.float64)

    # Convert FWHM to Gaussian sigma for the blur kernel
    sigma = fwhm * _FWHM_TO_SIGMA
    sigma = max(sigma, 0.5)  # floor to avoid no-op

    blurred = gaussian_filter(img, sigma=sigma)

    # Detail layer = original minus blurred.
    # Only keep POSITIVE detail — this brightens fine structure
    # (star cores, nebula filaments) without ever darkening anything.
    # Standard unsharp mask uses both positive and negative detail,
    # which dims star wings and creates visible dark rings when
    # the image is auto-stretched.
    detail = img - blurred
    detail = np.maximum(detail, 0.0)       # positive-only

    # Brightness protection: pixels already near the image peak get
    # progressively less sharpening.  Without this, bright nebula cores
    # and star halos are pushed even higher, which after auto-stretching
    # makes neighbouring dark regions look artificially darker (the
    # false-ringing effect).  Cap the addition at 15 % of the local
    # pixel value so faint detail is sharpened freely but bright peaks
    # are left largely alone.
    cap = img * 0.15
    detail = np.minimum(detail, cap)

    sharpened = img + amount * detail

    return sharpened.astype(np.float32)


def _sharpen_channel(args: tuple) -> np.ndarray:
    channel, fwhm, amount = args
    return _sharpen_mono(channel, fwhm, amount)


def _sharpen_colour(
    data: np.ndarray,
    fwhm: float,
    amount: float,
) -> np.ndarray:
    """Sharpen colour image with channels processed in parallel."""
    n_ch = data.shape[2]
    work = [(data[:, :, c], fwhm, amount) for c in range(n_ch)]
    with ThreadPoolExecutor(max_workers=n_ch) as pool:
        channels = list(pool.map(_sharpen_channel, work))
    return np.stack(channels, axis=2).astype(np.float32)
