"""Histogram panel showing pixel value distribution of the current image."""

from __future__ import annotations

import numpy as np
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QPainter, QPen
from PyQt6.QtWidgets import QLabel, QVBoxLayout, QWidget


class HistogramWidget(QWidget):
    """Draws a histogram of pixel values."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._hist_data: list[tuple[np.ndarray, QColor]] = []
        self.setMinimumHeight(100)
        self.setMinimumWidth(200)

    def set_data(self, data: np.ndarray | None):
        """Compute histogram from image data."""
        self._hist_data = []
        if data is None:
            self.update()
            return

        bins = 256

        if data.ndim == 3:
            colours = [
                QColor(220, 60, 60),    # Red
                QColor(60, 200, 60),    # Green
                QColor(80, 80, 240),    # Blue
            ]
            for c in range(min(data.shape[2], 3)):
                channel = data[:, :, c].ravel()
                valid = channel[np.isfinite(channel)]
                if len(valid) == 0:
                    continue
                hist, _ = np.histogram(valid, bins=bins, range=(0, 1))
                self._hist_data.append((hist.astype(np.float32), colours[c]))
        else:
            flat = data.ravel()
            valid = flat[np.isfinite(flat)]
            if len(valid) > 0:
                lo, hi = float(np.min(valid)), float(np.max(valid))
                if hi > lo:
                    hist, _ = np.histogram(valid, bins=bins, range=(lo, hi))
                else:
                    hist = np.zeros(bins, dtype=np.float32)
                self._hist_data.append(
                    (hist.astype(np.float32), QColor(200, 200, 200))
                )

        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Background
        painter.fillRect(self.rect(), QColor(13, 13, 13))

        if not self._hist_data:
            painter.setPen(QColor(100, 100, 100))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "No data")
            painter.end()
            return

        w = self.width() - 4
        h = self.height() - 4
        x_off = 2
        y_off = 2

        # Find global max for scaling (use log scale for better visibility)
        all_max = 1.0
        for hist, _ in self._hist_data:
            log_hist = np.log1p(hist)
            m = float(log_hist.max())
            if m > all_max:
                all_max = m

        for hist, colour in self._hist_data:
            log_hist = np.log1p(hist)
            n_bins = len(log_hist)
            pen = QPen(colour, 1)
            pen_colour = QColor(colour)
            pen_colour.setAlpha(180)
            pen = QPen(pen_colour, 1)
            painter.setPen(pen)

            bin_width = w / n_bins
            for i in range(n_bins):
                bar_h = int((log_hist[i] / all_max) * h)
                x = int(x_off + i * bin_width)
                painter.drawLine(x, y_off + h, x, y_off + h - bar_h)

        painter.end()


class HistogramPanel(QWidget):
    """Panel containing a histogram and stats label."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(4)

        header = QLabel("Histogram")
        header.setStyleSheet(
            "font-size: 12px; font-weight: 600; color: rgba(255,255,255,0.6);"
        )
        layout.addWidget(header)

        self.histogram = HistogramWidget()
        layout.addWidget(self.histogram)

        self.stats_label = QLabel("")
        self.stats_label.setStyleSheet(
            "font-size: 11px; color: rgba(255,255,255,0.4);"
            "font-family: 'SF Mono', 'Menlo', monospace;"
        )
        layout.addWidget(self.stats_label)

    def set_data(self, data: np.ndarray | None):
        self.histogram.set_data(data)
        if data is not None:
            valid = data[np.isfinite(data)]
            if len(valid) > 0:
                self.stats_label.setText(
                    f"Min: {valid.min():.4f}  "
                    f"Max: {valid.max():.4f}  "
                    f"Mean: {valid.mean():.4f}  "
                    f"Median: {np.median(valid):.4f}"
                )
            else:
                self.stats_label.setText("")
        else:
            self.stats_label.setText("")
