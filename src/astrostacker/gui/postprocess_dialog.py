"""Interactive post-processing window for AstroStacker.

Opens with any stacked image (from a pipeline run or loaded from disk),
lets the user work through a numbered five-step workflow, then save the
result.

Step layout
-----------
  ❶  COLOUR      — colour balance (fix casts before anything else)
  ❷  BACKGROUND  — gradient removal & auto-crop
  ❸  ENHANCE     — denoise & sharpen
  ❹  STARS       — star brightness reduction
  ❺  APPLY & SAVE

All steps are always visible; the numbers guide the recommended order
without forcing a strictly linear workflow.

Threading
---------
Apply runs the pipeline's _run_postprocessing() on a QThread.
The worker uses @pyqtSlot and an explicit QueuedConnection so the
result always lands back on the main thread for safe UI update.
"""

from __future__ import annotations

import traceback
from pathlib import Path

import numpy as np
from PyQt6.QtCore import QObject, QThread, QTimer, Qt, pyqtSignal, pyqtSlot
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSlider,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from astrostacker.gui.preview_panel import PreviewPanel
from astrostacker.pipeline.pipeline import Pipeline, PipelineConfig


# ── Background worker ──────────────────────────────────────────────────────

class _PostProcessWorker(QObject):
    """Runs Pipeline._run_postprocessing() on a background QThread."""

    finished = pyqtSignal(np.ndarray)
    error    = pyqtSignal(str)

    def __init__(self, raw_stack: np.ndarray, config: PipelineConfig):
        super().__init__()
        self._raw_stack = raw_stack
        self._config    = config

    @pyqtSlot()
    def run(self):
        try:
            pipeline = Pipeline(self._config)
            result   = pipeline._run_postprocessing(self._raw_stack.copy())
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(f"{type(e).__name__}: {e}\n{traceback.format_exc()}")


# ── Dialog ─────────────────────────────────────────────────────────────────

class PostProcessDialog(QDialog):
    """Large-preview interactive post-processing window.

    Args:
        raw_stack:  The pipeline-processed stacked image as float32 ndarray.
                    This is NEVER modified — every Apply starts from a copy.
        parent:     Parent widget so the macOS dark stylesheet propagates.
    """

    def __init__(self, raw_stack: np.ndarray, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Post-Processing")
        self.setMinimumSize(1200, 820)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setWindowFlag(Qt.WindowType.Window)

        self._raw_stack:          np.ndarray          = raw_stack
        self._working_stack:      np.ndarray          = raw_stack   # accumulates applied steps
        self._undo_stack:         list                = []          # up to 5 previous working stacks
        self._pending_undo        = None                            # saved before worker starts
        self._pending_had_crop:   bool                = False
        self._pending_config:     PipelineConfig | None = None   # config used for the running job
        self._processed:          np.ndarray | None   = None
        self._showing_original:   bool                = False
        self._worker:             _PostProcessWorker | None = None
        self._thread:             QThread | None      = None
        self._crop_rect:          tuple[int, int, int, int] | None = None
        self._ref_stretch_params: tuple | None        = None

        self._setup_ui()
        self.preview.show_data(raw_stack, info="Original (unprocessed)")
        self.preview.crop_selected.connect(self._on_crop_selected)

        # Open maximised to fill the screen (same as the main stacking window)
        QTimer.singleShot(0, self.showMaximized)

    # ── UI ─────────────────────────────────────────────────────────────────

    def _setup_ui(self):
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Left: large preview ─────────────────────────────────────────────
        left        = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(0)

        self.preview = PreviewPanel()
        left_layout.addWidget(self.preview, stretch=1)

        # Toggle bar below preview
        toggle_bar = QWidget()
        toggle_bar.setStyleSheet(
            "background-color: rgba(15, 15, 25, 0.90);"
            "border-top: 1px solid rgba(255,255,255,0.08);"
        )
        tl = QHBoxLayout(toggle_bar)
        tl.setContentsMargins(14, 6, 14, 6)
        tl.setSpacing(8)

        self._orig_btn = QPushButton("Show Original")
        self._orig_btn.setObjectName("secondaryButton")
        self._orig_btn.setEnabled(False)
        self._orig_btn.setCheckable(True)
        self._orig_btn.toggled.connect(self._on_toggle_original)
        tl.addWidget(self._orig_btn)

        self._compare_label = QLabel(
            "Choose options on the right, then click  ▶ Apply"
        )
        self._compare_label.setStyleSheet(
            "color: rgba(255,149,0,0.80); font-size: 12px; font-weight: 600;"
        )
        tl.addWidget(self._compare_label, stretch=1)

        self._crop_btn = QPushButton("✂  Crop")
        self._crop_btn.setObjectName("secondaryButton")
        self._crop_btn.setCheckable(True)
        self._crop_btn.setToolTip(
            "Draw a rectangle on the image to select the crop region.\n"
            "Click Apply after setting the crop to preview the result."
        )
        self._crop_btn.toggled.connect(self._on_crop_toggled)
        tl.addWidget(self._crop_btn)

        self._crop_info_label = QLabel("")
        self._crop_info_label.setStyleSheet(
            "color: rgba(255,149,0,0.85); font-size: 11px; font-weight: 600;"
        )
        self._crop_info_label.hide()
        tl.addWidget(self._crop_info_label)

        self._clear_crop_btn = QPushButton("✕ Clear")
        self._clear_crop_btn.setObjectName("secondaryButton")
        self._clear_crop_btn.setToolTip("Remove the crop selection.")
        self._clear_crop_btn.clicked.connect(self._on_clear_crop)
        self._clear_crop_btn.hide()
        tl.addWidget(self._clear_crop_btn)

        left_layout.addWidget(toggle_bar)
        root.addWidget(left, stretch=3)

        # ── Right: controls panel ───────────────────────────────────────────
        right = QWidget()
        right.setObjectName("ppRight")
        right.setFixedWidth(355)
        right.setStyleSheet(
            "QWidget#ppRight {"
            "  background-color: rgba(12, 12, 22, 0.95);"
            "  border-left: 1px solid rgba(255,255,255,0.08);"
            "}"
        )
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)

        # ── Title strip ───────────────────────────────────────────────────
        title_bar = QWidget()
        title_bar.setStyleSheet(
            "background-color: rgba(20, 20, 35, 0.98);"
            "border-bottom: 1px solid rgba(255,255,255,0.10);"
        )
        tb_layout = QHBoxLayout(title_bar)
        tb_layout.setContentsMargins(16, 10, 16, 10)
        title_lbl = QLabel("Post-Processing")
        title_lbl.setStyleSheet(
            "font-size: 14px; font-weight: 700; color: #ff9500;"
            "letter-spacing: 0.3px;"
        )
        tb_layout.addWidget(title_lbl)
        right_layout.addWidget(title_bar)

        # ── Step guide strip ──────────────────────────────────────────────
        step_bar = QWidget()
        step_bar.setStyleSheet(
            "background-color: rgba(16, 16, 28, 0.98);"
            "border-bottom: 1px solid rgba(255,255,255,0.07);"
        )
        sb_layout = QHBoxLayout(step_bar)
        sb_layout.setContentsMargins(10, 7, 10, 7)
        sb_layout.setSpacing(0)

        steps = [
            ("❶", "Colour"),
            ("❷", "Tone"),
            ("❸", "Background"),
            ("❹", "Enhance"),
            ("❺", "Stars"),
            ("❻", "Save"),
        ]
        for i, (num, name) in enumerate(steps):
            cell = QVBoxLayout()
            cell.setSpacing(1)
            cell.setContentsMargins(0, 0, 0, 0)

            num_lbl = QLabel(num)
            num_lbl.setAlignment(Qt.AlignmentFlag.AlignHCenter)
            num_lbl.setStyleSheet(
                "color: #ff9500; font-size: 13px; font-weight: 700;"
            )
            cell.addWidget(num_lbl)

            name_lbl = QLabel(name)
            name_lbl.setAlignment(Qt.AlignmentFlag.AlignHCenter)
            name_lbl.setStyleSheet(
                "color: rgba(255,255,255,0.55); font-size: 8px;"
            )
            cell.addWidget(name_lbl)

            sb_layout.addLayout(cell)

            if i < len(steps) - 1:
                arrow = QLabel("›")
                arrow.setAlignment(Qt.AlignmentFlag.AlignCenter)
                arrow.setStyleSheet(
                    "color: rgba(255,149,0,0.35); font-size: 14px;"
                    "padding-bottom: 6px;"
                )
                sb_layout.addWidget(arrow)

        right_layout.addWidget(step_bar)

        # ── Scroll area: steps ❶–❹ ────────────────────────────────────────
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        ctrl          = QWidget()
        ctrl_layout   = QVBoxLayout(ctrl)
        ctrl_layout.setContentsMargins(14, 10, 14, 10)
        ctrl_layout.setSpacing(4)

        # ── ❶  COLOUR BALANCE ────────────────────────────────────────────
        self._add_step_header(ctrl_layout, "❶", "COLOUR BALANCE")

        self.colour_check = QCheckBox("Enable colour balance")
        self.colour_check.setToolTip(
            "Correct colour cast from light pollution, airglow,\n"
            "or Bayer sensor bias. No-op on mono images."
        )
        self.colour_check.toggled.connect(self._on_colour_balance_toggled)
        ctrl_layout.addWidget(self.colour_check)

        self.colour_auto_check = QCheckBox("Auto (recommended)")
        self.colour_auto_check.setChecked(True)
        self.colour_auto_check.setEnabled(False)
        self.colour_auto_check.setToolTip(
            "Sample sky from image corners and neutralise any tint.\n"
            "Works well for most light-polluted skies."
        )
        self.colour_auto_check.toggled.connect(self._on_colour_auto_toggled)
        ctrl_layout.addWidget(self.colour_auto_check)

        for colour, attr in [("R", "r"), ("G", "g"), ("B", "b")]:
            row = QHBoxLayout()
            row.setSpacing(6)
            row.setContentsMargins(0, 0, 0, 0)
            lbl = QLabel(colour)
            lbl.setFixedWidth(14)
            lbl.setStyleSheet("color: rgba(255,255,255,0.7);")
            row.addWidget(lbl)
            slider = QSlider(Qt.Orientation.Horizontal)
            slider.setRange(50, 200)
            slider.setValue(100)
            slider.setEnabled(False)
            spinbox = QDoubleSpinBox()
            spinbox.setRange(0.50, 2.00)
            spinbox.setSingleStep(0.05)
            spinbox.setDecimals(2)
            spinbox.setSuffix("×")
            spinbox.setValue(1.00)
            spinbox.setFixedWidth(76)
            spinbox.setEnabled(False)
            slider.valueChanged.connect(
                lambda v, s=spinbox: (s.blockSignals(True), s.setValue(v / 100.0), s.blockSignals(False))
            )
            spinbox.valueChanged.connect(
                lambda v, sl=slider: (sl.blockSignals(True), sl.setValue(round(v * 100)), sl.blockSignals(False))
            )
            row.addWidget(slider)
            row.addWidget(spinbox)
            ctrl_layout.addLayout(row)
            setattr(self, f"colour_{attr}_slider",  slider)
            setattr(self, f"colour_{attr}_spinbox", spinbox)

        ctrl_layout.addSpacing(8)

        # ── ❷  TONE ───────────────────────────────────────────────────────
        self._add_step_header(ctrl_layout, "❷", "TONE")

        self.tone_check = QCheckBox("Enable tone adjustment")
        self.tone_check.setToolTip(
            "Adjust brightness, contrast and saturation of the image.\n\n"
            "Brightness — multiplicative (EV-stop scale).\n"
            "  +100% doubles brightness, −100% halves it.\n\n"
            "Contrast — scales values around the sky floor.\n"
            "  Positive widens the range; negative compresses it.\n\n"
            "Saturation — scales colour deviation from luminance.\n"
            "  +100% doubles colour intensity; −100% converts to grey.\n"
            "  No effect on mono images."
        )
        self.tone_check.toggled.connect(self._on_tone_toggled)
        ctrl_layout.addWidget(self.tone_check)

        for _label, _attr in [
            ("Brightness", "brightness"),
            ("Contrast",   "contrast"),
            ("Saturation", "saturation"),
        ]:
            row = QHBoxLayout()
            row.setSpacing(6)
            row.setContentsMargins(0, 0, 0, 0)
            lbl = QLabel(_label)
            lbl.setFixedWidth(68)
            lbl.setStyleSheet("color: rgba(255,255,255,0.70); font-size: 11px;")
            row.addWidget(lbl)
            slider = QSlider(Qt.Orientation.Horizontal)
            slider.setRange(-100, 100)
            slider.setValue(0)
            slider.setEnabled(False)
            spinbox = QSpinBox()
            spinbox.setRange(-100, 100)
            spinbox.setSuffix("%")
            spinbox.setValue(0)
            spinbox.setFixedWidth(72)
            spinbox.setEnabled(False)
            slider.valueChanged.connect(
                lambda v, s=spinbox: (
                    s.blockSignals(True), s.setValue(v), s.blockSignals(False)
                )
            )
            spinbox.valueChanged.connect(
                lambda v, sl=slider: (
                    sl.blockSignals(True), sl.setValue(v), sl.blockSignals(False)
                )
            )
            row.addWidget(slider)
            row.addWidget(spinbox)
            ctrl_layout.addLayout(row)
            setattr(self, f"tone_{_attr}_slider",  slider)
            setattr(self, f"tone_{_attr}_spinbox", spinbox)

        ctrl_layout.addSpacing(8)

        # ── ❸  BACKGROUND ────────────────────────────────────────────────
        self._add_step_header(ctrl_layout, "❸", "BACKGROUND")

        self.gradient_check = QCheckBox("Remove gradient")
        self.gradient_check.setToolTip(
            "Fit and subtract a smooth sky-background surface.\n"
            "Corrects light pollution gradients and vignetting.\n\n"
            "Applied to the final stacked image for best quality —\n"
            "works far more reliably than correcting individual frames."
        )
        ctrl_layout.addWidget(self.gradient_check)

        self.crop_check = QCheckBox("Auto-crop edges")
        self.crop_check.setToolTip(
            "Trim the dark borders created by frame alignment.\n"
            "Safe to enable for any stacked image."
        )
        ctrl_layout.addWidget(self.crop_check)

        ctrl_layout.addSpacing(8)

        # ── ❹  ENHANCE ───────────────────────────────────────────────────
        self._add_step_header(ctrl_layout, "❹", "ENHANCE")

        denoise_row = QHBoxLayout()
        denoise_row.setSpacing(8)
        denoise_row.setContentsMargins(0, 0, 0, 0)
        self.denoise_check = QCheckBox("Denoise")
        self.denoise_check.setToolTip(
            "Non-Local Means denoising on the final stacked image.\n"
            "Works best for galaxies, clusters, and planetary nebulae.\n"
            "On large emission nebulae that fill the frame, try without\n"
            "it first — it can soften extended structure.\n\n"
            "Applying denoise to the stack (not to individual frames)\n"
            "gives much cleaner results with fewer artefacts."
        )
        self.denoise_check.toggled.connect(self._on_denoise_toggled)
        denoise_row.addWidget(self.denoise_check)
        self.denoise_combo = QComboBox()
        self.denoise_combo.addItem("Light",  "light")
        self.denoise_combo.addItem("Medium", "medium")
        self.denoise_combo.addItem("Strong", "strong")
        self.denoise_combo.setCurrentIndex(1)
        self.denoise_combo.setEnabled(False)
        self.denoise_combo.setMinimumWidth(90)
        self.denoise_combo.setToolTip(
            "Light  — subtle, safest for preserving fine detail.\n"
            "Medium — good balance (recommended).\n"
            "Strong — aggressive, best for very noisy stacks."
        )
        denoise_row.addWidget(self.denoise_combo)
        denoise_row.addStretch()
        ctrl_layout.addLayout(denoise_row)

        sharpen_row = QHBoxLayout()
        sharpen_row.setSpacing(8)
        sharpen_row.setContentsMargins(0, 0, 0, 0)
        self.sharpen_check = QCheckBox("Sharpen")
        self.sharpen_check.setToolTip(
            "PSF-informed sharpening (Richardson-Lucy deconvolution).\n"
            "Tightens stars and reveals fine detail in the stack.\n\n"
            "Apply after Denoise for best results. Works best on\n"
            "well-exposed stacks with good signal-to-noise ratio."
        )
        self.sharpen_check.toggled.connect(self._on_sharpen_toggled)
        sharpen_row.addWidget(self.sharpen_check)
        self.sharpen_combo = QComboBox()
        self.sharpen_combo.addItem("Light",  "light")
        self.sharpen_combo.addItem("Medium", "medium")
        self.sharpen_combo.addItem("Strong", "strong")
        self.sharpen_combo.setCurrentIndex(1)
        self.sharpen_combo.setEnabled(False)
        self.sharpen_combo.setMinimumWidth(90)
        self.sharpen_combo.setToolTip(
            "Light  — subtle, safest for any stack.\n"
            "Medium — good balance (recommended).\n"
            "Strong — aggressive, best for high-SNR stacks."
        )
        sharpen_row.addWidget(self.sharpen_combo)
        sharpen_row.addStretch()
        ctrl_layout.addLayout(sharpen_row)

        ctrl_layout.addSpacing(8)

        # ── ❺  STARS ─────────────────────────────────────────────────────
        self._add_step_header(ctrl_layout, "❺", "STARS")

        self.star_reduce_check = QCheckBox("Reduce stars")
        self.star_reduce_check.setToolTip(
            "Reduce star brightness using morphological detection\n"
            "(no AI, no model files required).\n\n"
            "Drag the slider to set strength, click Apply, then\n"
            "compare with the original using 'Show Original'."
        )
        self.star_reduce_check.toggled.connect(self._on_star_reduce_toggled)
        ctrl_layout.addWidget(self.star_reduce_check)

        star_slider_row = QHBoxLayout()
        star_slider_row.setSpacing(6)
        star_slider_row.setContentsMargins(0, 0, 0, 0)
        self.star_slider = QSlider(Qt.Orientation.Horizontal)
        self.star_slider.setRange(0, 100)
        self.star_slider.setValue(50)
        self.star_slider.setEnabled(False)
        star_slider_row.addWidget(self.star_slider)
        self.star_spinbox = QSpinBox()
        self.star_spinbox.setRange(0, 100)
        self.star_spinbox.setSuffix("%")
        self.star_spinbox.setValue(50)
        self.star_spinbox.setFixedWidth(72)
        self.star_spinbox.setEnabled(False)
        self.star_slider.valueChanged.connect(
            lambda v: (self.star_spinbox.blockSignals(True),
                       self.star_spinbox.setValue(v),
                       self.star_spinbox.blockSignals(False))
        )
        self.star_spinbox.valueChanged.connect(
            lambda v: (self.star_slider.blockSignals(True),
                       self.star_slider.setValue(v),
                       self.star_slider.blockSignals(False))
        )
        star_slider_row.addWidget(self.star_spinbox)
        ctrl_layout.addLayout(star_slider_row)

        # ── Crop tip ──────────────────────────────────────────────────────
        ctrl_layout.addSpacing(10)
        crop_tip = QLabel("✂  Use Crop below the image to trim composition\nbefore saving.")
        crop_tip.setStyleSheet(
            "color: rgba(255,255,255,0.40); font-size: 10px;"
            "padding: 4px 0px;"
        )
        crop_tip.setWordWrap(True)
        ctrl_layout.addWidget(crop_tip)

        ctrl_layout.addStretch()

        scroll.setWidget(ctrl)
        right_layout.addWidget(scroll, stretch=1)

        # ── Status label ──────────────────────────────────────────────────
        self._status_label = QLabel("")
        self._status_label.setWordWrap(True)
        self._status_label.setStyleSheet(
            "color: rgba(255,255,255,0.55); font-size: 11px;"
            "padding: 4px 14px 2px 14px;"
        )
        self._status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        right_layout.addWidget(self._status_label)

        # ── ❺  APPLY & SAVE (fixed bottom) ───────────────────────────────
        actions_hr = QWidget()
        actions_hr.setFixedHeight(1)
        actions_hr.setStyleSheet("background-color: rgba(255,255,255,0.08);")
        right_layout.addWidget(actions_hr)

        actions = QWidget()
        actions.setStyleSheet("background-color: rgba(12, 12, 22, 0.98);")
        al = QVBoxLayout(actions)
        al.setContentsMargins(12, 10, 12, 12)
        al.setSpacing(6)

        # Step ❺ label inside the actions area
        step5_lbl = QLabel("❺  APPLY & SAVE")
        step5_lbl.setStyleSheet(
            "color: #ff9500; font-size: 10px; font-weight: 700;"
            "letter-spacing: 1px; padding-bottom: 2px;"
        )
        al.addWidget(step5_lbl)

        self.apply_btn = QPushButton("▶   Apply")
        self.apply_btn.setObjectName("primaryButton")
        self.apply_btn.setFixedHeight(44)
        self.apply_btn.setToolTip(
            "Run the selected steps on the current working image.\n"
            "Each Apply builds on the previous result (cumulative).\n"
            "Use Undo to step back one stage, or Reset to start over."
        )
        self.apply_btn.clicked.connect(self._on_apply)
        al.addWidget(self.apply_btn)

        undo_reset_row = QHBoxLayout()
        undo_reset_row.setSpacing(6)
        undo_reset_row.setContentsMargins(0, 0, 0, 0)

        self.undo_btn = QPushButton("↩ Undo")
        self.undo_btn.setObjectName("secondaryButton")
        self.undo_btn.setToolTip("Step back one Apply (up to 5 levels).")
        self.undo_btn.setEnabled(False)
        self.undo_btn.clicked.connect(self._on_undo)
        undo_reset_row.addWidget(self.undo_btn)

        self.reset_btn = QPushButton("Reset to Original")
        self.reset_btn.setObjectName("secondaryButton")
        self.reset_btn.setToolTip("Restore the unprocessed original image and clear all history.")
        self.reset_btn.clicked.connect(self._on_reset)
        undo_reset_row.addWidget(self.reset_btn)

        al.addLayout(undo_reset_row)

        divider = QWidget()
        divider.setFixedHeight(1)
        divider.setStyleSheet("background-color: rgba(255,255,255,0.08);")
        al.addSpacing(4)
        al.addWidget(divider)
        al.addSpacing(4)

        for label, fmt, tip in [
            ("Save FITS…",  "fits",  "Full 32-bit float — best for further processing"),
            ("Save TIFF…",  "tiff",  "16-bit TIFF — for Photoshop / printing"),
            ("Save JPEG…",  "jpeg",  "JPEG — for sharing online"),
            ("Save PNG…",   "png",   "PNG lossless — for web use"),
        ]:
            btn = QPushButton(label)
            btn.setObjectName("secondaryButton")
            btn.setToolTip(tip)
            btn.clicked.connect(lambda checked, f=fmt: self._save(f))
            al.addWidget(btn)

        al.addSpacing(4)
        close_btn = QPushButton("Close")
        close_btn.setObjectName("secondaryButton")
        close_btn.clicked.connect(self.close)
        al.addWidget(close_btn)

        right_layout.addWidget(actions)
        root.addWidget(right)

    # ── Helpers ─────────────────────────────────────────────────────────────

    def _add_step_header(self, layout: QVBoxLayout, number: str, title: str):
        """Add an orange numbered section header."""
        row = QHBoxLayout()
        row.setSpacing(6)
        row.setContentsMargins(0, 0, 0, 0)

        num_lbl = QLabel(number)
        num_lbl.setStyleSheet(
            "color: #ff9500; font-size: 15px; font-weight: 700;"
        )
        row.addWidget(num_lbl)

        title_lbl = QLabel(title)
        title_lbl.setStyleSheet(
            "color: #ff9500; font-size: 10px; font-weight: 700;"
            "letter-spacing: 1px; padding-top: 4px;"
        )
        row.addWidget(title_lbl)
        row.addStretch()

        layout.addLayout(row)

        sep = QWidget()
        sep.setFixedHeight(1)
        sep.setStyleSheet("background-color: rgba(255,149,0,0.20);")
        layout.addWidget(sep)
        layout.addSpacing(4)

    # ── Toggle helpers ───────────────────────────────────────────────────────

    def _on_tone_toggled(self, checked: bool):
        for attr in ("brightness", "contrast", "saturation"):
            getattr(self, f"tone_{attr}_slider").setEnabled(checked)
            getattr(self, f"tone_{attr}_spinbox").setEnabled(checked)

    def _on_denoise_toggled(self, checked: bool):
        self.denoise_combo.setEnabled(checked)

    def _on_sharpen_toggled(self, checked: bool):
        self.sharpen_combo.setEnabled(checked)

    def _on_star_reduce_toggled(self, checked: bool):
        self.star_slider.setEnabled(checked)
        self.star_spinbox.setEnabled(checked)

    def _on_colour_balance_toggled(self, checked: bool):
        self.colour_auto_check.setEnabled(checked)
        manual = checked and not self.colour_auto_check.isChecked()
        for attr in ("r", "g", "b"):
            getattr(self, f"colour_{attr}_slider").setEnabled(manual)
            getattr(self, f"colour_{attr}_spinbox").setEnabled(manual)

    def _on_colour_auto_toggled(self, checked: bool):
        enabled = self.colour_check.isChecked()
        manual  = enabled and not checked
        for attr in ("r", "g", "b"):
            getattr(self, f"colour_{attr}_slider").setEnabled(manual)
            getattr(self, f"colour_{attr}_spinbox").setEnabled(manual)

    def _on_toggle_original(self, checked: bool):
        self._showing_original = checked
        self._orig_btn.setText("Show Processed" if checked else "Show Original")
        if checked:
            self.preview.show_data(self._raw_stack, info="Original (unprocessed)")
        elif self._working_stack is not self._raw_stack:
            h, w = self._working_stack.shape[:2]
            chan  = "RGB" if self._working_stack.ndim == 3 else "mono"
            self.preview.show_data(
                self._working_stack,
                info=f"Post-processed  {w}×{h}  {chan}",
                fixed_stretch_params=self._ref_stretch_params,
            )

    def _on_crop_toggled(self, checked: bool):
        self.preview.set_crop_mode(checked)
        if checked:
            self._compare_label.setText(
                "Draw a rectangle on the image to select the crop region."
            )
        else:
            self._compare_label.setText(
                "Choose options on the right, then click  ▶ Apply"
            )

    def _on_crop_selected(self, x: int, y: int, w: int, h: int):
        self._crop_rect = (x, y, w, h)
        self._crop_btn.setChecked(False)
        self.preview.set_crop_mode(False)
        self._crop_info_label.setText(f"Crop: {w}×{h} px")
        self._crop_info_label.show()
        self._clear_crop_btn.show()
        self._compare_label.setText(
            f"Crop set ({w}×{h} px at {x},{y}).  Click ▶ Apply to preview."
        )

    def _on_clear_crop(self):
        self._crop_rect = None
        self._crop_btn.setChecked(False)
        self.preview.set_crop_mode(False)
        self._crop_info_label.hide()
        self._clear_crop_btn.hide()
        # Show the current working stack (may be processed, not necessarily raw)
        if self._processed is not None:
            h, w = self._working_stack.shape[:2]
            chan  = "RGB" if self._working_stack.ndim == 3 else "mono"
            self.preview.show_data(
                self._working_stack,
                info=f"Post-processed  {w}×{h}  {chan}",
                fixed_stretch_params=self._ref_stretch_params,
            )
        else:
            self.preview.show_data(self._raw_stack, info="Original (unprocessed)")
        self._compare_label.setText(
            "Choose options on the right, then click  ▶ Apply"
        )

    def _on_undo(self):
        """Step back one Apply — restores the previous working stack."""
        try:
            if self._thread is not None and self._thread.isRunning():
                return
            if not self._undo_stack:
                return

            prev = self._undo_stack.pop()

            # Validate before touching any UI (guard against corrupt state)
            if prev is None or not hasattr(prev, "shape"):
                self._status_label.setText("Undo failed — history corrupted.")
                self.undo_btn.setEnabled(len(self._undo_stack) > 0)
                return

            self._working_stack      = prev
            # If more history remains, show as "post-processed"; otherwise raw
            has_more = len(self._undo_stack) > 0
            self._processed          = prev if has_more else None
            self._ref_stretch_params = (
                self._compute_ref_stretch(prev, target=self.preview.stretch_target)
                if has_more else None
            )

            self._orig_btn.setEnabled(has_more)
            self._orig_btn.setChecked(False)
            self._orig_btn.setText("Show Original")
            self.undo_btn.setEnabled(has_more)

            h, w = prev.shape[:2]
            chan  = "RGB" if prev.ndim == 3 else "mono"
            label = (
                f"Post-processed  {w}×{h}  {chan}"
                if has_more else "Original (unprocessed)"
            )
            self.preview.show_data(
                prev, info=label, fixed_stretch_params=self._ref_stretch_params
            )
            steps_left = len(self._undo_stack)
            self._status_label.setText(
                f"Undone.  {steps_left} step{'s' if steps_left != 1 else ''} in history."
            )
            self._compare_label.setText(
                "Choose options on the right, then click  ▶ Apply"
            )
        except Exception as e:
            import traceback
            QMessageBox.critical(
                self,
                "Undo Error",
                f"Undo failed:\n{e}\n\n{traceback.format_exc()}",
            )
            # Reset to a known-good state rather than leaving the UI broken
            self._on_reset()

    # ── Stretch helpers ──────────────────────────────────────────────────────

    @staticmethod
    def _compute_ref_stretch(data: np.ndarray, target: float = 0.20) -> tuple:
        """Compute (shadow_clip, highlight, midtone) from *data* for locked display.

        Args:
            data:   Image array (H×W or H×W×C), float32.
            target: target_background — where the sky median maps to on screen
                    (0–1).  Lower = darker background, more aggressive stretch.
                    Defaults to 0.20 (Normal preset).  Pass
                    ``self.preview.stretch_target`` to respect the user's chosen
                    Stretch combo setting.
        """
        from astrostacker.utils.stretch import _compute_stretch_params
        arr = data.astype(np.float64)
        lum = (
            0.299 * arr[:, :, 0] + 0.587 * arr[:, :, 1] + 0.114 * arr[:, :, 2]
            if arr.ndim == 3 else arr
        )
        return _compute_stretch_params(lum, target_background=target)

    # ── Config builder ───────────────────────────────────────────────────────

    def _build_config(self) -> PipelineConfig:
        return PipelineConfig(
            output_path="",
            auto_crop=self.crop_check.isChecked(),
            remove_gradient=self.gradient_check.isChecked(),
            denoise=self.denoise_check.isChecked(),
            denoise_strength=self.denoise_combo.currentData(),
            deconvolve=self.sharpen_check.isChecked(),
            deconv_strength=self.sharpen_combo.currentData(),
            star_reduce=self.star_reduce_check.isChecked(),
            star_reduce_strength=self.star_slider.value() / 100.0,
            colour_balance=self.colour_check.isChecked(),
            colour_balance_auto=self.colour_auto_check.isChecked(),
            colour_balance_r=self.colour_r_slider.value() / 100.0,
            colour_balance_g=self.colour_g_slider.value() / 100.0,
            colour_balance_b=self.colour_b_slider.value() / 100.0,
            tone_adjust=self.tone_check.isChecked(),
            tone_brightness=float(self.tone_brightness_slider.value()),
            tone_contrast=float(self.tone_contrast_slider.value()),
            tone_saturation=float(self.tone_saturation_slider.value()),
        )

    # ── Apply / Reset ────────────────────────────────────────────────────────

    def _on_apply(self):
        if self._thread is not None and self._thread.isRunning():
            return

        config = self._build_config()
        nothing_selected = not any([
            config.auto_crop, config.remove_gradient,
            config.denoise, config.deconvolve,
            config.star_reduce, config.colour_balance,
            config.tone_adjust,
        ]) and self._crop_rect is None
        if nothing_selected:
            self._status_label.setText(
                "Enable at least one option above before clicking Apply."
            )
            return

        self._set_busy(True)
        self._status_label.setText("Processing — please wait…")

        # Use the working stack (accumulates previous applies) as the input
        raw_for_worker = self._working_stack
        self._pending_had_crop = self._crop_rect is not None
        if self._crop_rect is not None:
            cx, cy, cw, ch = self._crop_rect
            raw_for_worker = self._working_stack[cy:cy + ch, cx:cx + cw]

        # Save a copy of the current working stack for undo
        # (copy, not reference — guards against any in-place mutation downstream)
        self._pending_undo = self._working_stack.copy()

        # Save config so _on_worker_finished knows which steps ran.
        # Stretch params are NOT pre-computed here any more — the finished
        # handler chooses between input-stretch and result-stretch depending
        # on whether the step shifts absolute sky levels.
        self._pending_config = config

        self._worker = _PostProcessWorker(raw_for_worker, config)
        self._thread = QThread()
        self._thread.setStackSize(16 * 1024 * 1024)
        self._worker.moveToThread(self._thread)

        self._thread.started.connect(self._worker.run)
        self._worker.finished.connect(
            self._on_worker_finished, Qt.ConnectionType.QueuedConnection)
        self._worker.error.connect(
            self._on_worker_error, Qt.ConnectionType.QueuedConnection)
        self._worker.finished.connect(self._thread.quit)
        self._worker.error.connect(self._thread.quit)
        self._thread.finished.connect(self._on_thread_done)
        self._thread.start()

    def _on_reset(self):
        if self._thread is not None and self._thread.isRunning():
            return
        self._working_stack      = self._raw_stack
        self._undo_stack         = []
        self._pending_undo       = None
        self._pending_had_crop   = False
        self._pending_config     = None
        self._processed          = None
        self._ref_stretch_params = None
        self._orig_btn.setEnabled(False)
        self._orig_btn.setChecked(False)
        self._orig_btn.setText("Show Original")
        self.undo_btn.setEnabled(False)
        self._compare_label.setText(
            "Choose options on the right, then click  ▶ Apply"
        )
        self.preview.show_data(self._raw_stack, info="Original (unprocessed)")
        self._crop_rect = None
        self._crop_btn.setChecked(False)
        self.preview.set_crop_mode(False)
        self._crop_info_label.hide()
        self._clear_crop_btn.hide()
        self._status_label.setText("Reset to original.")

    @pyqtSlot(np.ndarray)
    def _on_worker_finished(self, result: np.ndarray):
        # Commit the undo snapshot (cap history at 5 steps)
        if self._pending_undo is not None:
            self._undo_stack.append(self._pending_undo)
            if len(self._undo_stack) > 5:
                self._undo_stack.pop(0)
            self._pending_undo = None

        # Clear the manual crop rect now that it is baked into the result
        if self._pending_had_crop:
            self._crop_rect = None
            self._crop_btn.setChecked(False)
            self.preview.set_crop_mode(False)
            self._crop_info_label.hide()
            self._clear_crop_btn.hide()
            self._pending_had_crop = False

        # Advance the working stack to this result
        self._working_stack = result
        self._processed      = result

        # Choose whether to compute stretch from the INPUT or the RESULT.
        #
        # The auto-stretch maps the luminance median to a fixed target
        # brightness.  Any step that changes overall luminance (brightness,
        # contrast) is therefore invisible if we recompute from the result —
        # the new median just gets re-mapped to the same target value.
        #
        # Using the INPUT (pre-apply) stretch instead keeps the shadow/
        # highlight anchored so that a brighter result genuinely looks brighter.
        #
        # Exception: gradient removal and auto colour-balance shift the
        # absolute sky floor dramatically (sky moves from ~1000 ADU to ~0).
        # The old shadow_clip then sits above the new sky level, making the
        # entire image go black.  For those steps we must recompute from the
        # result.
        cfg = self._pending_config
        sky_level_shifts = cfg is not None and (
            cfg.remove_gradient
            or (cfg.colour_balance and cfg.colour_balance_auto)
        )
        if sky_level_shifts:
            # Sky floor moved — recompute so display is not all-black.
            ref_data = result
        else:
            # All other steps (tone, sharpen, denoise, star reduction, manual
            # colour balance): use the pre-apply state so luminance / colour
            # changes remain visible.
            ref_data = self._undo_stack[-1] if self._undo_stack else result
        self._ref_stretch_params = self._compute_ref_stretch(
            ref_data, target=self.preview.stretch_target
        )
        self._pending_config = None

        h, w = result.shape[:2]
        chan  = "RGB" if result.ndim == 3 else "mono"
        self.preview.show_data(
            result,
            info=f"Post-processed  {w}×{h}  {chan}",
            fixed_stretch_params=self._ref_stretch_params,
        )
        steps_done = len(self._undo_stack)
        self._status_label.setText(
            f"✓  Done ({steps_done} step{'s' if steps_done != 1 else ''} applied)."
            "  Use Undo to step back or Reset to start over."
        )
        self._orig_btn.setEnabled(True)
        self._orig_btn.setChecked(False)
        self._orig_btn.setText("Show Original")
        self._compare_label.setText(
            "Showing post-processed result.  Use 'Show Original' to compare."
        )

    @pyqtSlot(str)
    def _on_worker_error(self, message: str):
        # Discard the pending undo snapshot — nothing was committed
        self._pending_undo    = None
        self._pending_had_crop = False
        self._status_label.setText("Processing failed — see error dialog.")
        QMessageBox.critical(self, "Post-Processing Error", message)

    def _on_thread_done(self):
        self._set_busy(False)
        self._thread = None
        self._worker = None

    def _set_busy(self, busy: bool):
        self.apply_btn.setEnabled(not busy)
        self.reset_btn.setEnabled(not busy)
        if not busy:
            self.undo_btn.setEnabled(len(self._undo_stack) > 0)
        else:
            self.undo_btn.setEnabled(False)

    # ── Save ─────────────────────────────────────────────────────────────────

    def _save(self, fmt: str):
        # Save the latest working stack (may be partially processed)
        data = self._working_stack

        fmt = fmt.lower()
        if fmt == "fits":
            filter_str = "FITS Files (*.fits);;XISF Files (*.xisf)"
        elif fmt == "tiff":
            filter_str = "TIFF Image (*.tiff *.tif)"
        elif fmt in ("jpeg", "jpg"):
            filter_str = "JPEG Image (*.jpg *.jpeg)"
            fmt = "jpeg"
        else:
            filter_str = "PNG Image (*.png)"
            fmt = "png"

        path, _ = QFileDialog.getSaveFileName(self, "Save Image", "", filter_str)
        if not path:
            self.raise_()
            self.activateWindow()
            return

        p = Path(path)
        if not p.suffix:
            ext_map = {"fits": ".fits", "tiff": ".tiff", "jpeg": ".jpg", "png": ".png"}
            path = str(p) + ext_map.get(fmt, ".fits")

        try:
            if fmt == "fits":
                from astrostacker.io.loader import save_image
                save_image(path, data)
            else:
                from astrostacker.utils.stretch import auto_stretch
                from astrostacker.utils.image_utils import numpy_to_qpixmap
                pixmap = numpy_to_qpixmap(auto_stretch(data))
                if not pixmap.save(path):
                    raise RuntimeError("QPixmap.save() failed — check path and format.")
            QMessageBox.information(self, "Saved", f"Image saved to:\n{path}")
        except Exception as e:
            QMessageBox.critical(self, "Save Error", str(e))
        finally:
            self.raise_()
            self.activateWindow()

    # ── Cleanup ──────────────────────────────────────────────────────────────

    def closeEvent(self, event):
        if self._thread is not None and self._thread.isRunning():
            self._thread.quit()
            self._thread.wait(3000)
        super().closeEvent(event)
