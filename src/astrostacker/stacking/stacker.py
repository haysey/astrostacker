"""High-level stacking interface."""

import numpy as np

from astrostacker.stacking.methods import METHODS


def stack_images(
    images: list[np.ndarray],
    method: str = "sigma_clip",
    **kwargs,
) -> np.ndarray:
    """Stack a list of aligned images using the specified method.

    Args:
        images: List of aligned float32 ndarrays, all same shape.
        method: Stacking method name (mean, median, sigma_clip, min, max).
        **kwargs: Extra arguments passed to the stacking function
                  (e.g., sigma_low, sigma_high for sigma_clip).

    Returns:
        Stacked result as float32 ndarray.
    """
    if not images:
        raise ValueError("No images to stack")

    if method not in METHODS:
        raise ValueError(f"Unknown method '{method}'. Available: {list(METHODS.keys())}")

    stack_3d = np.array(images, dtype=np.float32)
    method_fn = METHODS[method]

    if method == "sigma_clip":
        return method_fn(stack_3d, **kwargs)
    else:
        return method_fn(stack_3d)
