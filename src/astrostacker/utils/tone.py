"""Brightness, contrast and saturation adjustment for post-processed stacks.

All adjustments operate in linear float32 space (the native pixel range of a
calibrated / stacked image).  No gamma correction is assumed or applied.

Brightness
----------
Multiplicative scaling by 2^(amount/100).  +100 doubles the image; −100
halves it; 0 is unchanged.  A power-of-two ramp mirrors photographic EV
stops so each step feels perceptually equal.

Contrast
--------
Applied relative to the image's own sky floor (1st percentile of finite,
positive pixels) so the background stays anchored while bright nebulae and
stars are expanded (positive contrast) or compressed (negative contrast).
Scale factor is also 2^(amount/100).

Saturation
----------
Chroma is scaled relative to each pixel's luminance (0.299R + 0.587G +
0.114B).  +100 doubles the colour deviation from grey; −100 converts the
image to greyscale; 0 leaves colours unchanged.  Only applied to colour
(H×W×3) images — mono arrays are returned unchanged.
"""

from __future__ import annotations

import numpy as np


def adjust_tone(
    data: np.ndarray,
    brightness: float = 0.0,
    contrast: float = 0.0,
    saturation: float = 0.0,
) -> np.ndarray:
    """Apply brightness, contrast and saturation adjustments.

    Args:
        data:       Float32 image array, shape (H, W) or (H, W, C).
        brightness: −100 … +100.  0 = no change.
        contrast:   −100 … +100.  0 = no change.
        saturation: −100 … +100.  0 = no change.  Ignored for mono images.

    Returns:
        Adjusted float32 array, same shape as input, clipped to ≥ 0.
    """
    result = data.astype(np.float32, copy=True)

    # ── Brightness ────────────────────────────────────────────────────────────
    if brightness != 0.0:
        factor = float(2.0 ** (brightness / 100.0))
        result = result * factor

    # ── Contrast ─────────────────────────────────────────────────────────────
    if contrast != 0.0:
        factor = float(2.0 ** (contrast / 100.0))
        # Pivot at the sky floor so the background stays anchored
        valid = result[np.isfinite(result) & (result > 0)]
        pivot = float(np.percentile(valid, 1)) if len(valid) >= 10 else 0.0
        result = pivot + (result - pivot) * factor

    # ── Saturation ────────────────────────────────────────────────────────────
    if saturation != 0.0 and result.ndim == 3:
        factor = 1.0 + saturation / 100.0
        lum = (
            0.299 * result[:, :, 0].astype(np.float64)
            + 0.587 * result[:, :, 1].astype(np.float64)
            + 0.114 * result[:, :, 2].astype(np.float64)
        )[:, :, np.newaxis]                       # (H, W, 1) broadcast-ready
        result = (lum + factor * (result.astype(np.float64) - lum)).astype(np.float32)

    return np.clip(result, 0.0, None).astype(np.float32)
