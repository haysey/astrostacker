"""QThread worker for mosaic building."""

from __future__ import annotations

import traceback

import numpy as np
from PyQt6.QtCore import QObject, QThread, pyqtSignal

from astrostacker.mosaic.mosaic import build_mosaic


class MosaicWorker(QObject):
    """Background worker for building mosaics."""

    status_update = pyqtSignal(str)
    finished = pyqtSignal(np.ndarray)
    error = pyqtSignal(str)

    def __init__(self, panel_paths: list[str], output_path: str = ""):
        super().__init__()
        self._panel_paths = panel_paths
        self._output_path = output_path

    def run(self):
        try:
            result = build_mosaic(
                self._panel_paths,
                output_path=self._output_path,
                status_callback=lambda msg: self.status_update.emit(msg),
            )
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(f"{type(e).__name__}: {e}\n{traceback.format_exc()}")


def create_mosaic_thread(
    panel_paths: list[str], output_path: str = ""
) -> tuple[QThread, MosaicWorker]:
    thread = QThread()
    worker = MosaicWorker(panel_paths, output_path)
    worker.moveToThread(thread)
    thread.started.connect(worker.run)
    worker.finished.connect(thread.quit)
    worker.error.connect(thread.quit)
    return thread, worker
