"""Apply calibration (dark subtraction, flat correction) to light frames."""

from __future__ import annotations

import numpy as np


def calibrate_light(
    light: np.ndarray,
    master_dark: np.ndarray | None = None,
    master_flat: np.ndarray | None = None,
) -> np.ndarray:
    """Calibrate a single light frame.

    Applies dark subtraction and flat field correction:
        calibrated = (light - master_dark) / master_flat

    Either calibration frame can be None to skip that step.

    Args:
        light: Raw light frame as float32 ndarray.
        master_dark: Master dark frame (same dimensions as light).
        master_flat: Normalized master flat (values centered around 1.0).

    Returns:
        Calibrated light frame as float32 ndarray.
    """
    result = light.astype(np.float32, copy=True)

    if master_dark is not None:
        result = result - master_dark

    if master_flat is not None:
        # Protect against division by zero in dead/cold pixels
        safe_flat = np.where(master_flat > 0.01, master_flat, 1.0)
        result = result / safe_flat

    return result
