"""Light pollution gradient and amp-glow removal via background modelling.

Estimates the 2-D sky background using a sigma-clipped grid sampler,
then subtracts it.  The approach captures any smooth large-scale
variation — light pollution gradients, vignetting, and amp glow
concentrated in sensor corners — without assuming a fixed polynomial form.

Algorithm
---------
1. Divide the image into a 32 × 32 grid of cells.
2. In each cell, estimate the sky by iteratively sigma-clipping to reject
   stars (reject values above median + 3 × MAD, 3 passes).
3. Apply a 3 × 3 median filter across the grid to smooth noisy cells.
4. Bicubic-interpolate (scipy.ndimage.zoom) back to the full image size.
5. Subtract the surface, then re-centre so the sky sits at zero.

Why this is better than the old 2nd-order polynomial
------------------------------------------------------
A 6-parameter polynomial is fitted globally: it cannot model a steep
exponential ramp confined to one corner (typical amp glow) without
distorting the rest of the image.  The grid sampler makes no assumption
about shape — it follows the actual background wherever it goes.
"""

from __future__ import annotations

import numpy as np


def _sigma_clipped_sky(values: np.ndarray, max_iters: int = 3) -> float:
    """Return the sigma-clipped sky estimate for a 1-D array of pixel values.

    Stars and hot pixels are rejected by iteratively discarding anything
    above median + 3 × MAD.  Returns the median of the surviving values.
    """
    vals = values[np.isfinite(values)]
    vals = vals[vals > 0]
    if len(vals) < 5:
        return float(np.nanmedian(values)) if len(values) else 0.0

    for _ in range(max_iters):
        med = np.median(vals)
        mad = np.median(np.abs(vals - med)) * 1.4826
        keep = vals <= med + 3.0 * mad
        if keep.sum() < 5:
            break
        vals = vals[keep]

    return float(np.median(vals))


def _fit_background_surface(data_2d: np.ndarray, grid_size: int = 6) -> np.ndarray:
    """Estimate the 2-D sky background using a sigma-clipped grid.

    Grid size is set to 6×6 (cells of ~690×470 pixels for a typical
    camera frame).  This is a deliberate compromise between two competing
    demands:

    • Amp-glow removal needs fine enough cells that the corner glow — often
      confined to the outermost 100–300 pixels — represents a significant
      fraction of each corner cell and is captured by the sigma-clipped
      median.  A 4×4 grid (cells ~1000×700 px) diluted the corner glow to
      only ~20 % of the cell, leaving a visible residual.  A 6×6 grid
      raises that to ~30 %, reliably pulling the glow into the background
      model.

    • Nebulosity over-subtraction requires coarser cells so that extended
      emission (Hα, OIII) is outweighed by genuine sky pixels and does not
      get absorbed into the background estimate.  The 8×8 grid that preceded
      this caused visible over-subtraction on star-dense Milky Way fields.
      At 6×6 the cell area is still 1.78× larger than 8×8, keeping nebulosity
      bias low while recovering the amp-glow sensitivity.

    The sigma-clipped sky estimator and bicubic upsampling give better edge
    fidelity than the old 25th-percentile + 2nd-order polynomial approach.

    Args:
        data_2d: 2-D float image (single channel).
        grid_size: Number of grid divisions along each axis.

    Returns:
        Background model with the same shape as input, as float32.
    """
    try:
        from scipy.ndimage import zoom, median_filter
        _SCIPY = True
    except ImportError:
        _SCIPY = False

    h, w = data_2d.shape
    cell_h = max(1, h // grid_size)
    cell_w = max(1, w // grid_size)
    grid_h = (h + cell_h - 1) // cell_h
    grid_w = (w + cell_w - 1) // cell_w

    # ── Sample the sigma-clipped sky in every grid cell ───────────────
    bg_grid = np.zeros((grid_h, grid_w), dtype=np.float64)
    global_sky = float(np.nanmedian(data_2d))

    for gy in range(grid_h):
        for gx in range(grid_w):
            y0 = gy * cell_h
            y1 = min(y0 + cell_h, h)
            x0 = gx * cell_w
            x1 = min(x0 + cell_w, w)
            cell = data_2d[y0:y1, x0:x1].ravel()
            sky = _sigma_clipped_sky(cell)
            bg_grid[gy, gx] = sky if sky > 0 else global_sky

    # ── Smooth the grid to fill noisy / star-contaminated cells ──────
    if _SCIPY:
        bg_grid = median_filter(bg_grid, size=3)

    # ── Upsample back to full image resolution ────────────────────────
    if _SCIPY:
        zoom_y = h / grid_h
        zoom_x = w / grid_w
        surface = zoom(bg_grid, (zoom_y, zoom_x), order=3)  # bicubic
        surface = surface[:h, :w]                            # trim rounding
    else:
        # Fallback: bilinear with numpy if scipy is unavailable
        from numpy import interp
        ys = np.linspace(0, grid_h - 1, h)
        xs = np.linspace(0, grid_w - 1, w)
        # Two-pass bilinear via row then column interpolation
        rows = np.array([interp(xs, np.arange(grid_w), bg_grid[int(round(y))])
                         for y in ys])
        surface = rows

    return surface.astype(np.float32)


def _cleanup_corner_glow(
    channel: np.ndarray,
    corner_frac: float = 0.20,
    grid_size: int = 8,
) -> np.ndarray:
    """Remove residual amp glow from image corners with a dedicated fine-grid pass.

    Called as a *second* pass after the main 6×6 background subtraction.  The
    main grid captures the broad gradient but leaves residual amp glow because
    the glow — typically confined to the outermost 100–300 pixels — fills only
    ~20–30 % of a corner cell and is diluted by the surrounding sky, so the
    sigma-clipped median is pulled toward the sky level rather than the peak
    of the glow.

    This function isolates the four corner regions (outermost ``corner_frac``
    of each axis), fits a fine ``grid_size × grid_size`` background model
    inside that region, and subtracts it.  The image centre — where nebulosity
    and other faint signal lives — is never touched, so there is zero risk of
    over-subtraction on extended emission fields.

    Args:
        channel: 2-D float32 array (single channel) that has already had the
                 main background gradient removed.
        corner_frac: Fraction of image height / width defining each corner zone.
                     0.20 = outermost 20 % on each side.
        grid_size: Number of grid divisions inside each corner zone.
                   At 8×8 inside a 20 % corner, each cell covers roughly
                   (0.20 × H / 8) × (0.20 × W / 8) ≈ 87 × 104 px for a
                   typical ASI294MC frame — small enough to capture even a
                   tight corner glow.

    Returns:
        Channel with corner amp glow further reduced (modified in place and
        returned as a new float32 array for the modified corners).
    """
    h, w = channel.shape
    ch = max(grid_size * 2, int(h * corner_frac))
    cw = max(grid_size * 2, int(w * corner_frac))

    corners = [
        (slice(None, ch),     slice(None, cw)),       # top-left
        (slice(None, ch),     slice(w - cw, None)),   # top-right
        (slice(h - ch, None), slice(None, cw)),        # bottom-left
        (slice(h - ch, None), slice(w - cw, None)),   # bottom-right
    ]
    for y_sl, x_sl in corners:
        patch = channel[y_sl, x_sl]
        if patch.size < grid_size * grid_size * 4:
            continue  # corner too small to fit a meaningful grid
        bg = _fit_background_surface(patch, grid_size=grid_size)
        channel[y_sl, x_sl] = np.clip(patch - bg, 0, None).astype(np.float32)

    return channel


def remove_gradient(data: np.ndarray, grid_size: int = 6) -> np.ndarray:
    """Remove light pollution gradient and amp glow from an image.

    Works with both mono (H, W) and colour (H, W, C) images.
    Subtracts a fitted background model from each channel independently
    (each channel can have a different gradient / amp-glow profile),
    then re-centres ALL channels by the same luminance-derived pedestal
    so that the R : G : B ratios — and therefore the colour balance —
    are preserved.

    Using a per-channel pedestal (the old approach) shifted each channel
    by a different amount, which broke white balance and produced colour
    casts, especially on star-dense fields where the sky estimator gives
    slightly different readings for each channel.

    Args:
        data: Input image as float32 ndarray.
        grid_size: Number of grid divisions along each axis for the
                   background sampler.  6 (default) is a good balance
                   for final stacks.  Use 12 for per-frame local
                   normalisation: smaller cells (~235 × 345 px) capture
                   edge / corner amp glow that fills only ~200 px from
                   the sensor edge — at 12 × 12 the glow fills ~49 % of
                   each corner cell, enough for the sigma-clipped median
                   to model and remove it.

    Returns:
        Gradient-corrected image as float32.
    """
    if data.ndim == 3:
        result = np.empty(data.shape, dtype=np.float32)

        # ── Step 1: per-channel background subtraction ────────────────
        # Each channel can have a different sky gradient, vignetting or
        # amp-glow pattern, so the background model is fitted per channel.
        for c in range(data.shape[2]):
            bg = _fit_background_surface(data[:, :, c], grid_size=grid_size)
            result[:, :, c] = (data[:, :, c] - bg).astype(np.float32)

        # ── Step 2: single luminance pedestal for all channels ────────
        # Derive the pedestal from the mean of all corrected channels
        # (luminance proxy) and apply the *same* shift to every channel.
        # This keeps R : G : B ratios unchanged, preserving colour balance
        # even when the three channels started with slightly different sky
        # levels.
        lum = np.nanmean(result, axis=2)           # (H, W)
        valid = lum[np.isfinite(lum)].ravel()
        if len(valid) > 0:
            # Use 0.1th percentile (not 1st) so only extreme outlier pixels
            # are clipped.  Dust lanes in emission-rich fields can cover
            # 10–20 % of the frame; a 1 % floor clips significant structure
            # within the dust.  0.1 % preserves the full dark-lane gradient.
            k = max(0, len(valid) // 1000)        # 0.1th-percentile index
            pedestal = float(np.partition(valid, k)[k])
            result -= pedestal                     # same shift for R, G, B
            np.clip(result, 0, None, out=result)   # clean floor

        # ── Step 3: per-channel sky neutralisation ────────────────────
        # After the common pedestal shift the sky may still be colour-
        # tinted.  On Milky Way emission fields, widespread Hα lifts the
        # R channel slightly above the sky floor even after background
        # subtraction.  Sample the four image corners — typically free of
        # bright nebulosity and dominated by true sky — and subtract the
        # per-channel excess above the darkest channel.  The correction is
        # tiny relative to the signal (< 1 % of the dynamic range), so
        # stars and nebulae are unaffected while the background becomes
        # colour-neutral, letting OIII blue-green emerge alongside Hα red.
        _h, _w = result.shape[:2]
        _cs_h = max(1, _h // 10)   # 10 % border on each axis
        _cs_w = max(1, _w // 10)
        _corners = np.concatenate([
            result[:_cs_h,         :_cs_w,        :].reshape(-1, result.shape[2]),
            result[:_cs_h,         _w - _cs_w:,   :].reshape(-1, result.shape[2]),
            result[_h - _cs_h:,    :_cs_w,        :].reshape(-1, result.shape[2]),
            result[_h - _cs_h:,    _w - _cs_w:,   :].reshape(-1, result.shape[2]),
        ], axis=0)
        ch_sky = []
        for c in range(result.shape[2]):
            cv = _corners[:, c]
            cv = cv[np.isfinite(cv) & (cv >= 0)]
            ch_sky.append(float(np.median(cv)) if len(cv) > 0 else 0.0)

        ref_sky = min(ch_sky)
        for c in range(result.shape[2]):
            excess = ch_sky[c] - ref_sky
            if excess > 0:
                result[:, :, c] = np.clip(result[:, :, c] - excess, 0, None)

        return result

    return _remove_gradient_channel(data, grid_size=grid_size)


def _remove_gradient_channel(channel: np.ndarray, grid_size: int = 6) -> np.ndarray:
    """Remove gradient from a single 2-D channel."""
    bg = _fit_background_surface(channel, grid_size=grid_size)
    corrected = (channel - bg).astype(np.float32)

    # Re-centre: shift so the sky background sits at a small positive
    # pedestal (1st percentile of the corrected image) rather than at zero.
    # This preserves faint signal near zero without clipping it.
    valid = corrected[np.isfinite(corrected)]
    if len(valid) > 0:
        k = max(0, len(valid) // 1000)           # 0.1th percentile
        pedestal = float(np.partition(valid, k)[k])
        corrected = corrected - pedestal          # shift, keep negatives
        corrected = np.clip(corrected, 0, None)   # clean floor

    return corrected.astype(np.float32)
