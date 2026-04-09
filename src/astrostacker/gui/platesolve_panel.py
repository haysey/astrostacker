"""Plate solving panel with Astrometry.net integration."""

from __future__ import annotations

from PyQt6.QtCore import QSettings, QThread, Qt
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from astrostacker.config import FILE_FILTER
from astrostacker.gui.solve_result_window import SolveResultWindow
from astrostacker.platesolve.solver import SolveResult
from astrostacker.platesolve.worker import SolveWorker, create_solve_thread

SETTINGS_ORG = "HayseysAstrostacker"
SETTINGS_APP = "HayseysAstrostacker"


class PlateSolvePanel(QWidget):
    """Panel for plate solving images via Astrometry.net."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._worker: SolveWorker | None = None
        self._thread: QThread | None = None
        self._current_path: str | None = None
        self._result_window: SolveResultWindow | None = None
        self._last_result: SolveResult | None = None
        self._setup_ui()
        self._load_api_key()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(8)

        # Title
        title = QLabel("Plate Solve")
        title.setStyleSheet(
            "font-size: 18px; font-weight: 700; color: #ffffff;"
            "padding-bottom: 4px;"
        )
        layout.addWidget(title)

        # API key
        api_group = QGroupBox("Astrometry.net")
        api_layout = QFormLayout(api_group)
        api_layout.setSpacing(10)
        api_layout.setContentsMargins(12, 20, 12, 12)

        self.api_key_input = QLineEdit()
        self.api_key_input.setPlaceholderText("Leave blank for anonymous (slower)")
        self.api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.api_key_input.textChanged.connect(self._save_api_key)
        api_layout.addRow("API Key", self.api_key_input)

        # Show/hide toggle
        self.show_key_checkbox = QCheckBox("Show key")
        self.show_key_checkbox.toggled.connect(self._toggle_key_visibility)
        api_layout.addRow("", self.show_key_checkbox)

        layout.addWidget(api_group)

        # Image selection
        image_group = QGroupBox("Image")
        image_layout = QHBoxLayout(image_group)
        image_layout.setContentsMargins(12, 20, 12, 12)
        image_layout.setSpacing(8)

        self.image_path_input = QLineEdit()
        self.image_path_input.setPlaceholderText("Select an image to solve...")
        self.image_path_input.setReadOnly(True)
        image_layout.addWidget(self.image_path_input)

        browse_btn = QPushButton("Browse...")
        browse_btn.setFixedWidth(80)
        browse_btn.clicked.connect(self._browse_image)
        image_layout.addWidget(browse_btn)

        layout.addWidget(image_group)

        # Scale hints (optional, speeds up solving)
        hints_group = QGroupBox("Scale Hints (optional)")
        hints_layout = QFormLayout(hints_group)
        hints_layout.setSpacing(10)
        hints_layout.setContentsMargins(12, 20, 12, 12)

        self.scale_units_combo = QComboBox()
        self.scale_units_combo.addItem("Arcsec/pixel", "arcsecperpix")
        self.scale_units_combo.addItem("Arcmin (field width)", "arcminwidth")
        self.scale_units_combo.addItem("Degrees (field width)", "degwidth")
        hints_layout.addRow("Units", self.scale_units_combo)

        self.scale_lower_spin = QDoubleSpinBox()
        self.scale_lower_spin.setRange(0, 9999)
        self.scale_lower_spin.setValue(0)
        self.scale_lower_spin.setDecimals(2)
        self.scale_lower_spin.setSpecialValueText("Auto")
        hints_layout.addRow("Lower Bound", self.scale_lower_spin)

        self.scale_upper_spin = QDoubleSpinBox()
        self.scale_upper_spin.setRange(0, 9999)
        self.scale_upper_spin.setValue(0)
        self.scale_upper_spin.setDecimals(2)
        self.scale_upper_spin.setSpecialValueText("Auto")
        hints_layout.addRow("Upper Bound", self.scale_upper_spin)

        layout.addWidget(hints_group)

        # Solve button
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self.solve_btn = QPushButton("Solve")
        self.solve_btn.setObjectName("primaryButton")
        self.solve_btn.setFixedHeight(44)
        self.solve_btn.setMinimumWidth(160)
        self.solve_btn.clicked.connect(self._on_solve_cancel)
        btn_layout.addWidget(self.solve_btn)

        btn_layout.addStretch()

        btn_container = QWidget()
        btn_container.setFixedHeight(60)
        btn_container_layout = QVBoxLayout(btn_container)
        btn_container_layout.setContentsMargins(0, 6, 0, 6)
        btn_container_layout.addLayout(btn_layout)
        layout.addWidget(btn_container)

        # Results
        results_group = QGroupBox("Results")
        results_layout = QVBoxLayout(results_group)
        results_layout.setContentsMargins(12, 20, 12, 12)

        self.results_text = QTextEdit()
        self.results_text.setReadOnly(True)
        self.results_text.setPlaceholderText(
            "Solve results will appear here...\n\n"
            "Tips for faster solving:\n"
            "1. Get a free API key at nova.astrometry.net\n"
            "2. Add Scale Hints above (your camera's arcsec/pixel)\n"
            "   This dramatically speeds up solving!\n"
            "3. Be patient — solving can take 2-10 minutes"
        )
        self.results_text.setMinimumHeight(140)
        results_layout.addWidget(self.results_text)

        self.write_wcs_btn = QPushButton("Write WCS to FITS...")
        self.write_wcs_btn.setToolTip(
            "Embed astrometry WCS coordinates into any FITS file.\n"
            "Makes the image plate-solved in PixInsight, Siril, etc."
        )
        self.write_wcs_btn.setEnabled(False)
        self.write_wcs_btn.clicked.connect(self._write_wcs_to_fits)
        results_layout.addWidget(self.write_wcs_btn)

        layout.addWidget(results_group)
        layout.addStretch()

    # ── API key persistence ──

    def _load_api_key(self):
        """Load the saved API key from user preferences."""
        settings = QSettings(SETTINGS_ORG, SETTINGS_APP)
        saved_key = settings.value("astrometry/api_key", "", type=str)
        if saved_key:
            self.api_key_input.blockSignals(True)
            self.api_key_input.setText(saved_key)
            self.api_key_input.blockSignals(False)

    def _save_api_key(self):
        """Save the API key to user preferences whenever it changes."""
        settings = QSettings(SETTINGS_ORG, SETTINGS_APP)
        settings.setValue("astrometry/api_key", self.api_key_input.text().strip())

    def _toggle_key_visibility(self, checked: bool):
        """Toggle between showing and hiding the API key."""
        if checked:
            self.api_key_input.setEchoMode(QLineEdit.EchoMode.Normal)
        else:
            self.api_key_input.setEchoMode(QLineEdit.EchoMode.Password)

    # ── Image selection ──

    def set_image_path(self, path: str):
        """Set the image path (e.g. from clicking a file in the sidebar)."""
        self._current_path = path
        self.image_path_input.setText(path)

    def _browse_image(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Image to Solve", "", FILE_FILTER
        )
        if path:
            self.set_image_path(path)

    # ── Solve ──

    def _on_solve_cancel(self):
        if self._worker is not None:
            self._worker.cancel()
            return

        path = self._current_path or self.image_path_input.text()
        if not path:
            QMessageBox.warning(
                self, "No Image", "Please select an image to plate solve."
            )
            return

        api_key = self.api_key_input.text().strip()

        scale_lower = self.scale_lower_spin.value() if self.scale_lower_spin.value() > 0 else None
        scale_upper = self.scale_upper_spin.value() if self.scale_upper_spin.value() > 0 else None
        scale_units = self.scale_units_combo.currentData()

        self.results_text.clear()
        self.results_text.append("Starting plate solve...")
        self.solve_btn.setText("Cancel")
        self.solve_btn.setObjectName("dangerButton")
        self.solve_btn.style().unpolish(self.solve_btn)
        self.solve_btn.style().polish(self.solve_btn)

        self._thread, self._worker = create_solve_thread(
            image_path=path,
            api_key=api_key,
            scale_lower=scale_lower,
            scale_upper=scale_upper,
            scale_units=scale_units,
        )
        self._worker.status_update.connect(self._on_status)
        self._worker.finished.connect(self._on_finished)
        self._worker.error.connect(self._on_error)
        self._thread.finished.connect(self._on_thread_done)

        self._thread.start()

    def _on_status(self, msg: str):
        self.results_text.append(msg)

    def _on_finished(self, result: SolveResult):
        self._last_result = result
        self.write_wcs_btn.setEnabled(True)
        self.results_text.clear()
        self.results_text.append(result.summary())

        # Open the annotated solution window
        path = self._current_path or self.image_path_input.text()
        if path:
            self._result_window = SolveResultWindow(
                result=result,
                image_path=path,
            )
            self._result_window.show()
            self._result_window.raise_()

    def _on_error(self, msg: str):
        self.results_text.append(f"\nERROR: {msg}")

    def _on_thread_done(self):
        self.solve_btn.setText("Solve")
        self.solve_btn.setObjectName("primaryButton")
        self.solve_btn.style().unpolish(self.solve_btn)
        self.solve_btn.style().polish(self.solve_btn)
        self._worker = None
        self._thread = None

    def _write_wcs_to_fits(self):
        """Write WCS astrometry keywords into a user-chosen FITS file."""
        if self._last_result is None:
            return

        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select FITS file to embed WCS into",
            "",
            "FITS Files (*.fits *.fit *.fts)",
        )
        if not path:
            return

        try:
            from astropy.io import fits as pyfits

            wcs_dict = self._last_result.fits_header_dict()
            with pyfits.open(path, mode="update") as hdul:
                for key, val in wcs_dict.items():
                    hdul[0].header[key] = val
                hdul.flush()

            QMessageBox.information(
                self,
                "WCS Written",
                f"Astrometry WCS data ({len(wcs_dict)} keywords) "
                f"written to:\n{path}\n\n"
                "This file is now plate-solved and will be recognised "
                "by PixInsight, Siril, and other astro tools.",
            )
        except Exception as e:
            QMessageBox.critical(self, "Write Error", str(e))

    def get_last_result(self) -> SolveResult | None:
        """Return the last plate solve result, if any."""
        return self._last_result
