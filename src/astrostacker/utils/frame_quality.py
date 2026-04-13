"""Frame quality scoring based on star sharpness (FWHM/HFR).

Detects stars using peak_local_max and estimates the Half-Flux Radius
(HFR) for each star.  The median HFR across detected stars is the
frame's quality score — lower is sharper.
"""

from __future__ import annotations

import numpy as np
from skimage.feature import peak_local_max
from skimage.filters import gaussian


def _to_mono(data: np.ndarray) -> np.ndarray:
    """Convert to 2-D mono by averaging colour channels."""
    if data.ndim == 3:
        return np.mean(data, axis=2)
    return data


def estimate_hfr(data: np.ndarray, max_stars: int = 80) -> float:
    """Estimate the median Half-Flux Radius of stars in an image.

    Args:
        data: 2-D float image (mono) or 3-D (H, W, C).
        max_stars: Maximum number of brightest stars to measure.

    Returns:
        Median HFR in pixels.  Lower = sharper.
        Returns float('inf') if no stars detected.
    """
    img = _to_mono(data).astype(np.float64)
    img = np.nan_to_num(img, nan=0.0)
    lo, hi = img.min(), img.max()
    if hi <= lo:
        return float("inf")
    img = (img - lo) / (hi - lo)

    smoothed = gaussian(img, sigma=1.5)
    median = np.median(smoothed)
    std = np.std(smoothed)
    threshold = median + 3.0 * std

    coords = peak_local_max(
        smoothed,
        min_distance=5,
        threshold_abs=max(threshold, 0.02),
        num_peaks=max_stars,
    )

    if len(coords) == 0:
        return float("inf")

    # Measure HFR for each detected star
    h, w = img.shape
    radius = 10  # measurement aperture radius in pixels
    hfr_values = []

    for row, col in coords:
        r0 = max(0, row - radius)
        r1 = min(h, row + radius + 1)
        c0 = max(0, col - radius)
        c1 = min(w, col + radius + 1)
        stamp = img[r0:r1, c0:c1]

        bg = np.percentile(stamp, 20)
        stamp = stamp - bg
        stamp = np.clip(stamp, 0, None)

        total_flux = stamp.sum()
        if total_flux <= 0:
            continue

        # Compute flux-weighted distance from centroid
        yy, xx = np.mgrid[0:stamp.shape[0], 0:stamp.shape[1]]
        cx = np.sum(xx * stamp) / total_flux
        cy = np.sum(yy * stamp) / total_flux
        dist = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2)
        hfr = np.sum(dist * stamp) / total_flux
        if 0.5 < hfr < radius:
            hfr_values.append(hfr)

    if not hfr_values:
        return float("inf")

    return float(np.median(hfr_values))


def score_frames(
    frames: list[np.ndarray],
    rejection_sigma: float = 2.0,
) -> list[tuple[int, float, bool]]:
    """Score and flag frames for rejection based on star sharpness.

    Frames with HFR more than ``rejection_sigma`` standard deviations
    above the median are flagged for rejection (blurry / trailed).

    Args:
        frames: List of image arrays.
        rejection_sigma: Sigma threshold for rejection.

    Returns:
        List of (index, hfr, keep) tuples sorted by index.
    """
    scores = [(i, estimate_hfr(f)) for i, f in enumerate(frames)]

    finite = [s for _, s in scores if np.isfinite(s)]
    if len(finite) < 3:
        # Not enough data to reject — keep all
        return [(i, hfr, True) for i, hfr in scores]

    med = float(np.median(finite))
    std = float(np.std(finite))

    if std < 1e-6:
        return [(i, hfr, True) for i, hfr in scores]

    threshold = med + rejection_sigma * std

    return [
        (i, hfr, hfr <= threshold and np.isfinite(hfr))
        for i, hfr in scores
    ]
