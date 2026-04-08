"""Stacking algorithms: Mean, Median, Sigma Clip, Min, Max."""

from typing import Callable

import numpy as np
from astropy.stats import sigma_clip


def stack_mean(images: np.ndarray) -> np.ndarray:
    """Average stacking. Maximizes SNR with clean data.

    Args:
        images: 3D array of shape (N, H, W) or 4D (N, H, W, C).

    Returns:
        Stacked image as float32.
    """
    return np.nanmean(images, axis=0).astype(np.float32)


def stack_median(images: np.ndarray) -> np.ndarray:
    """Median stacking. Good outlier rejection for any frame count.

    Args:
        images: 3D array of shape (N, H, W) or 4D (N, H, W, C).

    Returns:
        Stacked image as float32.
    """
    return np.nanmedian(images, axis=0).astype(np.float32)


def stack_sigma_clip(
    images: np.ndarray,
    sigma_low: float = 2.5,
    sigma_high: float = 2.5,
    max_iters: int = 5,
) -> np.ndarray:
    """Kappa-Sigma clipping stack.

    Iteratively rejects outlier pixels beyond sigma_low/sigma_high
    standard deviations from the median, then takes the mean of
    remaining pixels. Best with 15+ frames.

    Args:
        images: 3D array of shape (N, H, W) or 4D (N, H, W, C).
        sigma_low: Lower rejection threshold in sigma units.
        sigma_high: Upper rejection threshold in sigma units.
        max_iters: Maximum clipping iterations.

    Returns:
        Stacked image as float32.
    """
    clipped = sigma_clip(
        images,
        sigma_lower=sigma_low,
        sigma_upper=sigma_high,
        maxiters=max_iters,
        axis=0,
        masked=True,
        cenfunc="median",
    )
    return np.ma.mean(clipped, axis=0).data.astype(np.float32)


def stack_min(images: np.ndarray) -> np.ndarray:
    """Minimum stacking. Useful for detecting light pollution gradients.

    Args:
        images: 3D array of shape (N, H, W) or 4D (N, H, W, C).

    Returns:
        Stacked image as float32.
    """
    return np.nanmin(images, axis=0).astype(np.float32)


def stack_max(images: np.ndarray) -> np.ndarray:
    """Maximum stacking. Useful for finding transient objects.

    Args:
        images: 3D array of shape (N, H, W) or 4D (N, H, W, C).

    Returns:
        Stacked image as float32.
    """
    return np.nanmax(images, axis=0).astype(np.float32)


# Method registry mapping names to callables
METHODS: dict[str, Callable] = {
    "mean": stack_mean,
    "median": stack_median,
    "sigma_clip": stack_sigma_clip,
    "min": stack_min,
    "max": stack_max,
}
