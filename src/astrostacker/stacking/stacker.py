"""High-level stacking interface."""

import inspect

import numpy as np

from astrostacker.stacking.methods import METHODS


def stack_images(
    images: list[np.ndarray],
    method: str = "median",
    **kwargs,
) -> np.ndarray:
    """Stack a list of aligned images using the specified method.

    Args:
        images: List of aligned float32 ndarrays, all same shape.
        method: Stacking method name (see METHODS registry).
        **kwargs: Extra arguments forwarded to the stacking function.
                  Only parameters that the chosen method accepts are
                  passed through; the rest are silently ignored.

    Returns:
        Stacked result as float32 ndarray.
    """
    if not images:
        raise ValueError("No images to stack")

    if method not in METHODS:
        raise ValueError(f"Unknown method '{method}'. Available: {list(METHODS.keys())}")

    stack_3d = np.array(images, dtype=np.float32)
    method_fn = METHODS[method]

    # Only forward kwargs that the method's signature actually accepts,
    # so callers can pass a superset without triggering TypeErrors.
    sig = inspect.signature(method_fn)
    valid_kwargs = {
        k: v for k, v in kwargs.items()
        if k in sig.parameters
    }
    return method_fn(stack_3d, **valid_kwargs)
