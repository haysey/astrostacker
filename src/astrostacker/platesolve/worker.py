"""QThread worker for plate solving without blocking the GUI."""

from __future__ import annotations

import traceback

from PyQt6.QtCore import QObject, QThread, pyqtSignal

from astrostacker.platesolve.solver import AstrometryNetSolver, SolveResult


class SolveWorker(QObject):
    """Background worker for plate solving.

    Signals:
        status_update(str): Progress messages.
        finished(SolveResult): Emitted on success.
        error(str): Emitted on failure.
    """

    status_update = pyqtSignal(str)
    finished = pyqtSignal(object)  # SolveResult
    error = pyqtSignal(str)

    def __init__(
        self,
        image_path: str,
        api_key: str = "",
        scale_lower: float | None = None,
        scale_upper: float | None = None,
        scale_units: str = "arcsecperpix",
    ):
        super().__init__()
        self.image_path = image_path
        self.solver = AstrometryNetSolver(api_key=api_key)
        self.solver.set_status_callback(self._on_status)
        self.scale_lower = scale_lower
        self.scale_upper = scale_upper
        self.scale_units = scale_units

    def _on_status(self, msg: str):
        self.status_update.emit(msg)

    def cancel(self):
        self.solver.cancel()

    def run(self):
        try:
            result = self.solver.solve(
                self.image_path,
                scale_lower=self.scale_lower,
                scale_upper=self.scale_upper,
                scale_units=self.scale_units,
            )
            self.finished.emit(result)
        except InterruptedError:
            self.status_update.emit("Plate solve cancelled.")
        except Exception as e:
            self.error.emit(f"{type(e).__name__}: {e}")


def create_solve_thread(
    image_path: str,
    api_key: str = "",
    scale_lower: float | None = None,
    scale_upper: float | None = None,
    scale_units: str = "arcsecperpix",
) -> tuple[QThread, SolveWorker]:
    """Create a QThread and SolveWorker pair.

    Returns:
        (QThread, SolveWorker) - worker is moved to the thread.
    """
    thread = QThread()
    worker = SolveWorker(
        image_path=image_path,
        api_key=api_key,
        scale_lower=scale_lower,
        scale_upper=scale_upper,
        scale_units=scale_units,
    )
    worker.moveToThread(thread)

    thread.started.connect(worker.run)
    worker.finished.connect(thread.quit)
    worker.error.connect(thread.quit)

    return thread, worker
