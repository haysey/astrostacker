"""Bayer pattern demosaicing for colour astro cameras.

Converts raw 2D Bayer-pattern data from colour cameras (e.g. ASI, QHY)
into full RGB images using bilinear interpolation.

Supports RGGB, GRBG, GBRG, BGGR patterns.

Optimised for Apple Silicon:
- All operations in float32 (NEON processes 4×float32 simultaneously).
- C-contiguous arrays for optimal memory access patterns.
- Mask counts pre-computed and cached per (height, width, pattern).
"""

from __future__ import annotations

import functools

import numpy as np
from scipy.ndimage import convolve

# Supported Bayer patterns
BAYER_PATTERNS = ["RGGB", "GRBG", "GBRG", "BGGR"]

# 3×3 bilinear interpolation kernel (float32 for NEON)
_KERNEL = np.ones((3, 3), dtype=np.float32)


@functools.lru_cache(maxsize=8)
def _cached_masks_and_counts(height: int, width: int, pattern: str):
    """Build and cache Bayer masks and their convolution counts.

    Cached so repeated calls with the same frame size (i.e. every frame
    in a session) reuse the masks instead of rebuilding them.
    Returns masks and pre-computed count arrays for each channel.
    """
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
        raise ValueError(
            f"Unknown Bayer pattern: {pattern}. Use one of {BAYER_PATTERNS}"
        )

    masks = [r, g, b]
    # Pre-compute the neighbour counts for each channel (expensive convolution)
    counts = []
    for mask in masks:
        count = convolve(mask, _KERNEL, mode="reflect")
        np.maximum(count, 1.0, out=count)  # in-place to avoid allocation
        counts.append(count)

    return masks, counts


def debayer(data: np.ndarray, pattern: str = "RGGB") -> np.ndarray:
    """Debayer a 2D Bayer-pattern image to RGB using bilinear interpolation.

    Uses cached masks and count arrays so only the per-frame convolution
    is computed (the mask setup is done once per image size).

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

    # Ensure float32 C-contiguous for NEON SIMD
    data = np.ascontiguousarray(data, dtype=np.float32)

    masks, counts = _cached_masks_and_counts(h, w, pattern)
    result = np.empty((h, w, 3), dtype=np.float32)

    for ch_idx, (mask, count) in enumerate(zip(masks, counts)):
        # In-place multiply avoids a temporary array allocation
        raw = np.multiply(data, mask)
        interp = convolve(raw, _KERNEL, mode="reflect")
        np.divide(interp, count, out=result[:, :, ch_idx])

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
