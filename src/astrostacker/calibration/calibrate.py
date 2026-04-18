"""Apply calibration (dark subtraction, flat correction) to light frames.

Optimised for Apple Silicon NEON SIMD — uses in-place float32
operations throughout (NEON processes 4×float32 simultaneously
vs 2×float64, giving ~2× throughput).

If a master dark or flat has different dimensions to the light frame
(e.g. different binning, or a master from a previous session), it is
automatically resized to match.
"""

from __future__ import annotations

import logging

import numpy as np
from scipy.ndimage import zoom

log = logging.getLogger(__name__)


def _match_shape(
    cal_frame: np.ndarray,
    target_shape: tuple[int, ...],
    label: str,
) -> np.ndarray:
    """Resize a calibration frame to match the light frame dimensions.

    Uses spline interpolation for smooth scaling — suitable for
    darks and flats which are slowly-varying signals.

    Args:
        cal_frame: The master dark or flat to resize.
        target_shape: Shape of the light frame (H, W) or (H, W, C).
        label: Name for the log message ("dark" or "flat").

    Returns:
        Resized frame as float32, or the original if shapes already match.
    """
    cal_hw = cal_frame.shape[:2]
    tgt_hw = target_shape[:2]

    if cal_hw != tgt_hw:
        log.warning(
            "Master %s is %s but lights are %s — resizing to match",
            label, "×".join(map(str, cal_hw)), "×".join(map(str, tgt_hw)),
        )

        # Compute zoom factors for the spatial dimensions
        factors = [tgt_hw[0] / cal_hw[0], tgt_hw[1] / cal_hw[1]]

        # If the cal frame is 3-D (colour), don't scale the channel axis
        if cal_frame.ndim == 3:
            factors.append(1.0)

        resized = zoom(cal_frame.astype(np.float64), factors, order=1)
        cal_frame = np.ascontiguousarray(resized, dtype=np.float32)

    # If the light is colour (H,W,3) but the calibration frame is mono
    # (H,W), add a channel axis so NumPy can broadcast across all channels.
    # This happens when the capture software saves pre-debayered colour FITS
    # but the darks/flats are raw mono frames.
    if len(target_shape) == 3 and cal_frame.ndim == 2:
        cal_frame = cal_frame[:, :, np.newaxis]

    return cal_frame


def prepare_flat_divisor(
    master_flat: np.ndarray,
    target_shape: tuple[int, ...] | None = None,
) -> np.ndarray:
    """Pre-compute the safe flat divisor once for reuse across all frames.

    Call this once before calibrating multiple frames to avoid
    recomputing the safe_flat for every frame.

    Args:
        master_flat: The master flat frame.
        target_shape: If provided and shapes differ, resize to match.
    """
    if target_shape is not None:
        master_flat = _match_shape(master_flat, target_shape, "flat")
    safe_flat = np.where(master_flat > 0.01, master_flat, 1.0)
    return np.ascontiguousarray(safe_flat, dtype=np.float32)


def calibrate_light(
    light: np.ndarray,
    master_dark: np.ndarray | None = None,
    master_flat: np.ndarray | None = None,
    flat_divisor: np.ndarray | None = None,
) -> np.ndarray:
    """Calibrate a single light frame.

    Applies dark subtraction and flat field correction:
        calibrated = (light - master_dark) / master_flat

    Either calibration frame can be None to skip that step.
    If a calibration frame has different dimensions, it is resized
    automatically (e.g. master from a different binning session).

    Uses in-place operations to minimise memory allocation and
    maximise NEON SIMD throughput on Apple Silicon.

    Args:
        light: Raw light frame as float32 ndarray.
        master_dark: Master dark frame.
        master_flat: Normalized master flat (values centered around 1.0).
        flat_divisor: Pre-computed safe flat from prepare_flat_divisor().
                      If provided, master_flat is ignored.

    Returns:
        Calibrated light frame as float32 ndarray.
    """
    # Copy to avoid modifying the original; stay in float32 for NEON
    result = light.astype(np.float32, copy=True)

    if master_dark is not None:
        dark = _match_shape(master_dark, result.shape, "dark")
        np.subtract(result, dark, out=result)

    if flat_divisor is not None:
        flat = _match_shape(flat_divisor, result.shape, "flat")
        np.divide(result, flat, out=result)
    elif master_flat is not None:
        flat = _match_shape(master_flat, result.shape, "flat")
        safe_flat = np.where(flat > 0.01, flat, 1.0)
        np.divide(result, safe_flat, out=result)

    return result
