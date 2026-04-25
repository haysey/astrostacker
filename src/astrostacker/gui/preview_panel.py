"""Image preview panel with modern macOS styling."""

from __future__ import annotations

import numpy as np
from PyQt6.QtCore import Qt, QPoint, QRect, pyqtSignal
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QRubberBand,
    QScrollArea,
    QStyle,
    QVBoxLayout,
    QWidget,
)

from astrostacker.io.loader import load_image, save_image
from astrostacker.utils.image_utils import numpy_to_qpixmap
from astrostacker.utils.stretch import auto_stretch, linear_stretch


class PreviewPanel(QWidget):
    """Image preview with stretch modes and zoom."""

    crop_selected = pyqtSignal(int, int, int, int)  # x, y, w, h in original image pixels

    def __init__(self, parent=None):
        super().__init__(parent)
        self._raw_data: np.ndarray | None = None
        self._current_pixmap: QPixmap | None = None
        self._crop_mode = False
        self._crop_start: QPoint | None = None
        self._rubber_band: QRubberBand | None = None
        # When set, _refresh_display uses these precomputed stretch params
        # instead of recomputing them from the current data.  This lets the
        # post-processing dialog lock the display scale to the original image
        # so effects like star reduction are visible rather than compensated.
        self._fixed_stretch_params: tuple | None = None
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
        self.save_btn.setObjectName("secondaryButton")
        self.save_btn.setMinimumWidth(110)
        self.save_btn.setIcon(
            self.style().standardIcon(QStyle.StandardPixmap.SP_DialogSaveButton)
        )
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
        self._empty_html = (
            '<div style="text-align: center;">'
            '<div style="font-size: 48px; color: rgba(255,149,0,0.35);'
            ' margin-bottom: 20px;">✦</div>'
            '<div style="color: rgba(255,255,255,0.60); font-size: 16px;'
            ' font-weight: 600; margin-bottom: 14px;">No image loaded</div>'
            '<div style="color: rgba(255,255,255,0.35); font-size: 13px;'
            ' line-height: 1.6;">'
            'Add light frames and click a file to preview,<br/>'
            'or run the pipeline to see the stacked result.'
            '</div>'
            '</div>'
        )
        self.image_label.setTextFormat(Qt.TextFormat.RichText)
        self.image_label.setText(self._empty_html)
        self.scroll_area.setWidget(self.image_label)
        self.image_label.installEventFilter(self)

        layout.addWidget(self.scroll_area)

    def show_file(self, path: str):
        try:
            data = load_image(path)
            self.show_data(data, info=path)
        except Exception as e:
            self.image_label.setText(f"Error loading image:\n{e}")

    def show_data(self, data: np.ndarray, info: str = "", fixed_stretch_params: tuple | None = None):
        self._raw_data = data
        self._fixed_stretch_params = fixed_stretch_params
        self.save_btn.setEnabled(True)
        shape_str = f"{data.shape[1]} x {data.shape[0]}"
        if data.ndim == 3:
            shape_str += f" x {data.shape[2]}"
        self.info_label.setText(f"{shape_str}   {data.dtype}   {info}")
        self._refresh_display()

    def _refresh_display(self):
        if self._raw_data is None:
            return

        if self._fixed_stretch_params is not None:
            # Use locked stretch params so the display scale stays consistent
            # across before/after comparisons (e.g. star reduction preview).
            from astrostacker.utils.stretch import _apply_stretch_params
            shadow, highlight, midtone = self._fixed_stretch_params
            arr = self._raw_data.astype(np.float64)
            if arr.ndim == 3:
                channels = [
                    _apply_stretch_params(arr[:, :, c], shadow, highlight, midtone)
                    for c in range(arr.shape[2])
                ]
                display_data = np.stack(channels, axis=2)
            else:
                display_data = _apply_stretch_params(arr, shadow, highlight, midtone)
        else:
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

    def set_crop_mode(self, enabled: bool):
        """Enter or exit crop-selection mode."""
        self._crop_mode = enabled
        cursor = Qt.CursorShape.CrossCursor if enabled else Qt.CursorShape.ArrowCursor
        self.image_label.setCursor(cursor)
        if not enabled and self._rubber_band is not None:
            self._rubber_band.hide()

    def _screen_to_image(self, label_pos: QPoint) -> tuple[int, int]:
        """Convert a point in image_label coordinates to original image pixel coords."""
        if self._raw_data is None:
            return 0, 0
        pm = self.image_label.pixmap()
        if pm is None or pm.isNull():
            return 0, 0
        # Qt centres the pixmap inside the label (due to AlignCenter).
        off_x = max(0, (self.image_label.width()  - pm.width())  // 2)
        off_y = max(0, (self.image_label.height() - pm.height()) // 2)
        px = label_pos.x() - off_x
        py = label_pos.y() - off_y
        orig_h, orig_w = self._raw_data.shape[:2]
        scale_x = orig_w / max(1, pm.width())
        scale_y = orig_h / max(1, pm.height())
        ix = int(max(0, min(orig_w - 1, px * scale_x)))
        iy = int(max(0, min(orig_h - 1, py * scale_y)))
        return ix, iy

    def eventFilter(self, obj, event):
        from PyQt6.QtCore import QEvent
        if obj is self.image_label and self._crop_mode and self._raw_data is not None:
            t = event.type()
            if t == QEvent.Type.MouseButtonPress and event.button() == Qt.MouseButton.LeftButton:
                self._crop_start = event.pos()
                if self._rubber_band is None:
                    self._rubber_band = QRubberBand(QRubberBand.Shape.Rectangle, self.image_label)
                self._rubber_band.setGeometry(QRect(self._crop_start, self._crop_start))
                self._rubber_band.show()
                return True
            elif t == QEvent.Type.MouseMove and self._crop_start is not None:
                if self._rubber_band is not None:
                    self._rubber_band.setGeometry(QRect(self._crop_start, event.pos()).normalized())
                return True
            elif t == QEvent.Type.MouseButtonRelease and event.button() == Qt.MouseButton.LeftButton:
                if self._crop_start is not None:
                    rect = QRect(self._crop_start, event.pos()).normalized()
                    x1, y1 = self._screen_to_image(rect.topLeft())
                    x2, y2 = self._screen_to_image(rect.bottomRight())
                    w = max(0, x2 - x1)
                    h = max(0, y2 - y1)
                    if w >= 10 and h >= 10:
                        self.crop_selected.emit(x1, y1, w, h)
                    self._crop_start = None
                return True
        return super().eventFilter(obj, event)

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
        self.image_label.setText(self._empty_html)
        self.info_label.setText("")
