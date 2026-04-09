"""FITS file reading and writing via astropy."""

from __future__ import annotations

import numpy as np
from astropy.io import fits


def read(path: str) -> np.ndarray:
    """Read a FITS file and return float32 ndarray.

    Handles mono (H, W) and color (H, W, C) images.
    FITS color images may store channels as NAXIS3 in (C, H, W) order;
    this function transposes them to channels-last (H, W, C).
    """
    with fits.open(path, memmap=False) as hdul:
        data = hdul[0].data
        if data is None:
            # Try the first extension with data
            for hdu in hdul[1:]:
                if hdu.data is not None:
                    data = hdu.data
                    break
        if data is None:
            raise ValueError(f"No image data found in {path}")

        # FITS stores data as big-endian. Convert to native byte order
        # float32 so downstream libraries (sep, scikit-image) work correctly.
        data = np.ascontiguousarray(data, dtype=np.float32)

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
