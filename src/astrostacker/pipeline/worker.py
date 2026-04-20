"""QThread-based worker for running the pipeline without blocking the GUI."""

import traceback

import numpy as np
from PyQt6.QtCore import QObject, QThread, pyqtSignal

from astrostacker.pipeline.pipeline import Pipeline, PipelineConfig


class PipelineWorker(QObject):
    """Worker that runs the stacking pipeline on a background thread.

    Signals:
        status_update(str): Pipeline stage status messages.
        progress_update(int, int, str): (current, total, stage_name).
        finished(ndarray): Emitted with the stacked result on success.
        error(str): Emitted with the error message on failure.
    """

    status_update = pyqtSignal(str)
    progress_update = pyqtSignal(int, int, str)
    finished = pyqtSignal(np.ndarray)
    error = pyqtSignal(str)
    cancelled = pyqtSignal()

    def __init__(self, config: PipelineConfig):
        super().__init__()
        self.pipeline = Pipeline(config)
        self.pipeline.set_callbacks(
            status=self._on_status,
            progress=self._on_progress,
        )

    def _on_status(self, message: str):
        self.status_update.emit(message)

    def _on_progress(self, current: int, total: int, stage: str):
        self.progress_update.emit(current, total, stage)

    def cancel(self):
        """Request pipeline cancellation."""
        self.pipeline.cancel()

    def run(self):
        """Execute the pipeline. Called from the worker thread."""
        try:
            result = self.pipeline.run()
            self.finished.emit(result)
        except InterruptedError:
            self.status_update.emit("Pipeline cancelled.")
            self.cancelled.emit()
        except Exception as e:
            self.error.emit(f"{type(e).__name__}: {e}\n{traceback.format_exc()}")


def create_worker_thread(config: PipelineConfig) -> tuple[QThread, PipelineWorker]:
    """Create a QThread and PipelineWorker pair.

    Usage:
        thread, worker = create_worker_thread(config)
        worker.finished.connect(on_done)
        worker.error.connect(on_error)
        thread.start()

    Returns:
        (QThread, PipelineWorker) tuple. The worker is moved to the thread.
    """
    thread = QThread()
    thread.setStackSize(16 * 1024 * 1024)  # 16 MB — LAPACK needs > default 512 KB
    worker = PipelineWorker(config)
    worker.moveToThread(thread)

    thread.started.connect(worker.run)
    worker.finished.connect(thread.quit)
    worker.error.connect(thread.quit)
    worker.cancelled.connect(thread.quit)

    return thread, worker
