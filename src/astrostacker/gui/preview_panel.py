"""Image preview panel with modern macOS styling."""

from __future__ import annotations

import numpy as np
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from astrostacker.io.loader import load_image, save_image
from astrostacker.utils.image_utils import numpy_to_qpixmap
from astrostacker.utils.stretch import auto_stretch, linear_stretch


class PreviewPanel(QWidget):
    """Image preview with stretch modes and zoom."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._raw_data: np.ndarray | None = None
        self._current_pixmap: QPixmap | None = None
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 4)
        layout.setSpacing(8)

        # Toolbar-style controls bar
        controls = QHBoxLayout()
        controls.setSpacing(12)

        stretch_label = QLabel("Stretch")
        stretch_label.setStyleSheet("color: rgba(255,255,255,0.5); font-size: 12px;")
        controls.addWidget(stretch_label)

        self.stretch_combo = QComboBox()
        self.stretch_combo.addItems(["Auto STF", "Linear"])
        self.stretch_combo.setFixedWidth(120)
        self.stretch_combo.setToolTip(
            "Auto STF: PixInsight-style screen stretch (best for deep sky).\n"
            "Linear: Simple min-max stretch."
        )
        self.stretch_combo.currentIndexChanged.connect(self._refresh_display)
        controls.addWidget(self.stretch_combo)

        zoom_label = QLabel("Zoom")
        zoom_label.setStyleSheet("color: rgba(255,255,255,0.5); font-size: 12px;")
        controls.addWidget(zoom_label)

        self.zoom_combo = QComboBox()
        self.zoom_combo.addItems(["Fit", "25%", "50%", "100%", "200%"])
        self.zoom_combo.setFixedWidth(90)
        self.zoom_combo.setToolTip("Zoom level. Use 100% to inspect details at native resolution.")
        self.zoom_combo.currentIndexChanged.connect(self._refresh_display)
        controls.addWidget(self.zoom_combo)

        controls.addStretch()

        self.save_btn = QPushButton("Save As...")
        self.save_btn.setFixedWidth(90)
        self.save_btn.setEnabled(False)
        self.save_btn.clicked.connect(self._save_image)
        controls.addWidget(self.save_btn)

        self.info_label = QLabel("")
        self.info_label.setStyleSheet(
            "color: rgba(255,255,255,0.4); font-size: 11px;"
            "font-family: 'SF Mono', 'Menlo', monospace;"
        )
        controls.addWidget(self.info_label)

        layout.addLayout(controls)

        # Image display area
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.scroll_area.setStyleSheet(
            "QScrollArea { background-color: #0d0d0d; border-radius: 10px; }"
        )

        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setText(
            "No image loaded\n\n"
            "Add light frames and click a file to preview,\n"
            "or run the pipeline to see the stacked result."
        )
        self.image_label.setStyleSheet(
            "color: rgba(255,255,255,0.25); font-size: 14px; font-weight: 400;"
        )
        self.scroll_area.setWidget(self.image_label)

        layout.addWidget(self.scroll_area)

    def show_file(self, path: str):
        try:
            data = load_image(path)
            self.show_data(data, info=path)
        except Exception as e:
            self.image_label.setText(f"Error loading image:\n{e}")

    def show_data(self, data: np.ndarray, info: str = ""):
        self._raw_data = data
        self.save_btn.setEnabled(True)
        shape_str = f"{data.shape[1]} x {data.shape[0]}"
        if data.ndim == 3:
            shape_str += f" x {data.shape[2]}"
        self.info_label.setText(f"{shape_str}   {data.dtype}   {info}")
        self._refresh_display()

    def _refresh_display(self):
        if self._raw_data is None:
            return

        stretch_mode = self.stretch_combo.currentText()
        if stretch_mode == "Auto STF":
            display_data = auto_stretch(self._raw_data)
        else:
            display_data = linear_stretch(self._raw_data)

        pixmap = numpy_to_qpixmap(display_data)
        self._current_pixmap = pixmap

        zoom_text = self.zoom_combo.currentText()
        if zoom_text == "Fit":
            # Fit mode: label fills the scroll area, image scales down
            self.scroll_area.setWidgetResizable(True)
            self.image_label.setMinimumSize(1, 1)
            available = self.scroll_area.viewport().size()
            scaled = pixmap.scaled(
                available,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            self.image_label.setPixmap(scaled)
        else:
            # Zoom mode: label can be larger than scroll area (scrollable)
            self.scroll_area.setWidgetResizable(False)
            zoom_pct = int(zoom_text.replace("%", "")) / 100.0
            w = max(1, int(pixmap.width() * zoom_pct))
            h = max(1, int(pixmap.height() * zoom_pct))
            scaled = pixmap.scaled(
                w, h,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            self.image_label.setPixmap(scaled)
            self.image_label.setMinimumSize(scaled.size())
            self.image_label.resize(scaled.size())

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self._current_pixmap and self.zoom_combo.currentText() == "Fit":
            self._refresh_display()

    def _save_image(self):
        """Save the current image data to a user-chosen location."""
        if self._raw_data is None:
            return

        path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Image",
            "",
            "FITS Files (*.fits);;XISF Files (*.xisf);;PNG Image (*.png);;TIFF Image (*.tiff)",
        )
        if not path:
            return

        try:
            ext = path.rsplit(".", 1)[-1].lower() if "." in path else ""
            if ext in ("png", "tiff", "tif"):
                # Save the displayed (stretched) version for raster formats
                if self._current_pixmap:
                    self._current_pixmap.save(path)
            else:
                # Save raw float data for FITS/XISF
                save_image(path, self._raw_data)
            QMessageBox.information(self, "Saved", f"Image saved to:\n{path}")
        except Exception as e:
            QMessageBox.critical(self, "Save Error", str(e))

    def clear(self):
        self._raw_data = None
        self._current_pixmap = None
        self.save_btn.setEnabled(False)
        self.image_label.clear()
        self.image_label.setText("No image loaded")
        self.info_label.setText("")
