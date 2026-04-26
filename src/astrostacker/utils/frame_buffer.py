"""Disk-backed frame buffer for low-RAM stacking of large frame sets.

numpy.memmap stores the calibrated frame array on disk as a temporary file
and lets the OS page portions in/out of RAM on demand.  This means:

  * A 594-frame, 140 MB/frame colour stack (83 GB total) can be processed
    on a machine with 8 GB of RAM — the OS keeps only the actively-needed
    pages in RAM and pages the rest out automatically.
  * No MemoryError crashes from allocating the full dataset at once.
  * The temp file is always cleaned up, even if an exception is raised.

Platform notes
--------------
Works identically on macOS, Windows, and Linux.  The only platform-specific
detail is Windows: a memory-mapped file cannot be deleted while the mapping
is open.  ``close()`` explicitly calls ``del self._buf`` (which flushes and
releases the file handle) *before* ``os.unlink()``, which is the correct
order on all platforms and essential on Windows.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import numpy as np


class _FrameBuffer:
    """Temporary disk-backed ``(n_frames, *frame_shape)`` float32 array.

    Behaves like a numpy array for per-frame access::

        with _FrameBuffer(n, (H, W, 3)) as buf:
            buf[i] = some_frame          # write frame i to disk
            view = buf.frame_view(i)     # zero-copy read-on-demand view
            copy = buf[i]                # fresh in-RAM copy of frame i

    The backing file lives in the OS temp directory (or *temp_dir* if given)
    and is deleted when ``close()`` is called or the context manager exits —
    including when an exception propagates out of the ``with`` block.
    """

    def __init__(
        self,
        n_frames: int,
        frame_shape: tuple,
        dtype: type = np.float32,
        temp_dir: str | None = None,
    ):
        fd, path = tempfile.mkstemp(suffix=".astrostacker.buf", dir=temp_dir)
        os.close(fd)
        self._path = path
        self._closed = False

        self._buf = np.memmap(
            path,
            dtype=dtype,
            mode="w+",
            shape=(n_frames, *frame_shape),
        )
        self.n_frames = n_frames
        self.frame_shape = frame_shape
        self.dtype = np.dtype(dtype)

    # ── Array interface ────────────────────────────────────────────────────

    def __setitem__(self, idx, value: np.ndarray) -> None:
        """Write *value* into slot(s) *idx* of the buffer (copies to disk)."""
        self._buf[idx] = value

    def __getitem__(self, idx) -> np.ndarray:
        """Return a fresh in-RAM copy of frame(s) at *idx*.

        Reads from disk into a new numpy array.  Subsequent modifications
        to the returned array do not affect the buffer.
        """
        return np.array(self._buf[idx])

    def frame_view(self, idx: int) -> np.ndarray:
        """Return a zero-copy memmap view of frame *idx*.

        The view is backed by the temp file; the OS pages data into RAM
        on first access and evicts it when RAM pressure rises.  Use this
        for read-only operations (e.g. passing to the stacker) to avoid
        copying each frame into RAM before it is needed.

        Do **not** hold onto views after ``close()`` is called.
        """
        return self._buf[idx]

    # ── Lifecycle ──────────────────────────────────────────────────────────

    def close(self) -> None:
        """Flush, close the memmap, and delete the temp file.

        Safe to call multiple times.  Called automatically by
        ``__exit__`` and ``__del__``.
        """
        if not self._closed:
            self._closed = True
            buf = getattr(self, "_buf", None)
            if buf is not None:
                del self._buf   # flushes pending writes + releases file handle
                self._buf = None  # critical on Windows before os.unlink
            try:
                os.unlink(self._path)
            except OSError:
                pass  # already deleted or permission denied — silently ignore

    def __del__(self) -> None:
        self.close()

    def __enter__(self) -> "_FrameBuffer":
        return self

    def __exit__(self, *_) -> None:
        self.close()

    # ── Info ───────────────────────────────────────────────────────────────

    def size_mb(self) -> float:
        """Total size of the backing file in mebibytes."""
        return (
            self.n_frames
            * int(np.prod(self.frame_shape))
            * self.dtype.itemsize
            / 1024 / 1024
        )

    @property
    def path(self) -> Path:
        """Path to the backing temp file."""
        return Path(self._path)
