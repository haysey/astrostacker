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
# 3.0 px gives a good response for typical astrophotography stars with
# FWHM 4–10 px.  Smaller values (e.g. 2 px) miss bloated or soft stars.
_DETECT_SIGMA = 3.0

# Mask sigma relative to the detection sigma.  3.5× gives mask_sigma ≈ 10.5 px,
# which covers stars up to ~35 px apparent diameter — including bright, bloated
# stars common at fast f-ratios or poor seeing conditions.
_MASK_SIGMA_FACTOR = 3.5

# Large-sigma blur used to estimate the local sky/nebulosity background
# under each star.  Must be much larger than a typical star FWHM (≈ 3–6 px)
# so that the star itself doesn't bias the estimate.
_BG_SIGMA = 25.0

# Maximum number of star peaks to process.  With the Gaussian-blur mask
# approach the painting step is O(image_size) not O(n_stars), so the cap
# only limits the peak_local_max call.  50 000 covers even very dense
# Milky Way and globular-cluster fields comfortably.
_MAX_PEAKS = 50000


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
    # Keep the unclipped version for robust noise estimation (see below).
    hp_unclipped = (lum.astype(np.float64) - blurred).astype(np.float32)
    stars_hp = np.clip(hp_unclipped, 0.0, None)

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

    # Robust noise estimate from the unclipped high-pass image.
    #
    # The high-pass filter produces a zero-mean image (positive signal from
    # stars/texture, negative from their blur halos).  MAD(|hp|) estimates
    # the noise floor robustly; stars are outliers and don't bias it.
    noise_mad = float(np.median(np.abs(hp_unclipped.ravel())))
    sigma_noise = noise_mad * 1.4826 if noise_mad > 1e-10 else float(np.std(hp_unclipped)) + 1e-9
    # 2σ threshold catches faint stars in dense fields without triggering on
    # pure background noise.  The floor at 0.2 % of peak is a safety net.
    threshold = max(sigma_noise * 2.0, img_max * 0.002)

    log.debug(
        "Star reduction: sigma_noise=%.2e  threshold=%.2e  img_max=%.2e",
        sigma_noise, threshold, img_max,
    )

    peaks = peak_local_max(
        stars_hp,
        min_distance=3,          # allow closely-packed stars in dense fields
        threshold_abs=threshold,
        num_peaks=_MAX_PEAKS,
    )

    n_stars = len(peaks)
    log.debug("Star reduction: detected %d stars (strength=%.2f)", n_stars, strength)
    if n_stars == 0:
        return image.astype(np.float32)

    # ── 4. Build soft star mask ───────────────────────────────────────
    # Use a Gaussian blur of the detected peak positions rather than painting
    # individual Gaussians per star.  This is O(image_size) regardless of
    # star count, so dense fields with tens of thousands of stars are handled
    # at the same speed as sparse fields.
    #
    # mask_sigma = 3.0 × 3.5 = 10.5 px → FWHM ≈ 24.7 px
    mask_sigma = _DETECT_SIGMA * _MASK_SIGMA_FACTOR

    # Stamp a 1 at each detected star centre, then blur to Gaussians.
    peaks_map = np.zeros(lum.shape, dtype=np.float32)
    for y, x in peaks:
        peaks_map[y, x] = 1.0

    # scipy gaussian_filter is a normalised kernel (sums to 1).
    # The peak of a single blurred delta = 1 / (2π σ²) in the continuous limit.
    # Dividing by that value scales each isolated star's centre back to 1.0.
    blurred = gaussian_filter(peaks_map.astype(np.float64), sigma=mask_sigma)
    gauss_peak = 1.0 / (2.0 * np.pi * mask_sigma ** 2)
    mask = np.clip(blurred / gauss_peak, 0.0, 1.0).astype(np.float32)

    # ── 5. Apply reduction per channel ────────────────────────────────
    # star_signal = image − local_sky_background (large Gaussian blur)
    # reduced = image − strength × mask × star_signal
    # Clipped to ≥ 0 so no negative pixels are created.
    #
    # Background estimation uses two scales:
    #   • Near  (sigma = _BG_SIGMA,      25 px) — used in non-star regions
    #   • Far   (sigma = _BG_SIGMA × 4, 100 px) — used inside star masks
    #
    # The near estimate is contaminated by a bright star's own halo flux,
    # which makes star_signal appear small at the halo radius and leaves a
    # visible glowing ring after reduction.  The far estimate averages over a
    # much wider area so it is unaffected by the star's own halo — giving a
    # more accurate sky value and allowing the subtraction to reach further
    # into the halo.  Outside star masks the near estimate is used unchanged
    # so the surrounding nebulosity and sky gradient are unaffected.
    _BG_SIGMA_FAR = _BG_SIGMA * 4.0   # 100 px
    if image.ndim == 3:
        result = image.astype(np.float32).copy()
        for c in range(image.shape[2]):
            ch = image[:, :, c].astype(np.float64)
            bg_near = gaussian_filter(ch, sigma=_BG_SIGMA).astype(np.float32)
            bg_far  = gaussian_filter(ch, sigma=_BG_SIGMA_FAR).astype(np.float32)
            # Blend: in star regions (mask → 1) use far estimate; outside use near
            local_bg = bg_near * (1.0 - mask) + bg_far * mask
            star_signal = np.clip(image[:, :, c] - local_bg, 0.0, None)
            result[:, :, c] = np.clip(
                image[:, :, c] - strength * mask * star_signal, 0.0, None
            )
    else:
        img64 = image.astype(np.float64)
        bg_near = gaussian_filter(img64, sigma=_BG_SIGMA).astype(np.float32)
        bg_far  = gaussian_filter(img64, sigma=_BG_SIGMA_FAR).astype(np.float32)
        local_bg = bg_near * (1.0 - mask) + bg_far * mask
        star_signal = np.clip(image - local_bg, 0.0, None)
        result = np.clip(image - strength * mask * star_signal, 0.0, None).astype(np.float32)

    return result
