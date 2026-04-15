"""Frame status bar showing accepted/rejected frame counts."""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QWidget,
)

_IDLE_STATUS_STYLE = (
    "color: rgba(255, 255, 255, 0.45);"
    "font-size: 12px;"
    "font-family: 'SF Mono', 'Menlo', 'Consolas', monospace;"
)
_ACTIVE_STATUS_STYLE = (
    "color: #ff9500;"
    "font-size: 12px;"
    "font-weight: 600;"
    "font-family: 'SF Mono', 'Menlo', 'Consolas', monospace;"
)


class FrameStatusBar(QWidget):
    """Bottom status bar showing frame acceptance/rejection stats."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._rejected_paths: list[str] = []
        self._spinner_base: str = ""
        self._spinner_phase: int = 0
        self._spinner_timer = QTimer(self)
        self._spinner_timer.setInterval(400)
        self._spinner_timer.timeout.connect(self._tick_spinner)
        self._setup_ui()

    def _setup_ui(self):
        self.setFixedHeight(32)
        self.setStyleSheet(
            "FrameStatusBar {"
            "  background-color: rgba(10, 12, 18, 0.85);"
            "  border-top: 1px solid rgba(255, 255, 255, 0.06);"
            "}"
        )

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 0, 16, 0)
        layout.setSpacing(20)

        self._status_label = QLabel("Ready")
        self._status_label.setStyleSheet(_IDLE_STATUS_STYLE)
        layout.addWidget(self._status_label)

        layout.addStretch()

        self._frames_label = QLabel("")
        self._frames_label.setStyleSheet(
            "color: rgba(255, 255, 255, 0.45);"
            "font-size: 12px;"
            "font-family: 'SF Mono', 'Menlo', 'Consolas', monospace;"
        )
        layout.addWidget(self._frames_label)

        self._delete_btn = QPushButton("Delete Rejected Files")
        self._delete_btn.setFixedHeight(22)
        self._delete_btn.setStyleSheet(
            "QPushButton {"
            "  background-color: rgba(200, 40, 40, 0.6) !important;"
            "  color: #ffffff !important;"
            "  border: none;"
            "  border-radius: 4px;"
            "  padding: 2px 10px;"
            "  font-size: 11px;"
            "  font-weight: 600;"
            "}"
            "QPushButton:hover {"
            "  background-color: rgba(220, 50, 50, 0.8) !important;"
            "}"
        )
        self._delete_btn.setVisible(False)
        self._delete_btn.clicked.connect(self._on_delete_rejected)
        layout.addWidget(self._delete_btn)

        self._version_label = QLabel("")
        self._version_label.setStyleSheet(
            "color: rgba(255, 255, 255, 0.25);"
            "font-size: 11px;"
        )
        layout.addWidget(self._version_label)

    def set_version(self, version: str):
        self._version_label.setText(f"v{version}")

    def set_status(self, text: str):
        """Update the status label.

        If the text ends with an ellipsis ('...'), a pulsing dot animation
        is started to signal a long-running operation. Any other text stops
        the animation and returns to the muted idle style.
        """
        if text.endswith("..."):
            # Strip trailing dots/whitespace — we supply animated dots ourselves
            base = text.rstrip(".").rstrip()
            self._start_spinner(base)
        else:
            self._stop_spinner()
            self._status_label.setStyleSheet(_IDLE_STATUS_STYLE)
            self._status_label.setText(text)

    def _start_spinner(self, base: str):
        self._spinner_base = base
        self._spinner_phase = 0
        self._status_label.setStyleSheet(_ACTIVE_STATUS_STYLE)
        self._render_spinner()
        if not self._spinner_timer.isActive():
            self._spinner_timer.start()

    def _stop_spinner(self):
        if self._spinner_timer.isActive():
            self._spinner_timer.stop()
        self._spinner_base = ""
        self._spinner_phase = 0

    def _tick_spinner(self):
        self._spinner_phase = (self._spinner_phase + 1) % 4
        self._render_spinner()

    def _render_spinner(self):
        dots = "." * self._spinner_phase
        pad = " " * (3 - self._spinner_phase)
        # pad keeps the label width stable so surrounding widgets don't jitter
        self._status_label.setText(f"{self._spinner_base}{dots}{pad}")

    def set_frame_counts(self, total: int, accepted: int, rejected_paths: list[str]):
        """Update the frame count display after pipeline completes."""
        self._rejected_paths = rejected_paths
        rejected = len(rejected_paths)

        if rejected > 0:
            self._frames_label.setText(
                f"Frames: {accepted} accepted / {rejected} rejected / {total} total"
            )
            self._frames_label.setStyleSheet(
                "color: #ff9500;"
                "font-size: 12px;"
                "font-family: 'SF Mono', 'Menlo', 'Consolas', monospace;"
            )
            self._delete_btn.setVisible(True)
        elif total > 0:
            self._frames_label.setText(f"Frames: {accepted} accepted / {total} total")
            self._frames_label.setStyleSheet(
                "color: rgba(100, 210, 100, 0.7);"
                "font-size: 12px;"
                "font-family: 'SF Mono', 'Menlo', 'Consolas', monospace;"
            )
            self._delete_btn.setVisible(False)
        else:
            self._frames_label.setText("")
            self._delete_btn.setVisible(False)

    def clear(self):
        self._frames_label.setText("")
        self._rejected_paths = []
        self._delete_btn.setVisible(False)
        self._stop_spinner()
        self._status_label.setStyleSheet(_IDLE_STATUS_STYLE)
        self._status_label.setText("Ready")

    def _on_delete_rejected(self):
        if not self._rejected_paths:
            return

        names = "\n".join(f"  {Path(p).name}" for p in self._rejected_paths)
        reply = QMessageBox.question(
            self,
            "Delete Rejected Frames",
            f"Permanently delete {len(self._rejected_paths)} rejected frame(s)?\n\n"
            f"{names}\n\n"
            "This cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if reply != QMessageBox.StandardButton.Yes:
            return

        deleted = 0
        errors = []
        for p in self._rejected_paths:
            try:
                Path(p).unlink()
                deleted += 1
            except Exception as e:
                errors.append(f"{Path(p).name}: {e}")

        self._rejected_paths = []
        self._delete_btn.setVisible(False)

        if errors:
            QMessageBox.warning(
                self,
                "Some Files Not Deleted",
                f"Deleted {deleted} file(s).\n\n"
                f"Errors:\n" + "\n".join(errors),
            )
        else:
            QMessageBox.information(
                self,
                "Deleted",
                f"Deleted {deleted} rejected frame(s).",
            )
