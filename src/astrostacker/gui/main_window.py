"""Main application window composing all GUI panels."""

from __future__ import annotations

import numpy as np
from PyQt6.QtCore import QThread, Qt
from PyQt6.QtGui import QBrush, QFont, QPalette, QPixmap
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QMainWindow,
    QMessageBox,
    QSplitter,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from astrostacker.config import APP_NAME, APP_VERSION
from astrostacker.gui.background import generate_background_pixmap
from astrostacker.gui.file_panel import FilePanel
from astrostacker.gui.news_ticker import NewsTicker
from astrostacker.gui.platesolve_panel import PlateSolvePanel
from astrostacker.gui.preview_panel import PreviewPanel
from astrostacker.gui.progress_panel import ProgressPanel
from astrostacker.gui.settings_panel import SettingsPanel
from astrostacker.pipeline.pipeline import PipelineConfig
from astrostacker.pipeline.worker import PipelineWorker, create_worker_thread

# macOS-native dark palette
MACOS_STYLESHEET = """
    /* ── Window ── */
    QMainWindow {
        background-color: transparent;
    }

    /* ── Base widget ── */
    QWidget {
        background-color: transparent;
        color: #e5e5e5;
        font-family: -apple-system, "SF Pro Text", "Helvetica Neue", sans-serif;
        font-size: 13px;
    }

    /* ── Sidebar (file panel) ── */
    QWidget#sidebar {
        background-color: rgba(20, 22, 30, 0.82);
        border-right: 1px solid rgba(255, 255, 255, 0.08);
    }

    /* ── Section headers ── */
    QLabel#sectionHeader {
        color: rgba(255, 255, 255, 0.55);
        font-size: 11px;
        font-weight: 600;
        letter-spacing: 0.5px;
        padding: 8px 0px 4px 2px;
    }

    /* ── File lists ── */
    QListWidget {
        background-color: rgba(255, 255, 255, 0.04);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 8px;
        padding: 2px;
        outline: none;
        font-size: 12px;
        color: #d1d1d1;
    }
    QListWidget::item {
        padding: 4px 8px;
        border-radius: 5px;
        margin: 1px 2px;
    }
    QListWidget::item:selected {
        background-color: rgba(0, 122, 255, 0.35);
        color: #ffffff;
    }
    QListWidget::item:hover:!selected {
        background-color: rgba(255, 255, 255, 0.06);
    }

    /* ── Buttons ── */
    QPushButton {
        background-color: #cc6600 !important;
        color: #ffffff !important;
        border: none;
        border-radius: 6px;
        padding: 5px 14px;
        font-size: 13px;
        font-weight: 600;
    }
    QPushButton:hover {
        background-color: #e87a00 !important;
    }
    QPushButton:pressed {
        background-color: #a85500 !important;
    }
    QPushButton:disabled {
        color: rgba(255, 255, 255, 0.35) !important;
        background-color: rgba(204, 102, 0, 0.3) !important;
    }

    /* ── Primary action button (Start Processing) ── */
    QPushButton#primaryButton {
        background-color: transparent !important;
        color: #ff9500 !important;
        border: 3px solid #ff9500 !important;
        border-radius: 10px;
        padding: 10px 28px;
        font-size: 15px;
        font-weight: 700;
    }
    QPushButton#primaryButton:hover {
        background-color: rgba(255, 149, 0, 0.15) !important;
        border-color: #ffb340 !important;
        color: #ffb340 !important;
    }
    QPushButton#primaryButton:pressed {
        background-color: rgba(255, 149, 0, 0.25) !important;
        border-color: #ff9500 !important;
    }

    /* ── Danger button (Cancel) ── */
    QPushButton#dangerButton {
        background-color: #cc2200 !important;
        color: #ffffff !important;
        border: none;
        border-radius: 8px;
        padding: 10px 28px;
        font-size: 14px;
        font-weight: 600;
    }
    QPushButton#dangerButton:hover {
        background-color: #ff6961;
    }
    QPushButton#dangerButton:pressed {
        background-color: #cc362e;
    }

    /* ── Combo boxes ── */
    QComboBox {
        background-color: rgba(255, 255, 255, 0.08);
        color: #e5e5e5;
        border: 1px solid rgba(255, 255, 255, 0.12);
        border-radius: 6px;
        padding: 5px 10px;
        font-size: 13px;
        min-height: 22px;
    }
    QComboBox:hover {
        background-color: rgba(255, 255, 255, 0.12);
    }
    QComboBox::drop-down {
        border: none;
        width: 20px;
    }
    QComboBox::down-arrow {
        image: none;
        border-left: 4px solid transparent;
        border-right: 4px solid transparent;
        border-top: 5px solid rgba(255, 255, 255, 0.5);
        margin-right: 8px;
    }
    QComboBox QAbstractItemView {
        background-color: #2a2a2a;
        color: #e5e5e5;
        border: 1px solid rgba(255, 255, 255, 0.15);
        border-radius: 8px;
        padding: 4px;
        selection-background-color: rgba(0, 122, 255, 0.35);
    }

    /* ── Spin boxes ── */
    QDoubleSpinBox, QSpinBox {
        background-color: rgba(255, 255, 255, 0.08);
        color: #e5e5e5;
        border: 1px solid rgba(255, 255, 255, 0.12);
        border-radius: 6px;
        padding: 5px 8px;
        font-size: 13px;
        min-height: 22px;
    }
    QDoubleSpinBox:hover, QSpinBox:hover {
        background-color: rgba(255, 255, 255, 0.12);
    }
    QDoubleSpinBox::up-button, QSpinBox::up-button,
    QDoubleSpinBox::down-button, QSpinBox::down-button {
        border: none;
        width: 16px;
    }

    /* ── Line edits ── */
    QLineEdit {
        background-color: rgba(255, 255, 255, 0.08);
        color: #e5e5e5;
        border: 1px solid rgba(255, 255, 255, 0.12);
        border-radius: 6px;
        padding: 5px 10px;
        font-size: 13px;
        min-height: 22px;
        selection-background-color: rgba(0, 122, 255, 0.5);
    }
    QLineEdit:focus {
        border-color: #0a84ff;
    }

    /* ── Group boxes ── */
    QGroupBox {
        background-color: rgba(15, 15, 25, 0.55);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 10px;
        margin-top: 14px;
        padding: 20px 12px 12px 12px;
        font-weight: 600;
        color: rgba(255, 255, 255, 0.55);
        font-size: 11px;
    }
    QGroupBox::title {
        subcontrol-origin: margin;
        left: 14px;
        padding: 0 6px;
        color: rgba(255, 255, 255, 0.55);
    }

    /* ── Progress bar ── */
    QProgressBar {
        background-color: rgba(255, 255, 255, 0.06);
        border: none;
        border-radius: 4px;
        text-align: center;
        color: rgba(255, 255, 255, 0.7);
        font-size: 11px;
        max-height: 8px;
        min-height: 8px;
    }
    QProgressBar::chunk {
        background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
            stop:0 #0a84ff, stop:1 #5ac8fa);
        border-radius: 4px;
    }

    /* ── Text edit (log) ── */
    QTextEdit {
        background-color: rgba(0, 0, 0, 0.35);
        color: rgba(255, 255, 255, 0.7);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 8px;
        padding: 8px;
        font-family: "SF Mono", "Menlo", "Monaco", monospace;
        font-size: 11px;
        selection-background-color: rgba(0, 122, 255, 0.35);
    }

    /* ── Scroll bars ── */
    QScrollBar:vertical {
        background: transparent;
        width: 8px;
        margin: 4px 2px;
    }
    QScrollBar::handle:vertical {
        background: rgba(255, 255, 255, 0.15);
        border-radius: 4px;
        min-height: 30px;
    }
    QScrollBar::handle:vertical:hover {
        background: rgba(255, 255, 255, 0.25);
    }
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
        height: 0px;
    }
    QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
        background: transparent;
    }
    QScrollBar:horizontal {
        background: transparent;
        height: 8px;
        margin: 2px 4px;
    }
    QScrollBar::handle:horizontal {
        background: rgba(255, 255, 255, 0.15);
        border-radius: 4px;
        min-width: 30px;
    }
    QScrollBar::handle:horizontal:hover {
        background: rgba(255, 255, 255, 0.25);
    }
    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
        width: 0px;
    }

    /* ── Splitter ── */
    QSplitter::handle {
        background: rgba(255, 255, 255, 0.06);
    }
    QSplitter::handle:vertical {
        height: 1px;
    }
    QSplitter::handle:horizontal {
        width: 1px;
    }

    /* ── Scroll area ── */
    QScrollArea {
        border: none;
    }

    /* ── Form labels ── */
    QFormLayout QLabel {
        color: rgba(255, 255, 255, 0.7);
        font-size: 13px;
    }

    /* ── Tabs ── */
    QTabWidget::pane {
        border: none;
        background-color: transparent;
    }
    QTabBar {
        background-color: rgba(15, 15, 25, 0.85);
    }
    QTabBar::tab {
        background-color: transparent;
        color: rgba(255, 255, 255, 0.5);
        border: none;
        padding: 8px 20px;
        font-size: 13px;
        font-weight: 600;
        border-bottom: 2px solid transparent;
    }
    QTabBar::tab:selected {
        color: #ff9500;
        border-bottom: 2px solid #ff9500;
    }
    QTabBar::tab:hover:!selected {
        color: rgba(255, 255, 255, 0.7);
    }

    /* ── Tooltips ── */
    QToolTip {
        background-color: #3a3a3c;
        color: #e5e5e5;
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 6px;
        padding: 4px 8px;
        font-size: 12px;
    }
"""


class _StarfieldWidget(QWidget):
    """Central widget that paints a procedural starfield background."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._bg_pixmap: QPixmap | None = None

    def paintEvent(self, event):
        from PyQt6.QtGui import QPainter
        painter = QPainter(self)
        if self._bg_pixmap is None or self._bg_pixmap.size() != self.size():
            self._bg_pixmap = generate_background_pixmap(
                self.width(), self.height()
            )
        painter.drawPixmap(0, 0, self._bg_pixmap)
        painter.end()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._bg_pixmap = None  # regenerate on next paint
        self.update()


class MainWindow(QMainWindow):
    """Main application window."""

    def __init__(self):
        super().__init__()
        self._worker: PipelineWorker | None = None
        self._thread: QThread | None = None
        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self):
        self.setWindowTitle(f"{APP_NAME} v{APP_VERSION}")
        self.setMinimumSize(1280, 820)
        self.setStyleSheet(MACOS_STYLESHEET)

        # Use unified toolbar area for macOS look
        self.setUnifiedTitleAndToolBarOnMac(True)

        central = _StarfieldWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Main horizontal splitter: sidebar | content
        h_splitter = QSplitter(Qt.Orientation.Horizontal)
        h_splitter.setHandleWidth(1)
        h_splitter.setChildrenCollapsible(False)

        # Left: Tabbed sidebar (Stacking / Plate Solve)
        sidebar = QWidget()
        sidebar.setObjectName("sidebar")
        sidebar.setMinimumWidth(280)
        sidebar.setMaximumWidth(400)
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(0, 0, 0, 0)
        sidebar_layout.setSpacing(0)

        self.sidebar_tabs = QTabWidget()
        self.sidebar_tabs.setDocumentMode(True)

        self.file_panel = FilePanel()
        self.platesolve_panel = PlateSolvePanel()

        self.sidebar_tabs.addTab(self.file_panel, "Stacking")
        self.sidebar_tabs.addTab(self.platesolve_panel, "Plate Solve")

        sidebar_layout.addWidget(self.sidebar_tabs)
        h_splitter.addWidget(sidebar)

        # Right: Preview on top, settings + progress on bottom
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)

        v_splitter = QSplitter(Qt.Orientation.Vertical)
        v_splitter.setHandleWidth(1)
        v_splitter.setChildrenCollapsible(False)

        self.preview_panel = PreviewPanel()
        v_splitter.addWidget(self.preview_panel)

        # Bottom: settings and progress side by side
        bottom_widget = QWidget()
        bottom_widget.setObjectName("bottomPanel")
        bottom_widget.setStyleSheet(
            "QWidget#bottomPanel {"
            "  background-color: rgba(15, 15, 25, 0.75);"
            "  border-top: 1px solid rgba(255, 255, 255, 0.06);"
            "}"
        )
        bottom_layout = QHBoxLayout(bottom_widget)
        bottom_layout.setContentsMargins(12, 12, 12, 12)
        bottom_layout.setSpacing(16)

        self.settings_panel = SettingsPanel()
        self.settings_panel.setMinimumWidth(300)
        self.settings_panel.setMaximumWidth(380)
        bottom_layout.addWidget(self.settings_panel)

        self.progress_panel = ProgressPanel()
        bottom_layout.addWidget(self.progress_panel)

        v_splitter.addWidget(bottom_widget)
        v_splitter.setStretchFactor(0, 3)
        v_splitter.setStretchFactor(1, 1)

        right_layout.addWidget(v_splitter)
        h_splitter.addWidget(right_widget)
        h_splitter.setStretchFactor(0, 0)
        h_splitter.setStretchFactor(1, 1)

        main_layout.addWidget(h_splitter)

        # News ticker at the bottom
        self.news_ticker = NewsTicker()
        main_layout.addWidget(self.news_ticker)

    def _connect_signals(self):
        self.file_panel.file_selected.connect(self._on_file_selected)
        self.progress_panel.start_btn.clicked.connect(self._on_start_cancel)
        self.file_panel.lights.files_changed.connect(self._on_lights_changed)

    def _on_file_selected(self, path: str):
        self.preview_panel.show_file(path)
        self.platesolve_panel.set_image_path(path)

    def _on_lights_changed(self):
        count = self.file_panel.lights.count()
        self.settings_panel.set_max_reference(count)

    def _on_start_cancel(self):
        if self._worker is not None:
            self._worker.cancel()
            return

        light_paths = self.file_panel.get_light_paths()
        if not light_paths:
            QMessageBox.warning(
                self, "No Light Frames", "Please add at least one light frame."
            )
            return

        config = PipelineConfig(
            light_paths=light_paths,
            dark_paths=self.file_panel.get_dark_paths(),
            flat_paths=self.file_panel.get_flat_paths(),
            dark_flat_paths=self.file_panel.get_dark_flat_paths(),
            stacking_method=self.settings_panel.get_method(),
            sigma_low=self.settings_panel.get_sigma_low(),
            sigma_high=self.settings_panel.get_sigma_high(),
            camera_type=self.settings_panel.get_camera_type(),
            bayer_pattern=self.settings_panel.get_bayer_pattern(),
            output_path=self.settings_panel.get_output_path(),
            reference_frame=self.settings_panel.get_reference_frame(),
        )

        self.progress_panel.reset()
        self.progress_panel.set_running(True)
        self.progress_panel.log(f"Starting pipeline with {len(light_paths)} light frames...")

        self._thread, self._worker = create_worker_thread(config)
        self._worker.status_update.connect(self._on_status)
        self._worker.progress_update.connect(self._on_progress)
        self._worker.finished.connect(self._on_finished)
        self._worker.error.connect(self._on_error)
        self._thread.finished.connect(self._on_thread_done)

        self._thread.start()

    def _on_status(self, message: str):
        self.progress_panel.log(message)

    def _on_progress(self, current: int, total: int, stage: str):
        self.progress_panel.set_progress(current, total, stage)

    def _on_finished(self, result: np.ndarray):
        self.progress_panel.log("Stacking complete!")
        self.progress_panel.set_progress(100, 100, "Done")
        self.preview_panel.show_data(result, info="Stacked Result")

        # Auto-embed WCS astrometry if a plate solve has been done
        solve_result = self.platesolve_panel.get_last_result()
        if solve_result is not None:
            try:
                output_path = self.settings_panel.get_output_path()
                if output_path.lower().endswith((".fits", ".fit", ".fts")):
                    from astropy.io import fits as pyfits
                    wcs_dict = solve_result.fits_header_dict()
                    with pyfits.open(output_path, mode="update") as hdul:
                        for key, val in wcs_dict.items():
                            hdul[0].header[key] = val
                        hdul.flush()
                    self.progress_panel.log(
                        f"WCS astrometry embedded ({len(wcs_dict)} keywords)"
                    )
            except Exception as e:
                self.progress_panel.log(f"WCS embed warning: {e}")

    def _on_error(self, message: str):
        self.progress_panel.log(f"ERROR: {message}")
        QMessageBox.critical(self, "Pipeline Error", message)

    def _on_thread_done(self):
        self.progress_panel.set_running(False)
        self._worker = None
        self._thread = None
