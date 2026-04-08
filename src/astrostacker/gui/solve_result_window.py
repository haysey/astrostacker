"""Solution window showing the plate solve result with annotated objects."""

from __future__ import annotations

import numpy as np
from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QBrush, QColor, QFont, QPainter, QPen, QPixmap
from PyQt6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSplitter,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from astrostacker.io.loader import load_image
from astrostacker.platesolve.solver import SOLVE_IMAGE_SCALE, Annotation, SolveResult
from astrostacker.utils.image_utils import numpy_to_qpixmap
from astrostacker.utils.stretch import auto_stretch


# Annotation scale factor - 1.2 = 20% larger than raw pixel values
ANNOTATION_SCALE = 1.2

# Use the same scale factor that was applied before solving,
# so annotation coordinates from astrometry.net align with the display image.
IMAGE_SCALE = SOLVE_IMAGE_SCALE

# Colors for different annotation types
ANNOTATION_COLORS = {
    "ic": QColor(255, 120, 50),       # Orange - IC objects
    "ngc": QColor(50, 200, 255),      # Cyan - NGC objects
    "hd": QColor(255, 255, 100),      # Yellow - HD stars
    "bright_star": QColor(255, 255, 200),  # Warm white - bright stars
    "messier": QColor(100, 255, 100),  # Green - Messier objects
    "other": QColor(200, 150, 255),    # Purple - other
}


def _get_annotation_color(ann: Annotation) -> QColor:
    """Pick a color based on the annotation type or name."""
    name_lower = ann.name.lower()
    if name_lower.startswith("m ") or name_lower.startswith("m") and name_lower[1:].strip().isdigit():
        return ANNOTATION_COLORS["messier"]
    ann_type = ann.ann_type.lower()
    return ANNOTATION_COLORS.get(ann_type, ANNOTATION_COLORS["other"])


def create_annotated_pixmap(
    image_data: np.ndarray,
    annotations: list[Annotation],
) -> QPixmap:
    """Render the image with annotation circles and labels drawn on top.

    The image is scaled up by IMAGE_SCALE (20%) to match the stretched image
    that was sent to Astrometry.net. Annotation coordinates from the solver
    are already in the stretched coordinate space, so no further scaling is
    needed for positions.
    """
    stretched = auto_stretch(image_data)
    base_pixmap = numpy_to_qpixmap(stretched)

    # Scale up to match the 20% stretch applied before solving
    new_w = int(base_pixmap.width() * IMAGE_SCALE)
    new_h = int(base_pixmap.height() * IMAGE_SCALE)
    pixmap = base_pixmap.scaled(
        new_w, new_h,
        Qt.AspectRatioMode.KeepAspectRatio,
        Qt.TransformationMode.SmoothTransformation,
    )

    if not annotations:
        return pixmap

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

    # 20% larger font
    label_font = QFont("Helvetica Neue", int(13 * ANNOTATION_SCALE), QFont.Weight.Bold)
    painter.setFont(label_font)

    for ann in annotations:
        color = _get_annotation_color(ann)

        # Circle - coordinates already in stretched space from astrometry
        pen = QPen(color, 2.5 * ANNOTATION_SCALE)
        painter.setPen(pen)
        painter.setBrush(QBrush(Qt.BrushStyle.NoBrush))

        radius = max(ann.radius, 18) * ANNOTATION_SCALE
        cx, cy = ann.pixel_x, ann.pixel_y
        painter.drawEllipse(QPointF(cx, cy), radius, radius)

        # Label background
        label_text = ann.name
        fm = painter.fontMetrics()
        text_rect = fm.boundingRect(label_text)
        text_w = text_rect.width() + 14
        text_h = text_rect.height() + 6

        label_x = cx + radius + 8
        label_y = cy - text_h / 2

        bg_color = QColor(0, 0, 0, 180)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(bg_color))
        painter.drawRoundedRect(
            QRectF(label_x - 3, label_y, text_w, text_h), 5, 5
        )

        # Label text
        painter.setPen(QPen(color))
        painter.drawText(
            QRectF(label_x + 4, label_y, text_w, text_h),
            Qt.AlignmentFlag.AlignVCenter,
            label_text,
        )

    painter.end()
    return pixmap


class SolveResultWindow(QWidget):
    """Popup window showing the annotated plate solve result."""

    ZOOM_LEVELS = [
        ("Fit", 0),
        ("25%", 0.25),
        ("50%", 0.5),
        ("75%", 0.75),
        ("100%", 1.0),
        ("150%", 1.5),
        ("200%", 2.0),
        ("300%", 3.0),
    ]

    def __init__(
        self,
        result: SolveResult,
        image_path: str,
        parent=None,
    ):
        super().__init__(parent, Qt.WindowType.Window)
        self.result = result
        self.image_path = image_path
        self._pixmap: QPixmap | None = None
        self._current_zoom = 0  # 0 = Fit
        self._setup_ui()
        self._load_and_annotate()

    def _setup_ui(self):
        self.setWindowTitle(f"Plate Solve Result - {self.result.ra_hms}  {self.result.dec_dms}")
        self.setMinimumSize(1100, 750)
        self.setStyleSheet("""
            QWidget {
                background-color: #1e1e1e;
                color: #e5e5e5;
                font-family: -apple-system, "SF Pro Text", "Helvetica Neue", sans-serif;
            }
            QListWidget {
                background-color: rgba(255, 255, 255, 0.04);
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 8px;
                padding: 4px;
                font-size: 12px;
            }
            QListWidget::item {
                padding: 5px 8px;
                border-radius: 4px;
                margin: 1px 2px;
            }
            QListWidget::item:selected {
                background-color: rgba(0, 122, 255, 0.3);
            }
            QTextEdit {
                background-color: rgba(0, 0, 0, 0.25);
                border: 1px solid rgba(255, 255, 255, 0.06);
                border-radius: 8px;
                padding: 8px;
                font-family: "SF Mono", "Menlo", monospace;
                font-size: 12px;
                color: rgba(255, 255, 255, 0.8);
            }
            QScrollArea {
                border: none;
                background-color: #0d0d0d;
            }
            QPushButton {
                background-color: rgba(255, 255, 255, 0.08);
                color: #e5e5e5;
                border: 1px solid rgba(255, 255, 255, 0.12);
                border-radius: 6px;
                padding: 4px 12px;
                font-size: 13px;
                font-weight: 600;
                min-height: 26px;
            }
            QPushButton:hover {
                background-color: rgba(255, 255, 255, 0.14);
            }
            QPushButton:pressed {
                background-color: rgba(255, 255, 255, 0.06);
            }
            QComboBox {
                background-color: rgba(255, 255, 255, 0.08);
                color: #e5e5e5;
                border: 1px solid rgba(255, 255, 255, 0.12);
                border-radius: 6px;
                padding: 4px 10px;
                font-size: 13px;
                min-height: 26px;
            }
            QComboBox QAbstractItemView {
                background-color: #2a2a2a;
                color: #e5e5e5;
                border: 1px solid rgba(255, 255, 255, 0.15);
                selection-background-color: rgba(0, 122, 255, 0.35);
            }
            QComboBox::drop-down { border: none; width: 20px; }
            QComboBox::down-arrow {
                image: none;
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-top: 5px solid rgba(255, 255, 255, 0.5);
                margin-right: 8px;
            }
            QScrollBar:vertical {
                background: transparent; width: 8px;
            }
            QScrollBar::handle:vertical {
                background: rgba(255, 255, 255, 0.15);
                border-radius: 4px; min-height: 30px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }
            QScrollBar:horizontal {
                background: transparent; height: 8px;
            }
            QScrollBar::handle:horizontal {
                background: rgba(255, 255, 255, 0.15);
                border-radius: 4px;
            }
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0px; }
            QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal { background: transparent; }
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        # ── Left: Image with zoom toolbar ──
        image_widget = QWidget()
        image_layout = QVBoxLayout(image_widget)
        image_layout.setContentsMargins(8, 8, 4, 8)
        image_layout.setSpacing(6)

        # Zoom toolbar
        zoom_bar = QHBoxLayout()
        zoom_bar.setSpacing(8)

        zoom_label = QLabel("Zoom")
        zoom_label.setStyleSheet("color: rgba(255,255,255,0.5); font-size: 12px;")
        zoom_bar.addWidget(zoom_label)

        self.zoom_out_btn = QPushButton("-")
        self.zoom_out_btn.setFixedWidth(32)
        self.zoom_out_btn.clicked.connect(self._zoom_out)
        zoom_bar.addWidget(self.zoom_out_btn)

        self.zoom_combo = QComboBox()
        for label, _ in self.ZOOM_LEVELS:
            self.zoom_combo.addItem(label)
        self.zoom_combo.setCurrentIndex(0)
        self.zoom_combo.setFixedWidth(90)
        self.zoom_combo.currentIndexChanged.connect(self._on_zoom_changed)
        zoom_bar.addWidget(self.zoom_combo)

        self.zoom_in_btn = QPushButton("+")
        self.zoom_in_btn.setFixedWidth(32)
        self.zoom_in_btn.clicked.connect(self._zoom_in)
        zoom_bar.addWidget(self.zoom_in_btn)

        self.save_btn = QPushButton("Save Image...")
        self.save_btn.setFixedWidth(110)
        self.save_btn.clicked.connect(self._save_image)
        zoom_bar.addWidget(self.save_btn)

        zoom_bar.addStretch()

        self.zoom_info = QLabel("")
        self.zoom_info.setStyleSheet(
            "color: rgba(255,255,255,0.35); font-size: 11px;"
            "font-family: 'SF Mono', 'Menlo', monospace;"
        )
        zoom_bar.addWidget(self.zoom_info)

        image_layout.addLayout(zoom_bar)

        # Scrollable image
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(False)
        self.scroll_area.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.image_label = QLabel("Loading image...")
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setStyleSheet("color: rgba(255,255,255,0.3);")
        self.scroll_area.setWidget(self.image_label)

        image_layout.addWidget(self.scroll_area)
        splitter.addWidget(image_widget)

        # ── Right: Info panel ──
        info_widget = QWidget()
        info_widget.setMinimumWidth(280)
        info_widget.setMaximumWidth(360)
        info_widget.setStyleSheet(
            "background-color: rgba(30, 30, 30, 0.95);"
            "border-left: 1px solid rgba(255, 255, 255, 0.06);"
        )
        info_layout = QVBoxLayout(info_widget)
        info_layout.setContentsMargins(14, 14, 14, 14)
        info_layout.setSpacing(12)

        # Solve data
        solve_title = QLabel("SOLUTION")
        solve_title.setStyleSheet(
            "color: rgba(255,255,255,0.5); font-size: 11px; font-weight: 600;"
        )
        info_layout.addWidget(solve_title)

        self.solve_info = QTextEdit()
        self.solve_info.setReadOnly(True)
        self.solve_info.setMaximumHeight(160)
        self.solve_info.setText(self.result.summary())
        info_layout.addWidget(self.solve_info)

        # Object list
        objects_title = QLabel(
            f"OBJECTS IN FIELD  ({len(self.result.annotations)})"
        )
        objects_title.setStyleSheet(
            "color: rgba(255,255,255,0.5); font-size: 11px; font-weight: 600;"
        )
        info_layout.addWidget(objects_title)

        self.object_list = QListWidget()
        for ann in self.result.annotations:
            color = _get_annotation_color(ann)
            item = QListWidgetItem(f"{ann.name}")
            item.setForeground(QBrush(color))
            item.setData(Qt.ItemDataRole.UserRole, ann)
            self.object_list.addItem(item)
        self.object_list.itemClicked.connect(self._on_object_clicked)
        info_layout.addWidget(self.object_list)

        # Legend
        legend_title = QLabel("LEGEND")
        legend_title.setStyleSheet(
            "color: rgba(255,255,255,0.5); font-size: 11px; font-weight: 600;"
        )
        info_layout.addWidget(legend_title)

        legend_items = [
            ("Messier", ANNOTATION_COLORS["messier"]),
            ("NGC", ANNOTATION_COLORS["ngc"]),
            ("IC", ANNOTATION_COLORS["ic"]),
            ("HD Stars", ANNOTATION_COLORS["hd"]),
            ("Bright Stars", ANNOTATION_COLORS["bright_star"]),
            ("Other", ANNOTATION_COLORS["other"]),
        ]
        for name, color in legend_items:
            lbl = QLabel(f"  {name}")
            lbl.setStyleSheet(
                f"color: {color.name()}; font-size: 12px; padding: 1px 0;"
            )
            info_layout.addWidget(lbl)

        info_layout.addStretch()
        splitter.addWidget(info_widget)

        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 0)

        layout.addWidget(splitter)

    # ── Image loading ──

    def _load_and_annotate(self):
        """Load the image and draw annotations."""
        try:
            image_data = load_image(self.image_path)
            self._pixmap = create_annotated_pixmap(
                image_data, self.result.annotations
            )
            if self._pixmap:
                w, h = self._pixmap.width(), self._pixmap.height()
                self.zoom_info.setText(f"{w} x {h} px")
            self._apply_zoom()
        except Exception as e:
            self.image_label.setText(f"Error loading image:\n{e}")

    # ── Save ──

    def _save_image(self):
        """Save the annotated solve result image to a user-chosen location."""
        if self._pixmap is None:
            return

        path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Annotated Image",
            "",
            "PNG Image (*.png);;JPEG Image (*.jpg);;TIFF Image (*.tiff)",
        )
        if not path:
            return

        try:
            self._pixmap.save(path)
            QMessageBox.information(self, "Saved", f"Image saved to:\n{path}")
        except Exception as e:
            QMessageBox.critical(self, "Save Error", str(e))

    # ── Zoom controls ──

    def _zoom_in(self):
        """Step to the next higher zoom level."""
        idx = self.zoom_combo.currentIndex()
        if idx < self.zoom_combo.count() - 1:
            self.zoom_combo.setCurrentIndex(idx + 1)

    def _zoom_out(self):
        """Step to the next lower zoom level."""
        idx = self.zoom_combo.currentIndex()
        if idx > 0:
            self.zoom_combo.setCurrentIndex(idx - 1)

    def _on_zoom_changed(self, index: int):
        """Handle zoom combo box change."""
        self._current_zoom = index
        self._apply_zoom()

    def _apply_zoom(self):
        """Apply the current zoom level to the image."""
        if self._pixmap is None:
            return

        _, zoom_factor = self.ZOOM_LEVELS[self._current_zoom]

        if zoom_factor == 0:
            # Fit mode
            available = self.scroll_area.size()
            scaled = self._pixmap.scaled(
                available,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        else:
            new_w = int(self._pixmap.width() * zoom_factor)
            new_h = int(self._pixmap.height() * zoom_factor)
            scaled = self._pixmap.scaled(
                new_w, new_h,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )

        self.image_label.setPixmap(scaled)
        self.image_label.resize(scaled.size())

    def _on_object_clicked(self, item: QListWidgetItem):
        """Click an object in the list to zoom in and center on it."""
        ann = item.data(Qt.ItemDataRole.UserRole)
        if ann and self._pixmap:
            # Switch to 100% zoom to see detail
            idx_100 = next(
                (i for i, (_, z) in enumerate(self.ZOOM_LEVELS) if z == 1.0), 4
            )
            self.zoom_combo.setCurrentIndex(idx_100)

            # Scroll to center the object (coordinates already in stretched space)
            sx = max(0, int(ann.pixel_x) - self.scroll_area.width() // 2)
            sy = max(0, int(ann.pixel_y) - self.scroll_area.height() // 2)
            self.scroll_area.horizontalScrollBar().setValue(sx)
            self.scroll_area.verticalScrollBar().setValue(sy)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self._current_zoom == 0:  # Only re-fit in Fit mode
            self._apply_zoom()
