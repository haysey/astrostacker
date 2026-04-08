"""XISF file reading and writing."""

from __future__ import annotations

import numpy as np
from xisf import XISF


def read(path: str) -> np.ndarray:
    """Read an XISF file and return float32 ndarray.

    XISF read_image returns channels-last by default for color images.
    Returns shape (H, W) for mono or (H, W, C) for color.
    """
    xisf_obj = XISF(path)
    data = xisf_obj.read_image(0)

    if data is None:
        raise ValueError(f"No image data found in {path}")

    data = data.astype(np.float32)

    # If channels-first (C, H, W), transpose to channels-last
    if data.ndim == 3 and data.shape[0] in (3, 4) and data.shape[2] not in (3, 4):
        data = np.transpose(data, (1, 2, 0))

    return data


def write(path: str, data: np.ndarray, metadata: dict | None = None) -> None:
    """Write a float32 ndarray to an XISF file.

    Args:
        path: Output file path.
        data: Image data, shape (H, W) or (H, W, C).
        metadata: Optional metadata dict.
    """
    write_data = data.astype(np.float32)
    XISF.write(
        path,
        write_data,
        creator_app="Haysey's Astrostacker",
        codec="lz4hc",
        shuffle=True,
    )
