"""Procedural starfield background for the application.

Generates a subtle deep-space background with stars and a faint
nebula glow — entirely procedurally, no external image files needed.
"""

from __future__ import annotations

import numpy as np
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QBrush, QImage, QPainter, QPalette, QPixmap, QRadialGradient, QColor


def _generate_starfield(width: int, height: int) -> np.ndarray:
    """Generate a starfield image as a uint8 RGB array.

    Creates:
    - A dark gradient sky (deep blue-black)
    - Scattered stars of varying brightness and size
    - Subtle nebula glow patches
    """
    rng = np.random.RandomState(42)  # fixed seed for consistent look

    # Base: dark gradient from deep blue-black to slightly lighter
    img = np.zeros((height, width, 3), dtype=np.float64)

    # Vertical gradient: darker at top, very slightly lighter at bottom
    for y in range(height):
        t = y / height
        img[y, :, 0] = 8 + t * 6      # R: 8 → 14
        img[y, :, 1] = 10 + t * 5     # G: 10 → 15
        img[y, :, 2] = 18 + t * 8     # B: 18 → 26

    # Faint stars (many, small, dim)
    n_faint = int(width * height * 0.0008)
    for _ in range(n_faint):
        x = rng.randint(0, width)
        y = rng.randint(0, height)
        brightness = rng.uniform(25, 55)
        # Slight colour variation (blue-white to warm-white)
        colour_shift = rng.uniform(-5, 5)
        if 0 <= y < height and 0 <= x < width:
            img[y, x, 0] = min(255, img[y, x, 0] + brightness + colour_shift)
            img[y, x, 1] = min(255, img[y, x, 1] + brightness)
            img[y, x, 2] = min(255, img[y, x, 2] + brightness - colour_shift)

    # Medium stars (fewer, slightly brighter)
    n_medium = int(width * height * 0.0002)
    for _ in range(n_medium):
        x = rng.randint(1, width - 1)
        y = rng.randint(1, height - 1)
        brightness = rng.uniform(45, 80)
        colour_shift = rng.uniform(-8, 8)
        # Star core
        img[y, x, 0] = min(255, img[y, x, 0] + brightness + colour_shift)
        img[y, x, 1] = min(255, img[y, x, 1] + brightness)
        img[y, x, 2] = min(255, img[y, x, 2] + brightness - colour_shift)
        # Subtle glow around medium stars
        glow = brightness * 0.3
        for dy, dx in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            ny, nx = y + dy, x + dx
            if 0 <= ny < height and 0 <= nx < width:
                img[ny, nx] = np.minimum(255, img[ny, nx] + glow * 0.5)

    # Bright stars (very few, noticeable)
    n_bright = max(3, int(width * height * 0.000015))
    for _ in range(n_bright):
        x = rng.randint(2, width - 2)
        y = rng.randint(2, height - 2)
        brightness = rng.uniform(70, 120)
        # Bright core
        img[y, x] = np.minimum(255, img[y, x] + brightness)
        # Cross-shaped diffraction spikes (very subtle)
        for dist in range(1, 3):
            falloff = brightness * (0.4 / dist)
            for dy, dx in [(-dist, 0), (dist, 0), (0, -dist), (0, dist)]:
                ny, nx = y + dy, x + dx
                if 0 <= ny < height and 0 <= nx < width:
                    img[ny, nx] = np.minimum(255, img[ny, nx] + falloff)

    return np.clip(img, 0, 255).astype(np.uint8)


def generate_background_pixmap(width: int, height: int) -> QPixmap:
    """Generate a starfield QPixmap with nebula glow overlay.

    The starfield is generated procedurally, then nebula glow patches
    are painted on top using Qt's radial gradient for smooth blending.
    """
    # Generate base starfield
    star_data = _generate_starfield(width, height)

    # Convert to QImage/QPixmap
    h, w, _ = star_data.shape
    bytes_per_line = w * 3
    qimage = QImage(
        star_data.tobytes(), w, h, bytes_per_line,
        QImage.Format.Format_RGB888
    )
    pixmap = QPixmap.fromImage(qimage)

    # Paint subtle nebula glow patches using Qt radial gradients
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Plus)

    # Nebula 1: faint teal/blue glow (upper right area)
    grad1 = QRadialGradient(width * 0.75, height * 0.3, min(width, height) * 0.35)
    grad1.setColorAt(0.0, QColor(0, 40, 60, 18))
    grad1.setColorAt(0.5, QColor(0, 25, 45, 8))
    grad1.setColorAt(1.0, QColor(0, 0, 0, 0))
    painter.setBrush(QBrush(grad1))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawEllipse(
        int(width * 0.4), int(height * 0.0),
        int(min(width, height) * 0.7), int(min(width, height) * 0.7)
    )

    # Nebula 2: very faint warm glow (lower left)
    grad2 = QRadialGradient(width * 0.2, height * 0.75, min(width, height) * 0.3)
    grad2.setColorAt(0.0, QColor(50, 15, 30, 12))
    grad2.setColorAt(0.5, QColor(30, 8, 20, 5))
    grad2.setColorAt(1.0, QColor(0, 0, 0, 0))
    painter.setBrush(QBrush(grad2))
    painter.drawEllipse(
        int(width * 0.05), int(height * 0.55),
        int(min(width, height) * 0.6), int(min(width, height) * 0.5)
    )

    painter.end()
    return pixmap
