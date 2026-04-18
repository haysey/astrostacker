"""Main application window composing all GUI panels."""

from __future__ import annotations

import numpy as np
import json
from pathlib import Path

from PyQt6.QtCore import QSettings, QThread, QTimer, Qt
from PyQt6.QtGui import QAction, QBrush, QFont, QPalette, QPixmap
from PyQt6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QMainWindow,
    QMenuBar,
    QMessageBox,
    QSplitter,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from astrostacker.config import APP_NAME, APP_CODENAME, APP_VERSION
from astrostacker.gui.about_dialog import AboutDialog
from astrostacker.gui.wizard import SetupWizard, should_show_wizard
from astrostacker.gui.background import generate_background_pixmap
from astrostacker.gui.blink_dialog import BlinkDialog
from astrostacker.gui.file_panel import FilePanel
from astrostacker.gui.fits_header_dialog import FitsHeaderDialog, read_fits_header
from astrostacker.gui.frame_status_bar import FrameStatusBar
from astrostacker.gui.histogram_panel import HistogramPanel
from astrostacker.gui.mosaic_panel import MosaicPanel
from astrostacker.gui.platesolve_panel import PlateSolvePanel
from astrostacker.mosaic.worker import MosaicWorker, create_mosaic_thread
from astrostacker.gui.preview_panel import PreviewPanel
from astrostacker.gui.progress_panel import ProgressPanel
from astrostacker.gui.settings_panel import SettingsPanel
from astrostacker.pipeline.pipeline import PipelineConfig
from astrostacker.pipeline.worker import PipelineWorker, create_worker_thread
from astrostacker.platesolve.solver import SolveResult
from astrostacker.platesolve.worker import SolveWorker, create_solve_thread
from astrostacker.utils.sounds import play_error, play_success

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
        background-color: rgba(255, 149, 0, 0.30);
        color: #ffffff;
    }
    QListWidget::item:hover:!selected {
        background-color: rgba(255, 255, 255, 0.06);
    }

    /* ── Buttons (default = primary-filled orange) ── */
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
        padding-top: 6px;
        padding-bottom: 4px;
    }
    QPushButton:disabled {
        color: rgba(255, 255, 255, 0.35) !important;
        background-color: rgba(204, 102, 0, 0.3) !important;
    }

    /* ── Secondary button (muted, for Add/Remove/Browse/etc) ── */
    QPushButton#secondaryButton {
        background-color: rgba(255, 255, 255, 0.06) !important;
        color: #e5e5e5 !important;
        border: 1px solid rgba(255, 255, 255, 0.15) !important;
        border-radius: 6px;
        padding: 5px 14px;
        font-size: 13px;
        font-weight: 500;
    }
    QPushButton#secondaryButton:hover {
        background-color: rgba(255, 149, 0, 0.12) !important;
        border-color: rgba(255, 149, 0, 0.5) !important;
        color: #ffb340 !important;
    }
    QPushButton#secondaryButton:pressed {
        background-color: rgba(255, 149, 0, 0.20) !important;
        padding-top: 6px;
        padding-bottom: 4px;
    }
    QPushButton#secondaryButton:disabled {
        color: rgba(255, 255, 255, 0.25) !important;
        border-color: rgba(255, 255, 255, 0.08) !important;
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
        padding-top: 11px;
        padding-bottom: 9px;
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
        border-radius: 8px;
        padding: 5px 10px;
        font-size: 13px;
        min-height: 26px;
    }
    QComboBox:hover {
        background-color: rgba(255, 255, 255, 0.12);
        border-color: rgba(255, 255, 255, 0.20);
    }
    QComboBox:focus {
        border: 1px solid #ff9500;
        background-color: rgba(255, 149, 0, 0.06);
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
        selection-background-color: rgba(255, 149, 0, 0.35);
    }

    /* ── Spin boxes ── */
    QDoubleSpinBox, QSpinBox {
        background-color: rgba(255, 255, 255, 0.08);
        color: #e5e5e5;
        border: 1px solid rgba(255, 255, 255, 0.12);
        border-radius: 8px;
        padding: 5px 8px;
        font-size: 13px;
        min-height: 26px;
    }
    QDoubleSpinBox:hover, QSpinBox:hover {
        background-color: rgba(255, 255, 255, 0.12);
        border-color: rgba(255, 255, 255, 0.20);
    }
    QDoubleSpinBox:focus, QSpinBox:focus {
        border: 1px solid #ff9500;
        background-color: rgba(255, 149, 0, 0.06);
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
        border-radius: 8px;
        padding: 5px 10px;
        font-size: 13px;
        min-height: 22px;
        selection-background-color: rgba(255, 149, 0, 0.5);
    }
    QLineEdit:hover {
        border-color: rgba(255, 255, 255, 0.20);
    }
    QLineEdit:focus {
        border: 1px solid #ff9500;
        background-color: rgba(255, 149, 0, 0.06);
    }

    /* ── Group boxes (card-style) ── */
    QGroupBox {
        background-color: rgba(22, 24, 34, 0.70);
        border: 1px solid rgba(255, 255, 255, 0.10);
        border-top: 1px solid rgba(255, 255, 255, 0.15);
        border-radius: 10px;
        margin-top: 18px;
        padding: 28px 14px 14px 14px;
        font-weight: 700;
        color: rgba(255, 255, 255, 0.70);
        font-size: 11px;
    }
    QGroupBox::title {
        subcontrol-origin: margin;
        subcontrol-position: top left;
        left: 14px;
        top: 4px;
        padding: 0 8px;
        color: #ff9500;
        letter-spacing: 0.5px;
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
            stop:0 #cc6600, stop:1 #ff9500);
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
        selection-background-color: rgba(255, 149, 0, 0.35);
    }
    QTextEdit:focus {
        border-color: rgba(255, 149, 0, 0.5);
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
        min-height: 26px;
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
        padding: 10px 22px 8px 22px;
        font-size: 13px;
        font-weight: 600;
        border-bottom: 3px solid transparent;
    }
    QTabBar::tab:selected {
        color: #ff9500;
        border-bottom: 3px solid #ff9500;
        font-weight: 700;
    }
    QTabBar::tab:hover:!selected {
        color: rgba(255, 255, 255, 0.8);
        border-bottom: 3px solid rgba(255, 149, 0, 0.25);
    }

    /* ── Checkboxes ── */
    QCheckBox {
        spacing: 8px;
        min-height: 28px;
    }
    QCheckBox::indicator {
        width: 18px;
        height: 18px;
    }

    /* ── Menus (Add button dropdown, etc) ── */
    QMenu {
        background-color: #2a2a2e;
        color: #e5e5e5;
        border: 1px solid rgba(255, 255, 255, 0.15);
        border-radius: 8px;
        padding: 4px;
        font-size: 13px;
    }
    QMenu::item {
        padding: 6px 16px 6px 10px;
        border-radius: 5px;
    }
    QMenu::item:selected {
        background-color: rgba(255, 149, 0, 0.30);
        color: #ffffff;
    }
    QMenu::icon {
        padding-left: 6px;
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
        self._solve_worker: SolveWorker | None = None
        self._solve_thread: QThread | None = None
        self._mosaic_worker: MosaicWorker | None = None
        self._mosaic_thread: QThread | None = None
        self._last_aligned_frames: list | None = None
        self._setup_ui()
        self._setup_menu_bar()
        self._connect_signals()
        self._size_to_screen()
        # Show the first-run wizard after the window is ready
        if should_show_wizard():
            QTimer.singleShot(200, self._run_wizard)

    def _size_to_screen(self):
        """Open maximized to fill the screen."""
        self.showMaximized()

    def _setup_ui(self):
        self.setWindowTitle(f"{APP_NAME} v{APP_VERSION} — {APP_CODENAME}")
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
        self.mosaic_panel = MosaicPanel()

        self.sidebar_tabs.addTab(self.file_panel, "Stacking")
        self.sidebar_tabs.addTab(self.platesolve_panel, "Plate Solve")
        self.sidebar_tabs.addTab(self.mosaic_panel, "Mosaic")

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

        # Preview + histogram side by side
        preview_area = QWidget()
        preview_layout = QHBoxLayout(preview_area)
        preview_layout.setContentsMargins(0, 0, 0, 0)
        preview_layout.setSpacing(0)

        self.preview_panel = PreviewPanel()
        preview_layout.addWidget(self.preview_panel, stretch=1)

        self.histogram_panel = HistogramPanel()
        self.histogram_panel.setMaximumWidth(280)
        self.histogram_panel.setMinimumWidth(200)
        preview_layout.addWidget(self.histogram_panel)

        v_splitter.addWidget(preview_area)

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
        bottom_layout.addWidget(self.settings_panel, stretch=2)

        self.progress_panel = ProgressPanel()
        bottom_layout.addWidget(self.progress_panel, stretch=3)

        v_splitter.addWidget(bottom_widget)
        # Give more room to Settings/Progress so all options are visible
        # on startup without scrolling. Preview expands when an image loads.
        v_splitter.setStretchFactor(0, 2)
        v_splitter.setStretchFactor(1, 3)

        right_layout.addWidget(v_splitter)
        h_splitter.addWidget(right_widget)
        h_splitter.setStretchFactor(0, 0)
        h_splitter.setStretchFactor(1, 1)

        main_layout.addWidget(h_splitter)

        # Frame status bar at the bottom
        self.frame_status_bar = FrameStatusBar()
        self.frame_status_bar.set_version(f"{APP_VERSION} — {APP_CODENAME}")
        main_layout.addWidget(self.frame_status_bar)

    def _setup_menu_bar(self):
        menu_bar = self.menuBar()

        # File menu
        file_menu = menu_bar.addMenu("File")

        save_session_action = QAction("Save Session...", self)
        save_session_action.triggered.connect(self._save_session)
        file_menu.addAction(save_session_action)

        load_session_action = QAction("Load Session...", self)
        load_session_action.triggered.connect(self._load_session)
        file_menu.addAction(load_session_action)

        file_menu.addSeparator()

        export_tiff = QAction("Export as TIFF...", self)
        export_tiff.triggered.connect(lambda: self._export_image("tiff"))
        file_menu.addAction(export_tiff)

        export_png = QAction("Export as PNG...", self)
        export_png.triggered.connect(lambda: self._export_image("png"))
        file_menu.addAction(export_png)

        # Tools menu
        tools_menu = menu_bar.addMenu("Tools")

        blink_action = QAction("Blink Comparator...", self)
        blink_action.triggered.connect(self._open_blink)
        tools_menu.addAction(blink_action)

        header_action = QAction("View FITS Header...", self)
        header_action.triggered.connect(self._view_fits_header)
        tools_menu.addAction(header_action)

        tools_menu.addSeparator()

        # Setup Wizard — NoRole prevents macOS from auto-promoting it
        # out of the menu into the application menu as "Preferences"
        wizard_action = QAction("Setup Wizard...", self)
        wizard_action.setMenuRole(QAction.MenuRole.NoRole)
        wizard_action.triggered.connect(self._run_wizard)
        tools_menu.addAction(wizard_action)

        tools_menu.addSeparator()

        about_action = QAction(f"About {APP_NAME}...", self)
        about_action.setMenuRole(QAction.MenuRole.NoRole)
        about_action.triggered.connect(self._show_about)
        tools_menu.addAction(about_action)

    def _connect_signals(self):
        self.file_panel.file_selected.connect(self._on_file_selected)
        self.progress_panel.start_btn.clicked.connect(self._on_start_cancel)
        self.file_panel.lights.files_changed.connect(self._on_lights_changed)
        self.mosaic_panel.build_btn.clicked.connect(self._on_build_mosaic)
        self.settings_panel.auto_solve_check.toggled.connect(self._on_auto_solve_toggled)

    def _on_file_selected(self, path: str):
        self.preview_panel.show_file(path)
        self.platesolve_panel.set_image_path(path)
        # Update histogram when a file is selected
        try:
            from astrostacker.io.loader import load_image
            data = load_image(path)
            self.histogram_panel.set_data(data)
        except Exception:
            pass

    def _on_lights_changed(self):
        count = self.file_panel.lights.count()
        self.settings_panel.set_max_reference(count)

    def _on_auto_solve_toggled(self, checked: bool):
        """Warn the user if they enable auto plate solve without scale hints set."""
        if not checked:
            return
        ps = self.platesolve_panel
        if ps.scale_lower_spin.value() == 0 or ps.scale_upper_spin.value() == 0:
            QMessageBox.information(
                self,
                "Set Your Equipment Details First",
                "Before using Auto Plate Solve, please go to the Plate Solve tab "
                "and enter your telescope focal length and camera pixel size, "
                "then click Calculate & Apply.\n\n"
                "Without these, plate solving can take 10+ minutes or fail entirely.\n\n"
                "You only need to do this once — the app remembers your setup."
            )

    def _on_start_cancel(self):
        if self._worker is not None:
            self._worker.cancel()
            return
        if self._solve_worker is not None:
            self._solve_worker.cancel()
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
            master_dark_path=self.file_panel.get_master_dark_path(),
            master_flat_path=self.file_panel.get_master_flat_path(),
            stacking_method=self.settings_panel.get_method(),
            sigma_low=self.settings_panel.get_sigma_low(),
            sigma_high=self.settings_panel.get_sigma_high(),
            percentile_low=self.settings_panel.get_percentile_low(),
            percentile_high=self.settings_panel.get_percentile_high(),
            camera_type=self.settings_panel.get_camera_type(),
            bayer_pattern=self.settings_panel.get_bayer_pattern(),
            output_path=self.settings_panel.get_output_path(),
            reference_frame=self.settings_panel.get_reference_frame(),
            auto_reject=self.settings_panel.get_auto_reject(),
            remove_gradient=self.settings_panel.get_remove_gradient(),
            local_normalise=self.settings_panel.get_local_normalise(),
            denoise=self.settings_panel.get_denoise(),
            denoise_strength=self.settings_panel.get_denoise_strength(),
            deconvolve=self.settings_panel.get_deconvolve(),
            deconv_strength=self.settings_panel.get_deconv_strength(),
            auto_crop=self.settings_panel.get_auto_crop(),
            drizzle=self.settings_panel.get_drizzle(),
        )

        self.progress_panel.reset()
        self.progress_panel.set_running(True)
        self.frame_status_bar.clear()
        self.frame_status_bar.set_status("Processing...")
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
        self.progress_panel.set_progress(100, 100, "Stacking done")
        self.preview_panel.show_data(result, info="Stacked Result")
        self.histogram_panel.set_data(result)

        # Update frame status bar with rejection info
        total = len(self.file_panel.get_light_paths())
        rejected = self._worker.pipeline.rejected_paths if self._worker else []
        accepted = self._worker.pipeline.accepted_count if self._worker else total
        self.frame_status_bar.set_status("Stacking complete")
        self.frame_status_bar.set_frame_counts(total, accepted, rejected)

        # Embed WCS from a previous plate solve if available
        self._embed_existing_wcs()

        # Auto plate solve if the user ticked the checkbox
        if self.settings_panel.get_auto_solve():
            self._start_auto_solve()
        else:
            play_success()

    def _embed_existing_wcs(self):
        """Embed WCS from a previous plate solve into the stacked FITS."""
        solve_result = self.platesolve_panel.get_last_result()
        if solve_result is not None:
            try:
                output_path = self.settings_panel.get_output_path()
                if output_path.lower().endswith((".fits", ".fit", ".fts")):
                    from astropy.io import fits as pyfits
                    with pyfits.open(output_path, mode="update") as hdul:
                        img_w = hdul[0].header.get("NAXIS1", 0)
                        img_h = hdul[0].header.get("NAXIS2", 0)
                        wcs_dict = solve_result.fits_header_dict(
                            image_width=img_w, image_height=img_h
                        )
                        for key, val in wcs_dict.items():
                            hdul[0].header[key] = val
                        hdul.flush()
                    self.progress_panel.log(
                        f"WCS astrometry embedded ({len(wcs_dict)} keywords)"
                    )
            except Exception as e:
                self.progress_panel.log(f"WCS embed warning: {e}")

    def _start_auto_solve(self):
        """Kick off an automatic plate solve of the stacked image."""
        output_path = self.settings_panel.get_output_path()
        api_key = self.platesolve_panel.api_key_input.text().strip()

        if not api_key:
            self.progress_panel.log(
                "Auto plate solve skipped — no API key set in Plate Solve tab. "
                "See README for info on how to get a free Astrometry API key."
            )
            play_success()
            return

        self.progress_panel.log("Starting auto plate solve...")

        # Get scale hints from the plate solve panel if set
        ps = self.platesolve_panel
        scale_lower = ps.scale_lower_spin.value() if ps.scale_lower_spin.value() > 0 else None
        scale_upper = ps.scale_upper_spin.value() if ps.scale_upper_spin.value() > 0 else None
        scale_units = ps.scale_units_combo.currentData()

        # Drizzle (2x) doubles the image resolution, halving the arcsec/pixel
        # scale. Adjust hints so nova.astrometry.net searches the right range.
        if self.settings_panel.get_drizzle() and scale_lower is not None and scale_upper is not None:
            scale_lower = round(scale_lower / 2.0, 3)
            scale_upper = round(scale_upper / 2.0, 3)
            self.progress_panel.log(
                f"Drizzle active — scale hints halved to "
                f"{scale_lower}–{scale_upper} arcsec/px for drizzled image."
            )

        self._solve_thread, self._solve_worker = create_solve_thread(
            image_path=output_path,
            api_key=api_key,
            scale_lower=scale_lower,
            scale_upper=scale_upper,
            scale_units=scale_units,
        )
        self._solve_worker.status_update.connect(self._on_status)
        self._solve_worker.finished.connect(self._on_auto_solve_finished)
        self._solve_worker.error.connect(self._on_auto_solve_error)
        self._solve_thread.finished.connect(self._on_auto_solve_thread_done)

        self._solve_thread.start()

    def _on_auto_solve_finished(self, result: SolveResult):
        self.progress_panel.log("Auto plate solve succeeded!")
        self.progress_panel.log(result.summary())

        # Store result in the plate solve panel for reuse
        self.platesolve_panel._last_result = result
        self.platesolve_panel.write_wcs_btn.setEnabled(True)

        # Embed WCS into the stacked FITS
        try:
            output_path = self.settings_panel.get_output_path()
            if output_path.lower().endswith((".fits", ".fit", ".fts")):
                from astropy.io import fits as pyfits
                with pyfits.open(output_path, mode="update") as hdul:
                    img_w = hdul[0].header.get("NAXIS1", 0)
                    img_h = hdul[0].header.get("NAXIS2", 0)
                    wcs_dict = result.fits_header_dict(
                        image_width=img_w, image_height=img_h
                    )
                    for key, val in wcs_dict.items():
                        hdul[0].header[key] = val
                    hdul.flush()
                self.progress_panel.log(
                    f"WCS astrometry embedded into {output_path}"
                )
        except Exception as e:
            self.progress_panel.log(f"WCS embed warning: {e}")

        play_success()

    def _on_auto_solve_error(self, message: str):
        self.progress_panel.log(f"Auto plate solve failed: {message}")
        play_error()

    def _on_auto_solve_thread_done(self):
        self._solve_worker = None
        self._solve_thread = None
        self.progress_panel.set_running(False)

    def _on_error(self, message: str):
        self.progress_panel.log(f"ERROR: {message}")
        self.frame_status_bar.set_status("Error")
        play_error()
        QMessageBox.critical(self, "Pipeline Error", message)

    def _on_thread_done(self):
        # Only reset running state if no auto-solve is pending
        if self._solve_thread is None or not self._solve_thread.isRunning():
            self.progress_panel.set_running(False)
        self._worker = None
        self._thread = None

    # ── Session save/load ──

    def _save_session(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Session", "", "Astrostacker Session (*.json)"
        )
        if not path:
            return

        session = {
            "light_paths": self.file_panel.get_light_paths(),
            "dark_paths": self.file_panel.get_dark_paths(),
            "flat_paths": self.file_panel.get_flat_paths(),
            "dark_flat_paths": self.file_panel.get_dark_flat_paths(),
            "master_dark_path": self.file_panel.get_master_dark_path(),
            "master_flat_path": self.file_panel.get_master_flat_path(),
            "stacking_method": self.settings_panel.get_method(),
            "sigma_low": self.settings_panel.get_sigma_low(),
            "sigma_high": self.settings_panel.get_sigma_high(),
            "percentile_low": self.settings_panel.get_percentile_low(),
            "percentile_high": self.settings_panel.get_percentile_high(),
            "camera_type": self.settings_panel.get_camera_type(),
            "bayer_pattern": self.settings_panel.get_bayer_pattern(),
            "output_path": self.settings_panel.get_output_path(),
            "reference_frame": self.settings_panel.get_reference_frame(),
            "auto_reject": self.settings_panel.get_auto_reject(),
            "remove_gradient": self.settings_panel.get_remove_gradient(),
            "local_normalise": self.settings_panel.get_local_normalise(),
            "denoise": self.settings_panel.get_denoise(),
            "denoise_strength": self.settings_panel.get_denoise_strength(),
            "deconvolve": self.settings_panel.get_deconvolve(),
            "deconv_strength": self.settings_panel.get_deconv_strength(),
            "auto_crop": self.settings_panel.get_auto_crop(),
            "drizzle": self.settings_panel.get_drizzle(),
            "auto_solve": self.settings_panel.get_auto_solve(),
        }

        try:
            with open(path, "w") as f:
                json.dump(session, f, indent=2)
            self.progress_panel.log(f"Session saved to {path}")
        except Exception as e:
            QMessageBox.critical(self, "Save Error", str(e))

    def _load_session(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Load Session", "", "Astrostacker Session (*.json)"
        )
        if not path:
            return

        try:
            with open(path) as f:
                session = json.load(f)
        except Exception as e:
            QMessageBox.critical(self, "Load Error", str(e))
            return

        # Populate file lists
        self._load_paths_into_list(
            self.file_panel.lights, session.get("light_paths", [])
        )
        self._load_paths_into_list(
            self.file_panel.darks, session.get("dark_paths", [])
        )
        self._load_paths_into_list(
            self.file_panel.flats, session.get("flat_paths", [])
        )
        self._load_paths_into_list(
            self.file_panel.dark_flats, session.get("dark_flat_paths", [])
        )

        # Master frames
        md = session.get("master_dark_path", "")
        if md:
            self.file_panel._master_dark_path = md
            self.file_panel._master_dark_label.setText(f"Dark: {Path(md).name}")
            self.file_panel._master_dark_btn.setText("Master Dark ✓")

        mf = session.get("master_flat_path", "")
        if mf:
            self.file_panel._master_flat_path = mf
            self.file_panel._master_flat_label.setText(f"Flat: {Path(mf).name}")
            self.file_panel._master_flat_btn.setText("Master Flat ✓")

        # Settings
        method = session.get("stacking_method", "sigma_clip")
        idx = self.settings_panel.method_combo.findData(method)
        if idx >= 0:
            self.settings_panel.method_combo.setCurrentIndex(idx)

        self.settings_panel.sigma_low_spin.setValue(session.get("sigma_low", 2.5))
        self.settings_panel.sigma_high_spin.setValue(session.get("sigma_high", 2.5))
        self.settings_panel.pct_low_spin.setValue(session.get("percentile_low", 10.0))
        self.settings_panel.pct_high_spin.setValue(session.get("percentile_high", 10.0))
        self.settings_panel.output_path.setText(session.get("output_path", "stacked.fits"))
        self.settings_panel.reference_spin.setValue(session.get("reference_frame", 0))

        cam = session.get("camera_type", "mono")
        idx = self.settings_panel.camera_combo.findData(cam)
        if idx >= 0:
            self.settings_panel.camera_combo.setCurrentIndex(idx)

        pat = session.get("bayer_pattern", "RGGB")
        idx = self.settings_panel.bayer_combo.findData(pat)
        if idx >= 0:
            self.settings_panel.bayer_combo.setCurrentIndex(idx)

        self.settings_panel.auto_reject_check.setChecked(session.get("auto_reject", False))
        self.settings_panel.gradient_check.setChecked(session.get("remove_gradient", False))
        self.settings_panel.local_norm_check.setChecked(session.get("local_normalise", False))
        self.settings_panel.denoise_check.setChecked(session.get("denoise", False))
        strength = session.get("denoise_strength", "medium")
        idx = self.settings_panel.denoise_strength_combo.findData(strength)
        if idx >= 0:
            self.settings_panel.denoise_strength_combo.setCurrentIndex(idx)
        self.settings_panel.deconv_check.setChecked(session.get("deconvolve", False))
        deconv_str = session.get("deconv_strength", "medium")
        idx = self.settings_panel.deconv_strength_combo.findData(deconv_str)
        if idx >= 0:
            self.settings_panel.deconv_strength_combo.setCurrentIndex(idx)
        self.settings_panel.auto_crop_check.setChecked(session.get("auto_crop", False))
        self.settings_panel.drizzle_check.setChecked(session.get("drizzle", False))
        self.settings_panel.auto_solve_check.setChecked(session.get("auto_solve", False))

        self.progress_panel.log(f"Session loaded from {path}")

    def _load_paths_into_list(self, group, paths: list[str]):
        """Populate a FrameListGroup from a list of file paths."""
        from PyQt6.QtWidgets import QListWidgetItem
        group.list_widget.clear()
        for p in paths:
            if Path(p).exists():
                item = QListWidgetItem(Path(p).name)
                item.setData(Qt.ItemDataRole.UserRole, p)
                item.setToolTip(p)
                group.list_widget.addItem(item)
        group._update_header()

    # ── Export ──

    def _export_image(self, fmt: str):
        """Export the current preview image as TIFF or PNG with auto-stretch."""
        raw = self.preview_panel._raw_data
        if raw is None:
            QMessageBox.information(self, "No Image", "No image to export. Run the pipeline first.")
            return

        if fmt == "tiff":
            filter_str = "TIFF Image (*.tiff *.tif)"
            default_ext = ".tiff"
        else:
            filter_str = "PNG Image (*.png)"
            default_ext = ".png"

        path, _ = QFileDialog.getSaveFileName(self, "Export Image", "", filter_str)
        if not path:
            return

        if not path.lower().endswith(default_ext) and "." not in Path(path).name:
            path += default_ext

        try:
            from astrostacker.utils.stretch import auto_stretch
            from astrostacker.utils.image_utils import numpy_to_qpixmap
            stretched = auto_stretch(raw)
            pixmap = numpy_to_qpixmap(stretched)
            pixmap.save(path)
            self.progress_panel.log(f"Exported {fmt.upper()} to {path}")
            QMessageBox.information(self, "Exported", f"Image exported to:\n{path}")
        except Exception as e:
            QMessageBox.critical(self, "Export Error", str(e))

    # ── Blink comparator ──

    def _open_blink(self):
        """Open the blink comparator with loaded light frames."""
        paths = self.file_panel.get_light_paths()
        if len(paths) < 2:
            QMessageBox.information(
                self, "Need Frames",
                "Add at least 2 light frames to use the Blink Comparator."
            )
            return

        self.progress_panel.log("Loading frames for blink comparator...")
        try:
            from astrostacker.io.loader import load_image
            frames = [load_image(p) for p in paths]
            dlg = BlinkDialog(frames, parent=self)
            dlg.exec()
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    # ── FITS header viewer ──

    def _run_wizard(self) -> None:
        """Launch the setup wizard (first-run or on-demand from Help menu)."""
        wiz = SetupWizard(self)
        if wiz.exec():
            # Apply camera type chosen in wizard to the settings panel
            cam = wiz.camera_type
            idx = self.settings_panel.camera_combo.findData(cam)
            if idx >= 0:
                self.settings_panel.camera_combo.setCurrentIndex(idx)
            # Reload plate solve settings in case wizard saved API key / FOV
            self.platesolve_panel._load_api_key()

    def _show_about(self):
        """Show the About dialog."""
        dlg = AboutDialog(self)
        dlg.exec()

    def _view_fits_header(self):
        """Show FITS header of the currently selected or output file."""
        # Try the plate solve panel path first, then the output path
        path = ""
        if hasattr(self.platesolve_panel, '_image_path'):
            path = self.platesolve_panel._image_path or ""
        if not path:
            path = self.settings_panel.get_output_path()
        if not path or not Path(path).exists():
            # Ask user to pick a file
            path, _ = QFileDialog.getOpenFileName(
                self, "Select FITS File", "",
                "FITS Files (*.fits *.fit *.fts);;All Files (*)"
            )
        if not path:
            return

        header_text = read_fits_header(path)
        dlg = FitsHeaderDialog(header_text, file_path=path, parent=self)
        dlg.exec()

    # ── Mosaic ──

    def _on_build_mosaic(self):
        """Start building a mosaic from plate-solved panels."""
        paths = self.mosaic_panel.get_panel_paths()
        if len(paths) < 2:
            QMessageBox.warning(
                self, "Need Panels",
                "Add at least 2 plate-solved FITS panels to build a mosaic."
            )
            return

        output_path = self.mosaic_panel.get_output_path()
        self.mosaic_panel.log_text.clear()
        self.mosaic_panel.log("Starting mosaic build...")
        self.mosaic_panel.build_btn.setEnabled(False)
        self.frame_status_bar.set_status("Building mosaic...")

        self._mosaic_thread, self._mosaic_worker = create_mosaic_thread(
            paths, output_path
        )
        self._mosaic_worker.status_update.connect(self.mosaic_panel.log)
        self._mosaic_worker.finished.connect(self._on_mosaic_finished)
        self._mosaic_worker.error.connect(self._on_mosaic_error)
        self._mosaic_thread.finished.connect(self._on_mosaic_thread_done)
        self._mosaic_thread.start()

    def _on_mosaic_finished(self, result):
        self.mosaic_panel.log("Mosaic complete!")
        self.preview_panel.show_data(result, info="Mosaic Result")
        self.histogram_panel.set_data(result)
        self.frame_status_bar.set_status("Mosaic complete")
        play_success()

    def _on_mosaic_error(self, message: str):
        self.mosaic_panel.log(f"ERROR: {message}")
        self.frame_status_bar.set_status("Mosaic failed")
        play_error()
        QMessageBox.critical(self, "Mosaic Error", message)

    def _on_mosaic_thread_done(self):
        self._mosaic_worker = None
        self._mosaic_thread = None
        self.mosaic_panel.build_btn.setEnabled(True)
