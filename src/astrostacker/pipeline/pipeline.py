"""Top-level pipeline: calibrate -> align -> stack."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

import numpy as np

from astrostacker.alignment.align import align_frames
from astrostacker.calibration.calibrate import calibrate_light
from astrostacker.calibration.master_frames import build_master_dark, build_master_flat
from astrostacker.config import CAMERA_COLOUR, CAMERA_MONO
from astrostacker.io.loader import load_image, save_image
from astrostacker.stacking.stacker import stack_images
from astrostacker.utils.debayer import debayer
from astrostacker.utils.parallel import parallel_load_images


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

        if self.config.dark_paths:
            self._report("Building master dark frame...")
            master_dark = build_master_dark(self.config.dark_paths)
            self._check_cancel()

        if self.config.flat_paths:
            self._report("Building master flat frame...")
            master_flat = build_master_flat(
                self.config.flat_paths,
                self.config.dark_flat_paths or None,
            )
            self._check_cancel()

        # Stage 2: Load and calibrate light frames (parallel I/O)
        self._report("Loading light frames...")
        lights = parallel_load_images(self.config.light_paths, load_image)
        self._check_cancel()

        self._report("Calibrating light frames...")
        calibrated = []
        for i, light in enumerate(lights):
            self._check_cancel()
            cal = calibrate_light(light, master_dark, master_flat)
            calibrated.append(cal)
            self._report_progress(i + 1, len(lights), "Calibrating")

        # Stage 2b: Debayer colour camera frames
        if self.config.camera_type == CAMERA_COLOUR:
            self._report(f"Debayering with {self.config.bayer_pattern} pattern...")
            debayered = []
            for i, frame in enumerate(calibrated):
                self._check_cancel()
                if frame.ndim == 2:
                    # Only debayer mono (raw Bayer) frames
                    debayered.append(debayer(frame, self.config.bayer_pattern))
                else:
                    # Already colour — pass through
                    debayered.append(frame)
                self._report_progress(i + 1, len(calibrated), "Debayering")
            calibrated = debayered

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
        self._report(f"Saving result to {self.config.output_path}...")
        save_image(self.config.output_path, result)

        self._report("Done!")
        return result
