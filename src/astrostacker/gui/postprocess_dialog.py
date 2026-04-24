"""Dedicated post-processing window with large image preview and save options.

Open via Settings panel → Post-Processing → "Open Image for Post-Processing…"
or automatically after loading any FITS file.  The dialog lets the user:

  • Apply auto-crop, gradient removal, sharpening, denoise, star reduction,
    and colour balance interactively without re-stacking.
  • Preview the result at full size with zoom and stretch controls.
  • Save the processed image as FITS (full precision) or a stretched
    8-bit raster (TIFF / JPEG / PNG) for sharing.

Processing runs on a background QThread so the UI stays responsive.
"""

from __future__ import annotations

import traceback
from pathlib import Path

import numpy as np
from PyQt6.QtCore import QObject, QThread, Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSlider,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from astrostacker.gui.preview_panel import PreviewPanel
from astrostacker.pipeline.pipeline import Pipeline, PipelineConfig


# ── Background worker ───────────────────────────────────────────────────────

class _PostProcessWorker(QObject):
    """Runs Pipeline._run_postprocessing on a background thread.

    Does NOT call pipeline.reprocess() (which would also try to save to disk).
    Instead we call _run_postprocessing() directly so the dialog manages saving.
    """

    finished = pyqtSignal(np.ndarray)
    error = pyqtSignal(str)

    def __init__(self, raw_stack: np.ndarray, config: PipelineConfig):
        super().__init__()
        self._raw_stack = raw_stack
        self._config = config

    def run(self):
        try:
            pipeline = Pipeline(self._config)
            # _run_postprocessing works on a copy of the raw stack and uses
            # pipeline.config for all options.  measured_fwhm falls back to
            # 2.5 px when not available, which is fine for interactive use.
            result = pipeline._run_postprocessing(self._raw_stack.copy())
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(f"{type(e).__name__}: {e}\n{traceback.format_exc()}")


# ── Dialog ──────────────────────────────────────────────────────────────────

class PostProcessDialog(QDialog):
    """Large-preview interactive post-processing window.

    Args:
        raw_stack:      The pre-post-processing image (float32 ndarray).
                        This is kept unchanged throughout the session — every
                        Apply starts from this original.
        initial_config: PipelineConfig from the main window used to pre-fill
                        the controls.  Pass None to use defaults.
        parent:         Parent widget (main window) so the dialog inherits
                        the macOS dark stylesheet automatically.
    """

    def __init__(
        self,
        raw_stack: np.ndarray,
        initial_config: PipelineConfig | None = None,
        parent=None,
    ):
        super().__init__(parent)
        self.setWindowTitle("Post-Processing")
        self.setMinimumSize(1100, 780)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setWindowFlag(Qt.WindowType.Window)   # separate macOS window

        self._raw_stack: np.ndarray = raw_stack          # never modified
        self._current: np.ndarray = raw_stack.copy()     # latest result
        self._worker: _PostProcessWorker | None = None
        self._thread: QThread | None = None

        self._setup_ui()
        self._populate_from_config(initial_config)

        # Show the raw stack immediately so the user sees something straight away
        self.preview.show_data(raw_stack, info="Original (unprocessed)")

    # ── UI construction ─────────────────────────────────────────────────────

    def _setup_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.setChildrenCollapsible(False)
        splitter.setHandleWidth(2)

        # ── Top: large image preview ────────────────────────────────────────
        self.preview = PreviewPanel()
        splitter.addWidget(self.preview)

        # ── Bottom: controls + action buttons ──────────────────────────────
        bottom = QWidget()
        bottom.setObjectName("ppDialogBottom")
        bottom.setStyleSheet(
            "QWidget#ppDialogBottom {"
            "  background-color: rgba(15, 15, 25, 0.90);"
            "  border-top: 1px solid rgba(255, 255, 255, 0.08);"
            "}"
        )
        bottom_root = QVBoxLayout(bottom)
        bottom_root.setContentsMargins(14, 10, 14, 12)
        bottom_root.setSpacing(10)

        # ── Four-column controls row ────────────────────────────────────────
        ctrl_row = QHBoxLayout()
        ctrl_row.setSpacing(12)

        # Column 1 — Cleanup
        col1 = QGroupBox("Cleanup")
        col1_layout = QVBoxLayout(col1)
        col1_layout.setSpacing(6)
        col1_layout.setContentsMargins(10, 22, 10, 8)

        self.crop_check = QCheckBox("Auto-crop edges")
        self.crop_check.setToolTip(
            "Trim the dark borders left by frame alignment.\n"
            "Gives a clean rectangular image."
        )
        col1_layout.addWidget(self.crop_check)

        self.gradient_check = QCheckBox("Remove gradient")
        self.gradient_check.setToolTip(
            "Fit and subtract a smooth sky background surface.\n"
            "Corrects light pollution tint and vignetting.\n"
            "Works best after Auto-crop clears the alignment borders."
        )
        col1_layout.addWidget(self.gradient_check)
        col1_layout.addStretch()

        ctrl_row.addWidget(col1)

        # Column 2 — Enhance
        col2 = QGroupBox("Enhance")
        col2_layout = QVBoxLayout(col2)
        col2_layout.setSpacing(6)
        col2_layout.setContentsMargins(10, 22, 10, 8)

        sharpen_row = QHBoxLayout()
        sharpen_row.setSpacing(8)
        self.sharpen_check = QCheckBox("Sharpen")
        self.sharpen_check.setToolTip(
            "Sharpens the image using the star profile (PSF).\n"
            "Best on well-exposed stacks with good SNR."
        )
        self.sharpen_check.toggled.connect(self._on_sharpen_toggled)
        sharpen_row.addWidget(self.sharpen_check)
        self.sharpen_combo = QComboBox()
        self.sharpen_combo.addItem("Light", "light")
        self.sharpen_combo.addItem("Medium", "medium")
        self.sharpen_combo.addItem("Strong", "strong")
        self.sharpen_combo.setCurrentIndex(1)
        self.sharpen_combo.setEnabled(False)
        self.sharpen_combo.setMinimumWidth(90)
        sharpen_row.addWidget(self.sharpen_combo)
        sharpen_row.addStretch()
        col2_layout.addLayout(sharpen_row)

        denoise_row = QHBoxLayout()
        denoise_row.setSpacing(8)
        self.denoise_check = QCheckBox("Denoise")
        self.denoise_check.setToolTip(
            "Non-Local Means denoising. Works best on compact targets\n"
            "(galaxies, clusters). May smear large nebulae — try without first."
        )
        self.denoise_check.toggled.connect(self._on_denoise_toggled)
        denoise_row.addWidget(self.denoise_check)
        self.denoise_combo = QComboBox()
        self.denoise_combo.addItem("Light", "light")
        self.denoise_combo.addItem("Medium", "medium")
        self.denoise_combo.addItem("Strong", "strong")
        self.denoise_combo.setCurrentIndex(1)
        self.denoise_combo.setEnabled(False)
        self.denoise_combo.setMinimumWidth(90)
        denoise_row.addWidget(self.denoise_combo)
        denoise_row.addStretch()
        col2_layout.addLayout(denoise_row)

        col2_layout.addStretch()
        ctrl_row.addWidget(col2)

        # Column 3 — Stars
        col3 = QGroupBox("Stars")
        col3_layout = QVBoxLayout(col3)
        col3_layout.setSpacing(6)
        col3_layout.setContentsMargins(10, 22, 10, 8)

        self.star_reduce_check = QCheckBox("Reduce stars")
        self.star_reduce_check.setToolTip(
            "Reduce star brightness using high-pass detection + Gaussian masks.\n"
            "No AI or model files required.\n"
            "Adjust the strength slider and click Apply to preview."
        )
        self.star_reduce_check.toggled.connect(self._on_star_reduce_toggled)
        col3_layout.addWidget(self.star_reduce_check)

        star_slider_row = QHBoxLayout()
        star_slider_row.setSpacing(6)
        self.star_slider = QSlider(Qt.Orientation.Horizontal)
        self.star_slider.setRange(0, 100)
        self.star_slider.setValue(50)
        self.star_slider.setEnabled(False)
        self.star_slider.valueChanged.connect(
            lambda v: self.star_pct_label.setText(f"{v}%")
        )
        star_slider_row.addWidget(self.star_slider)
        self.star_pct_label = QLabel("50%")
        self.star_pct_label.setFixedWidth(36)
        star_slider_row.addWidget(self.star_pct_label)
        col3_layout.addLayout(star_slider_row)

        col3_layout.addStretch()
        ctrl_row.addWidget(col3)

        # Column 4 — Colour Balance
        col4 = QGroupBox("Colour Balance")
        col4_layout = QVBoxLayout(col4)
        col4_layout.setSpacing(4)
        col4_layout.setContentsMargins(10, 22, 10, 8)

        self.colour_check = QCheckBox("Enable colour balance")
        self.colour_check.setToolTip(
            "Correct colour cast from light pollution, airglow, or\n"
            "Bayer sensor green-channel dominance.\n"
            "No-op on mono images."
        )
        self.colour_check.toggled.connect(self._on_colour_balance_toggled)
        col4_layout.addWidget(self.colour_check)

        self.colour_auto_check = QCheckBox("Auto (recommended)")
        self.colour_auto_check.setChecked(True)
        self.colour_auto_check.setEnabled(False)
        self.colour_auto_check.setToolTip(
            "Sample sky from image corners and make it neutral grey.\n"
            "Works well for most light-polluted skies."
        )
        self.colour_auto_check.toggled.connect(self._on_colour_auto_toggled)
        col4_layout.addWidget(self.colour_auto_check)

        # R / G / B sliders (enabled only when Auto is off)
        for colour, attr in [("R", "r"), ("G", "g"), ("B", "b")]:
            row = QHBoxLayout()
            row.setSpacing(6)
            lbl = QLabel(colour)
            lbl.setFixedWidth(14)
            row.addWidget(lbl)
            slider = QSlider(Qt.Orientation.Horizontal)
            slider.setRange(50, 200)   # 0.50× – 2.00×
            slider.setValue(100)       # 1.00× default
            slider.setEnabled(False)
            slider.setMinimumWidth(70)
            val_lbl = QLabel("1.00×")
            val_lbl.setFixedWidth(44)
            slider.valueChanged.connect(
                lambda v, l=val_lbl: l.setText(f"{v / 100:.2f}×")
            )
            row.addWidget(slider)
            row.addWidget(val_lbl)
            col4_layout.addLayout(row)
            setattr(self, f"colour_{attr}_slider", slider)
            setattr(self, f"colour_{attr}_label", val_lbl)

        ctrl_row.addWidget(col4)
        bottom_root.addLayout(ctrl_row)

        # ── Action / Save button row ────────────────────────────────────────
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)

        self.apply_btn = QPushButton("▶  Apply")
        self.apply_btn.setToolTip(
            "Apply the selected post-processing steps.\n"
            "Re-click with different settings to refine — the original\n"
            "unprocessed image is never overwritten."
        )
        self.apply_btn.clicked.connect(self._on_apply)
        btn_row.addWidget(self.apply_btn)

        self.reset_btn = QPushButton("Reset")
        self.reset_btn.setObjectName("secondaryButton")
        self.reset_btn.setToolTip("Discard all changes and show the original image.")
        self.reset_btn.clicked.connect(self._on_reset)
        btn_row.addWidget(self.reset_btn)

        self._status_label = QLabel("")
        self._status_label.setStyleSheet(
            "color: rgba(255,255,255,0.55); font-size: 12px;"
        )
        btn_row.addWidget(self._status_label, stretch=1)

        # Save buttons
        save_fits_btn = QPushButton("Save FITS…")
        save_fits_btn.setObjectName("secondaryButton")
        save_fits_btn.setToolTip(
            "Save as 32-bit float FITS — full precision, ideal for\n"
            "further processing in PixInsight, AstroPixelProcessor, etc."
        )
        save_fits_btn.clicked.connect(lambda: self._save("fits"))
        btn_row.addWidget(save_fits_btn)

        save_tiff_btn = QPushButton("Save TIFF…")
        save_tiff_btn.setObjectName("secondaryButton")
        save_tiff_btn.setToolTip(
            "Save as a stretched 8-bit TIFF — good for printing or\n"
            "editing in Photoshop / Lightroom."
        )
        save_tiff_btn.clicked.connect(lambda: self._save("tiff"))
        btn_row.addWidget(save_tiff_btn)

        save_jpg_btn = QPushButton("Save JPEG…")
        save_jpg_btn.setObjectName("secondaryButton")
        save_jpg_btn.setToolTip(
            "Save as a stretched JPEG — compact file size, ideal for\n"
            "sharing on social media or astronomy forums."
        )
        save_jpg_btn.clicked.connect(lambda: self._save("jpeg"))
        btn_row.addWidget(save_jpg_btn)

        save_png_btn = QPushButton("Save PNG…")
        save_png_btn.setObjectName("secondaryButton")
        save_png_btn.setToolTip(
            "Save as a stretched PNG — lossless, good for web use."
        )
        save_png_btn.clicked.connect(lambda: self._save("png"))
        btn_row.addWidget(save_png_btn)

        close_btn = QPushButton("Close")
        close_btn.setObjectName("secondaryButton")
        close_btn.clicked.connect(self.close)
        btn_row.addWidget(close_btn)

        bottom_root.addLayout(btn_row)
        splitter.addWidget(bottom)

        # Give the preview most of the space; controls are fixed-ish at bottom
        splitter.setStretchFactor(0, 4)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([520, 260])

        root.addWidget(splitter)

    # ── Initial value population ────────────────────────────────────────────

    def _populate_from_config(self, config: PipelineConfig | None):
        """Pre-fill controls from a PipelineConfig (from the main window)."""
        if config is None:
            return

        _str_to_idx = {"light": 0, "medium": 1, "strong": 2}

        self.crop_check.setChecked(config.auto_crop)
        self.gradient_check.setChecked(config.remove_gradient)

        self.sharpen_check.setChecked(config.deconvolve)
        self.sharpen_combo.setCurrentIndex(
            _str_to_idx.get(config.deconv_strength, 1)
        )
        self.sharpen_combo.setEnabled(config.deconvolve)

        self.denoise_check.setChecked(config.denoise)
        self.denoise_combo.setCurrentIndex(
            _str_to_idx.get(config.denoise_strength, 1)
        )
        self.denoise_combo.setEnabled(config.denoise)

        self.star_reduce_check.setChecked(config.star_reduce)
        self.star_slider.setValue(int(config.star_reduce_strength * 100))
        self.star_slider.setEnabled(config.star_reduce)

        self.colour_check.setChecked(config.colour_balance)
        self.colour_auto_check.setEnabled(config.colour_balance)
        self.colour_auto_check.setChecked(config.colour_balance_auto)

        manual = config.colour_balance and not config.colour_balance_auto
        for attr, val in [
            ("r", config.colour_balance_r),
            ("g", config.colour_balance_g),
            ("b", config.colour_balance_b),
        ]:
            slider = getattr(self, f"colour_{attr}_slider")
            slider.setValue(int(val * 100))
            slider.setEnabled(manual)

    # ── Control toggle helpers ──────────────────────────────────────────────

    def _on_sharpen_toggled(self, checked: bool):
        self.sharpen_combo.setEnabled(checked)

    def _on_denoise_toggled(self, checked: bool):
        self.denoise_combo.setEnabled(checked)

    def _on_star_reduce_toggled(self, checked: bool):
        self.star_slider.setEnabled(checked)

    def _on_colour_balance_toggled(self, checked: bool):
        self.colour_auto_check.setEnabled(checked)
        manual = checked and not self.colour_auto_check.isChecked()
        for attr in ("r", "g", "b"):
            getattr(self, f"colour_{attr}_slider").setEnabled(manual)

    def _on_colour_auto_toggled(self, checked: bool):
        enabled = self.colour_check.isChecked()
        manual = enabled and not checked
        for attr in ("r", "g", "b"):
            getattr(self, f"colour_{attr}_slider").setEnabled(manual)

    # ── Config builder ──────────────────────────────────────────────────────

    def _build_config(self) -> PipelineConfig:
        """Assemble a PipelineConfig from the current dialog controls."""
        return PipelineConfig(
            # output_path left blank — dialog handles saving itself
            output_path="",
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
        """Kick off post-processing on a background thread."""
        if self._thread is not None and self._thread.isRunning():
            return  # already busy

        config = self._build_config()
        self._set_busy(True)
        self._status_label.setText("Processing…")

        self._thread = QThread()
        self._thread.setStackSize(16 * 1024 * 1024)
        self._worker = _PostProcessWorker(self._raw_stack, config)
        self._worker.moveToThread(self._thread)

        self._thread.started.connect(self._worker.run)
        self._worker.finished.connect(self._on_worker_finished)
        self._worker.error.connect(self._on_worker_error)
        self._worker.finished.connect(self._thread.quit)
        self._worker.error.connect(self._thread.quit)
        self._thread.finished.connect(self._on_thread_done)

        self._thread.start()

    def _on_reset(self):
        """Restore the original unprocessed stack."""
        if self._thread is not None and self._thread.isRunning():
            return
        self._current = self._raw_stack.copy()
        self.preview.show_data(self._raw_stack, info="Original (unprocessed)")
        self._status_label.setText("Reset to original.")

    def _on_worker_finished(self, result: np.ndarray):
        self._current = result
        h, w = result.shape[:2]
        chan = "RGB" if result.ndim == 3 else "mono"
        self.preview.show_data(result, info=f"Post-processed  {w}×{h}  {chan}")
        self._status_label.setText("Done.")

    def _on_worker_error(self, message: str):
        self._status_label.setText("Error — see dialog")
        QMessageBox.critical(self, "Post-Processing Error", message)

    def _on_thread_done(self):
        self._set_busy(False)
        self._thread = None
        self._worker = None

    def _set_busy(self, busy: bool):
        self.apply_btn.setEnabled(not busy)
        self.reset_btn.setEnabled(not busy)

    # ── Save helpers ────────────────────────────────────────────────────────

    def _save(self, fmt: str):
        """Save the current image (processed or original if Apply not clicked)."""
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
            return

        # Ensure extension
        p = Path(path)
        if not p.suffix:
            ext_map = {
                "fits": ".fits",
                "tiff": ".tiff",
                "jpeg": ".jpg",
                "png": ".png",
            }
            path = str(p) + ext_map.get(fmt, ".fits")

        try:
            if fmt == "fits":
                from astrostacker.io.loader import save_image
                save_image(path, self._current)
            else:
                from astrostacker.utils.stretch import auto_stretch
                from astrostacker.utils.image_utils import numpy_to_qpixmap
                stretched = auto_stretch(self._current)
                pixmap = numpy_to_qpixmap(stretched)
                ok = pixmap.save(path)
                if not ok:
                    raise RuntimeError(
                        f"QPixmap.save() returned False — check path and format."
                    )

            QMessageBox.information(
                self, "Saved", f"Image saved to:\n{path}"
            )
        except Exception as e:
            QMessageBox.critical(self, "Save Error", str(e))

    # ── Clean up on close ───────────────────────────────────────────────────

    def closeEvent(self, event):
        """Stop any running worker thread before closing."""
        if self._thread is not None and self._thread.isRunning():
            self._thread.quit()
            self._thread.wait(3000)
        super().closeEvent(event)
