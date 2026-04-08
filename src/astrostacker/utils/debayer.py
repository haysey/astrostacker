"""Bayer pattern demosaicing for colour astro cameras.

Converts raw 2D Bayer-pattern data from colour cameras (e.g. ASI, QHY)
into full RGB images using bilinear interpolation.

Supports RGGB, GRBG, GBRG, BGGR patterns.
"""

from __future__ import annotations

import numpy as np
from scipy.ndimage import convolve

# Supported Bayer patterns
BAYER_PATTERNS = ["RGGB", "GRBG", "GBRG", "BGGR"]


def _build_masks(height: int, width: int, pattern: str):
    """Build boolean masks for R, G, B pixel positions in a Bayer pattern."""
    r = np.zeros((height, width), dtype=np.float32)
    g = np.zeros((height, width), dtype=np.float32)
    b = np.zeros((height, width), dtype=np.float32)

    if pattern == "RGGB":
        r[0::2, 0::2] = 1.0
        g[0::2, 1::2] = 1.0
        g[1::2, 0::2] = 1.0
        b[1::2, 1::2] = 1.0
    elif pattern == "GRBG":
        g[0::2, 0::2] = 1.0
        r[0::2, 1::2] = 1.0
        b[1::2, 0::2] = 1.0
        g[1::2, 1::2] = 1.0
    elif pattern == "GBRG":
        g[0::2, 0::2] = 1.0
        b[0::2, 1::2] = 1.0
        r[1::2, 0::2] = 1.0
        g[1::2, 1::2] = 1.0
    elif pattern == "BGGR":
        b[0::2, 0::2] = 1.0
        g[0::2, 1::2] = 1.0
        g[1::2, 0::2] = 1.0
        r[1::2, 1::2] = 1.0
    else:
        raise ValueError(f"Unknown Bayer pattern: {pattern}. Use one of {BAYER_PATTERNS}")

    return r, g, b


def debayer(data: np.ndarray, pattern: str = "RGGB") -> np.ndarray:
    """Debayer a 2D Bayer-pattern image to RGB using bilinear interpolation.

    Args:
        data: 2D float32 array (H, W) containing raw Bayer data.
        pattern: Bayer pattern - one of 'RGGB', 'GRBG', 'GBRG', 'BGGR'.

    Returns:
        3D float32 array (H, W, 3) with interpolated RGB channels.
    """
    if data.ndim != 2:
        raise ValueError(f"Expected 2D array, got shape {data.shape}")

    pattern = pattern.upper().strip()
    h, w = data.shape
    r_mask, g_mask, b_mask = _build_masks(h, w, pattern)

    kernel = np.ones((3, 3), dtype=np.float32)
    result = np.zeros((h, w, 3), dtype=np.float32)

    for ch_idx, mask in enumerate([r_mask, g_mask, b_mask]):
        raw = data * mask
        interp = convolve(raw, kernel, mode="reflect")
        count = convolve(mask, kernel, mode="reflect")
        count = np.maximum(count, 1.0)
        result[:, :, ch_idx] = interp / count

    return result


def detect_bayer_from_fits(header) -> str | None:
    """Try to detect Bayer pattern from FITS header keywords.

    Many astro cameras embed the pattern as BAYERPAT, COLORTYP, etc.

    Returns:
        Pattern string if found (e.g. 'RGGB'), or None.
    """
    for key in ("BAYERPAT", "COLORTYP", "BAYER", "CFA-PATT"):
        val = header.get(key)
        if val and isinstance(val, str):
            val = val.upper().strip()
            if val in BAYER_PATTERNS:
                return val
    return None
