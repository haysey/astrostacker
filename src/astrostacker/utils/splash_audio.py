"""Splash screen orchestral launch fanfare.

Full orchestral arrangement over the 7-second splash screen:

  Harp    -- opening arpeggio (Em sparkle, first ~0.8 s)
  Strings -- sustained ensemble pad, chord progression Em → G → Am → Em
  Bass    -- low cello anchoring each chord root
  Flute   -- melody line on top (E-minor pentatonic, ~6.5 s)
  Reverb  -- Schroeder hall reverb via scipy (already a dependency)

All synthesis from numpy + stdlib (wave).  No new packages needed.
Runs in a daemon thread — non-blocking, silently fails if audio is
unavailable so the splash always appears.
"""

from __future__ import annotations

import io
import os
import platform
import subprocess
import tempfile
import threading
import time
import wave

import numpy as np
from scipy.signal import lfilter


_SR = 44_100   # sample rate (Hz)


# ── Melody (E minor pentatonic) ────────────────────────────────────────
# (freq_hz, duration_sec)  —  0 Hz = rest

_MELODY: list[tuple[float, float]] = [
    # Phrase 1 — ascending arpeggio
    (329.63, 0.30),   # E4
    (392.00, 0.30),   # G4
    (493.88, 0.30),   # B4
    (659.25, 0.60),   # E5  ← peak
    (493.88, 0.30),   # B4
    (392.00, 0.30),   # G4
    (440.00, 0.30),   # A4
    (493.88, 0.60),   # B4  ← held
    # Breath
    (0,      0.15),
    # Phrase 2 — variation, resolves home
    (440.00, 0.30),   # A4
    (493.88, 0.30),   # B4
    (587.33, 0.30),   # D5
    (659.25, 0.50),   # E5  ← peak
    (493.88, 0.25),   # B4
    (392.00, 0.25),   # G4
    (329.63, 0.90),   # E4  ← resolution
]
# Total ≈ 6.65 s


# ── Orchestral chord sequence ──────────────────────────────────────────
# Em → G → Am → Em  (classic cinematic minor)
# (start_sec, end_sec, [string_freqs], bass_freq)

_ORCH_CHORDS: list[tuple[float, float, list[float], float]] = [
    (0.00, 2.10, [164.81, 196.00, 246.94], 82.41),   # Em  E3 G3 B3 / bass E2
    (1.55, 3.35, [196.00, 246.94, 293.66], 98.00),   # G   G3 B3 D4 / bass G2
    (2.95, 4.85, [220.00, 261.63, 329.63], 110.00),  # Am  A3 C4 E4 / bass A2
    (4.45, 6.80, [164.81, 246.94, 329.63], 82.41),   # Em  E3 B3 E4 / bass E2
]

# Harp opening arpeggio — Em chord, ascending
_HARP_FREQS = [164.81, 196.00, 246.94, 329.63, 392.00]   # E3 G3 B3 E4 G4


# ── Synthesis helpers ──────────────────────────────────────────────────

def _phase(inst_freq: np.ndarray) -> np.ndarray:
    """Accumulate phase from instantaneous frequency array (float64 precision)."""
    return (2.0 * np.pi * np.cumsum(inst_freq.astype(np.float64)) / _SR).astype(np.float32)


def _amp_env(n: int, atk_s: float, sus: float, rel_s: float) -> np.ndarray:
    """Simple attack–sustain–release amplitude envelope."""
    atk = min(int(_SR * atk_s), n // 4)
    rel = min(int(_SR * rel_s), n // 3)
    env = np.full(n, sus, dtype=np.float32)
    if atk:
        env[:atk] = np.linspace(0.0, 1.0, atk)
    if rel:
        env[n - rel:] = np.linspace(sus, 0.0, rel)
    return env


# ── Flute melody note ──────────────────────────────────────────────────

def _make_flute_note(freq: float, dur: float) -> np.ndarray:
    """Concert flute: FM vibrato, attack chiff, breathiness, ADSR."""
    n = int(_SR * dur)
    if freq == 0 or n == 0:
        return np.zeros(n, dtype=np.float32)

    rng = np.random.default_rng(int(freq * 137))
    t   = np.linspace(0.0, dur, n, endpoint=False, dtype=np.float32)

    # Vibrato — delayed onset, gradual ramp
    VIB_RATE  = 5.5
    VIB_DEPTH = 0.006
    vib_delay = min(0.18, dur * 0.35)
    vib_ramp  = min(0.22, dur * 0.30)
    dn, rn = int(_SR * vib_delay), int(_SR * vib_ramp)
    vib_env = np.zeros(n, dtype=np.float32)
    if dn < n:
        end = min(dn + rn, n)
        vib_env[dn:end] = np.linspace(0.0, 1.0, end - dn)
        vib_env[end:] = 1.0

    inst_f = freq * (1.0 + VIB_DEPTH * vib_env * np.sin(2.0 * np.pi * VIB_RATE * t))
    ph = _phase(inst_f)

    # Harmonics (register-dependent — high notes are purer)
    h2 = 0.16 if freq < 450 else 0.09
    sig  = np.sin(ph)
    sig += h2   * np.sin(2.0 * ph)
    sig += 0.03 * np.sin(3.0 * ph)

    # Amplitude vibrato (±3 %, in sync)
    sig *= 1.0 + 0.03 * vib_env * np.sin(2.0 * np.pi * VIB_RATE * t + 0.4)

    # Attack chiff
    cn = min(int(_SR * 0.022), n // 6)
    if cn:
        chiff = rng.standard_normal(cn).astype(np.float32)
        sig[:cn] += chiff * np.linspace(0.20, 0.0, cn)

    # Breathiness
    noise = rng.standard_normal(n).astype(np.float32)
    smooth = max(2, int(_SR / max(freq * 3.0, 1.0)))
    noise = np.convolve(noise, np.ones(smooth) / smooth, mode='same')
    sig += noise * (0.022 * np.exp(-t * 13.0) + 0.005).astype(np.float32)

    sig *= _amp_env(n, 0.020, 0.80, 0.115)
    sig *= 0.40
    return sig.astype(np.float32)


# ── String ensemble pad ────────────────────────────────────────────────

def _make_string_pad(freqs: list[float], dur: float) -> np.ndarray:
    """Orchestral string section: multiple detuned voices, rich harmonics.

    The ensemble detuning (±5 cents across 5 voices per note) creates
    the characteristic beating and warmth of real string players who are
    never perfectly in unison.
    """
    n   = int(_SR * dur)
    mix = np.zeros(n, dtype=np.float32)
    t   = np.linspace(0.0, dur, n, endpoint=False, dtype=np.float32)

    for freq in freqs:
        rng = np.random.default_rng(int(freq * 89))
        for cents in np.linspace(-5.0, 5.0, 5):
            f   = freq * (2.0 ** (cents / 1200.0))
            vp  = rng.uniform(0, 2 * np.pi)   # random vibrato phase per player
            inst_f = f * (1.0 + 0.004 * np.sin(2.0 * np.pi * 5.7 * t + vp))
            ph = _phase(inst_f)

            # Rich harmonic series (strings carry many overtones)
            v  = np.sin(ph)
            v += 0.48 * np.sin(2.0 * ph)
            v += 0.30 * np.sin(3.0 * ph)
            v += 0.18 * np.sin(4.0 * ph)
            v += 0.10 * np.sin(5.0 * ph)
            v += 0.05 * np.sin(6.0 * ph)
            mix += v

    n_voices = len(freqs) * 5
    mix /= n_voices

    # Subtle bow noise (strongest at attack)
    rng2 = np.random.default_rng(7)
    noise = rng2.standard_normal(n).astype(np.float32)
    mix  += noise * (0.014 * np.exp(-t * 7.0) + 0.003).astype(np.float32)

    mix *= _amp_env(n, 0.07, 0.88, 0.22)
    mix *= 0.30
    return mix.astype(np.float32)


# ── Bass cello ─────────────────────────────────────────────────────────

def _make_bass_note(freq: float, dur: float) -> np.ndarray:
    """Deep cello/bass: very rich harmonics, slow bow attack."""
    n  = int(_SR * dur)
    t  = np.linspace(0.0, dur, n, endpoint=False, dtype=np.float32)
    ph = 2.0 * np.pi * freq * t

    sig  = np.sin(ph)
    sig += 0.55 * np.sin(2.0 * ph)
    sig += 0.35 * np.sin(3.0 * ph)
    sig += 0.20 * np.sin(4.0 * ph)
    sig += 0.10 * np.sin(5.0 * ph)
    sig += 0.06 * np.sin(6.0 * ph)

    sig *= _amp_env(n, 0.08, 0.85, 0.28)
    sig *= 0.24
    return sig.astype(np.float32)


# ── Harp arpeggio ──────────────────────────────────────────────────────

def _make_harp_arpeggio(freqs: list[float], total_dur: float) -> np.ndarray:
    """Plucked harp: bright attack, natural exponential decay, strummed."""
    n   = int(_SR * total_dur)
    sig = np.zeros(n, dtype=np.float32)

    for i, freq in enumerate(freqs):
        offset = int(i * 0.058 * _SR)    # 58 ms between string plucks
        if offset >= n:
            break
        rem = n - offset
        t   = np.linspace(0.0, rem / _SR, rem, endpoint=False, dtype=np.float32)

        tone  = np.sin(2.0 * np.pi * freq * t)
        tone += 0.40 * np.sin(4.0 * np.pi * freq * t)   # 2nd harmonic
        tone += 0.12 * np.sin(6.0 * np.pi * freq * t)   # 3rd
        tone *= np.exp(-t * 2.6)                          # harp decay

        sig[offset:] += tone * 0.38

    return sig.astype(np.float32)


# ── Hall reverb ────────────────────────────────────────────────────────

def _hall_reverb(signal: np.ndarray, wet: float = 0.20) -> np.ndarray:
    """Schroeder reverberator: 4 parallel comb filters + 2 all-pass.

    Uses scipy.signal.lfilter (already a project dependency) for fast
    vectorised IIR filtering — no Python loops over samples.
    """
    # 4 parallel feedback comb filters
    comb_params = [
        (int(_SR * 0.0297), 0.820),
        (int(_SR * 0.0371), 0.808),
        (int(_SR * 0.0411), 0.798),
        (int(_SR * 0.0437), 0.790),
    ]
    rev = np.zeros_like(signal)
    for delay, decay in comb_params:
        a = np.zeros(delay + 1)
        a[0] = 1.0
        a[delay] = -decay
        rev += lfilter([1.0], a, signal)
    rev /= 4.0

    # 2 series all-pass filters for diffusion
    for delay, decay in [(89, 0.7), (179, 0.7)]:
        b = np.zeros(delay + 1)
        b[0] = -decay
        b[delay] = 1.0
        a = np.zeros(delay + 1)
        a[0] = 1.0
        a[delay] = -decay
        rev = lfilter(b, a, rev)

    return (signal * (1.0 - wet) + rev * wet).astype(np.float32)


# ── Master render ──────────────────────────────────────────────────────

def _build_wav_bytes() -> bytes:
    """Render the full orchestral arrangement to 16-bit mono WAV bytes."""

    total_s = sum(d for _, d in _MELODY) + 0.9
    total_n = int(_SR * total_s)

    # ── Harp (opening arpeggio, rings for ~3 s) ─────────────────────
    harp = _make_harp_arpeggio(_HARP_FREQS, min(3.0, total_s))

    # ── Strings + bass per chord ─────────────────────────────────────
    strings = np.zeros(total_n, dtype=np.float32)
    bass    = np.zeros(total_n, dtype=np.float32)

    for start_s, end_s, str_freqs, bass_freq in _ORCH_CHORDS:
        dur = end_s - start_s
        off = int(_SR * start_s)

        pad  = _make_string_pad(str_freqs, dur)
        bl   = _make_bass_note(bass_freq, dur)

        for arr, layer in [(pad, strings), (bl, bass)]:
            end_idx = min(off + len(arr), total_n)
            layer[off:end_idx] += arr[: end_idx - off]

    # ── Flute melody ─────────────────────────────────────────────────
    melody = np.concatenate([_make_flute_note(f, d) for f, d in _MELODY])

    # ── Mix ──────────────────────────────────────────────────────────
    audio = np.zeros(total_n, dtype=np.float32)
    audio[:min(len(harp),   total_n)] += harp[:total_n]
    audio += strings
    audio += bass
    audio[:len(melody)]               += melody

    # ── Hall reverb ──────────────────────────────────────────────────
    audio = _hall_reverb(audio, wet=0.18)

    # ── Fade out last 0.70 s ─────────────────────────────────────────
    fade_n = min(int(_SR * 0.70), total_n)
    audio[-fade_n:] *= np.linspace(1.0, 0.0, fade_n, dtype=np.float32)

    # ── Normalise to 90 % full scale ─────────────────────────────────
    peak = np.max(np.abs(audio))
    if peak > 0:
        audio *= 0.90 / peak

    pcm = (audio * 32_767).astype(np.int16)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(_SR)
        wf.writeframes(pcm.tobytes())
    return buf.getvalue()


# ── Playback ───────────────────────────────────────────────────────────

def _schedule_delete(path: str, delay: float) -> None:
    def _rm():
        time.sleep(delay)
        try:
            os.unlink(path)
        except Exception:
            pass
    threading.Thread(target=_rm, daemon=True).start()


def _play(wav_bytes: bytes) -> None:
    """Write WAV to a temp file and hand it to the platform audio system."""
    fd, tmp = tempfile.mkstemp(suffix=".wav", prefix="astrostacker_")
    try:
        os.write(fd, wav_bytes)
        os.close(fd)

        system = platform.system()

        if system == "Darwin":
            subprocess.Popen(
                ["afplay", "-v", "0.85", tmp],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            _schedule_delete(tmp, delay=10.0)

        elif system == "Windows":
            import winsound
            winsound.PlaySound(tmp, winsound.SND_FILENAME | winsound.SND_ASYNC)
            _schedule_delete(tmp, delay=10.0)

        else:
            launched = False
            for player in ("pw-play", "paplay", "aplay"):
                try:
                    subprocess.Popen(
                        [player, tmp],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
                    launched = True
                    break
                except FileNotFoundError:
                    continue
            _schedule_delete(tmp, delay=10.0 if launched else 0.5)

    except Exception:
        try:
            os.close(fd)
        except Exception:
            pass
        try:
            os.unlink(tmp)
        except Exception:
            pass


# ── Public API ─────────────────────────────────────────────────────────

def play_splash_melody() -> None:
    """Generate and play the orchestral launch fanfare in a daemon thread.

    Returns immediately.  The splash screen appears and the app loads
    regardless of whether audio is available on this system.
    """
    def _worker() -> None:
        try:
            _play(_build_wav_bytes())
        except Exception:
            pass

    threading.Thread(target=_worker, daemon=True, name="splash-melody").start()
