"""Colour balance correction for stacked astrophotography images.

Two modes
---------
Auto balance
    Samples the sky background from the four image corners using a
    sigma-clipped median, computes per-channel multiplicative scale
    factors that make the sky neutral grey, and applies them.  The
    correction is purely multiplicative so that the relative brightness
    of stars and nebulae is preserved — only the white-point of the sky
    background shifts.

    This automatically compensates for:
    - Light pollution colour tint (sodium = orange, LED = blue-white)
    - Natural airglow (typically green)
    - The two-green-channel bias of Bayer sensors (G channel sampled
      at 2× density; if flats are imperfect, G can appear slightly
      dominant)

Manual balance
    User-specified per-channel gain multipliers (1.0 = no change).
    Useful for targets near H-alpha emission fields where the red
    channel genuinely should be brighter, or for artistic tuning.

Both functions are no-ops on mono (H, W) images.
"""

from __future__ import annotations

import logging

import numpy as np

log = logging.getLogger(__name__)


def auto_colour_balance(
    image: np.ndarray,
    corner_frac: float = 0.10,
) -> tuple[np.ndarray, tuple[float, float, float]]:
    """Automatically balance colours by neutralising the sky background.

    Samples the four image corners (typically free of bright nebulosity)
    using a sigma-clipped median, then scales each channel so that its
    sky level equals the mean sky luminance across all three channels.

    Args:
        image: Stacked colour image (H, W, 3) as float32.
        corner_frac: Fraction of image height/width to sample from each
                     corner (0.10 = outermost 10 % on each axis).

    Returns:
        Tuple of (corrected_image, (r_factor, g_factor, b_factor)).
        Factors > 1.0 boost that channel; < 1.0 reduce it.
        Returns the input unchanged with factors (1, 1, 1) for mono images.
    """
    if image.ndim != 3 or image.shape[2] != 3:
        return image.astype(np.float32), (1.0, 1.0, 1.0)

    h, w = image.shape[:2]
    ch = max(1, int(h * corner_frac))
    cw = max(1, int(w * corner_frac))

    # Concatenate all four corners into a flat (N, 3) array
    corners = np.concatenate([
        image[:ch,     :cw,     :].reshape(-1, 3),
        image[:ch,     w - cw:, :].reshape(-1, 3),
        image[h - ch:, :cw,     :].reshape(-1, 3),
        image[h - ch:, w - cw:, :].reshape(-1, 3),
    ], axis=0).astype(np.float64)

    # ── Corner sigma-clipped sky estimate ────────────────────────────────
    ch_sky: list[float] = []
    for c in range(3):
        vals = corners[:, c]
        vals = vals[np.isfinite(vals) & (vals >= 0.0)]
        if len(vals) < 10:
            ch_sky.append(0.0)
            continue
        for _ in range(3):
            med = float(np.median(vals))
            mad = float(np.median(np.abs(vals - med))) * 1.4826
            keep = vals <= med + 2.5 * mad
            if keep.sum() < 5:
                break
            vals = vals[keep]
        ch_sky.append(float(np.median(vals)))

    # ── Full-frame fallback for targets that fill the FOV ─────────────────
    # Emission nebulae (e.g. H-alpha rich fields) can fill the entire frame,
    # leaving no clean sky in the corners.  The corner estimate then samples
    # bright nebulosity and over-estimates the sky level, producing wildly
    # wrong colour factors.
    #
    # Detection: if the corner sky estimate for ANY channel is more than 2×
    # the full-image 5th-percentile sky, the corners are contaminated.
    # Fallback: use the 5th percentile of the whole image per channel.  Even
    # in a heavily nebula-filled frame the darkest 5 % of pixels are sky.
    full_sky: list[float] = []
    for c in range(3):
        all_v = image[:, :, c].ravel().astype(np.float64)
        all_v = all_v[np.isfinite(all_v) & (all_v > 0)]
        full_sky.append(float(np.percentile(all_v, 5)) if len(all_v) >= 100 else ch_sky[c])

    if any(
        ch_sky[c] > 2.0 * full_sky[c]
        for c in range(3)
        if full_sky[c] > 0 and ch_sky[c] > 0
    ):
        log.debug(
            "Auto colour balance: corners contaminated by nebulosity — "
            "switching to full-image 5th-percentile sky estimate"
        )
        ch_sky = full_sky

    sky_lum = float(np.mean(ch_sky))
    if sky_lum < 1e-8:
        log.debug("Auto colour balance: sky level too low — skipping")
        return image.astype(np.float32), (1.0, 1.0, 1.0)

    # Scale factors: make each channel's sky equal the mean sky luminance
    factors: tuple[float, float, float] = tuple(
        sky_lum / max(s, 1e-8) for s in ch_sky
    )  # type: ignore[assignment]

    log.debug(
        "Auto colour balance: sky R=%.4f G=%.4f B=%.4f → factors R×%.3f G×%.3f B×%.3f",
        *ch_sky, *factors,
    )

    result = image.astype(np.float32).copy()
    for c, f in enumerate(factors):
        result[:, :, c] = np.clip(image[:, :, c] * float(f), 0.0, None)

    return result, factors


def apply_rgb_balance(
    image: np.ndarray,
    r: float = 1.0,
    g: float = 1.0,
    b: float = 1.0,
) -> np.ndarray:
    """Apply manual per-channel gain multipliers.

    Args:
        image: Stacked colour image (H, W, 3) as float32.
        r, g, b: Gain multipliers (1.0 = no change, 0.5 = halve, 2.0 = double).

    Returns:
        Colour-adjusted image as float32.  Mono images are returned unchanged.
    """
    if image.ndim != 3 or image.shape[2] != 3:
        return image.astype(np.float32)

    result = image.astype(np.float32).copy()
    for c, f in enumerate([r, g, b]):
        result[:, :, c] = np.clip(image[:, :, c] * float(f), 0.0, None)

    log.debug("Manual colour balance: R×%.2f G×%.2f B×%.2f", r, g, b)
    return result
