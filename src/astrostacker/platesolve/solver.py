"""Astrometry.net plate solver using the nova.astrometry.net API.

Workflow:
    1. Login with API key to get a session.
    2. Upload an image file for solving.
    3. Poll the submission/job status until complete.
    4. Retrieve calibration results (RA, Dec, field size, orientation, etc).
"""

from __future__ import annotations

import io
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import numpy as np
import requests
from astropy.io import fits
from scipy.ndimage import zoom

from astrostacker.io.loader import load_image

API_BASE = "https://nova.astrometry.net/api"
DEFAULT_TIMEOUT = 300  # seconds

# Stretch factor applied to the image before uploading for solving.
# 1.2 = 20% larger, which improves readability of the annotated result.
SOLVE_IMAGE_SCALE = 1.2


@dataclass
class Annotation:
    """A single object annotation with pixel position and metadata."""

    name: str  # Object name (e.g. "M31", "NGC 224")
    pixel_x: float  # X position in pixels
    pixel_y: float  # Y position in pixels
    radius: float  # Radius in pixels for the circle
    ann_type: str  # Type: "ic", "ngc", "hd", "bright_star", etc.


@dataclass
class SolveResult:
    """Results from a successful plate solve."""

    ra: float  # Right Ascension in degrees
    dec: float  # Declination in degrees
    ra_hms: str  # RA in hours:minutes:seconds
    dec_dms: str  # Dec in degrees:arcmin:arcsec
    orientation: float  # Field rotation in degrees (E of N)
    field_w: float  # Field width in arcminutes
    field_h: float  # Field height in arcminutes
    pixel_scale: float  # Arcseconds per pixel
    parity: str  # "Normal" or "Flipped"
    objects_in_field: list[str]  # Named objects found
    annotations: list[Annotation]  # Object annotations with pixel positions
    job_id: int
    calibration_id: int

    def summary(self) -> str:
        """Human-readable summary of the solve result."""
        lines = [
            f"RA:          {self.ra_hms}  ({self.ra:.6f} deg)",
            f"Dec:         {self.dec_dms}  ({self.dec:.6f} deg)",
            f"Orientation: {self.orientation:.2f} deg (E of N)",
            f"Field size:  {self.field_w:.2f}' x {self.field_h:.2f}'",
            f"Pixel scale: {self.pixel_scale:.3f} arcsec/px",
            f"Parity:      {self.parity}",
        ]
        if self.objects_in_field:
            lines.append(f"Objects:     {', '.join(self.objects_in_field[:10])}")
        return "\n".join(lines)


def _ra_to_hms(ra_deg: float) -> str:
    """Convert RA in degrees to HH:MM:SS.s format."""
    ra_h = ra_deg / 15.0
    h = int(ra_h)
    m = int((ra_h - h) * 60)
    s = (ra_h - h - m / 60.0) * 3600
    return f"{h:02d}h {m:02d}m {s:05.2f}s"


def _dec_to_dms(dec_deg: float) -> str:
    """Convert Dec in degrees to DD:MM:SS.s format."""
    sign = "+" if dec_deg >= 0 else "-"
    dec_abs = abs(dec_deg)
    d = int(dec_abs)
    m = int((dec_abs - d) * 60)
    s = (dec_abs - d - m / 60.0) * 3600
    return f"{sign}{d:02d}d {m:02d}' {s:04.1f}\""


def _image_to_fits_bytes(path: str) -> bytes:
    """Convert any supported image to FITS bytes for upload.

    The image is stretched by SOLVE_IMAGE_SCALE (20%) before conversion
    so that the solved/annotated result is larger and easier to read.
    """
    ext = Path(path).suffix.lower()
    if ext in (".fits", ".fit", ".fts"):
        with fits.open(path) as hdul:
            data = hdul[0].data.astype(np.float32)
    else:
        data = load_image(path)

    if data.ndim == 3:
        # Convert to mono for solving (luminance)
        data = np.mean(data, axis=2)

    # Stretch image by 20% before solving for better readability
    data = zoom(data, SOLVE_IMAGE_SCALE, order=1)

    hdu = fits.PrimaryHDU(data.astype(np.float32))
    buf = io.BytesIO()
    hdu.writeto(buf)
    return buf.getvalue()


class AstrometryNetSolver:
    """Plate solver using the nova.astrometry.net web API."""

    def __init__(self, api_key: str = ""):
        self.api_key = api_key
        self.session_key: str | None = None
        self._status_callback: Callable[[str], None] | None = None
        self.cancelled = False

    def set_status_callback(self, callback: Callable[[str], None] | None):
        self._status_callback = callback

    def _report(self, msg: str):
        if self._status_callback:
            self._status_callback(msg)

    def cancel(self):
        self.cancelled = True

    def _check_cancel(self):
        if self.cancelled:
            raise InterruptedError("Plate solve cancelled")

    def login(self) -> str:
        """Login to Astrometry.net and get a session key.

        If no API key is provided, uses anonymous login.
        """
        self._report("Connecting to Astrometry.net...")
        payload = {"apikey": self.api_key} if self.api_key else {}
        resp = requests.post(
            f"{API_BASE}/login",
            data={"request-json": json.dumps(payload)},
            timeout=30,
        )
        resp.raise_for_status()
        result = resp.json()

        if result.get("status") != "success":
            raise RuntimeError(
                f"Login failed: {result.get('errormessage', 'Unknown error')}"
            )

        self.session_key = result["session"]
        self._report("Connected to Astrometry.net")
        return self.session_key

    def upload(
        self,
        image_path: str,
        scale_lower: float | None = None,
        scale_upper: float | None = None,
        scale_units: str = "arcsecperpix",
        downsample_factor: int = 2,
    ) -> int:
        """Upload an image for plate solving.

        Args:
            image_path: Path to the image file.
            scale_lower: Optional lower bound for image scale.
            scale_upper: Optional upper bound for image scale.
            scale_units: Scale units (arcsecperpix, arcminwidth, degwidth).
            downsample_factor: Downsample before solving (faster).

        Returns:
            Submission ID.
        """
        if not self.session_key:
            self.login()

        self._check_cancel()
        self._report(f"Uploading {Path(image_path).name}...")

        upload_args = {
            "session": self.session_key,
            "allow_commercial_use": "n",
            "allow_modifications": "n",
            "publicly_visible": "n",
            "downsample_factor": downsample_factor,
        }

        # Adjust scale hints for the 20% image stretch.
        # arcsecperpix shrinks (each pixel covers less sky after stretching).
        # arcminwidth / degwidth are angular and don't change.
        adj_lower = scale_lower
        adj_upper = scale_upper
        if scale_units == "arcsecperpix":
            if adj_lower is not None:
                adj_lower = adj_lower / SOLVE_IMAGE_SCALE
            if adj_upper is not None:
                adj_upper = adj_upper / SOLVE_IMAGE_SCALE

        if adj_lower is not None:
            upload_args["scale_lower"] = adj_lower
        if adj_upper is not None:
            upload_args["scale_upper"] = adj_upper
        if adj_lower is not None or adj_upper is not None:
            upload_args["scale_units"] = scale_units
            upload_args["scale_type"] = "ul"

        fits_data = _image_to_fits_bytes(image_path)

        resp = requests.post(
            f"{API_BASE}/upload",
            data={"request-json": json.dumps(upload_args)},
            files={"file": (Path(image_path).name, fits_data, "application/fits")},
            timeout=120,
        )
        resp.raise_for_status()
        result = resp.json()

        if result.get("status") != "success":
            raise RuntimeError(
                f"Upload failed: {result.get('errormessage', 'Unknown error')}"
            )

        subid = result["subid"]
        self._report(f"Uploaded. Submission ID: {subid}")
        return subid

    def _poll_submission(self, subid: int, timeout: int = DEFAULT_TIMEOUT) -> int:
        """Poll a submission until a job ID is assigned.

        Returns:
            Job ID.
        """
        self._report("Waiting for job to start...")
        start = time.time()

        while time.time() - start < timeout:
            self._check_cancel()
            resp = requests.get(f"{API_BASE}/submissions/{subid}", timeout=30)
            resp.raise_for_status()
            result = resp.json()

            jobs = result.get("jobs", [])
            if jobs and jobs[0] is not None:
                job_id = jobs[0]
                self._report(f"Job started: {job_id}")
                return job_id

            time.sleep(5)

        raise TimeoutError(f"No job assigned after {timeout}s")

    def _poll_job(self, job_id: int, timeout: int = DEFAULT_TIMEOUT) -> str:
        """Poll a job until it succeeds or fails.

        Returns:
            'success' or 'failure'.
        """
        self._report("Solving...")
        start = time.time()

        while time.time() - start < timeout:
            self._check_cancel()
            resp = requests.get(f"{API_BASE}/jobs/{job_id}", timeout=30)
            resp.raise_for_status()
            result = resp.json()

            status = result.get("status")
            if status == "success":
                self._report("Solve succeeded!")
                return "success"
            elif status == "failure":
                raise RuntimeError("Plate solve failed - no solution found")

            time.sleep(5)

        raise TimeoutError(f"Job did not complete after {timeout}s")

    def _get_calibration(self, job_id: int) -> SolveResult:
        """Retrieve calibration data, object info, and annotations."""
        self._report("Retrieving calibration data...")

        resp = requests.get(f"{API_BASE}/jobs/{job_id}/calibration/", timeout=30)
        resp.raise_for_status()
        cal = resp.json()

        # Get objects in field
        self._report("Retrieving object info...")
        resp2 = requests.get(f"{API_BASE}/jobs/{job_id}/info/", timeout=30)
        resp2.raise_for_status()
        info = resp2.json()

        # Get annotations (pixel positions of objects)
        self._report("Retrieving annotations...")
        annotations = []
        try:
            resp3 = requests.get(
                f"{API_BASE}/jobs/{job_id}/annotations/", timeout=30
            )
            resp3.raise_for_status()
            ann_data = resp3.json()

            for ann in ann_data.get("annotations", []):
                # Each annotation has: type, names, pixelx, pixely, radius
                names = ann.get("names", [])
                name = names[0] if names else ann.get("type", "Unknown")
                annotations.append(
                    Annotation(
                        name=name,
                        pixel_x=float(ann.get("pixelx", 0)),
                        pixel_y=float(ann.get("pixely", 0)),
                        radius=float(ann.get("radius", 30)),
                        ann_type=ann.get("type", ""),
                    )
                )
        except Exception:
            pass  # Annotations are non-critical

        ra = cal["ra"]
        dec = cal["dec"]

        return SolveResult(
            ra=ra,
            dec=dec,
            ra_hms=_ra_to_hms(ra),
            dec_dms=_dec_to_dms(dec),
            orientation=cal.get("orientation", 0.0),
            field_w=cal.get("width_arcmin", 0.0),
            field_h=cal.get("height_arcmin", 0.0),
            pixel_scale=cal.get("pixscale", 0.0),
            parity=("Normal" if cal.get("parity", 0) == 0 else "Flipped"),
            objects_in_field=info.get("objects_in_field", []),
            annotations=annotations,
            job_id=job_id,
            calibration_id=info.get("calibration", 0),
        )

    def solve(
        self,
        image_path: str,
        scale_lower: float | None = None,
        scale_upper: float | None = None,
        scale_units: str = "arcsecperpix",
        timeout: int = DEFAULT_TIMEOUT,
    ) -> SolveResult:
        """Plate solve an image end-to-end.

        Steps: login -> upload -> poll submission -> poll job -> get results.

        Args:
            image_path: Path to FITS or XISF image.
            scale_lower: Optional lower scale hint (speeds up solving).
            scale_upper: Optional upper scale hint.
            scale_units: Units for scale hints.
            timeout: Max seconds to wait for solving.

        Returns:
            SolveResult with coordinates and field info.
        """
        self.cancelled = False

        if not self.session_key:
            self.login()

        subid = self.upload(
            image_path,
            scale_lower=scale_lower,
            scale_upper=scale_upper,
            scale_units=scale_units,
        )

        job_id = self._poll_submission(subid, timeout=timeout)
        self._poll_job(job_id, timeout=timeout)

        result = self._get_calibration(job_id)
        self._report("Plate solve complete!")
        return result
