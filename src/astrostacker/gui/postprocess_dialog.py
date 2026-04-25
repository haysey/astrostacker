"""Interactive post-processing window for AstroStacker.

Opens with any stacked image (from a pipeline run or loaded from disk),
lets the user apply and preview post-processing steps, then save the result.

Layout
------
  ┌──────────────────────────────┬────────────────┐
  │                              │  CONTROLS      │
  │   Large image preview        │  (scroll)      │
  │   (stretch + zoom controls)  │                │
  │                              │  [▶  APPLY]    │
  │   [Processed] [Original]     │  [  Reset  ]   │
  │   toggle buttons             │  ──────────    │
  │                              │  [Save FITS]   │
  │                              │  [Save TIFF]   │
  │                              │  [Save JPEG]   │
  │                              │  [Save PNG ]   │
  │                              │  [  Close  ]   │
  └──────────────────────────────┴────────────────┘

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
from PyQt6.QtCore import QObject, QThread, Qt, pyqtSignal, pyqtSlot
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSlider,
    QSpinBox,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from astrostacker.gui.preview_panel import PreviewPanel
from astrostacker.pipeline.pipeline import Pipeline, PipelineConfig


# ── Background worker ──────────────────────────────────────────────────────

class _PostProcessWorker(QObject):
    """Runs Pipeline._run_postprocessing() on a background QThread.

    Emits finished(result) on success or error(message) on failure.
    @pyqtSlot ensures PyQt6 creates a proper cross-thread queued invocation
    when thread.started connects to run().
    """

    finished = pyqtSignal(np.ndarray)
    error = pyqtSignal(str)

    def __init__(self, raw_stack: np.ndarray, config: PipelineConfig):
        super().__init__()
        self._raw_stack = raw_stack
        self._config = config

    @pyqtSlot()
    def run(self):
        try:
            pipeline = Pipeline(self._config)
            # _run_postprocessing operates on a copy; output_path="" is safe
            # because this method never writes to disk itself.
            result = pipeline._run_postprocessing(self._raw_stack.copy())
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(f"{type(e).__name__}: {e}\n{traceback.format_exc()}")


# ── Dialog ─────────────────────────────────────────────────────────────────

class PostProcessDialog(QDialog):
    """Large-preview interactive post-processing window.

    Args:
        raw_stack:  The pre-post-processing image as float32 ndarray.
                    This is NEVER modified — every Apply starts from it.
        parent:     Parent widget so the macOS dark stylesheet propagates.
    """

    def __init__(
        self,
        raw_stack: np.ndarray,
        parent=None,
    ):
        super().__init__(parent)
        self.setWindowTitle("Post-Processing")
        self.setMinimumSize(1200, 820)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setWindowFlag(Qt.WindowType.Window)

        self._raw_stack: np.ndarray = raw_stack          # never modified
        self._processed: np.ndarray | None = None        # latest Apply result
        self._showing_original = False                   # toggle state
        self._worker: _PostProcessWorker | None = None
        self._thread: QThread | None = None
        self._crop_rect: tuple[int, int, int, int] | None = None  # x, y, w, h in image pixels
        self._ref_stretch_params: tuple | None = None  # locked display scale for before/after

        self._setup_ui()

        # Show the raw stack right away
        self.preview.show_data(raw_stack, info="Original (unprocessed)")
        self.preview.crop_selected.connect(self._on_crop_selected)

    # ── UI ─────────────────────────────────────────────────────────────────

    def _setup_ui(self):
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Left: large preview ─────────────────────────────────────────────
        left = QWidget()
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
        toggle_layout = QHBoxLayout(toggle_bar)
        toggle_layout.setContentsMargins(14, 6, 14, 6)
        toggle_layout.setSpacing(8)

        self._orig_btn = QPushButton("Show Original")
        self._orig_btn.setObjectName("secondaryButton")
        self._orig_btn.setEnabled(False)   # enabled after first Apply
        self._orig_btn.setCheckable(True)
        self._orig_btn.toggled.connect(self._on_toggle_original)
        toggle_layout.addWidget(self._orig_btn)

        self._compare_label = QLabel(
            "Click  ▶ Apply  on the right to preview post-processing changes"
        )
        self._compare_label.setStyleSheet(
            "color: rgba(255,149,0,0.80); font-size: 12px; font-weight: 600;"
        )
        toggle_layout.addWidget(self._compare_label, stretch=1)

        self._crop_btn = QPushButton("✂  Crop")
        self._crop_btn.setObjectName("secondaryButton")
        self._crop_btn.setCheckable(True)
        self._crop_btn.setToolTip(
            "Draw a rectangle on the image to select the crop region.\n"
            "Click Apply after setting the crop to preview the result."
        )
        self._crop_btn.toggled.connect(self._on_crop_toggled)
        toggle_layout.addWidget(self._crop_btn)

        self._crop_info_label = QLabel("")
        self._crop_info_label.setStyleSheet(
            "color: rgba(255,149,0,0.85); font-size: 11px; font-weight: 600;"
        )
        self._crop_info_label.hide()
        toggle_layout.addWidget(self._crop_info_label)

        self._clear_crop_btn = QPushButton("✕ Clear")
        self._clear_crop_btn.setObjectName("secondaryButton")
        self._clear_crop_btn.setToolTip("Remove the crop selection.")
        self._clear_crop_btn.clicked.connect(self._on_clear_crop)
        self._clear_crop_btn.hide()
        toggle_layout.addWidget(self._clear_crop_btn)

        left_layout.addWidget(toggle_bar)
        root.addWidget(left, stretch=3)

        # ── Right: controls + action buttons ───────────────────────────────
        right = QWidget()
        right.setObjectName("ppRight")
        right.setFixedWidth(330)
        right.setStyleSheet(
            "QWidget#ppRight {"
            "  background-color: rgba(12, 12, 22, 0.95);"
            "  border-left: 1px solid rgba(255,255,255,0.08);"
            "}"
        )
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)

        # Title strip
        title_bar = QWidget()
        title_bar.setStyleSheet(
            "background-color: rgba(20, 20, 35, 0.95);"
            "border-bottom: 1px solid rgba(255,255,255,0.10);"
        )
        title_bar_layout = QHBoxLayout(title_bar)
        title_bar_layout.setContentsMargins(16, 10, 16, 10)
        title_lbl = QLabel("Post-Processing")
        title_lbl.setStyleSheet(
            "font-size: 14px; font-weight: 700; color: #ff9500;"
            "letter-spacing: 0.3px;"
        )
        title_bar_layout.addWidget(title_lbl)
        right_layout.addWidget(title_bar)

        # Scroll area for controls
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        ctrl_container = QWidget()
        ctrl_layout = QVBoxLayout(ctrl_container)
        ctrl_layout.setContentsMargins(12, 8, 12, 8)
        ctrl_layout.setSpacing(6)

        # ── Cleanup ──────────────────────────────────────────────────────
        self._add_group_header(ctrl_layout, "CLEANUP")

        self.crop_check = QCheckBox("Auto-crop edges")
        self.crop_check.setToolTip(
            "Trim dark borders created by frame alignment.\n"
            "Safe to enable for any stacked image."
        )
        ctrl_layout.addWidget(self.crop_check)

        self.gradient_check = QCheckBox("Remove gradient")
        self.gradient_check.setToolTip(
            "Fit and subtract a smooth sky background surface.\n"
            "Corrects light pollution and vignetting."
        )
        ctrl_layout.addWidget(self.gradient_check)

        ctrl_layout.addSpacing(4)

        # ── Enhance ──────────────────────────────────────────────────────
        self._add_group_header(ctrl_layout, "ENHANCE")

        sharpen_row = QHBoxLayout()
        sharpen_row.setSpacing(8)
        sharpen_row.setContentsMargins(0, 0, 0, 0)
        self.sharpen_check = QCheckBox("Sharpen")
        self.sharpen_check.setToolTip(
            "PSF-informed sharpening (Richardson-Lucy).\n"
            "Best on well-exposed stacks."
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
        sharpen_row.addWidget(self.sharpen_combo)
        sharpen_row.addStretch()
        ctrl_layout.addLayout(sharpen_row)

        denoise_row = QHBoxLayout()
        denoise_row.setSpacing(8)
        denoise_row.setContentsMargins(0, 0, 0, 0)
        self.denoise_check = QCheckBox("Denoise")
        self.denoise_check.setToolTip(
            "Non-Local Means denoising. Great for galaxies and clusters.\n"
            "Avoid on large emission nebulae — can smear real structure."
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
        denoise_row.addWidget(self.denoise_combo)
        denoise_row.addStretch()
        ctrl_layout.addLayout(denoise_row)

        ctrl_layout.addSpacing(4)

        # ── Stars ─────────────────────────────────────────────────────────
        self._add_group_header(ctrl_layout, "STARS")

        self.star_reduce_check = QCheckBox("Reduce stars")
        self.star_reduce_check.setToolTip(
            "Reduce star brightness using morphological detection\n"
            "(no AI, no model files).\n"
            "Drag the slider, click Apply, compare with original."
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

        ctrl_layout.addSpacing(4)

        # ── Colour Balance ─────────────────────────────────────────────────
        self._add_group_header(ctrl_layout, "COLOUR BALANCE")

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
            "Sample sky from image corners and neutralise any tint."
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
            # Bidirectional sync (blockSignals prevents feedback loops)
            slider.valueChanged.connect(
                lambda v, s=spinbox: (s.blockSignals(True), s.setValue(v / 100.0), s.blockSignals(False))
            )
            spinbox.valueChanged.connect(
                lambda v, sl=slider: (sl.blockSignals(True), sl.setValue(round(v * 100)), sl.blockSignals(False))
            )
            row.addWidget(slider)
            row.addWidget(spinbox)
            ctrl_layout.addLayout(row)
            setattr(self, f"colour_{attr}_slider", slider)
            setattr(self, f"colour_{attr}_spinbox", spinbox)

        ctrl_layout.addStretch()

        scroll.setWidget(ctrl_container)
        right_layout.addWidget(scroll, stretch=1)

        # ── Status label ────────────────────────────────────────────────────
        self._status_label = QLabel("")
        self._status_label.setWordWrap(True)
        self._status_label.setStyleSheet(
            "color: rgba(255,255,255,0.55); font-size: 11px;"
            "padding: 4px 14px 2px 14px;"
        )
        self._status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        right_layout.addWidget(self._status_label)

        # ── Action buttons ──────────────────────────────────────────────────
        # Separate 1px divider — avoids CSS border-top on actions which can
        # cause Qt to clip child widgets near the top of the container.
        actions_hr = QWidget()
        actions_hr.setFixedHeight(1)
        actions_hr.setStyleSheet("background-color: rgba(255,255,255,0.08);")
        right_layout.addWidget(actions_hr)

        actions = QWidget()
        actions.setStyleSheet("background-color: rgba(12, 12, 22, 0.98);")
        actions_layout = QVBoxLayout(actions)
        actions_layout.setContentsMargins(12, 12, 12, 12)
        actions_layout.setSpacing(6)

        self.apply_btn = QPushButton("▶   Apply")
        self.apply_btn.setObjectName("primaryButton")
        self.apply_btn.setFixedHeight(44)
        self.apply_btn.setToolTip(
            "Run the selected post-processing steps and update the preview.\n"
            "The original image is always preserved — click Reset to go back.\n"
            "Adjust settings and click Apply again to refine."
        )
        self.apply_btn.clicked.connect(self._on_apply)
        actions_layout.addWidget(self.apply_btn)

        self.reset_btn = QPushButton("Reset to Original")
        self.reset_btn.setObjectName("secondaryButton")
        self.reset_btn.setToolTip("Restore the unprocessed original image.")
        self.reset_btn.clicked.connect(self._on_reset)
        actions_layout.addWidget(self.reset_btn)

        # Divider
        divider = QWidget()
        divider.setFixedHeight(1)
        divider.setStyleSheet("background-color: rgba(255,255,255,0.08);")
        actions_layout.addSpacing(4)
        actions_layout.addWidget(divider)
        actions_layout.addSpacing(4)

        for label, fmt, tip in [
            ("Save FITS…",  "fits",  "Full 32-bit float — for further processing"),
            ("Save TIFF…",  "tiff",  "Stretched 8-bit TIFF — for printing/Photoshop"),
            ("Save JPEG…",  "jpeg",  "Stretched JPEG — for sharing online"),
            ("Save PNG…",   "png",   "Stretched PNG — lossless web format"),
        ]:
            btn = QPushButton(label)
            btn.setObjectName("secondaryButton")
            btn.setToolTip(tip)
            btn.clicked.connect(lambda checked, f=fmt: self._save(f))
            actions_layout.addWidget(btn)

        actions_layout.addSpacing(4)
        close_btn = QPushButton("Close")
        close_btn.setObjectName("secondaryButton")
        close_btn.clicked.connect(self.close)
        actions_layout.addWidget(close_btn)

        right_layout.addWidget(actions)
        root.addWidget(right)

    def _add_group_header(self, layout: QVBoxLayout, text: str):
        lbl = QLabel(text)
        lbl.setStyleSheet(
            "color: #ff9500; font-size: 10px; font-weight: 700;"
            "letter-spacing: 1px; padding-top: 6px; padding-bottom: 2px;"
        )
        layout.addWidget(lbl)

    # ── Toggle helpers ──────────────────────────────────────────────────────

    def _on_sharpen_toggled(self, checked: bool):
        self.sharpen_combo.setEnabled(checked)

    def _on_denoise_toggled(self, checked: bool):
        self.denoise_combo.setEnabled(checked)

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
        manual = enabled and not checked
        for attr in ("r", "g", "b"):
            getattr(self, f"colour_{attr}_slider").setEnabled(manual)
            getattr(self, f"colour_{attr}_spinbox").setEnabled(manual)

    def _on_toggle_original(self, checked: bool):
        self._showing_original = checked
        self._orig_btn.setText("Show Processed" if checked else "Show Original")
        if checked:
            self.preview.show_data(self._raw_stack, info="Original (unprocessed)")
        elif self._processed is not None:
            h, w = self._processed.shape[:2]
            chan = "RGB" if self._processed.ndim == 3 else "mono"
            self.preview.show_data(
                self._processed,
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
                "Click  ▶ Apply  on the right to preview post-processing changes"
            )

    def _on_crop_selected(self, x: int, y: int, w: int, h: int):
        """Called when the user finishes drawing a crop rectangle."""
        self._crop_rect = (x, y, w, h)
        self._crop_btn.setChecked(False)          # exit crop mode automatically
        self.preview.set_crop_mode(False)
        self._crop_info_label.setText(f"Crop: {w}×{h} px")
        self._crop_info_label.show()
        self._clear_crop_btn.show()
        self._compare_label.setText(
            f"Crop set ({w}×{h} px at {x},{y}).  Click ▶ Apply to preview."
        )

    def _on_clear_crop(self):
        """Remove the active crop selection."""
        self._crop_rect = None
        self._crop_btn.setChecked(False)
        self.preview.set_crop_mode(False)
        self._crop_info_label.hide()
        self._clear_crop_btn.hide()
        self.preview.show_data(self._raw_stack, info="Original (unprocessed)")
        self._compare_label.setText(
            "Click  ▶ Apply  on the right to preview post-processing changes"
        )

    # ── Stretch helpers ─────────────────────────────────────────────────────

    @staticmethod
    def _compute_ref_stretch(data: np.ndarray) -> tuple:
        """Compute luminance-based stretch params from *data* for locked display.

        Using these params on the processed result (instead of auto-stretching
        it) keeps the display scale identical to the original, so changes like
        star reduction are visible rather than being silently compensated by
        the auto-stretch renormalisation.
        """
        from astrostacker.utils.stretch import _compute_stretch_params
        arr = data.astype(np.float64)
        if arr.ndim == 3:
            lum = 0.299 * arr[:, :, 0] + 0.587 * arr[:, :, 1] + 0.114 * arr[:, :, 2]
        else:
            lum = arr
        return _compute_stretch_params(lum, target_background=0.25)

    # ── Config builder ──────────────────────────────────────────────────────

    def _build_config(self) -> PipelineConfig:
        return PipelineConfig(
            output_path="",   # dialog saves separately — never writes to disk
            auto_crop=self.crop_check.isChecked(),
            remove_gradient=self.gradient_check.isChecked(),
            deconvolve=self.sharpen_check.isChecked(),
            deconv_strength=self.sharpen_combo.currentData(),
            denoise=self.denoise_check.isChecked(),
            denoise_strength=self.denoise_combo.currentData(),
            star_reduce=self.star_reduce_check.isChecked(),
            star_reduce_strength=self.star_slider.value() / 100.0,
            colour_balance=self.colour_check.isChecked(),
            colour_balance_auto=self.colour_auto_check.isChecked(),
            colour_balance_r=self.colour_r_slider.value() / 100.0,
            colour_balance_g=self.colour_g_slider.value() / 100.0,
            colour_balance_b=self.colour_b_slider.value() / 100.0,
        )

    # ── Apply / Reset ───────────────────────────────────────────────────────

    def _on_apply(self):
        """Launch post-processing on a background thread."""
        if self._thread is not None and self._thread.isRunning():
            return

        # Make sure at least one option is enabled (or a crop region is set —
        # Apply with only a crop still produces a useful cropped preview).
        config = self._build_config()
        nothing_selected = not any([
            config.auto_crop, config.remove_gradient,
            config.deconvolve, config.denoise,
            config.star_reduce, config.colour_balance,
        ]) and self._crop_rect is None
        if nothing_selected:
            self._status_label.setText(
                "Enable at least one option above before clicking Apply."
            )
            return

        self._set_busy(True)
        self._status_label.setText("Processing — please wait…")

        # Apply crop region if one has been drawn
        raw_for_worker = self._raw_stack
        if self._crop_rect is not None:
            cx, cy, cw, ch = self._crop_rect
            raw_for_worker = self._raw_stack[cy:cy + ch, cx:cx + cw]

        # Lock the display scale to the original (pre-processing) data so that
        # the processed preview is shown on the same axis.  Without this the
        # auto-stretch re-normalises star-reduced data back to the same
        # brightness, making the effect invisible in the preview.
        self._ref_stretch_params = self._compute_ref_stretch(raw_for_worker)

        self._worker = _PostProcessWorker(raw_for_worker, config)
        self._thread = QThread()
        self._thread.setStackSize(16 * 1024 * 1024)
        self._worker.moveToThread(self._thread)

        # Use explicit QueuedConnection so the slots always run on the
        # main thread regardless of which thread emits the signal.
        self._thread.started.connect(self._worker.run)
        self._worker.finished.connect(
            self._on_worker_finished,
            Qt.ConnectionType.QueuedConnection,
        )
        self._worker.error.connect(
            self._on_worker_error,
            Qt.ConnectionType.QueuedConnection,
        )
        self._worker.finished.connect(self._thread.quit)
        self._worker.error.connect(self._thread.quit)
        self._thread.finished.connect(self._on_thread_done)

        self._thread.start()

    def _on_reset(self):
        if self._thread is not None and self._thread.isRunning():
            return
        self._processed = None
        self._ref_stretch_params = None
        self._orig_btn.setEnabled(False)
        self._orig_btn.setChecked(False)
        self._orig_btn.setText("Show Original")
        self._compare_label.setText(
            "Click  ▶ Apply  on the right to preview post-processing changes"
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
        self._processed = result
        h, w = result.shape[:2]
        chan = "RGB" if result.ndim == 3 else "mono"
        info = f"Post-processed  {w}×{h}  {chan}"
        # Show with the locked stretch so changes are visible vs original
        self.preview.show_data(result, info=info,
                               fixed_stretch_params=self._ref_stretch_params)
        self._status_label.setText("✓  Done — compare with original using the button.")
        self._orig_btn.setEnabled(True)
        self._orig_btn.setChecked(False)
        self._orig_btn.setText("Show Original")
        self._compare_label.setText(
            "Showing post-processed result.  Use 'Show Original' to compare."
        )

    @pyqtSlot(str)
    def _on_worker_error(self, message: str):
        self._status_label.setText("Processing failed — see error dialog.")
        QMessageBox.critical(self, "Post-Processing Error", message)

    def _on_thread_done(self):
        self._set_busy(False)
        self._thread = None
        self._worker = None

    def _set_busy(self, busy: bool):
        self.apply_btn.setEnabled(not busy)
        self.reset_btn.setEnabled(not busy)

    # ── Save ───────────────────────────────────────────────────────────────

    def _save(self, fmt: str):
        """Save the current image (processed if available, else original)."""
        data = self._processed if self._processed is not None else self._raw_stack

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

    # ── Cleanup ─────────────────────────────────────────────────────────────

    def closeEvent(self, event):
        if self._thread is not None and self._thread.isRunning():
            self._thread.quit()
            self._thread.wait(3000)
        super().closeEvent(event)
