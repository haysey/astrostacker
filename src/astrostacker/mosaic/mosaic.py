"""WCS-based mosaic stitching for multi-panel astrophotography.

Each input panel must be a plate-solved FITS file with valid WCS
(CRPIX, CRVAL, CD matrix).  The mosaic engine:

1. Reads the WCS from each panel to determine sky coverage.
2. Computes a common output WCS grid that spans all panels.
3. Reprojects each panel onto that grid using scipy interpolation.
4. Blends overlapping regions using weighted feathering for
   seamless transitions.

Reference: Calabretta & Greisen 2002, A&A 395, 1077 (WCS standard)
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import numpy as np
from astropy.io import fits
from astropy.wcs import WCS
from scipy.ndimage import map_coordinates


@dataclass
class MosaicPanel:
    """A single panel in the mosaic."""
    path: str
    data: np.ndarray        # (H, W) or (H, W, C)
    wcs: WCS
    weight: np.ndarray      # (H, W) feathering weight map


def _build_feather_weight(h: int, w: int, border: int = 30) -> np.ndarray:
    """Build a feathering weight map that tapers to 0 at edges.

    This ensures smooth blending where panels overlap — the centre
    of each panel has weight 1.0, tapering linearly to 0 at the edges.
    """
    weight = np.ones((h, w), dtype=np.float32)

    for i in range(border):
        t = (i + 1) / border
        weight[i, :] = np.minimum(weight[i, :], t)          # top
        weight[h - 1 - i, :] = np.minimum(weight[h - 1 - i, :], t)  # bottom
        weight[:, i] = np.minimum(weight[:, i], t)           # left
        weight[:, w - 1 - i] = np.minimum(weight[:, w - 1 - i], t)  # right

    return weight


def load_panel(path: str) -> MosaicPanel:
    """Load a plate-solved FITS file as a mosaic panel.

    Raises ValueError if the file has no valid WCS.
    """
    with fits.open(path) as hdul:
        header = hdul[0].header
        data = hdul[0].data.astype(np.float32)

    # FITS stores (C, H, W) for colour — transpose to (H, W, C)
    if data.ndim == 3 and data.shape[0] in (3, 4):
        data = np.transpose(data, (1, 2, 0))

    # Swap byte order if needed
    if data.dtype.byteorder not in ('=', '|', '<' if np.little_endian else '>'):
        data = data.byteswap().view(data.dtype.newbyteorder('='))
        data = np.ascontiguousarray(data)

    wcs = WCS(header, naxis=2)

    # Validate WCS
    if not wcs.has_celestial:
        raise ValueError(
            f"{Path(path).name} has no valid WCS astrometric solution. "
            "Please plate solve this panel first."
        )

    h, w = data.shape[:2]
    weight = _build_feather_weight(h, w)

    return MosaicPanel(path=path, data=data, wcs=wcs, weight=weight)


def _compute_output_wcs(panels: list[MosaicPanel], scale: float = 0.0) -> tuple[WCS, int, int]:
    """Compute an output WCS grid that covers all panels.

    Args:
        panels: List of loaded mosaic panels.
        scale: Output pixel scale in degrees/pixel. 0 = auto (use finest input scale).

    Returns:
        (output_wcs, output_width, output_height)
    """
    # Collect all corner sky coordinates
    all_ra = []
    all_dec = []

    for panel in panels:
        h, w = panel.data.shape[:2]
        corners_pix = np.array([
            [0, 0],
            [w - 1, 0],
            [0, h - 1],
            [w - 1, h - 1],
        ], dtype=np.float64)
        corners_sky = panel.wcs.all_pix2world(corners_pix, 0)
        all_ra.extend(corners_sky[:, 0])
        all_dec.extend(corners_sky[:, 1])

    ra_min, ra_max = min(all_ra), max(all_ra)
    dec_min, dec_max = min(all_dec), max(all_dec)

    # Handle RA wraparound at 360/0 boundary
    ra_range = ra_max - ra_min
    if ra_range > 180:
        # Wraparound — shift negative
        all_ra = [r - 360 if r > 180 else r for r in all_ra]
        ra_min, ra_max = min(all_ra), max(all_ra)

    # Determine pixel scale (use the finest input scale if auto)
    if scale <= 0:
        scales = []
        for panel in panels:
            h, w = panel.data.shape[:2]
            # Measure pixel scale from center
            cx, cy = w / 2, h / 2
            c1 = panel.wcs.all_pix2world([[cx, cy]], 0)[0]
            c2 = panel.wcs.all_pix2world([[cx + 1, cy]], 0)[0]
            dx = abs(c2[0] - c1[0]) * np.cos(np.radians(c1[1]))
            dy = abs(c2[1] - c1[1])
            scales.append(np.sqrt(dx ** 2 + dy ** 2))
        scale = min(scales)

    # Centre of output
    ra_cen = (ra_min + ra_max) / 2
    dec_cen = (dec_min + dec_max) / 2

    # Output dimensions (add 5% padding)
    cos_dec = np.cos(np.radians(dec_cen))
    out_w = int(1.05 * (ra_max - ra_min) * cos_dec / scale) + 1
    out_h = int(1.05 * (dec_max - dec_min) / scale) + 1

    # Ensure reasonable size (cap at 20000 pixels)
    max_dim = 20000
    if out_w > max_dim or out_h > max_dim:
        reduce = max(out_w, out_h) / max_dim
        scale *= reduce
        out_w = int(out_w / reduce)
        out_h = int(out_h / reduce)

    # Build output WCS (simple TAN projection)
    out_wcs = WCS(naxis=2)
    out_wcs.wcs.crpix = [out_w / 2, out_h / 2]
    out_wcs.wcs.crval = [ra_cen, dec_cen]
    out_wcs.wcs.cdelt = [-scale, scale]  # RA decreases with pixel X
    out_wcs.wcs.ctype = ["RA---TAN", "DEC--TAN"]

    return out_wcs, out_w, out_h


def _reproject_panel(
    panel: MosaicPanel,
    out_wcs: WCS,
    out_w: int,
    out_h: int,
) -> tuple[np.ndarray, np.ndarray]:
    """Reproject a single panel onto the output WCS grid.

    Returns:
        (reprojected_data, reprojected_weight) matching output grid size.
    """
    # Build grid of output pixel coordinates
    yy, xx = np.mgrid[0:out_h, 0:out_w]

    # Output pixels -> sky coordinates
    sky = out_wcs.all_pix2world(
        np.column_stack([xx.ravel(), yy.ravel()]), 0
    )

    # Sky coordinates -> input panel pixel coordinates
    in_pix = panel.wcs.all_world2pix(sky, 0)
    in_x = in_pix[:, 0].reshape(out_h, out_w)
    in_y = in_pix[:, 1].reshape(out_h, out_w)

    in_h, in_w = panel.data.shape[:2]

    # Mask: which output pixels fall within this panel
    valid = (
        (in_x >= 0) & (in_x < in_w - 1) &
        (in_y >= 0) & (in_y < in_h - 1)
    )

    is_colour = panel.data.ndim == 3
    coords = np.array([in_y, in_x])

    if is_colour:
        n_ch = panel.data.shape[2]
        out_data = np.zeros((out_h, out_w, n_ch), dtype=np.float32)
        for c in range(n_ch):
            channel = map_coordinates(
                panel.data[:, :, c], coords, order=1, mode='constant', cval=0
            ).reshape(out_h, out_w)
            out_data[:, :, c] = np.where(valid, channel, 0)
    else:
        out_data = map_coordinates(
            panel.data, coords, order=1, mode='constant', cval=0
        ).reshape(out_h, out_w).astype(np.float32)
        out_data = np.where(valid, out_data, 0)

    # Reproject the feathering weights too
    out_weight = map_coordinates(
        panel.weight, coords, order=1, mode='constant', cval=0
    ).reshape(out_h, out_w).astype(np.float32)
    out_weight = np.where(valid, out_weight, 0)

    return out_data, out_weight


def build_mosaic(
    panel_paths: list[str],
    output_path: str = "",
    status_callback: Callable[[str], None] | None = None,
) -> np.ndarray:
    """Build a mosaic from plate-solved FITS panels.

    Args:
        panel_paths: Paths to plate-solved FITS files.
        output_path: If set, save the mosaic FITS here.
        status_callback: Optional callback for progress messages.

    Returns:
        Mosaic image as float32 ndarray.
    """
    def _report(msg: str):
        if status_callback:
            status_callback(msg)

    if len(panel_paths) < 2:
        raise ValueError("Need at least 2 panels for a mosaic")

    # Load panels
    _report(f"Loading {len(panel_paths)} panels...")
    panels = []
    for i, path in enumerate(panel_paths):
        _report(f"  Loading panel {i + 1}: {Path(path).name}")
        panels.append(load_panel(path))

    # Compute output grid
    _report("Computing output mosaic grid...")
    out_wcs, out_w, out_h = _compute_output_wcs(panels)
    _report(f"  Output size: {out_w} x {out_h} pixels")

    is_colour = panels[0].data.ndim == 3

    # Reproject and accumulate
    if is_colour:
        n_ch = panels[0].data.shape[2]
        flux_sum = np.zeros((out_h, out_w, n_ch), dtype=np.float64)
    else:
        flux_sum = np.zeros((out_h, out_w), dtype=np.float64)
    weight_sum = np.zeros((out_h, out_w), dtype=np.float64)

    for i, panel in enumerate(panels):
        _report(f"Reprojecting panel {i + 1}/{len(panels)}: {Path(panel.path).name}")
        data, weight = _reproject_panel(panel, out_wcs, out_w, out_h)

        if is_colour:
            for c in range(n_ch):
                flux_sum[:, :, c] += data[:, :, c] * weight
        else:
            flux_sum += data * weight
        weight_sum += weight

    # Normalize
    _report("Blending panels...")
    good = weight_sum > 0
    if is_colour:
        result = np.zeros_like(flux_sum, dtype=np.float32)
        for c in range(n_ch):
            result[:, :, c][good] = (flux_sum[:, :, c][good] / weight_sum[good]).astype(np.float32)
    else:
        result = np.zeros_like(flux_sum, dtype=np.float32)
        result[good] = (flux_sum[good] / weight_sum[good]).astype(np.float32)

    # Save if requested
    if output_path:
        _report(f"Saving mosaic to {output_path}...")
        hdu = fits.PrimaryHDU(data=result.astype(np.float32))
        # Write output WCS to header
        hdu.header.update(out_wcs.to_header())
        hdu.writeto(output_path, overwrite=True)
        _report(f"Mosaic saved: {out_w} x {out_h}")

    _report(f"Mosaic complete! {len(panels)} panels stitched into {out_w} x {out_h}")
    return result
