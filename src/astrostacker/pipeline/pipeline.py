"""Top-level pipeline: calibrate -> align -> stack."""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

import numpy as np

from concurrent.futures import ThreadPoolExecutor

from astrostacker.alignment.align import align_frames
from astrostacker.calibration.calibrate import calibrate_light, prepare_flat_divisor
from astrostacker.calibration.master_frames import build_master_dark, build_master_flat
from astrostacker.config import CAMERA_COLOUR, CAMERA_MONO
from astrostacker.io.loader import load_image, save_image
from astrostacker.stacking.stacker import stack_images
from astrostacker.stacking.drizzle import drizzle_stack
from astrostacker.utils.debayer import debayer
from astrostacker.utils.deconvolution import sharpen_image
from astrostacker.utils.denoise import denoise_image
from astrostacker.utils.frame_quality import score_frames
from astrostacker.utils.gradient import remove_gradient
from astrostacker.utils.parallel import optimal_workers, parallel_load_images


@dataclass
class PipelineConfig:
    """Configuration for a stacking pipeline run."""

    light_paths: list[str] = field(default_factory=list)
    dark_paths: list[str] = field(default_factory=list)
    flat_paths: list[str] = field(default_factory=list)
    dark_flat_paths: list[str] = field(default_factory=list)

    # Pre-built master frames (skip building from individual frames)
    master_dark_path: str = ""
    master_flat_path: str = ""

    stacking_method: str = "median"
    sigma_low: float = 2.5
    sigma_high: float = 2.5
    percentile_low: float = 10.0
    percentile_high: float = 10.0

    camera_type: str = "mono"
    bayer_pattern: str = "RGGB"

    output_path: str = "stacked.fits"
    reference_frame: int = 0

    # Frame rejection
    auto_reject: bool = False
    rejection_sigma: float = 2.0

    # Gradient removal
    remove_gradient: bool = False

    # Local normalisation (per-frame gradient removal before stacking)
    local_normalise: bool = False

    # Drizzle
    drizzle: bool = False
    drizzle_scale: int = 2

    # Denoising
    denoise: bool = False
    denoise_strength: str = "medium"  # "light", "medium", "strong"

    # Deconvolution (sharpening via Richardson-Lucy)
    deconvolve: bool = False
    deconv_strength: str = "medium"  # "light", "medium", "strong"

    # Auto-crop stacking edges
    auto_crop: bool = False


class Pipeline:
    """Orchestrates the full calibrate -> align -> stack pipeline."""

    def __init__(self, config: PipelineConfig):
        self.config = config
        self.cancelled = False
        self._status_callback: Callable[[str], None] | None = None
        self._progress_callback: Callable[[int, int, str], None] | None = None
        # Populated after run() — paths of rejected light frames
        self.rejected_paths: list[str] = []
        self.accepted_count: int = 0
        # Populated by PSF measurement — used for deconvolution kernel
        self.measured_fwhm: float | None = None

    def set_callbacks(
        self,
        status: Callable[[str], None] | None = None,
        progress: Callable[[int, int, str], None] | None = None,
    ):
        """Set callback functions for status messages and progress updates."""
        self._status_callback = status
        self._progress_callback = progress

    def _report(self, message: str):
        if self._status_callback:
            self._status_callback(message)

    def _report_progress(self, current: int, total: int, stage: str = ""):
        if self._progress_callback:
            self._progress_callback(current, total, stage)

    def cancel(self):
        """Request cancellation of the running pipeline."""
        self.cancelled = True

    def _check_cancel(self):
        if self.cancelled:
            raise InterruptedError("Pipeline cancelled by user")

    def run(self) -> np.ndarray:
        """Execute the full pipeline.

        Returns:
            Stacked result as float32 ndarray.

        Raises:
            InterruptedError: If cancelled by user.
            ValueError: If no light frames provided.
        """
        if not self.config.light_paths:
            raise ValueError("No light frames provided")

        self.cancelled = False

        # Resolve relative output paths against the first light frame's
        # directory.  Inside a macOS .app bundle the working directory is
        # read-only, so bare names like "stacked.fits" would fail.
        out = Path(self.config.output_path)
        if not out.is_absolute():
            lights_dir = Path(self.config.light_paths[0]).parent
            out = lights_dir / out
            self.config = dataclasses.replace(
                self.config, output_path=str(out)
            )

        # Stage 1: Build or load master calibration frames
        master_dark = None
        master_flat = None

        # Directory to save master frames alongside the output file
        output_dir = Path(self.config.output_path).parent

        if self.config.master_dark_path:
            self._report(f"Loading master dark: {Path(self.config.master_dark_path).name}")
            master_dark = load_image(self.config.master_dark_path)
        elif self.config.dark_paths:
            self._report("Building master dark frame...")
            master_dark = build_master_dark(self.config.dark_paths)
            dark_path = str(output_dir / "master_dark.fits")
            save_image(dark_path, master_dark)
            self._report(f"Master dark saved → {dark_path}")
        self._check_cancel()

        if self.config.master_flat_path:
            self._report(f"Loading master flat: {Path(self.config.master_flat_path).name}")
            master_flat = load_image(self.config.master_flat_path)
        elif self.config.flat_paths:
            self._report("Building master flat frame...")
            master_flat = build_master_flat(
                self.config.flat_paths,
                self.config.dark_flat_paths or None,
            )
            flat_path = str(output_dir / "master_flat.fits")
            save_image(flat_path, master_flat)
            self._report(f"Master flat saved → {flat_path}")
        self._check_cancel()

        # Stage 2: Load and calibrate light frames
        #   - Parallel I/O for loading
        #   - Pre-computed flat divisor (computed once, reused per frame)
        #   - Parallel calibration across performance cores
        self._report("Loading light frames...")
        lights = parallel_load_images(self.config.light_paths, load_image)
        self._check_cancel()

        # Pre-compute the safe flat divisor once (avoids repeat work per frame).
        # Pass the light frame shape so a mismatched flat is resized once,
        # not on every frame.
        light_shape = lights[0].shape
        flat_div = (
            prepare_flat_divisor(master_flat, target_shape=light_shape)
            if master_flat is not None else None
        )

        # Also resize master dark once if dimensions differ
        if master_dark is not None and master_dark.shape[:2] != light_shape[:2]:
            from astrostacker.calibration.calibrate import _match_shape
            self._report(
                f"Master dark is {master_dark.shape[1]}×{master_dark.shape[0]} "
                f"but lights are {light_shape[1]}×{light_shape[0]} — resizing to match"
            )
            master_dark = _match_shape(master_dark, light_shape, "dark")

        workers = optimal_workers(io_bound=False)
        n_frames = len(lights)
        self._report(f"Calibrating {n_frames} frames across {workers} cores...")

        def _calibrate_one(light):
            return calibrate_light(light, master_dark, flat_divisor=flat_div)

        with ThreadPoolExecutor(max_workers=workers) as pool:
            calibrated = list(pool.map(_calibrate_one, lights))
        self._report_progress(n_frames, n_frames, "Calibrating")
        self._check_cancel()

        # Free raw lights to reduce peak memory
        del lights

        # Stage 2b: Debayer colour camera frames (parallel across cores)
        if self.config.camera_type == CAMERA_COLOUR:
            self._report(
                f"Debayering {n_frames} frames ({self.config.bayer_pattern}) "
                f"across {workers} cores..."
            )
            pattern = self.config.bayer_pattern

            def _debayer_one(frame):
                if frame.ndim == 2:
                    return debayer(frame, pattern)
                return frame

            with ThreadPoolExecutor(max_workers=workers) as pool:
                calibrated = list(pool.map(_debayer_one, calibrated))
            self._report_progress(n_frames, n_frames, "Debayering")
            self._check_cancel()
            self._report(f"Debayer complete — frames are now RGB {calibrated[0].shape}")
        else:
            self._report("Camera set to Mono — skipping debayer")

        # Stage 2b: Auto frame rejection (PSF-based)
        self.rejected_paths = []
        if self.config.auto_reject and len(calibrated) >= 3:
            self._report("Scoring frame quality (PSF fitting)...")
            scores = score_frames(calibrated, self.config.rejection_sigma)
            kept = []
            for s in scores:
                label = (
                    f"  Frame {s.index}: FWHM={s.fwhm:.2f}px  "
                    f"Ecc={s.eccentricity:.2f}  Round={s.roundness:.2f}  "
                    f"Stars={s.n_stars}"
                )
                if s.keep:
                    kept.append(calibrated[s.index])
                    self._report(f"{label} — kept")
                else:
                    self.rejected_paths.append(self.config.light_paths[s.index])
                    self._report(f"{label} — REJECTED")
            if len(kept) >= 2:
                self._report(
                    f"Frame rejection: kept {len(kept)}/{len(calibrated)}, "
                    f"rejected {len(self.rejected_paths)}"
                )
                calibrated = kept
            else:
                self._report("Too few frames would remain — keeping all")
                self.rejected_paths = []
            self._check_cancel()

        self.accepted_count = len(calibrated)

        # Stage 3: Align calibrated frames
        self._report("Aligning frames...")

        def align_progress(current, total):
            self._check_cancel()
            self._report_progress(current, total, "Aligning")

        aligned = align_frames(
            calibrated,
            reference_index=min(self.config.reference_frame, len(calibrated) - 1),
            progress_callback=align_progress,
            status_callback=self._report,
        )
        self._check_cancel()

        if len(aligned) < 2:
            raise ValueError(
                f"Only {len(aligned)} frame(s) aligned successfully. "
                "Need at least 2 to stack."
            )

        # Stage 3b: Local normalisation (per-frame gradient removal)
        if self.config.local_normalise:
            self._report("Local normalisation (per-frame gradient removal)...")
            for i in range(len(aligned)):
                aligned[i] = remove_gradient(aligned[i])
            self._report("Local normalisation complete")
            self._check_cancel()

        # Stage 4: Stack
        if self.config.drizzle:
            self._report(
                f"Drizzle stacking {len(aligned)} frames "
                f"({self.config.drizzle_scale}x upscale)..."
            )
            result = drizzle_stack(
                aligned, scale=self.config.drizzle_scale
            )
        else:
            self._report(f"Stacking {len(aligned)} frames ({self.config.stacking_method})...")

            # Build kwargs relevant to the chosen stacking method.
            # stacker.py filters out any that the method doesn't accept.
            kwargs = {
                "sigma_low": self.config.sigma_low,
                "sigma_high": self.config.sigma_high,
                "pct_low": self.config.percentile_low,
                "pct_high": self.config.percentile_high,
            }

            # Measure PSF if needed for weighted stacking or deconvolution
            need_psf = (
                self.config.stacking_method == "weighted_mean"
                or self.config.deconvolve
            )
            if need_psf:
                self._report("Measuring star PSF profiles...")
                psf_scores = score_frames(aligned)
                valid_fwhms = [
                    s.fwhm for s in psf_scores if np.isfinite(s.fwhm)
                ]
                if valid_fwhms:
                    self.measured_fwhm = float(np.median(valid_fwhms))
                    self._report(
                        f"Median PSF FWHM = {self.measured_fwhm:.2f}px "
                        f"({len(valid_fwhms)} frames measured)"
                    )

            # For weighted mean: compute quality weights from PSF scores
            if self.config.stacking_method == "weighted_mean":
                # Combined weight: sharper AND rounder = higher weight
                weights = np.array([
                    (1.0 / max(s.fwhm, 0.1)) * s.roundness
                    for s in psf_scores
                ], dtype=np.float32)
                kwargs["weights"] = weights
                for s in psf_scores:
                    w = weights[s.index]
                    self._report(
                        f"  Frame {s.index}: FWHM={s.fwhm:.2f}px  "
                        f"Ecc={s.eccentricity:.2f}  weight={w:.3f}"
                    )

            result = stack_images(aligned, method=self.config.stacking_method, **kwargs)
        self._check_cancel()

        # Stage 4b: Auto-crop stacking edges (NaN/zero borders)
        if self.config.auto_crop:
            result = self._auto_crop(result)
            self._check_cancel()

        # Stage 4c: Gradient removal
        if self.config.remove_gradient:
            self._report("Removing light pollution gradient...")
            result = remove_gradient(result)
            self._check_cancel()

        # Stage 4d: PSF-informed sharpening (unsharp mask)
        if self.config.deconvolve:
            fwhm = self.measured_fwhm or 2.5  # fallback if not measured

            # If drizzle was used, the stacked image is 2x resolution
            # so the effective FWHM in pixels is also 2x larger.
            if self.config.drizzle:
                fwhm *= self.config.drizzle_scale
                self._report(
                    f"Drizzle {self.config.drizzle_scale}x active — "
                    f"scaled PSF FWHM to {fwhm:.2f}px"
                )

            strength = self.config.deconv_strength
            self._report(
                f"Sharpening ({strength}, FWHM={fwhm:.2f}px)..."
            )
            result = sharpen_image(result, fwhm, strength=strength)
            self._report("Sharpening complete")
            self._check_cancel()

        # Stage 4e: Denoising (Non-Local Means)
        if self.config.denoise:
            strength = self.config.denoise_strength
            self._report(f"Denoising (Non-Local Means, {strength})...")
            result = denoise_image(result, strength=strength)
            self._report("Denoising complete")
            self._check_cancel()

        # Stage 5: Save
        colour_info = "RGB colour" if result.ndim == 3 else "mono"
        self._report(f"Saving {colour_info} result {result.shape} to {self.config.output_path}...")
        save_image(self.config.output_path, result)

        self._report("Done!")
        return result

    def _auto_crop(self, data: np.ndarray) -> np.ndarray:
        """Crop NaN/zero borders left by alignment."""
        self._report("Auto-cropping stacking edges...")

        if data.ndim == 3:
            # Use sum across channels to find valid pixels
            mask = np.all(np.isfinite(data), axis=2) & np.any(data > 0, axis=2)
        else:
            mask = np.isfinite(data) & (data > 0)

        rows = np.any(mask, axis=1)
        cols = np.any(mask, axis=0)

        if not np.any(rows) or not np.any(cols):
            return data

        r_min, r_max = np.where(rows)[0][[0, -1]]
        c_min, c_max = np.where(cols)[0][[0, -1]]

        # Add small margin
        margin = 2
        r_min = max(0, r_min + margin)
        r_max = min(data.shape[0] - 1, r_max - margin)
        c_min = max(0, c_min + margin)
        c_max = min(data.shape[1] - 1, c_max - margin)

        cropped = data[r_min:r_max + 1, c_min:c_max + 1]
        self._report(
            f"Cropped from {data.shape[1]}x{data.shape[0]} "
            f"to {cropped.shape[1]}x{cropped.shape[0]}"
        )
        return cropped
