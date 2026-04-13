"""Blink comparator dialog for cycling through frames."""

from __future__ import annotations

import numpy as np
from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QVBoxLayout,
)

from astrostacker.utils.image_utils import numpy_to_qpixmap
from astrostacker.utils.stretch import auto_stretch


class BlinkDialog(QDialog):
    """Dialog that blinks through a list of images for visual inspection."""

    def __init__(self, frames: list[np.ndarray], parent=None):
        super().__init__(parent)
        self.setWindowTitle("Blink Comparator")
        self.setMinimumSize(800, 600)
        self._frames = frames
        self._current = 0
        self._playing = False
        self._timer = QTimer()
        self._timer.timeout.connect(self._next_frame)
        self._setup_ui()
        self._show_frame(0)

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        # Image display
        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setStyleSheet("background-color: #0d0d0d; border-radius: 6px;")
        self.image_label.setMinimumSize(400, 300)
        layout.addWidget(self.image_label, stretch=1)

        # Frame info
        self.info_label = QLabel()
        self.info_label.setStyleSheet(
            "color: rgba(255,255,255,0.6); font-size: 13px;"
            "font-family: 'SF Mono', 'Menlo', monospace;"
        )
        self.info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.info_label)

        # Controls
        controls = QHBoxLayout()
        controls.setSpacing(12)

        self.prev_btn = QPushButton("< Prev")
        self.prev_btn.setFixedWidth(80)
        self.prev_btn.clicked.connect(self._prev_frame)
        controls.addWidget(self.prev_btn)

        self.play_btn = QPushButton("Play")
        self.play_btn.setFixedWidth(80)
        self.play_btn.clicked.connect(self._toggle_play)
        controls.addWidget(self.play_btn)

        self.next_btn = QPushButton("Next >")
        self.next_btn.setFixedWidth(80)
        self.next_btn.clicked.connect(self._next_frame)
        controls.addWidget(self.next_btn)

        controls.addSpacing(20)

        speed_label = QLabel("Speed")
        speed_label.setStyleSheet("color: rgba(255,255,255,0.5); font-size: 12px;")
        controls.addWidget(speed_label)

        self.speed_slider = QSlider(Qt.Orientation.Horizontal)
        self.speed_slider.setRange(100, 2000)
        self.speed_slider.setValue(500)
        self.speed_slider.setFixedWidth(150)
        self.speed_slider.setToolTip("Blink interval (ms)")
        self.speed_slider.valueChanged.connect(self._on_speed_changed)
        controls.addWidget(self.speed_slider)

        controls.addStretch()
        layout.addLayout(controls)

    def _show_frame(self, idx: int):
        if not self._frames:
            return
        self._current = idx % len(self._frames)
        frame = self._frames[self._current]

        stretched = auto_stretch(frame)
        pixmap = numpy_to_qpixmap(stretched)

        available = self.image_label.size()
        scaled = pixmap.scaled(
            available,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.image_label.setPixmap(scaled)

        self.info_label.setText(
            f"Frame {self._current + 1} / {len(self._frames)}  "
            f"({frame.shape[1]} x {frame.shape[0]})"
        )

    def _next_frame(self):
        self._show_frame(self._current + 1)

    def _prev_frame(self):
        self._show_frame(self._current - 1)

    def _toggle_play(self):
        if self._playing:
            self._timer.stop()
            self._playing = False
            self.play_btn.setText("Play")
        else:
            self._timer.start(self.speed_slider.value())
            self._playing = True
            self.play_btn.setText("Stop")

    def _on_speed_changed(self, value: int):
        if self._playing:
            self._timer.setInterval(value)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._show_frame(self._current)
