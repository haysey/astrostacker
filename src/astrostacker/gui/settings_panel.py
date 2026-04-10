"""Settings panel with modern macOS-style controls."""

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
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from astrostacker.config import (
    CAMERA_COLOUR,
    CAMERA_MONO,
    DEFAULT_BAYER_PATTERN,
    DEFAULT_SIGMA_HIGH,
    DEFAULT_SIGMA_LOW,
    DEFAULT_STACKING_METHOD,
    STACKING_METHODS,
)
from astrostacker.utils.debayer import BAYER_PATTERNS


class SettingsPanel(QWidget):
    """Panel for configuring stacking method and output settings."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(6)

        # Section title
        title = QLabel("Settings")
        title.setStyleSheet(
            "font-size: 15px; font-weight: 700; color: #ffffff;"
            "padding-bottom: 4px;"
        )
        layout.addWidget(title)

        # Camera type
        camera_group = QGroupBox("Camera")
        camera_layout = QFormLayout(camera_group)
        camera_layout.setSpacing(10)
        camera_layout.setContentsMargins(12, 20, 12, 12)

        self.camera_combo = QComboBox()
        self.camera_combo.addItem("Mono", CAMERA_MONO)
        self.camera_combo.addItem("Colour (Bayer)", CAMERA_COLOUR)
        self.camera_combo.setToolTip(
            "Select Colour (Bayer) if your camera has a colour sensor.\n"
            "Raw Bayer data will be debayered to RGB before stacking."
        )
        self.camera_combo.currentIndexChanged.connect(self._on_camera_changed)
        camera_layout.addRow("Type", self.camera_combo)

        self.bayer_combo = QComboBox()
        for pat in BAYER_PATTERNS:
            self.bayer_combo.addItem(pat, pat)
        default_idx = BAYER_PATTERNS.index(DEFAULT_BAYER_PATTERN)
        self.bayer_combo.setCurrentIndex(default_idx)
        self.bayer_combo.setEnabled(False)
        self.bayer_combo.setToolTip(
            "The Bayer pattern of your camera sensor.\n"
            "Most colour astro cameras use RGGB.\n"
            "Check your camera specs if unsure."
        )
        camera_layout.addRow("Bayer Pattern", self.bayer_combo)

        layout.addWidget(camera_group)

        # Stacking method
        method_group = QGroupBox("Stacking")
        method_layout = QFormLayout(method_group)
        method_layout.setSpacing(10)
        method_layout.setContentsMargins(12, 20, 12, 12)

        self.method_combo = QComboBox()
        method_labels = {
            "mean": "Mean (Average)",
            "median": "Median",
            "sigma_clip": "Sigma Clipping (Kappa-Sigma)",
            "min": "Minimum",
            "max": "Maximum",
        }
        for method in STACKING_METHODS:
            self.method_combo.addItem(method_labels.get(method, method), method)
        default_idx = list(STACKING_METHODS).index(DEFAULT_STACKING_METHOD)
        self.method_combo.setCurrentIndex(default_idx)
        self.method_combo.setToolTip(
            "Sigma Clipping is recommended (rejects satellites, planes, noise).\n"
            "Median is good with fewer frames. Mean maximises signal."
        )
        self.method_combo.currentIndexChanged.connect(self._on_method_changed)
        method_layout.addRow("Method", self.method_combo)

        self.sigma_low_spin = QDoubleSpinBox()
        self.sigma_low_spin.setRange(0.5, 10.0)
        self.sigma_low_spin.setSingleStep(0.1)
        self.sigma_low_spin.setValue(DEFAULT_SIGMA_LOW)
        self.sigma_low_spin.setDecimals(1)
        self.sigma_low_spin.setToolTip(
            "Reject pixels this many sigma BELOW the median.\n"
            "Lower = more aggressive rejection. Default 2.5 works well."
        )
        method_layout.addRow("Sigma Low", self.sigma_low_spin)

        self.sigma_high_spin = QDoubleSpinBox()
        self.sigma_high_spin.setRange(0.5, 10.0)
        self.sigma_high_spin.setSingleStep(0.1)
        self.sigma_high_spin.setValue(DEFAULT_SIGMA_HIGH)
        self.sigma_high_spin.setDecimals(1)
        self.sigma_high_spin.setToolTip(
            "Reject pixels this many sigma ABOVE the median.\n"
            "Removes satellite trails, hot pixels. Default 2.5 works well."
        )
        method_layout.addRow("Sigma High", self.sigma_high_spin)

        layout.addWidget(method_group)

        # Alignment
        ref_group = QGroupBox("Alignment")
        ref_layout = QFormLayout(ref_group)
        ref_layout.setSpacing(10)
        ref_layout.setContentsMargins(12, 20, 12, 12)

        self.reference_spin = QSpinBox()
        self.reference_spin.setMinimum(0)
        self.reference_spin.setToolTip("Index of the light frame to use as alignment reference (0 = first)")
        ref_layout.addRow("Reference Frame", self.reference_spin)

        layout.addWidget(ref_group)

        # Output
        output_group = QGroupBox("Output")
        output_layout = QHBoxLayout(output_group)
        output_layout.setContentsMargins(12, 20, 12, 12)
        output_layout.setSpacing(8)

        self.output_path = QLineEdit("stacked.fits")
        output_layout.addWidget(self.output_path)

        browse_btn = QPushButton("Browse...")
        browse_btn.setFixedWidth(80)
        browse_btn.clicked.connect(self._browse_output)
        output_layout.addWidget(browse_btn)

        layout.addWidget(output_group)

        # Auto plate solve
        self.auto_solve_check = QCheckBox("Auto plate solve after stacking")
        self.auto_solve_check.setToolTip(
            "Automatically plate solve the stacked image and embed\n"
            "WCS astrometry data into the FITS file.\n"
            "Requires an API key in the Plate Solve tab."
        )
        self.auto_solve_check.setStyleSheet(
            "QCheckBox { color: rgba(255, 255, 255, 0.7); font-size: 12px; padding: 6px 2px; }"
            "QCheckBox::indicator { width: 16px; height: 16px; }"
        )
        layout.addWidget(self.auto_solve_check)

        layout.addStretch()

        self._on_method_changed()

    def _on_camera_changed(self):
        is_colour = self.camera_combo.currentData() == CAMERA_COLOUR
        self.bayer_combo.setEnabled(is_colour)

    def _on_method_changed(self):
        is_sigma = self.get_method() == "sigma_clip"
        self.sigma_low_spin.setEnabled(is_sigma)
        self.sigma_high_spin.setEnabled(is_sigma)

    def _browse_output(self):
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Stacked Result",
            self.output_path.text(),
            "FITS Files (*.fits);;XISF Files (*.xisf)",
        )
        if path:
            self.output_path.setText(path)

    def get_method(self) -> str:
        return self.method_combo.currentData()

    def get_sigma_low(self) -> float:
        return self.sigma_low_spin.value()

    def get_sigma_high(self) -> float:
        return self.sigma_high_spin.value()

    def get_output_path(self) -> str:
        return self.output_path.text()

    def get_reference_frame(self) -> int:
        return self.reference_spin.value()

    def get_auto_solve(self) -> bool:
        return self.auto_solve_check.isChecked()

    def get_camera_type(self) -> str:
        return self.camera_combo.currentData()

    def get_bayer_pattern(self) -> str:
        return self.bayer_combo.currentData()

    def set_max_reference(self, count: int):
        self.reference_spin.setMaximum(max(0, count - 1))
