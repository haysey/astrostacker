"""Frame quality scoring via PSF (Point Spread Function) fitting.

Detects stars and fits 2-D elliptical Gaussian profiles to measure
accurate FWHM and eccentricity.  Frames are scored and optionally
rejected based on both sharpness (FWHM) and elongation (eccentricity),
catching blurry *and* trailed frames.

Replaces the earlier simple HFR (Half-Flux Radius) approach with
proper model-based PSF fitting for more reliable quality metrics.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from astrostacker.utils.psf import measure_frame_psf


@dataclass
class FrameScore:
    """Quality score for a single frame."""

    index: int
    fwhm: float            # median FWHM in pixels (lower = sharper)
    eccentricity: float    # median eccentricity (0 = round, 1 = line)
    roundness: float       # minor/major axis ratio (1 = round)
    n_stars: int           # number of stars successfully fitted
    keep: bool             # whether this frame passes quality checks


def score_frames(
    frames: list[np.ndarray],
    rejection_sigma: float = 2.0,
) -> list[FrameScore]:
    """Score frames by PSF quality and flag outliers for rejection.

    Each frame's stars are fitted with elliptical 2-D Gaussians.
    Frames whose median FWHM *or* eccentricity exceeds
    ``rejection_sigma`` standard deviations above the population
    median are flagged for rejection.

    Args:
        frames: List of image arrays (2-D or 3-D).
        rejection_sigma: Number of sigma for outlier rejection.

    Returns:
        One :class:`FrameScore` per frame, in index order.
    """
    metrics = [measure_frame_psf(f) for f in frames]

    fwhms = np.array([m.fwhm for m in metrics])
    eccs = np.array([m.eccentricity for m in metrics])
    finite = np.isfinite(fwhms)

    if np.sum(finite) < 3:
        # Too few measured frames to compute statistics — keep all
        return [
            FrameScore(i, m.fwhm, m.eccentricity, m.roundness, m.n_stars, True)
            for i, m in enumerate(metrics)
        ]

    # ── FWHM rejection ──
    med_fwhm = float(np.median(fwhms[finite]))
    std_fwhm = float(np.std(fwhms[finite]))
    fwhm_thresh = med_fwhm + rejection_sigma * std_fwhm

    # ── Eccentricity rejection (catches trailing / wind shake) ──
    med_ecc = float(np.median(eccs[finite]))
    std_ecc = float(np.std(eccs[finite]))
    ecc_thresh = min(med_ecc + rejection_sigma * std_ecc, 0.8)

    scores: list[FrameScore] = []
    for i, m in enumerate(metrics):
        keep = (
            np.isfinite(m.fwhm)
            and m.fwhm <= fwhm_thresh
            and m.eccentricity <= ecc_thresh
        )
        scores.append(
            FrameScore(i, m.fwhm, m.eccentricity, m.roundness, m.n_stars, keep)
        )

    return scores
