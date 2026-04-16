"""PSF (Point Spread Function) fitting for astrophotography frames.

Fits 2D elliptical Gaussian models to detected stars, providing
accurate FWHM, eccentricity, and roundness metrics for frame
quality scoring, weighted stacking, and deconvolution.

Also builds Moffat PSF kernels for Richardson-Lucy deconvolution
— Moffat profiles model real star profiles more accurately than
Gaussians because they have broader wings (atmospheric seeing).

Uses scipy.optimize.curve_fit — no additional dependencies needed.

Reference: Moffat, A.F.J., 1969, "A Theoretical Investigation of
Focal Stellar Images in the Photographic Emulsion", Astronomy &
Astrophysics.
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass

import numpy as np
from scipy.ndimage import gaussian_filter
from scipy.optimize import curve_fit

# ── Constants ──

FWHM_FACTOR = 2.0 * np.sqrt(2.0 * np.log(2.0))  # ≈ 2.3548
STAMP_RADIUS = 12   # pixels around each star for fitting
MIN_FWHM = 0.5      # reject fits below this (sub-pixel noise)
MAX_FWHM = 15.0     # reject fits above this (not a point source)
MAX_ECCENTRICITY = 0.95  # reject very elongated fits


# ── Data classes ──

@dataclass
class StarPSF:
    """PSF fit result for a single star."""

    x: float            # sub-pixel x position in frame
    y: float            # sub-pixel y position in frame
    fwhm_x: float       # FWHM along major axis (pixels)
    fwhm_y: float       # FWHM along minor axis (pixels)
    fwhm: float          # geometric mean FWHM (pixels)
    eccentricity: float  # 0 = perfectly round, 1 = line
    roundness: float     # minor/major ratio (1 = round, 0 = line)
    amplitude: float     # peak signal above background
    background: float    # local background level
    theta: float         # position angle (radians)


@dataclass
class FramePSF:
    """Aggregate PSF metrics for an entire frame."""

    fwhm: float          # median FWHM across fitted stars
    eccentricity: float  # median eccentricity
    roundness: float     # median roundness (minor/major)
    n_stars: int         # number of successfully fitted stars
    stars: list[StarPSF]  # individual star fits


_EMPTY_FRAME = FramePSF(
    fwhm=float("inf"), eccentricity=0.0, roundness=1.0,
    n_stars=0, stars=[],
)


# ── 2D model functions (for scipy curve_fit) ──

def _gaussian_2d(coords, amplitude, x0, y0, sigma_x, sigma_y, theta, background):
    """Elliptical 2D Gaussian — 7 parameters."""
    x, y = coords
    cos_t = np.cos(theta)
    sin_t = np.sin(theta)
    sx2 = 2.0 * sigma_x**2
    sy2 = 2.0 * sigma_y**2
    a = cos_t**2 / sx2 + sin_t**2 / sy2
    b = sin_t * cos_t * (1.0 / sy2 - 1.0 / sx2)
    c = sin_t**2 / sx2 + cos_t**2 / sy2
    dx = x - x0
    dy = y - y0
    return (
        amplitude * np.exp(-(a * dx**2 + 2.0 * b * dx * dy + c * dy**2))
        + background
    ).ravel()


def _moffat_2d(coords, amplitude, x0, y0, alpha, beta, background):
    """Circular 2D Moffat — 6 parameters (for kernel building)."""
    x, y = coords
    r2 = (x - x0) ** 2 + (y - y0) ** 2
    return (amplitude * (1.0 + r2 / alpha**2) ** (-beta) + background).ravel()


# ── Single-star fitting ──

def fit_star(stamp: np.ndarray) -> StarPSF | None:
    """Fit an elliptical 2D Gaussian to a star stamp.

    Args:
        stamp: Small 2-D cutout centred on a star.

    Returns:
        StarPSF on success, *None* if the fit fails or is rejected.
    """
    h, w = stamp.shape
    cy_init, cx_init = h / 2.0, w / 2.0

    bg = float(np.percentile(stamp, 20))
    peak = float(np.max(stamp))
    amp = max(peak - bg, 1e-6)

    y_grid, x_grid = np.mgrid[0:h, 0:w]
    coords = (x_grid.astype(np.float64), y_grid.astype(np.float64))
    data = stamp.ravel().astype(np.float64)

    p0 = [amp, cx_init, cy_init, 2.0, 2.0, 0.0, bg]
    lo = [0.0, 0.0, 0.0, 0.3, 0.3, -np.pi, 0.0]
    hi = [amp * 3.0, float(w), float(h), w / 2.0, h / 2.0, np.pi, peak]

    try:
        popt, _ = curve_fit(
            _gaussian_2d, coords, data,
            p0=p0, bounds=(lo, hi), maxfev=500,
        )
    except (RuntimeError, ValueError):
        return None

    amplitude, x0, y0, sigma_x, sigma_y, theta, background = popt

    # Ensure sigma_x >= sigma_y (major >= minor)
    if sigma_x < sigma_y:
        sigma_x, sigma_y = sigma_y, sigma_x
        theta += np.pi / 2.0

    fwhm_x = sigma_x * FWHM_FACTOR
    fwhm_y = sigma_y * FWHM_FACTOR
    fwhm = float(np.sqrt(fwhm_x * fwhm_y))

    if fwhm < MIN_FWHM or fwhm > MAX_FWHM:
        return None
    if amplitude < bg * 0.1:          # too faint relative to background
        return None

    ratio = sigma_y / sigma_x         # minor / major  ≤ 1
    eccentricity = float(np.sqrt(1.0 - ratio**2))
    roundness = float(ratio)

    if eccentricity > MAX_ECCENTRICITY:
        return None

    return StarPSF(
        x=float(x0), y=float(y0),
        fwhm_x=float(fwhm_x), fwhm_y=float(fwhm_y),
        fwhm=fwhm, eccentricity=eccentricity,
        roundness=roundness, amplitude=float(amplitude),
        background=float(background), theta=float(theta),
    )


# ── Frame-level PSF measurement ──

def measure_frame_psf(
    image: np.ndarray,
    max_stars: int = 60,
    detection_sigma: float = 3.0,
) -> FramePSF:
    """Detect stars and fit PSFs across an entire frame.

    Works with both mono (H, W) and colour (H, W, C) images.

    Args:
        image: Image array (2-D or 3-D).
        max_stars: Cap on the number of stars to fit.
        detection_sigma: Detection threshold in sigma above background.

    Returns:
        FramePSF with per-star fits and aggregate statistics.
    """
    from skimage.feature import peak_local_max

    # Work on a mono representation
    if image.ndim == 3:
        mono = np.mean(image, axis=2)
    else:
        mono = image
    mono = mono.astype(np.float64)

    smoothed = gaussian_filter(mono, sigma=1.5)
    valid = smoothed[np.isfinite(smoothed)]
    if len(valid) == 0:
        return _EMPTY_FRAME

    med = float(np.median(valid))
    std = float(np.std(valid))
    threshold = max(med + detection_sigma * std, med + 0.02)

    peaks = peak_local_max(
        smoothed,
        min_distance=8,
        threshold_abs=threshold,
        num_peaks=max_stars,
    )
    if len(peaks) == 0:
        return _EMPTY_FRAME

    h, w = mono.shape
    stars: list[StarPSF] = []

    for row, col in peaks:
        r0 = max(0, row - STAMP_RADIUS)
        r1 = min(h, row + STAMP_RADIUS + 1)
        c0 = max(0, col - STAMP_RADIUS)
        c1 = min(w, col + STAMP_RADIUS + 1)
        stamp = mono[r0:r1, c0:c1]

        if stamp.shape[0] < 5 or stamp.shape[1] < 5:
            continue

        result = fit_star(stamp)
        if result is not None:
            # Translate stamp coordinates → frame coordinates
            result = dataclasses.replace(
                result, x=result.x + c0, y=result.y + r0,
            )
            stars.append(result)

    if not stars:
        return _EMPTY_FRAME

    fwhms = [s.fwhm for s in stars]
    eccs = [s.eccentricity for s in stars]
    rounds = [s.roundness for s in stars]

    return FramePSF(
        fwhm=float(np.median(fwhms)),
        eccentricity=float(np.median(eccs)),
        roundness=float(np.median(rounds)),
        n_stars=len(stars),
        stars=stars,
    )


# ── PSF kernel construction (for deconvolution) ──

def build_moffat_kernel(
    fwhm: float,
    beta: float = 3.5,
    size: int = 0,
) -> np.ndarray:
    """Build a normalised 2-D Moffat PSF kernel.

    Moffat profiles model real star images more accurately than
    Gaussians — they have broader wings that match atmospheric
    seeing and telescope optics.

    Args:
        fwhm: Full-width at half-maximum in pixels.
        beta: Moffat shape parameter (2.5–4.5 typical; 3.5 default).
        size: Kernel side length in pixels (0 = auto, ~4 × FWHM).

    Returns:
        2-D kernel normalised to sum to 1.0 (float64).
    """
    if size == 0:
        size = int(np.ceil(fwhm * 4)) | 1   # odd, ≈ 4× FWHM
        size = max(size, 7)

    alpha = fwhm / (2.0 * np.sqrt(2.0 ** (1.0 / beta) - 1.0))
    centre = size // 2
    y, x = np.mgrid[0:size, 0:size]
    r2 = (x.astype(np.float64) - centre) ** 2 + (y.astype(np.float64) - centre) ** 2
    kernel = (1.0 + r2 / alpha**2) ** (-beta)
    kernel /= kernel.sum()
    return kernel
