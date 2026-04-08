"""Image utility functions for format conversion and normalization."""

import numpy as np
from PyQt6.QtGui import QImage, QPixmap


def numpy_to_qimage(data: np.ndarray) -> QImage:
    """Convert a uint8 numpy array to a QImage.

    Args:
        data: uint8 ndarray, shape (H, W) for grayscale or (H, W, 3) for RGB.

    Returns:
        QImage ready for display.
    """
    if data.ndim == 2:
        h, w = data.shape
        bytes_per_line = w
        return QImage(
            data.tobytes(), w, h, bytes_per_line, QImage.Format.Format_Grayscale8
        )
    elif data.ndim == 3 and data.shape[2] == 3:
        h, w, _ = data.shape
        bytes_per_line = w * 3
        return QImage(
            data.tobytes(), w, h, bytes_per_line, QImage.Format.Format_RGB888
        )
    else:
        raise ValueError(f"Unsupported array shape for QImage: {data.shape}")


def numpy_to_qpixmap(data: np.ndarray) -> QPixmap:
    """Convert a uint8 numpy array to a QPixmap for display."""
    qimage = numpy_to_qimage(data)
    return QPixmap.fromImage(qimage)
