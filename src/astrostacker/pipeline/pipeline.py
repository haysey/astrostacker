"""Top-level pipeline: calibrate -> align -> stack."""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

import numpy as np

import tempfile as _tempmod
from concurrent.futures import ThreadPoolExecutor, as_completed

from astrostacker.alignment.align import (
    _normalise_for_alignment,
    _align_single_frame,
)
from astrostacker.calibration.calibrate import calibrate_light, prepare_flat_divisor
from astrostacker.calibration.master_frames import build_master_dark, build_master_flat
from astrostacker.config import CAMERA_COLOUR, CAMERA_MONO
from astrostacker.io.loader import load_image, save_image
from astrostacker.stacking.stacker import stack_images
from astrostacker.stacking.drizzle import drizzle_stack
from astrostacker.utils.debayer import debayer
from astrostacker.utils.colour_balance import auto_colour_balance, apply_rgb_balance
from astrostacker.utils.deconvolution import sharpen_image
from astrostacker.utils.denoise import denoise_image
from astrostacker.utils.frame_quality import score_frames
from astrostacker.utils.gradient import remove_gradient
from astrostacker.utils.frame_buffer import _FrameBuffer
from astrostacker.utils.parallel import optimal_workers
from astrostacker.utils.star_reduction import reduce_stars


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

    # Star reduction (post-stack)
    star_reduce: bool = False
    star_reduce_strength: float = 0.5   # 0.0 = none, 1.0 = maximum

    # Colour balance (post-stack)
    colour_balance: bool = False
    colour_balance_auto: bool = True    # True = auto, False = manual sliders
    colour_balance_r: float = 1.0
    colour_balance_g: float = 1.0
    colour_balance_b: float = 1.0

    # Tone adjustment: brightness / contrast / saturation (post-stack)
    tone_adjust: bool = False
    tone_brightness: float = 0.0   # −100 … +100  (EV-stop scale: 2^(v/100))
    tone_contrast: float = 0.0     # −100 … +100  (scale around sky floor)
    tone_saturation: float = 0.0   # −100 … +100  (chroma scale around lum)

    # SCNR — green channel noise reduction (post-stack, colour images only)
    scnr: bool = False
    scnr_amount: float = 1.0       # 0.0 = no-op, 1.0 = full average-neutral SCNR


class Pipeline:
    """Orchestrates the full calibrate -> align -> stack pipeline."""

    def __init__(self, config: PipelineConfig):
        self.config = config
        self.cancelled = False
        self._raw_stack: np.ndarray | None = None   # cached pre-post-processing stack
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

        # Stage 2: Calibrate, debayer, align, and stack via a disk-backed buffer.
        #
        # WHY numpy.memmap rather than Python lists:
        #   Holding all calibrated frames in RAM simultaneously is not feasible
        #   for large stacks.  A 594-frame colour stack at 140 MB/frame = 83 GB.
        #   numpy.memmap writes frames to a temp file and lets the OS page data
        #   in/out of RAM on demand — only the actively-needed pages are in memory
        #   at any moment, rather than the full dataset.  Peak RAM drops from
        #   "entire dataset" to "a handful of frames" (calibration: 1 frame;
        #   alignment: reference + source + scratch ≈ 3 frames; stacking: one
        #   adaptive-sized strip).  This is how PixInsight handles large stacks.
        #
        #   The temp file is deleted automatically when stacking completes or if
        #   any exception (including cancellation) propagates out of the with block.
        n_frames = len(self.config.light_paths)
        self._report(f"Loading light frames (1/{n_frames})...")

        # Probe the first frame to learn its raw shape, prepare the flat
        # divisor, and optionally resize the master dark — all once up-front.
        _probe = load_image(self.config.light_paths[0])
        light_shape = _probe.shape

        flat_div = (
            prepare_flat_divisor(master_flat, target_shape=light_shape)
            if master_flat is not None else None
        )

        if master_dark is not None and master_dark.shape[:2] != light_shape[:2]:
            from astrostacker.calibration.calibrate import _match_shape
            self._report(
                f"Master dark is {master_dark.shape[1]}×{master_dark.shape[0]} "
                f"but lights are {light_shape[1]}×{light_shape[0]} — resizing to match"
            )
            master_dark = _match_shape(master_dark, light_shape, "dark")

        # Calibrate and optionally debayer the probe frame now so we know
        # the final frame shape before allocating the buffer.
        is_colour = self.config.camera_type == CAMERA_COLOUR
        _probe_cal = calibrate_light(_probe, master_dark, flat_divisor=flat_div)
        del _probe
        if is_colour and _probe_cal.ndim == 2:
            _probe_final = debayer(_probe_cal, self.config.bayer_pattern)
            final_frame_shape = _probe_final.shape   # (H, W, 3)
            del _probe_final
        else:
            final_frame_shape = _probe_cal.shape     # (H, W) mono

        # Report expected disk usage so users are not surprised by a large
        # temp file appearing on their system drive during a long stack.
        _tmpdir = _tempmod.gettempdir()
        _frame_mb = int(np.prod(final_frame_shape)) * 4 / 1024 / 1024
        _total_mb = n_frames * _frame_mb
        self._report(
            f"Temp buffer: {_total_mb:,.0f} MB in {_tmpdir} "
            f"({n_frames} × {_frame_mb:.0f} MB/frame — deleted on completion)"
        )

        dark_opt_note = " (with dark optimisation)" if master_dark is not None else ""
        self._report(
            f"Calibrating{' and debayering' if is_colour else ''} "
            f"{n_frames} frames{dark_opt_note}..."
        )

        with _FrameBuffer(n_frames, final_frame_shape) as frame_buf:

            # ── Calibrate (+ debayer for colour) into the buffer ──────────────
            # Frame 0 was already calibrated above as the probe; reuse it.
            # Each frame is loaded, calibrated, written to disk, then freed
            # from RAM — peak RAM during this stage = 1 raw + 1 calibrated frame.
            for i, path in enumerate(self.config.light_paths):
                if i == 0:
                    frame = _probe_cal
                    del _probe_cal          # drop outer ref; `frame` still holds data
                else:
                    raw = load_image(path)
                    frame = calibrate_light(raw, master_dark, flat_divisor=flat_div)
                    del raw
                if is_colour and frame.ndim == 2:
                    frame = debayer(frame, self.config.bayer_pattern)
                frame_buf[i] = frame        # write to disk
                del frame                   # free from RAM; data is now in the buffer
                self._report_progress(i + 1, n_frames, "Calibrating")
                self._check_cancel()

            if is_colour:
                self._report(
                    f"Calibration and debayer complete — "
                    f"frames are now RGB {final_frame_shape}"
                )
            else:
                self._report("Camera set to Mono — skipping debayer")

            # ── Auto frame rejection (PSF-based) ──────────────────────────────
            self.rejected_paths = []
            accepted_indices = list(range(n_frames))   # default: use all frames

            if self.config.auto_reject and n_frames >= 3:
                self._report("Scoring frame quality (PSF fitting)...")
                # frame_view() gives the stacker a zero-copy memmap view;
                # score_frames reads each frame from disk as needed.
                score_views = [frame_buf.frame_view(i) for i in range(n_frames)]
                scores = score_frames(score_views, self.config.rejection_sigma)
                del score_views
                kept = []
                for s in scores:
                    label = (
                        f"  Frame {s.index}: FWHM={s.fwhm:.2f}px  "
                        f"Ecc={s.eccentricity:.2f}  Round={s.roundness:.2f}  "
                        f"Stars={s.n_stars}"
                    )
                    if s.keep:
                        kept.append(s.index)
                        self._report(f"{label} — kept")
                    else:
                        self.rejected_paths.append(
                            self.config.light_paths[s.index]
                        )
                        self._report(f"{label} — REJECTED")
                if len(kept) >= 2:
                    self._report(
                        f"Frame rejection: kept {len(kept)}/{n_frames}, "
                        f"rejected {len(self.rejected_paths)}"
                    )
                    accepted_indices = kept
                else:
                    self._report("Too few frames would remain — keeping all")
                    self.rejected_paths = []
                self._check_cancel()

            self.accepted_count = len(accepted_indices)
            n_accepted = self.accepted_count

            # ── Align frames in-place in the buffer ───────────────────────────
            # Each frame is read from disk into RAM, aligned to the reference,
            # then written back to its original slot in the buffer (overwriting
            # the pre-alignment data).  Peak RAM = reference + source frame +
            # alignment scratch ≈ 3 × frame_size instead of 2 × full dataset.
            self._report("Aligning frames...")
            ref_idx = min(self.config.reference_frame, n_accepted - 1)
            ref_buf_idx = accepted_indices[ref_idx]

            reference = frame_buf[ref_buf_idx]   # RAM copy via __getitem__
            is_color = reference.ndim == 3
            if is_color:
                ref_lum = _normalise_for_alignment(np.mean(reference, axis=2))
                ref_channels_norm = [
                    _normalise_for_alignment(reference[:, :, c])
                    for c in range(reference.shape[2])
                ]
            else:
                ref_lum = _normalise_for_alignment(reference)
                ref_channels_norm = []

            # Parallel alignment across CPU cores.
            #
            # WHY parallel is now safe (it wasn't before memmap):
            #   Previously, all frames lived in RAM as Python lists.  Running
            #   N worker threads meant N frames being read + N aligned copies
            #   being written simultaneously — on top of the full frame list
            #   already in RAM.  Peak RAM could reach 3× the full dataset.
            #
            #   With memmap, each thread reads one frame from disk (~140 MB),
            #   aligns it (CPU-bound: star detection + affine transform), then
            #   writes the result back to the SAME disk slot before moving on.
            #   Peak RAM = n_workers × ~400 MB regardless of total frame count.
            #   On an 8-core / 8 GB machine that is ≈ 3 GB — well within budget.
            #
            #   numpy and SciPy release the GIL during their heavy C-level work,
            #   so threads genuinely run in parallel across all CPU cores.
            workers = optimal_workers(io_bound=False)
            self._report(
                f"Aligning {n_accepted} frames across {workers} cores..."
            )

            align_failed = 0
            completed = 0
            succeeded_out_i: set[int] = set()   # out_i values that aligned OK

            # Reference frame needs no computation — mark it done immediately.
            self._report(f"  Frame {ref_idx}: reference (kept as-is)")
            completed += 1
            self._report_progress(completed, n_accepted, "Aligning")

            # Worker function: runs in a thread pool.
            # Each call reads one slot from the buffer (disk → RAM), aligns,
            # then writes the result back to the same slot (RAM → disk).
            # Thread safety: every thread operates on a DIFFERENT buf_i slot,
            # so there are no overlapping reads or writes in the memmap.
            def _do_align(job):
                out_i, buf_i = job
                frame = frame_buf[buf_i]        # disk read → fresh RAM copy
                args = (out_i, frame, ref_lum, ref_channels_norm,
                        reference, is_color)
                _, aligned_frame, error_msg = _align_single_frame(args)
                del frame
                if aligned_frame is not None:
                    frame_buf[buf_i] = aligned_frame  # write aligned data back
                    del aligned_frame
                    return out_i, True, ""
                return out_i, False, error_msg

            non_ref_jobs = [
                (out_i, buf_i)
                for out_i, buf_i in enumerate(accepted_indices)
                if buf_i != ref_buf_idx
            ]

            if non_ref_jobs:
                with ThreadPoolExecutor(max_workers=workers) as pool:
                    future_map = {
                        pool.submit(_do_align, job): job
                        for job in non_ref_jobs
                    }
                    for future in as_completed(future_map):
                        self._check_cancel()
                        out_i, ok, error_msg = future.result()
                        if ok:
                            succeeded_out_i.add(out_i)
                        else:
                            align_failed += 1
                            self._report(
                                f"  Frame {out_i} alignment failed — skipping: "
                                f"{error_msg[:120]}"
                            )
                        completed += 1
                        self._report_progress(completed, n_accepted, "Aligning")

            # Rebuild valid_indices in original accepted order.
            # (Stacking methods are commutative across frames, so order does
            # not affect the result — but keeping original order is tidy.)
            valid_indices = [
                buf_i
                for out_i, buf_i in enumerate(accepted_indices)
                if buf_i == ref_buf_idx or out_i in succeeded_out_i
            ]

            del reference, ref_lum, ref_channels_norm

            self._report(
                f"Alignment: {len(valid_indices)}/{n_accepted} succeeded, "
                f"{align_failed} failed"
            )
            self._check_cancel()

            if len(valid_indices) < 2:
                raise ValueError(
                    f"Only {len(valid_indices)} frame(s) aligned successfully. "
                    "Need at least 2 to stack."
                )

            # Memmap views: zero-copy references into the buffer.
            # The OS pages each frame strip into RAM on demand during stacking.
            valid_views = [frame_buf.frame_view(i) for i in valid_indices]

            # ── Stage 4: Stack ────────────────────────────────────────────────
            if self.config.drizzle:
                self._report(
                    f"Drizzle stacking {len(valid_views)} frames "
                    f"({self.config.drizzle_scale}x upscale)..."
                )
                result = drizzle_stack(
                    valid_views, scale=self.config.drizzle_scale
                )
            else:
                self._report(
                    f"Stacking {len(valid_views)} frames "
                    f"({self.config.stacking_method})..."
                )

                # Build kwargs relevant to the chosen stacking method.
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
                    psf_scores = score_frames(valid_views)
                    valid_fwhms = [
                        s.fwhm for s in psf_scores if np.isfinite(s.fwhm)
                    ]
                    if valid_fwhms:
                        self.measured_fwhm = float(np.median(valid_fwhms))
                        self._report(
                            f"Median PSF FWHM = {self.measured_fwhm:.2f}px "
                            f"({len(valid_fwhms)} frames measured)"
                        )

                if self.config.stacking_method == "weighted_mean":
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

                result = stack_images(
                    valid_views, method=self.config.stacking_method, **kwargs
                )
            self._check_cancel()

        # frame_buf context exits here — temp file flushed and deleted.

        # Cache raw stack so post-processing can be re-applied without re-stacking
        self._raw_stack = result.copy()

        result = self._run_postprocessing(result)

        # Stage 5: Save
        colour_info = "RGB colour" if result.ndim == 3 else "mono"
        self._report(f"Saving {colour_info} result {result.shape} to {self.config.output_path}...")
        save_image(self.config.output_path, result)

        self._report("Done!")
        return result

    def reprocess(self) -> np.ndarray:
        """Re-run post-processing on the cached raw stack.

        Skips calibration, alignment, and stacking — only reruns:
        auto-crop, gradient removal, sharpen, denoise, star reduction,
        colour balance.  Call ``run()`` at least once first to populate
        the cache.

        Returns:
            Post-processed result as float32 ndarray.

        Raises:
            RuntimeError: If ``run()`` has not been called yet.
        """
        if self._raw_stack is None:
            raise RuntimeError(
                "No cached stack available — run() must be called first."
            )
        self.cancelled = False
        self._report("Re-applying post-processing...")
        result = self._run_postprocessing(self._raw_stack.copy())

        colour_info = "RGB colour" if result.ndim == 3 else "mono"
        self._report(f"Saving {colour_info} result to {self.config.output_path}...")
        save_image(self.config.output_path, result)
        self._report("Done!")
        return result

    def _run_postprocessing(self, result: np.ndarray) -> np.ndarray:
        """Run all post-stack processing stages on *result* and return it."""

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

        # Stage 4f: Star reduction
        if self.config.star_reduce and self.config.star_reduce_strength > 0:
            pct = int(round(self.config.star_reduce_strength * 100))
            self._report(f"Reducing stars ({pct}%)...")
            result = reduce_stars(result, strength=self.config.star_reduce_strength)
            self._report("Star reduction complete")
            self._check_cancel()

        # Stage 4g: Colour balance
        if self.config.colour_balance and result.ndim == 3:
            if self.config.colour_balance_auto:
                self._report("Applying automatic colour balance...")
                result, factors = auto_colour_balance(result)
                self._report(
                    f"  Colour balance — R×{factors[0]:.3f}  "
                    f"G×{factors[1]:.3f}  B×{factors[2]:.3f}"
                )
            else:
                r = self.config.colour_balance_r
                g = self.config.colour_balance_g
                b = self.config.colour_balance_b
                self._report(
                    f"Applying manual colour balance "
                    f"(R×{r:.2f}  G×{g:.2f}  B×{b:.2f})..."
                )
                result = apply_rgb_balance(result, r=r, g=g, b=b)
            self._check_cancel()

        # Stage 4h: SCNR — remove excess green from stars and background
        if self.config.scnr and result.ndim == 3:
            from astrostacker.utils.scnr import apply_scnr
            pct = int(round(self.config.scnr_amount * 100))
            self._report(f"Applying green SCNR ({pct}% strength)...")
            result = apply_scnr(result, amount=self.config.scnr_amount)
            self._report("SCNR complete")
            self._check_cancel()

        # Stage 4i: Tone adjustment (brightness / contrast / saturation)
        if self.config.tone_adjust:
            from astrostacker.utils.tone import adjust_tone
            b_val = self.config.tone_brightness
            c_val = self.config.tone_contrast
            s_val = self.config.tone_saturation
            self._report(
                f"Tone adjust — brightness {b_val:+.0f}%  "
                f"contrast {c_val:+.0f}%  saturation {s_val:+.0f}%"
            )
            result = adjust_tone(result,
                                  brightness=b_val,
                                  contrast=c_val,
                                  saturation=s_val)
            self._check_cancel()

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
