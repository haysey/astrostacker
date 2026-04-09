"""Apply calibration (dark subtraction, flat correction) to light frames.

Optimised for Apple Silicon NEON SIMD — uses in-place float32
operations throughout (NEON processes 4×float32 simultaneously
vs 2×float64, giving ~2× throughput).
"""

from __future__ import annotations

import numpy as np


def prepare_flat_divisor(master_flat: np.ndarray) -> np.ndarray:
    """Pre-compute the safe flat divisor once for reuse across all frames.

    Call this once before calibrating multiple frames to avoid
    recomputing the safe_flat for every frame.
    """
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

    Uses in-place operations to minimise memory allocation and
    maximise NEON SIMD throughput on Apple Silicon.

    Args:
        light: Raw light frame as float32 ndarray.
        master_dark: Master dark frame (same dimensions as light).
        master_flat: Normalized master flat (values centered around 1.0).
        flat_divisor: Pre-computed safe flat from prepare_flat_divisor().
                      If provided, master_flat is ignored.

    Returns:
        Calibrated light frame as float32 ndarray.
    """
    # Copy to avoid modifying the original; stay in float32 for NEON
    result = light.astype(np.float32, copy=True)

    if master_dark is not None:
        np.subtract(result, master_dark, out=result)

    if flat_divisor is not None:
        np.divide(result, flat_divisor, out=result)
    elif master_flat is not None:
        safe_flat = np.where(master_flat > 0.01, master_flat, 1.0)
        np.divide(result, safe_flat, out=result)

    return result
