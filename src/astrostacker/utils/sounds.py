"""Audio notification sounds for process completion.

Uses built-in OS sounds so no audio files need to be bundled.
All functions are non-blocking and fail silently if audio is unavailable.
"""

import platform
import subprocess


def play_success():
    """Play a short bell/chime to notify that a process has finished."""
    try:
        if platform.system() == "Darwin":
            subprocess.Popen(
                ["afplay", "/System/Library/Sounds/Glass.aiff"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        elif platform.system() == "Windows":
            import winsound
            winsound.MessageBeep(winsound.MB_OK)
    except Exception:
        pass  # Audio is non-critical


def play_error():
    """Play a sound to notify that a process has failed."""
    try:
        if platform.system() == "Darwin":
            subprocess.Popen(
                ["afplay", "/System/Library/Sounds/Sosumi.aiff"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        elif platform.system() == "Windows":
            import winsound
            winsound.MessageBeep(winsound.MB_ICONHAND)
    except Exception:
        pass
