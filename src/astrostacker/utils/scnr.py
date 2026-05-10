"""Subtractive Chromatic Noise Reduction (SCNR) for astrophotography.

SCNR reduces the contribution of a target channel (typically green) where
it exceeds the level predicted by the other two channels.  This corrects
the strong green excess caused by:

  - Bayer RGGB sensors (two green photosites per four-pixel block)
  - Residual green airglow after stacking
  - Per-star colour artefacts from demosaicing

Algorithm: Average Neutral Protection
--------------------------------------
For every pixel the "neutral" value for the target channel is defined as
the arithmetic mean of the other two channels:

    neutral = (other_1 + other_2) / 2

Where the target channel exceeds the neutral value, the excess is reduced
by the requested fraction (amount):

    channel_new = channel - (channel - neutral) * amount

Pixels where the target channel is already ≤ neutral are left unchanged.
This is purely subtractive — star halos and nebula structure that is
genuinely in the target channel are not affected, only the colour excess.

    amount = 1.0  →  full removal (classic PixInsight SCNR default)
    amount = 0.5  →  half-strength (softer, less aggressive)
    amount = 0.0  →  no-op
"""

from __future__ import annotations

import numpy as np


def apply_scnr(
    data: np.ndarray,
    amount: float = 1.0,
    target_channel: int = 1,          # 0 = R, 1 = G, 2 = B  (green is default)
) -> np.ndarray:
    """Apply Average Neutral Protection SCNR.

    Args:
        data:           Float32 colour image (H, W, 3).  Mono images are
                        returned unchanged.
        amount:         Reduction strength 0.0–1.0.  1.0 = full SCNR
                        (target channel capped at the neutral average of the
                        other two channels).  0.0 = no change.
        target_channel: Channel index to reduce.  Defaults to 1 (green).

    Returns:
        Float32 array the same shape as *data*, clipped to ≥ 0.
    """
    if data.ndim != 3 or data.shape[2] < 3:
        return data.astype(np.float32)

    amount = float(np.clip(amount, 0.0, 1.0))
    if amount == 0.0:
        return data.astype(np.float32)

    result = data.astype(np.float32, copy=True)

    tc = target_channel
    other = [c for c in range(result.shape[2]) if c != tc]

    # Neutral level: average of the other two channels
    neutral = np.mean(
        [result[:, :, c].astype(np.float64) for c in other], axis=0
    ).astype(np.float32)

    ch = result[:, :, tc]

    # Only touch pixels where the target channel is above neutral
    excess_mask = ch > neutral
    result[:, :, tc] = np.where(
        excess_mask,
        ch - (ch - neutral) * amount,
        ch,
    )

    return np.clip(result, 0.0, None).astype(np.float32)
