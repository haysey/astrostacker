"""Apple Silicon-aware parallel processing utilities.

Detects CPU core count and provides helpers for distributing work
across performance cores. On Apple Silicon (M1-M5), uses the
optimal number of workers based on performance core count.
"""

from __future__ import annotations

import multiprocessing
import os
import platform
import subprocess
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from typing import Callable, TypeVar

import numpy as np

T = TypeVar("T")


def _get_apple_silicon_perf_cores() -> int | None:
    """Get the number of performance cores on Apple Silicon.

    Returns None if not on Apple Silicon or detection fails.
    """
    if platform.machine() != "arm64" or platform.system() != "Darwin":
        return None
    try:
        result = subprocess.run(
            ["sysctl", "-n", "hw.perflevel0.logicalcpu"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            return int(result.stdout.strip())
    except Exception:
        pass
    return None


def optimal_workers(io_bound: bool = False) -> int:
    """Return the optimal number of workers for the current system.

    For CPU-bound work on Apple Silicon, uses performance cores only
    (efficiency cores add overhead for compute-heavy tasks).
    For I/O-bound work, uses all logical CPUs.
    """
    total = os.cpu_count() or 4

    if io_bound:
        # I/O-bound: use all cores, cap at 8 to avoid file handle issues
        return min(total, 8)

    perf_cores = _get_apple_silicon_perf_cores()
    if perf_cores is not None:
        return perf_cores

    # Non-Apple Silicon: use all cores minus 1 (leave room for GUI)
    return max(1, total - 1)


def parallel_map_threads(
    fn: Callable[..., T],
    items: list,
    max_workers: int | None = None,
) -> list[T]:
    """Map a function over items using a thread pool.

    Best for I/O-bound work (file loading, network).
    """
    if not items:
        return []
    workers = max_workers or optimal_workers(io_bound=True)
    workers = min(workers, len(items))

    with ThreadPoolExecutor(max_workers=workers) as pool:
        return list(pool.map(fn, items))


def parallel_load_images(
    paths: list[str],
    loader: Callable[[str], np.ndarray],
) -> list[np.ndarray]:
    """Load multiple images in parallel using threads.

    File I/O benefits from threading even with the GIL since it
    releases the GIL during actual disk reads.
    """
    return parallel_map_threads(loader, paths)
