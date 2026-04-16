"""Settings panel with modern macOS-style controls."""

from PyQt6.QtCore import Qt
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
    QScrollArea,
    QSpinBox,
    QStyle,
    QVBoxLayout,
    QWidget,
)

from astrostacker.config import (
    CAMERA_COLOUR,
    CAMERA_MONO,
    DEFAULT_BAYER_PATTERN,
    DEFAULT_DECONV_ITERATIONS,
    DEFAULT_PERCENTILE_HIGH,
    DEFAULT_PERCENTILE_LOW,
    DEFAULT_SIGMA_HIGH,
    DEFAULT_SIGMA_LOW,
    DEFAULT_STACKING_METHOD,
    STACKING_METHODS,
)
from astrostacker.utils.debayer import BAYER_PATTERNS

# Human-readable labels and tooltips for each stacking method
_METHOD_LABELS = {
    "mean": "Mean (Average)",
    "median": "Median",
    "sigma_clip": "Sigma Clipping",
    "winsorized_sigma": "Winsorized Sigma",
    "percentile_clip": "Percentile Clipping",
    "weighted_mean": "Weighted Mean (Quality)",
    "noise_weighted": "Noise-Weighted Mean",
    "min": "Minimum",
    "max": "Maximum",
}

# Methods that use sigma_low / sigma_high parameters
_SIGMA_METHODS = {"sigma_clip", "winsorized_sigma"}
# Methods that use percentile parameters
_PERCENTILE_METHODS = {"percentile_clip"}


class SettingsPanel(QWidget):
    """Panel for configuring stacking method and output settings."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        container = QWidget()
        layout = QVBoxLayout(container)
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
        camera_layout.setSpacing(14)
        camera_layout.setContentsMargins(12, 24, 12, 12)

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
        self._method_layout = QFormLayout(method_group)
        self._method_layout.setSpacing(14)
        self._method_layout.setContentsMargins(12, 24, 12, 12)

        self.method_combo = QComboBox()
        for method in STACKING_METHODS:
            self.method_combo.addItem(_METHOD_LABELS.get(method, method), method)
        default_idx = list(STACKING_METHODS).index(DEFAULT_STACKING_METHOD)
        self.method_combo.setCurrentIndex(default_idx)
        self.method_combo.setToolTip(
            "Median — safe default, good outlier rejection.\n"
            "Sigma Clipping — best with 15+ frames, rejects satellites/planes.\n"
            "Winsorized Sigma — like sigma clip but keeps more signal.\n"
            "Percentile Clipping — simple and effective with any frame count.\n"
            "Weighted Mean — sharper frames contribute more.\n"
            "Noise-Weighted — cleaner exposures contribute more.\n"
            "Mean — maximises SNR with clean data.\n"
            "Min/Max — diagnostic use."
        )
        self.method_combo.currentIndexChanged.connect(self._on_method_changed)
        self._method_layout.addRow("Method", self.method_combo)

        # Sigma parameters (shown for sigma_clip and winsorized_sigma)
        self.sigma_low_spin = QDoubleSpinBox()
        self.sigma_low_spin.setRange(0.5, 10.0)
        self.sigma_low_spin.setSingleStep(0.1)
        self.sigma_low_spin.setValue(DEFAULT_SIGMA_LOW)
        self.sigma_low_spin.setDecimals(1)
        self.sigma_low_spin.setToolTip(
            "Reject/clamp pixels this many sigma BELOW the median.\n"
            "Lower = more aggressive. Default 2.5 works well."
        )
        self._method_layout.addRow("Sigma Low", self.sigma_low_spin)

        self.sigma_high_spin = QDoubleSpinBox()
        self.sigma_high_spin.setRange(0.5, 10.0)
        self.sigma_high_spin.setSingleStep(0.1)
        self.sigma_high_spin.setValue(DEFAULT_SIGMA_HIGH)
        self.sigma_high_spin.setDecimals(1)
        self.sigma_high_spin.setToolTip(
            "Reject/clamp pixels this many sigma ABOVE the median.\n"
            "Removes satellite trails, hot pixels. Default 2.5 works well."
        )
        self._method_layout.addRow("Sigma High", self.sigma_high_spin)

        # Percentile parameters (shown for percentile_clip)
        self.pct_low_spin = QDoubleSpinBox()
        self.pct_low_spin.setRange(0.0, 49.0)
        self.pct_low_spin.setSingleStep(1.0)
        self.pct_low_spin.setValue(DEFAULT_PERCENTILE_LOW)
        self.pct_low_spin.setDecimals(0)
        self.pct_low_spin.setSuffix("%")
        self.pct_low_spin.setToolTip(
            "Percentage of lowest pixel values to reject.\n"
            "10% is a good default. Increase for more aggressive rejection."
        )
        self._method_layout.addRow("Reject Low", self.pct_low_spin)

        self.pct_high_spin = QDoubleSpinBox()
        self.pct_high_spin.setRange(0.0, 49.0)
        self.pct_high_spin.setSingleStep(1.0)
        self.pct_high_spin.setValue(DEFAULT_PERCENTILE_HIGH)
        self.pct_high_spin.setDecimals(0)
        self.pct_high_spin.setSuffix("%")
        self.pct_high_spin.setToolTip(
            "Percentage of highest pixel values to reject.\n"
            "10% is a good default. Helps remove satellite trails."
        )
        self._method_layout.addRow("Reject High", self.pct_high_spin)

        layout.addWidget(method_group)

        # Alignment
        ref_group = QGroupBox("Alignment")
        ref_layout = QFormLayout(ref_group)
        ref_layout.setSpacing(14)
        ref_layout.setContentsMargins(12, 24, 12, 12)

        self.reference_spin = QSpinBox()
        self.reference_spin.setMinimum(0)
        self.reference_spin.setToolTip("Index of the light frame to use as alignment reference (0 = first)")
        ref_layout.addRow("Reference Frame", self.reference_spin)

        layout.addWidget(ref_group)

        # Output
        output_group = QGroupBox("Output")
        output_layout = QHBoxLayout(output_group)
        output_layout.setContentsMargins(12, 24, 12, 12)
        output_layout.setSpacing(8)

        self.output_path = QLineEdit("stacked.fits")
        output_layout.addWidget(self.output_path)

        browse_btn = QPushButton("Browse...")
        browse_btn.setObjectName("secondaryButton")
        browse_btn.setMinimumWidth(100)
        browse_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DirOpenIcon))
        browse_btn.clicked.connect(self._browse_output)
        output_layout.addWidget(browse_btn)

        layout.addWidget(output_group)

        # Processing options
        proc_group = QGroupBox("Processing")
        proc_layout = QFormLayout(proc_group)
        proc_layout.setSpacing(14)
        proc_layout.setContentsMargins(12, 24, 12, 12)

        self.auto_reject_check = QCheckBox("Auto-reject blurry/trailed frames")
        self.auto_reject_check.setToolTip(
            "Fits PSF profiles to stars in each frame and automatically\n"
            "rejects frames with poor FWHM (blurry) or high eccentricity\n"
            "(trailed/wind shake). Requires at least 3 light frames."
        )
        proc_layout.addRow(self.auto_reject_check)

        self.gradient_check = QCheckBox("Remove light pollution gradient")
        self.gradient_check.setToolTip(
            "Fits and subtracts a smooth background surface from the\n"
            "final stacked result to remove sky gradients from light\n"
            "pollution, moonlight, or vignetting."
        )
        proc_layout.addRow(self.gradient_check)

        self.local_norm_check = QCheckBox("Local normalisation (per-frame)")
        self.local_norm_check.setToolTip(
            "Remove sky gradients from each frame individually BEFORE\n"
            "stacking. This prevents gradient differences between frames\n"
            "(e.g. from moonrise or changing sky glow) from contaminating\n"
            "the stack. More thorough than post-stack gradient removal."
        )
        proc_layout.addRow(self.local_norm_check)

        self.auto_crop_check = QCheckBox("Auto-crop stacking edges")
        self.auto_crop_check.setToolTip(
            "Automatically crop the black/NaN borders left by\n"
            "frame alignment to give a clean rectangular result."
        )
        proc_layout.addRow(self.auto_crop_check)

        # Denoise row: checkbox + strength combo side by side
        denoise_row = QHBoxLayout()
        denoise_row.setSpacing(12)
        denoise_row.setContentsMargins(0, 0, 0, 0)

        self.denoise_check = QCheckBox("Denoise")
        self.denoise_check.setToolTip(
            "Apply Non-Local Means denoising to the stacked result.\n"
            "Smooths noisy background while preserving star profiles\n"
            "and nebula structure. No model files or GPU required."
        )
        self.denoise_check.toggled.connect(self._on_denoise_toggled)
        denoise_row.addWidget(self.denoise_check)

        self.denoise_strength_combo = QComboBox()
        self.denoise_strength_combo.addItem("Light", "light")
        self.denoise_strength_combo.addItem("Medium", "medium")
        self.denoise_strength_combo.addItem("Strong", "strong")
        self.denoise_strength_combo.setCurrentIndex(1)  # Medium default
        self.denoise_strength_combo.setMinimumWidth(100)
        self.denoise_strength_combo.setEnabled(False)
        self.denoise_strength_combo.setToolTip(
            "Light — subtle smoothing, safest for detail.\n"
            "Medium — good balance (recommended).\n"
            "Strong — aggressive, best for very noisy stacks."
        )
        denoise_row.addWidget(self.denoise_strength_combo)
        denoise_row.addStretch()

        proc_layout.addRow(denoise_row)

        # Deconvolution row: checkbox + iterations spinner side by side
        deconv_row = QHBoxLayout()
        deconv_row.setSpacing(12)
        deconv_row.setContentsMargins(0, 0, 0, 0)

        self.deconv_check = QCheckBox("Sharpen")
        self.deconv_check.setToolTip(
            "Apply Richardson-Lucy deconvolution to sharpen the\n"
            "stacked result using the measured star PSF.\n"
            "Works best on well-exposed stacks with good SNR."
        )
        self.deconv_check.toggled.connect(self._on_deconv_toggled)
        deconv_row.addWidget(self.deconv_check)

        self.deconv_iter_spin = QSpinBox()
        self.deconv_iter_spin.setRange(5, 50)
        self.deconv_iter_spin.setValue(DEFAULT_DECONV_ITERATIONS)
        self.deconv_iter_spin.setSuffix(" iter")
        self.deconv_iter_spin.setMinimumWidth(100)
        self.deconv_iter_spin.setEnabled(False)
        self.deconv_iter_spin.setToolTip(
            "Number of Richardson-Lucy iterations.\n"
            "More iterations = sharper but risk amplifying noise.\n"
            "10–20 is typically good."
        )
        deconv_row.addWidget(self.deconv_iter_spin)
        deconv_row.addStretch()

        proc_layout.addRow(deconv_row)

        self.drizzle_check = QCheckBox("Drizzle (2x resolution)")
        self.drizzle_check.setToolTip(
            "Use drizzle stacking to produce an image at 2x the native\n"
            "pixel resolution. Best with well-dithered sub-exposures.\n"
            "Output will be 4x larger in file size."
        )
        proc_layout.addRow(self.drizzle_check)

        layout.addWidget(proc_group)

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

        scroll.setWidget(container)
        outer.addWidget(scroll)

        self._on_method_changed()
        self._on_camera_changed()

    # ── Visibility logic ──

    def _set_row_visible(self, widget, visible: bool):
        """Show or hide a widget and its QFormLayout label."""
        widget.setVisible(visible)
        label = self._method_layout.labelForField(widget)
        if label is not None:
            label.setVisible(visible)

    def _on_camera_changed(self):
        is_colour = self.camera_combo.currentData() == CAMERA_COLOUR
        self.bayer_combo.setVisible(is_colour)
        label = self.bayer_combo.parent().layout().labelForField(self.bayer_combo)
        if label is not None:
            label.setVisible(is_colour)

    def _on_method_changed(self):
        method = self.get_method()
        show_sigma = method in _SIGMA_METHODS
        show_pct = method in _PERCENTILE_METHODS

        self._set_row_visible(self.sigma_low_spin, show_sigma)
        self._set_row_visible(self.sigma_high_spin, show_sigma)
        self._set_row_visible(self.pct_low_spin, show_pct)
        self._set_row_visible(self.pct_high_spin, show_pct)

    def _on_denoise_toggled(self, checked: bool):
        self.denoise_strength_combo.setEnabled(checked)

    def _on_deconv_toggled(self, checked: bool):
        self.deconv_iter_spin.setEnabled(checked)

    # ── Browse ──

    def _browse_output(self):
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Stacked Result",
            self.output_path.text(),
            "FITS Files (*.fits);;XISF Files (*.xisf)",
        )
        if path:
            self.output_path.setText(path)

    # ── Getters ──

    def get_method(self) -> str:
        return self.method_combo.currentData()

    def get_sigma_low(self) -> float:
        return self.sigma_low_spin.value()

    def get_sigma_high(self) -> float:
        return self.sigma_high_spin.value()

    def get_percentile_low(self) -> float:
        return self.pct_low_spin.value()

    def get_percentile_high(self) -> float:
        return self.pct_high_spin.value()

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

    def get_auto_reject(self) -> bool:
        return self.auto_reject_check.isChecked()

    def get_remove_gradient(self) -> bool:
        return self.gradient_check.isChecked()

    def get_local_normalise(self) -> bool:
        return self.local_norm_check.isChecked()

    def get_auto_crop(self) -> bool:
        return self.auto_crop_check.isChecked()

    def get_denoise(self) -> bool:
        return self.denoise_check.isChecked()

    def get_denoise_strength(self) -> str:
        return self.denoise_strength_combo.currentData()

    def get_deconvolve(self) -> bool:
        return self.deconv_check.isChecked()

    def get_deconv_iterations(self) -> int:
        return self.deconv_iter_spin.value()

    def get_drizzle(self) -> bool:
        return self.drizzle_check.isChecked()

    def set_max_reference(self, count: int):
        self.reference_spin.setMaximum(max(0, count - 1))
