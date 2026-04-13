"""Top-level pipeline: calibrate -> align -> stack."""

from __future__ import annotations

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
from astrostacker.utils.debayer import debayer
from astrostacker.utils.parallel import optimal_workers, parallel_load_images


@dataclass
class PipelineConfig:
    """Configuration for a stacking pipeline run."""

    light_paths: list[str] = field(default_factory=list)
    dark_paths: list[str] = field(default_factory=list)
    flat_paths: list[str] = field(default_factory=list)
    dark_flat_paths: list[str] = field(default_factory=list)

    stacking_method: str = "sigma_clip"
    sigma_low: float = 2.5
    sigma_high: float = 2.5

    camera_type: str = "mono"
    bayer_pattern: str = "RGGB"

    output_path: str = "stacked.fits"
    reference_frame: int = 0


class Pipeline:
    """Orchestrates the full calibrate -> align -> stack pipeline."""

    def __init__(self, config: PipelineConfig):
        self.config = config
        self.cancelled = False
        self._status_callback: Callable[[str], None] | None = None
        self._progress_callback: Callable[[int, int, str], None] | None = None

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

        # Stage 1: Build master calibration frames
        master_dark = None
        master_flat = None

        # Directory to save master frames alongside the output file
        output_dir = Path(self.config.output_path).parent

        if self.config.dark_paths:
            self._report("Building master dark frame...")
            master_dark = build_master_dark(self.config.dark_paths)
            dark_path = str(output_dir / "master_dark.fits")
            save_image(dark_path, master_dark)
            self._report(f"Master dark saved → {dark_path}")
            self._check_cancel()

        if self.config.flat_paths:
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

        # Pre-compute the safe flat divisor once (avoids repeat work per frame)
        flat_div = prepare_flat_divisor(master_flat) if master_flat is not None else None

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

        # Stage 3: Align calibrated frames
        self._report("Aligning frames...")

        def align_progress(current, total):
            self._check_cancel()
            self._report_progress(current, total, "Aligning")

        aligned = align_frames(
            calibrated,
            reference_index=self.config.reference_frame,
            progress_callback=align_progress,
            status_callback=self._report,
        )
        self._check_cancel()

        if len(aligned) < 2:
            raise ValueError(
                f"Only {len(aligned)} frame(s) aligned successfully. "
                "Need at least 2 to stack."
            )

        # Stage 4: Stack
        self._report(f"Stacking {len(aligned)} frames ({self.config.stacking_method})...")
        kwargs = {}
        if self.config.stacking_method == "sigma_clip":
            kwargs["sigma_low"] = self.config.sigma_low
            kwargs["sigma_high"] = self.config.sigma_high

        result = stack_images(aligned, method=self.config.stacking_method, **kwargs)
        self._check_cancel()

        # Stage 5: Save
        colour_info = "RGB colour" if result.ndim == 3 else "mono"
        self._report(f"Saving {colour_info} result {result.shape} to {self.config.output_path}...")
        save_image(self.config.output_path, result)

        self._report("Done!")
        return result
