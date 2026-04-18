"""About dialog for Haysey's Astrostacker.

Displays version, codename, copyright, license summary, contact
details, GitHub link, build info, and key library acknowledgements.
"""

from __future__ import annotations

import platform
import sys
from pathlib import Path

from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtGui import QDesktopServices, QFont, QPixmap
from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from astrostacker.config import APP_CODENAME, APP_NAME, APP_VERSION

# Bronze palette (matches splash screen)
_BRONZE      = "#CD7F32"
_BRONZE_LIGHT = "#E8A044"
_TEXT_DIM    = "#8899AA"
_TEXT_MAIN   = "#E0E8F0"
_DIVIDER     = "rgba(255,255,255,0.10)"
_BG          = "#12151F"
_CARD        = "#1A1E2E"

_STYLESHEET = f"""
QDialog {{
    background-color: {_BG};
    color: {_TEXT_MAIN};
}}
QLabel {{
    color: {_TEXT_MAIN};
    background: transparent;
}}
QLabel#dim {{
    color: {_TEXT_DIM};
    font-size: 11px;
}}
QLabel#bronze {{
    color: {_BRONZE_LIGHT};
}}
QLabel#section {{
    color: {_TEXT_DIM};
    font-size: 10px;
    letter-spacing: 1px;
    text-transform: uppercase;
}}
QLabel#link {{
    color: {_BRONZE_LIGHT};
    text-decoration: underline;
}}
QPushButton {{
    background-color: {_CARD};
    color: {_TEXT_MAIN};
    border: 1px solid rgba(255,255,255,0.12);
    border-radius: 6px;
    padding: 6px 20px;
    font-size: 13px;
}}
QPushButton:hover {{
    background-color: rgba(255,255,255,0.08);
    border-color: {_BRONZE};
}}
QPushButton:pressed {{
    background-color: rgba(205,127,50,0.20);
}}
"""


def _section_label(text: str) -> QLabel:
    lbl = QLabel(text.upper())
    lbl.setObjectName("section")
    font = QFont()
    font.setPointSize(10)
    lbl.setFont(font)
    return lbl


def _divider() -> QWidget:
    line = QWidget()
    line.setFixedHeight(1)
    line.setStyleSheet(f"background-color: {_DIVIDER};")
    return line


class AboutDialog(QDialog):
    """Dark-themed About dialog matching the app's visual style."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"About {APP_NAME}")
        self.setFixedWidth(480)
        self.setModal(True)
        self.setStyleSheet(_STYLESHEET)
        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 28, 28, 20)
        root.setSpacing(0)

        # ── Icon + name block ─────────────────────────────────────────
        top = QHBoxLayout()
        top.setSpacing(18)

        icon_lbl = QLabel()
        icon_lbl.setFixedSize(72, 72)
        px = self._load_icon(72)
        if px:
            icon_lbl.setPixmap(px)
        icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        top.addWidget(icon_lbl)

        name_col = QVBoxLayout()
        name_col.setSpacing(2)

        app_lbl = QLabel(APP_NAME)
        fn = QFont()
        fn.setFamilies(["SF Pro Display", "Helvetica Neue", "Segoe UI", "Arial"])
        fn.setPointSize(17)
        fn.setBold(True)
        app_lbl.setFont(fn)
        name_col.addWidget(app_lbl)

        ver_lbl = QLabel(f"Version {APP_VERSION}")
        fv = QFont()
        fv.setPointSize(13)
        ver_lbl.setFont(fv)
        ver_lbl.setObjectName("dim")
        name_col.addWidget(ver_lbl)

        code_lbl = QLabel(APP_CODENAME)
        fc = QFont()
        fc.setPointSize(13)
        fc.setBold(True)
        code_lbl.setFont(fc)
        code_lbl.setObjectName("bronze")
        name_col.addWidget(code_lbl)

        name_col.addStretch()
        top.addLayout(name_col)
        top.addStretch()
        root.addLayout(top)
        root.addSpacing(20)
        root.addWidget(_divider())
        root.addSpacing(16)

        # ── Description ───────────────────────────────────────────────
        desc = QLabel(
            "A free astrophotography image stacking application for macOS, "
            "Windows, Linux, and Raspberry Pi. Built for members of the "
            "Astronomical Society of Victoria (ASV) and the wider amateur "
            "astronomy community."
        )
        desc.setWordWrap(True)
        fd = QFont()
        fd.setPointSize(12)
        desc.setFont(fd)
        root.addWidget(desc)
        root.addSpacing(10)

        gs_lbl = QLabel(
            "New here? Run <b>Help &gt; Setup Wizard</b> for a guided first-run walkthrough, "
            "or open <b>GETTING_STARTED.txt</b> (bundled with the app) for a full beginner guide."
        )
        gs_lbl.setWordWrap(True)
        gs_f = QFont()
        gs_f.setPointSize(11)
        gs_lbl.setFont(gs_f)
        gs_lbl.setObjectName("dim")
        root.addWidget(gs_lbl)
        root.addSpacing(18)
        root.addWidget(_divider())
        root.addSpacing(16)

        # ── Legal ─────────────────────────────────────────────────────
        root.addWidget(_section_label("License"))
        root.addSpacing(6)

        copy_lbl = QLabel(f"© 2024 Andrew Hayes. All rights reserved.")
        fc2 = QFont()
        fc2.setPointSize(12)
        copy_lbl.setFont(fc2)
        root.addWidget(copy_lbl)

        lic_lbl = QLabel(
            "Free for personal, non-commercial astrophotography use. "
            "Repackaging, redistribution, or commercial use requires prior "
            "written permission from the copyright holder."
        )
        lic_lbl.setWordWrap(True)
        lic_lbl.setObjectName("dim")
        fl = QFont()
        fl.setPointSize(11)
        lic_lbl.setFont(fl)
        root.addWidget(lic_lbl)
        root.addSpacing(18)
        root.addWidget(_divider())
        root.addSpacing(16)

        # ── Contact & links ───────────────────────────────────────────
        root.addWidget(_section_label("Contact & Links"))
        root.addSpacing(6)

        links_layout = QVBoxLayout()
        links_layout.setSpacing(4)

        email_row = QHBoxLayout()
        email_lbl = QLabel("Licensing enquiries:")
        email_lbl.setObjectName("dim")
        fe = QFont()
        fe.setPointSize(11)
        email_lbl.setFont(fe)
        email_row.addWidget(email_lbl)
        email_btn = QPushButton("haysey@haysey.id.au")
        email_btn.setFlat(True)
        email_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        email_btn.setStyleSheet(f"color:{_BRONZE_LIGHT}; border:none; text-decoration:underline; padding:0; font-size:11px;")
        email_btn.clicked.connect(lambda: QDesktopServices.openUrl(QUrl("mailto:haysey@haysey.id.au")))
        email_row.addWidget(email_btn)
        email_row.addStretch()
        links_layout.addLayout(email_row)

        bug_row = QHBoxLayout()
        bug_lbl = QLabel("Bug reports:")
        bug_lbl.setObjectName("dim")
        bug_lbl.setFont(fe)
        bug_row.addWidget(bug_lbl)
        bug_btn = QPushButton("haysey@haysey.id.au")
        bug_btn.setFlat(True)
        bug_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        bug_btn.setStyleSheet(f"color:{_BRONZE_LIGHT}; border:none; text-decoration:underline; padding:0; font-size:11px;")
        bug_btn.clicked.connect(lambda: QDesktopServices.openUrl(QUrl("mailto:haysey@haysey.id.au")))
        bug_row.addWidget(bug_btn)
        bug_row.addStretch()
        links_layout.addLayout(bug_row)

        gh_row = QHBoxLayout()
        gh_lbl = QLabel("Source code:")
        gh_lbl.setObjectName("dim")
        gh_lbl.setFont(fe)
        gh_row.addWidget(gh_lbl)
        gh_btn = QPushButton("github.com/haysey/astrostacker")
        gh_btn.setFlat(True)
        gh_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        gh_btn.setStyleSheet(f"color:{_BRONZE_LIGHT}; border:none; text-decoration:underline; padding:0; font-size:11px;")
        gh_btn.clicked.connect(lambda: QDesktopServices.openUrl(QUrl("https://github.com/haysey/astrostacker")))
        gh_row.addWidget(gh_btn)
        gh_row.addStretch()
        links_layout.addLayout(gh_row)

        root.addLayout(links_layout)
        root.addSpacing(18)
        root.addWidget(_divider())
        root.addSpacing(16)

        # ── Acknowledgements ──────────────────────────────────────────
        root.addWidget(_section_label("Built With"))
        root.addSpacing(6)

        libs = [
            ("Astropy",       "FITS I/O and astronomy utilities"),
            ("Astroalign",    "Automatic frame alignment"),
            ("PyQt6",         "Graphical interface"),
            ("scikit-image",  "Star detection and image processing"),
            ("SciPy",         "PSF fitting and signal processing"),
            ("NumPy",         "High-performance array operations"),
            ("Astrometry.net","Online plate solving engine"),
        ]
        for lib, desc in libs:
            row = QHBoxLayout()
            row.setSpacing(0)
            lib_lbl = QLabel(f"{lib}")
            fl2 = QFont()
            fl2.setPointSize(11)
            fl2.setBold(True)
            lib_lbl.setFont(fl2)
            row.addWidget(lib_lbl)
            sep = QLabel(f"  —  {desc}")
            sep.setObjectName("dim")
            fs = QFont()
            fs.setPointSize(11)
            sep.setFont(fs)
            row.addWidget(sep)
            row.addStretch()
            root.addLayout(row)

        root.addSpacing(18)
        root.addWidget(_divider())
        root.addSpacing(16)

        # ── Build / system info ───────────────────────────────────────
        root.addWidget(_section_label("Build Info"))
        root.addSpacing(6)

        py_ver = sys.version.split()[0]
        os_info = f"{platform.system()} {platform.release()} ({platform.machine()})"

        for label, value in [
            ("Platform", os_info),
            ("Python",   py_ver),
        ]:
            row = QHBoxLayout()
            lbl = QLabel(f"{label}:")
            lbl.setObjectName("dim")
            fb = QFont()
            fb.setPointSize(11)
            lbl.setFont(fb)
            row.addWidget(lbl)
            val = QLabel(value)
            val.setFont(fb)
            row.addWidget(val)
            row.addStretch()
            root.addLayout(row)

        root.addSpacing(20)

        # ── Close button ──────────────────────────────────────────────
        btn_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        btn_box.rejected.connect(self.accept)
        btn_box.setStyleSheet("QDialogButtonBox { background: transparent; }")
        root.addWidget(btn_box, alignment=Qt.AlignmentFlag.AlignRight)

    @staticmethod
    def _load_icon(size: int) -> QPixmap | None:
        """Load the bundled icon.png, falling back gracefully."""
        # PyInstaller bundles icon.png into the same dir as the executable
        candidates = [
            Path(sys.executable).parent / "icon.png",          # frozen app
            Path(__file__).parent.parent.parent.parent / "icon.png",  # dev
        ]
        for path in candidates:
            if path.exists():
                px = QPixmap(str(path))
                if not px.isNull():
                    return px.scaled(
                        size, size,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )
        return None
