"""Mosaic panel for stitching plate-solved panels into a wide-field image."""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from astrostacker.config import FILE_FILTER


class MosaicPanel(QWidget):
    """Panel for loading plate-solved panels and building mosaics."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(8)

        title = QLabel("Mosaic")
        title.setStyleSheet(
            "font-size: 18px; font-weight: 700; color: #ffffff;"
            "padding-bottom: 4px;"
        )
        layout.addWidget(title)

        info = QLabel(
            "Add plate-solved FITS panels to stitch into a mosaic.\n"
            "Each panel must have WCS astrometry (plate solve first)."
        )
        info.setWordWrap(True)
        info.setStyleSheet(
            "color: rgba(255, 255, 255, 0.5); font-size: 12px;"
            "padding-bottom: 4px;"
        )
        layout.addWidget(info)

        # Panel list
        header = QLabel("MOSAIC PANELS")
        header.setObjectName("sectionHeader")
        layout.addWidget(header)

        self.panel_list = QListWidget()
        self.panel_list.setMinimumHeight(120)
        layout.addWidget(self.panel_list)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(6)

        self.add_btn = QPushButton("Add Panels")
        self.add_btn.setFixedHeight(26)
        self.add_btn.clicked.connect(self._add_panels)
        btn_layout.addWidget(self.add_btn)

        self.remove_btn = QPushButton("Remove")
        self.remove_btn.setFixedHeight(26)
        self.remove_btn.clicked.connect(self._remove_selected)
        btn_layout.addWidget(self.remove_btn)

        self.clear_btn = QPushButton("Clear")
        self.clear_btn.setFixedHeight(26)
        self.clear_btn.clicked.connect(self._clear_all)
        btn_layout.addWidget(self.clear_btn)

        layout.addLayout(btn_layout)

        # Output path
        output_group = QGroupBox("Output")
        output_layout = QHBoxLayout(output_group)
        output_layout.setContentsMargins(12, 24, 12, 12)
        output_layout.setSpacing(8)

        self.output_path = QLineEdit("mosaic.fits")
        output_layout.addWidget(self.output_path)

        browse_btn = QPushButton("Browse...")
        browse_btn.setFixedWidth(80)
        browse_btn.clicked.connect(self._browse_output)
        output_layout.addWidget(browse_btn)

        layout.addWidget(output_group)

        # Build button
        self.build_btn = QPushButton("Build Mosaic")
        self.build_btn.setFixedHeight(40)
        self.build_btn.setStyleSheet(
            "QPushButton {"
            "  background-color: transparent !important;"
            "  color: #ff9500 !important;"
            "  border: 3px solid #ff9500 !important;"
            "  border-radius: 10px;"
            "  font-size: 15px;"
            "  font-weight: 700;"
            "}"
            "QPushButton:hover {"
            "  background-color: rgba(255, 149, 0, 0.15) !important;"
            "}"
        )
        layout.addWidget(self.build_btn)

        # Log
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setPlaceholderText("Mosaic output will appear here...")
        self.log_text.setStyleSheet("font-size: 13px;")
        layout.addWidget(self.log_text, stretch=1)

        layout.addStretch()

    def _add_panels(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Add Mosaic Panels", "",
            "FITS Files (*.fits *.fit *.fts);;All Files (*)"
        )
        if paths:
            for path in paths:
                item = QListWidgetItem(Path(path).name)
                item.setData(Qt.ItemDataRole.UserRole, path)
                item.setToolTip(path)
                self.panel_list.addItem(item)

    def _remove_selected(self):
        for item in self.panel_list.selectedItems():
            self.panel_list.takeItem(self.panel_list.row(item))

    def _clear_all(self):
        self.panel_list.clear()

    def _browse_output(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Mosaic", self.output_path.text(),
            "FITS Files (*.fits)"
        )
        if path:
            self.output_path.setText(path)

    def get_panel_paths(self) -> list[str]:
        paths = []
        for i in range(self.panel_list.count()):
            item = self.panel_list.item(i)
            path = item.data(Qt.ItemDataRole.UserRole)
            if path:
                paths.append(path)
        return paths

    def get_output_path(self) -> str:
        return self.output_path.text()

    def log(self, message: str):
        self.log_text.append(message)
        scrollbar = self.log_text.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
