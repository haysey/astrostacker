"""Star brightness reduction for stacked astrophotography images.

Uses a classical morphological approach — no AI model files required.

Algorithm
---------
1. High-pass filter (image minus Gaussian blur) isolates point sources.
   Stars are sharp; nebulosity and gradients are soft and survive the blur.
2. Peak detection on the high-pass layer finds star centres.
3. A soft Gaussian mask is painted over each detected star, sized to match
   the apparent star radius.
4. For each channel: subtract (strength × mask × star_signal_above_local_bg).
   The local background is estimated by a large-sigma Gaussian blur so that
   only the stellar excess is removed — sky, nebulosity, and dust structure
   underneath are preserved.

Works well for the vast majority of astrophotography targets.  Stars embedded
deep inside bright nebula cores may not be fully reduced (the background
estimator is elevated by the surrounding nebulosity), but the result is always
physically plausible — never creates dark holes or halos.

Reference: Mighell & Rich 1995, "Reduction Techniques for Crowded-Field CCD
Photometry", PASP — background the basis for the local-sky model used here.
"""

from __future__ import annotations

import logging

import numpy as np
from scipy.ndimage import gaussian_filter

log = logging.getLogger(__name__)

# Sigma of the Gaussian used for the high-pass star detection filter.
# Larger = detects only bigger / brighter stars.  Smaller = picks up faint
# stars but risks flagging fine nebula texture peaks.
_DETECT_SIGMA = 2.0

# Mask sigma relative to the detection sigma.  1.8× gives a mask that
# comfortably covers the star's Airy disk + first diffraction ring without
# blending into adjacent stars too aggressively.
_MASK_SIGMA_FACTOR = 1.8

# Large-sigma blur used to estimate the local sky/nebulosity background
# under each star.  Must be much larger than a typical star FWHM (≈ 3–6 px)
# so that the star itself doesn't bias the estimate.
_BG_SIGMA = 25.0

# Maximum number of star peaks to process.  Capped so that very star-dense
# Milky Way fields don't cause excessive compute time.
_MAX_PEAKS = 8000


def reduce_stars(
    image: np.ndarray,
    strength: float = 0.5,
) -> np.ndarray:
    """Reduce star brightness in a stacked image.

    Args:
        image: Stacked image as float32 ndarray, shape (H, W) or (H, W, C).
        strength: Reduction fraction — 0.0 = no change, 1.0 = maximum
                  reduction (stars brought to local background level).

    Returns:
        Star-reduced image as float32, same shape as input.
    """
    if strength <= 0.0:
        return image.astype(np.float32)
    strength = float(np.clip(strength, 0.0, 1.0))

    # ── 1. Luminosity for detection ───────────────────────────────────
    if image.ndim == 3:
        lum = np.nanmean(image, axis=2).astype(np.float32)
    else:
        lum = image.astype(np.float32)

    # ── 2. High-pass filter: isolate point sources ────────────────────
    blurred = gaussian_filter(lum.astype(np.float64), sigma=_DETECT_SIGMA)
    stars_hp = np.clip(lum.astype(np.float64) - blurred, 0.0, None).astype(np.float32)

    img_max = float(np.nanmax(stars_hp))
    if img_max <= 0.0:
        log.debug("Star reduction: high-pass image is empty — skipping")
        return image.astype(np.float32)

    # ── 3. Detect peaks ───────────────────────────────────────────────
    try:
        from skimage.feature import peak_local_max
    except ImportError:
        log.warning("scikit-image not available — star reduction skipped")
        return image.astype(np.float32)

    # Threshold: 70th percentile of positive high-pass pixels.
    # This picks up medium-bright and bright stars while ignoring the
    # diffuse positive noise floor of the high-pass image.
    pos_pixels = stars_hp[stars_hp > 0]
    if len(pos_pixels) == 0:
        return image.astype(np.float32)
    threshold = float(np.percentile(pos_pixels, 70))

    peaks = peak_local_max(
        stars_hp,
        min_distance=5,          # minimum separation between detected stars
        threshold_abs=threshold,
        num_peaks=_MAX_PEAKS,
    )

    n_stars = len(peaks)
    log.debug("Star reduction: detected %d stars (strength=%.2f)", n_stars, strength)
    if n_stars == 0:
        return image.astype(np.float32)

    # ── 4. Build soft star mask ───────────────────────────────────────
    mask_sigma = _DETECT_SIGMA * _MASK_SIGMA_FACTOR
    r = int(np.ceil(mask_sigma * 4))   # Gaussian truncation radius
    mask = np.zeros(lum.shape, dtype=np.float32)

    for y, x in peaks:
        y0 = max(0, y - r)
        y1 = min(lum.shape[0], y + r + 1)
        x0 = max(0, x - r)
        x1 = min(lum.shape[1], x + r + 1)
        Y, X = np.ogrid[y0:y1, x0:x1]
        g = np.exp(-((X - x) ** 2 + (Y - y) ** 2) / (2.0 * mask_sigma ** 2))
        mask[y0:y1, x0:x1] = np.maximum(mask[y0:y1, x0:x1], g.astype(np.float32))

    # ── 5. Apply reduction per channel ────────────────────────────────
    # star_signal = image − local_sky_background (large Gaussian blur)
    # reduced = image − strength × mask × star_signal
    # Clipped to ≥ 0 so no negative pixels are created.
    if image.ndim == 3:
        result = image.astype(np.float32).copy()
        for c in range(image.shape[2]):
            ch = image[:, :, c].astype(np.float64)
            local_bg = gaussian_filter(ch, sigma=_BG_SIGMA).astype(np.float32)
            star_signal = np.clip(image[:, :, c] - local_bg, 0.0, None)
            result[:, :, c] = np.clip(
                image[:, :, c] - strength * mask * star_signal, 0.0, None
            )
    else:
        local_bg = gaussian_filter(image.astype(np.float64), sigma=_BG_SIGMA).astype(np.float32)
        star_signal = np.clip(image - local_bg, 0.0, None)
        result = np.clip(image - strength * mask * star_signal, 0.0, None).astype(np.float32)

    return result
