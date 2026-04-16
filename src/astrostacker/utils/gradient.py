"""Light pollution gradient removal via background modelling.

Fits a smooth 2-D polynomial surface to the image background (after
masking bright objects) and subtracts it, removing large-scale sky
gradients caused by light pollution, moonlight, or vignetting.
"""

from __future__ import annotations

import numpy as np


def _fit_background_surface(data_2d: np.ndarray, grid_size: int = 8) -> np.ndarray:
    """Fit a smooth polynomial surface to the background.

    Divides the image into a grid, takes the median of each cell
    (a robust estimate of sky background), and fits a low-order 2-D
    polynomial surface through those sample points.

    Args:
        data_2d: 2-D float image.
        grid_size: Number of grid divisions along each axis.

    Returns:
        Background model with same shape as input.
    """
    h, w = data_2d.shape
    cell_h = h // grid_size
    cell_w = w // grid_size

    sample_y = []
    sample_x = []
    sample_z = []

    for gy in range(grid_size):
        for gx in range(grid_size):
            y0 = gy * cell_h
            y1 = y0 + cell_h if gy < grid_size - 1 else h
            x0 = gx * cell_w
            x1 = x0 + cell_w if gx < grid_size - 1 else w

            cell = data_2d[y0:y1, x0:x1]
            valid = cell[np.isfinite(cell)]
            if len(valid) == 0:
                continue

            # Use 25th percentile as sky estimate (below most stars).
            # np.partition is O(n) vs np.percentile's O(n log n).
            k25 = max(0, len(valid) // 4)
            sky = float(np.partition(valid, k25)[k25])

            cy = (y0 + y1) / 2.0
            cx = (x0 + x1) / 2.0
            sample_y.append(cy)
            sample_x.append(cx)
            sample_z.append(sky)

    if len(sample_z) < 6:
        # Not enough samples — return flat background
        return np.full_like(data_2d, np.nanmedian(data_2d))

    # Normalise coordinates to [-1, 1] for numerical stability
    sy = np.array(sample_y)
    sx = np.array(sample_x)
    sz = np.array(sample_z)
    yn = (sy - h / 2) / (h / 2)
    xn = (sx - w / 2) / (w / 2)

    # Build design matrix for 2nd-order polynomial:
    # z = a0 + a1*x + a2*y + a3*x^2 + a4*y^2 + a5*x*y
    A = np.column_stack([
        np.ones_like(xn),
        xn, yn,
        xn ** 2, yn ** 2,
        xn * yn,
    ])

    # Least-squares fit
    coeffs, _, _, _ = np.linalg.lstsq(A, sz, rcond=None)

    # Evaluate over full image
    yy, xx = np.mgrid[0:h, 0:w]
    yn_full = (yy.astype(np.float64) - h / 2) / (h / 2)
    xn_full = (xx.astype(np.float64) - w / 2) / (w / 2)

    surface = (
        coeffs[0]
        + coeffs[1] * xn_full
        + coeffs[2] * yn_full
        + coeffs[3] * xn_full ** 2
        + coeffs[4] * yn_full ** 2
        + coeffs[5] * xn_full * yn_full
    )

    return surface.astype(np.float32)


def remove_gradient(data: np.ndarray) -> np.ndarray:
    """Remove light pollution gradient from an image.

    Works with both mono (H, W) and colour (H, W, C) images.
    Subtracts a fitted background model from each channel,
    then re-centres so the result has the same median.

    Args:
        data: Input image as float32 ndarray.

    Returns:
        Gradient-corrected image as float32.
    """
    if data.ndim == 3:
        result = np.empty_like(data)
        for c in range(data.shape[2]):
            result[:, :, c] = _remove_gradient_channel(data[:, :, c])
        return result
    else:
        return _remove_gradient_channel(data)


def _remove_gradient_channel(channel: np.ndarray) -> np.ndarray:
    """Remove gradient from a single 2-D channel."""
    bg = _fit_background_surface(channel)
    corrected = channel - bg

    # Shift so minimum is at 0 (prevent negative values)
    valid = corrected[np.isfinite(corrected)]
    if len(valid) > 0:
        k1 = max(0, len(valid) // 100)  # 1st percentile
        corrected -= float(np.partition(valid, k1)[k1])
        corrected = np.clip(corrected, 0, None)

    return corrected.astype(np.float32)
