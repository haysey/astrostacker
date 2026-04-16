"""FITS file reading and writing via astropy."""

from __future__ import annotations

import numpy as np
from astropy.io import fits


def _read_data(path: str, memmap: bool) -> np.ndarray | None:
    """Try to read image data from a FITS file.

    Returns the raw data array, or None if no image data is found.
    Raises on errors other than BZERO/BSCALE incompatibility.
    """
    try:
        with fits.open(path, memmap=memmap) as hdul:
            data = hdul[0].data
            if data is None:
                for hdu in hdul[1:]:
                    if hdu.data is not None:
                        data = hdu.data
                        break
            if data is not None:
                # Force a read while the file handle is open
                data = np.ascontiguousarray(data, dtype=np.float32)
            return data
    except ValueError as exc:
        if "memmap" in str(exc).lower() and memmap:
            # BZERO/BSCALE/BLANK present — caller should retry without memmap
            return None
        raise


def read(path: str) -> np.ndarray:
    """Read a FITS file and return float32 ndarray.

    Handles mono (H, W) and color (H, W, C) images.
    FITS color images may store channels as NAXIS3 in (C, H, W) order;
    this function transposes them to channels-last (H, W, C).
    """
    # Try memmap first (halves peak RAM per frame), but fall back to
    # non-memmap for FITS files with BZERO/BSCALE/BLANK scaling keywords
    # — astropy cannot apply integer-to-float rescaling on mapped data.
    data = _read_data(path, memmap=True)
    if data is None:
        data = _read_data(path, memmap=False)
    if data is None:
        raise ValueError(f"No image data found in {path}")

    # FITS color images: (C, H, W) -> (H, W, C)
    if data.ndim == 3 and data.shape[0] in (3, 4):
        data = np.transpose(data, (1, 2, 0))
        data = np.ascontiguousarray(data)

    return data


def write(path: str, data: np.ndarray, header_extra: dict | None = None) -> None:
    """Write a float32 ndarray to a FITS file.

    Args:
        path: Output file path.
        data: Image data, shape (H, W) or (H, W, C).
        header_extra: Optional extra header keywords.
    """
    write_data = data.copy()

    # Convert channels-last to FITS channels-first
    if write_data.ndim == 3 and write_data.shape[2] in (3, 4):
        write_data = np.transpose(write_data, (2, 0, 1))

    hdu = fits.PrimaryHDU(write_data.astype(np.float32))
    hdu.header["HISTORY"] = "Stacked with Haysey's Astrostacker"

    # Mark colour images so PixInsight and other readers detect RGB
    if write_data.ndim == 3 and write_data.shape[0] in (3, 4):
        hdu.header["COLORTYP"] = "RGB"

    if header_extra:
        for key, value in header_extra.items():
            hdu.header[key] = value

    hdu.writeto(path, overwrite=True)
