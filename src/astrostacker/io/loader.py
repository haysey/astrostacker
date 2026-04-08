"""Unified image loader dispatching by file extension."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from astrostacker.config import SUPPORTED_EXTENSIONS
from astrostacker.io import fits_io, xisf_io


def load_image(path: str) -> np.ndarray:
    """Load an image file and return a float32 ndarray.

    Dispatches to the appropriate reader based on file extension.
    Returns shape (H, W) for mono or (H, W, C) for color.
    """
    ext = Path(path).suffix.lower()

    if ext in (".fits", ".fit", ".fts"):
        data = fits_io.read(path)
    elif ext == ".xisf":
        data = xisf_io.read(path)
    else:
        raise ValueError(
            f"Unsupported format: {ext}. Supported: {SUPPORTED_EXTENSIONS}"
        )

    return data.astype(np.float32)


def save_image(path: str, data: np.ndarray, metadata: dict | None = None) -> None:
    """Save an image to FITS or XISF based on file extension.

    Args:
        path: Output file path.
        data: float32 ndarray, shape (H, W) or (H, W, C).
        metadata: Optional metadata.
    """
    ext = Path(path).suffix.lower()

    if ext in (".fits", ".fit", ".fts"):
        fits_io.write(path, data, header_extra=metadata)
    elif ext == ".xisf":
        xisf_io.write(path, data, metadata=metadata)
    else:
        raise ValueError(
            f"Unsupported output format: {ext}. Supported: {SUPPORTED_EXTENSIONS}"
        )
