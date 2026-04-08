"""Progress and log panel with modern macOS styling."""

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)


class ProgressPanel(QWidget):
    """Panel showing processing progress and log messages."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 12)
        layout.setSpacing(10)

        # Section title
        title = QLabel("Progress")
        title.setStyleSheet(
            "font-size: 15px; font-weight: 700; color: #ffffff;"
            "padding-bottom: 2px;"
        )
        layout.addWidget(title)

        # Progress bar with label
        progress_layout = QVBoxLayout()
        progress_layout.setSpacing(4)

        self.progress_label = QLabel("")
        self.progress_label.setStyleSheet(
            "color: rgba(255,255,255,0.5); font-size: 11px;"
        )
        progress_layout.addWidget(self.progress_label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setFixedHeight(6)
        progress_layout.addWidget(self.progress_bar)

        layout.addLayout(progress_layout)

        # Log output
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumHeight(80)
        self.log_text.setPlaceholderText("Pipeline output will appear here...")
        layout.addWidget(self.log_text)

        # Start/Cancel button - fixed height container so it never gets clipped
        btn_container = QWidget()
        btn_container.setFixedHeight(60)
        btn_layout = QHBoxLayout(btn_container)
        btn_layout.setContentsMargins(0, 6, 0, 6)
        btn_layout.addStretch()

        self.start_btn = QPushButton("Start Processing")
        self.start_btn.setObjectName("primaryButton")
        self.start_btn.setFixedHeight(44)
        self.start_btn.setMinimumWidth(200)
        btn_layout.addWidget(self.start_btn)

        btn_layout.addStretch()
        layout.addWidget(btn_container)

        self.setMinimumHeight(220)

    def log(self, message: str):
        self.log_text.append(message)
        scrollbar = self.log_text.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def set_progress(self, current: int, total: int, stage: str = ""):
        if total > 0:
            pct = int((current / total) * 100)
            self.progress_bar.setValue(pct)
            if stage:
                self.progress_label.setText(f"{stage}: {current}/{total}")
            else:
                self.progress_label.setText(f"{current}/{total}")

    def reset(self):
        self.progress_bar.setValue(0)
        self.progress_label.setText("")
        self.log_text.clear()

    def set_running(self, running: bool):
        if running:
            self.start_btn.setText("Cancel")
            self.start_btn.setObjectName("dangerButton")
        else:
            self.start_btn.setText("Start Processing")
            self.start_btn.setObjectName("primaryButton")
        # Force style refresh after changing objectName
        self.start_btn.style().unpolish(self.start_btn)
        self.start_btn.style().polish(self.start_btn)
