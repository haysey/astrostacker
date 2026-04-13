"""FITS header viewer dialog."""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
)


class FitsHeaderDialog(QDialog):
    """Dialog showing FITS header keywords and values."""

    def __init__(self, header_text: str, file_path: str = "", parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"FITS Header — {file_path}" if file_path else "FITS Header")
        self.setMinimumSize(700, 500)
        self._setup_ui(header_text)

    def _setup_ui(self, header_text: str):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        info = QLabel("FITS header keywords and values:")
        info.setStyleSheet("color: rgba(255,255,255,0.6); font-size: 13px;")
        layout.addWidget(info)

        self.text_edit = QTextEdit()
        self.text_edit.setReadOnly(True)
        self.text_edit.setPlainText(header_text)
        self.text_edit.setStyleSheet(
            "QTextEdit {"
            "  background-color: rgba(0, 0, 0, 0.5);"
            "  color: #e0e0e0;"
            "  font-family: 'SF Mono', 'Menlo', 'Monaco', monospace;"
            "  font-size: 13px;"
            "  border: 1px solid rgba(255, 255, 255, 0.1);"
            "  border-radius: 6px;"
            "  padding: 8px;"
            "}"
        )
        layout.addWidget(self.text_edit)

        btn_row = QHBoxLayout()
        btn_row.addStretch()

        copy_btn = QPushButton("Copy to Clipboard")
        copy_btn.clicked.connect(self._copy)
        btn_row.addWidget(copy_btn)

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.close)
        btn_row.addWidget(close_btn)

        layout.addLayout(btn_row)

    def _copy(self):
        from PyQt6.QtWidgets import QApplication
        clipboard = QApplication.clipboard()
        if clipboard:
            clipboard.setText(self.text_edit.toPlainText())


def read_fits_header(path: str) -> str:
    """Read FITS header from a file and return as formatted text."""
    from astropy.io import fits
    try:
        with fits.open(path) as hdul:
            header = hdul[0].header
            lines = []
            for key in header.keys():
                if key and key.strip():
                    val = header[key]
                    comment = header.comments.get(key, "")
                    if comment:
                        lines.append(f"{key:8s} = {val!r:>30s}  / {comment}")
                    else:
                        lines.append(f"{key:8s} = {val!r}")
            return "\n".join(lines) if lines else "(empty header)"
    except Exception as e:
        return f"Error reading FITS header: {e}"
