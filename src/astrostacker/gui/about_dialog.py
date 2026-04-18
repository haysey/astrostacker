"""About dialog for Haysey's Astrostacker."""

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
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from astrostacker.config import APP_CODENAME, APP_NAME, APP_VERSION

_BRONZE       = "#CD7F32"
_BRONZE_LIGHT = "#E8A044"
_TEXT_DIM     = "#8899AA"
_TEXT_MAIN    = "#E0E8F0"
_DIVIDER      = "rgba(255,255,255,0.10)"
_BG           = "#12151F"
_CARD         = "#1A1E2E"

_STYLESHEET = f"""
QDialog {{
    background-color: {_BG};
    color: {_TEXT_MAIN};
}}
QWidget {{
    background-color: transparent;
    color: {_TEXT_MAIN};
}}
QScrollArea {{
    border: none;
    background-color: {_BG};
}}
QLabel {{
    color: {_TEXT_MAIN};
    background: transparent;
}}
QLabel#dim {{
    color: {_TEXT_DIM};
    font-size: 12px;
}}
QLabel#bronze {{
    color: {_BRONZE_LIGHT};
}}
QLabel#section {{
    color: {_TEXT_DIM};
    font-size: 10px;
    letter-spacing: 1px;
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
    f = QFont()
    f.setPointSize(10)
    f.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 1.0)
    lbl.setFont(f)
    return lbl


def _divider() -> QWidget:
    line = QWidget()
    line.setFixedHeight(1)
    line.setStyleSheet(f"background-color: {_DIVIDER};")
    return line


def _link_btn(label: str, url: str) -> QPushButton:
    btn = QPushButton(label)
    btn.setFlat(True)
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    btn.setStyleSheet(
        f"color:{_BRONZE_LIGHT}; border:none; text-decoration:underline;"
        f"padding:0; font-size:12px; background:transparent;"
    )
    btn.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(url)))
    return btn


class AboutDialog(QDialog):
    """About dialog — scrollable, dark-themed, personal branding."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"About {APP_NAME}")
        self.setMinimumWidth(520)
        self.setMaximumWidth(600)
        self.setMinimumHeight(500)
        self.resize(540, 680)
        self.setModal(True)
        self.setStyleSheet(_STYLESHEET)
        self._build_ui()

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # ── Scrollable content area ───────────────────────────────────
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        content = QWidget()
        root = QVBoxLayout(content)
        root.setContentsMargins(32, 28, 32, 24)
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
        name_col.setSpacing(4)

        app_lbl = QLabel(APP_NAME)
        fn = QFont()
        fn.setFamilies(["SF Pro Display", "Helvetica Neue", "Segoe UI", "Arial"])
        fn.setPointSize(18)
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
        root.addSpacing(22)
        root.addWidget(_divider())
        root.addSpacing(18)

        # ── Description ───────────────────────────────────────────────
        desc = QLabel(
            f"{APP_NAME} is a free astrophotography image stacking application "
            "for macOS, Windows, and Linux. Built for the amateur astronomy "
            "community — no coding or command-line experience required."
        )
        desc.setWordWrap(True)
        fd = QFont()
        fd.setPointSize(13)
        desc.setFont(fd)
        root.addWidget(desc)
        root.addSpacing(12)

        docs_lbl = QLabel(
            "New here? Run <b>Tools → Setup Wizard</b> for a guided first-run "
            "walkthrough. <b>GETTING_STARTED.txt</b> and <b>USER_MANUAL.txt</b> "
            "(bundled with the app) cover the full workflow in detail."
        )
        docs_lbl.setWordWrap(True)
        docs_f = QFont()
        docs_f.setPointSize(12)
        docs_lbl.setFont(docs_f)
        docs_lbl.setObjectName("dim")
        root.addWidget(docs_lbl)
        root.addSpacing(22)
        root.addWidget(_divider())
        root.addSpacing(18)

        # ── Legal ─────────────────────────────────────────────────────
        root.addWidget(_section_label("Copyright & Licence"))
        root.addSpacing(8)

        copy_lbl = QLabel("© 2025 Andrew Hayes. All rights reserved.")
        fc2 = QFont()
        fc2.setPointSize(13)
        copy_lbl.setFont(fc2)
        root.addWidget(copy_lbl)
        root.addSpacing(6)

        lic_lbl = QLabel(
            "Free for personal, non-commercial astrophotography use. "
            "Repackaging, redistribution, or commercial use requires prior "
            "written permission from the copyright holder."
        )
        lic_lbl.setWordWrap(True)
        lic_lbl.setObjectName("dim")
        fl = QFont()
        fl.setPointSize(12)
        lic_lbl.setFont(fl)
        root.addWidget(lic_lbl)
        root.addSpacing(22)
        root.addWidget(_divider())
        root.addSpacing(18)

        # ── Contact & links ───────────────────────────────────────────
        root.addWidget(_section_label("Contact & Links"))
        root.addSpacing(8)

        fe = QFont()
        fe.setPointSize(12)

        for row_label, display, url in [
            ("Licensing enquiries:", "haysey@haysey.id.au",           "mailto:haysey@haysey.id.au"),
            ("Bug reports:",         "haysey@haysey.id.au",           "mailto:haysey@haysey.id.au"),
            ("Source code:",         "github.com/haysey/astrostacker", "https://github.com/haysey/astrostacker"),
        ]:
            row = QHBoxLayout()
            row.setSpacing(6)
            lbl = QLabel(row_label)
            lbl.setObjectName("dim")
            lbl.setFont(fe)
            row.addWidget(lbl)
            btn = _link_btn(display, url)
            row.addWidget(btn)
            row.addStretch()
            root.addLayout(row)
            root.addSpacing(4)

        root.addSpacing(18)
        root.addWidget(_divider())
        root.addSpacing(18)

        # ── Acknowledgements ──────────────────────────────────────────
        root.addWidget(_section_label("Built With"))
        root.addSpacing(8)

        libs = [
            ("Astropy",        "FITS I/O and astronomy utilities"),
            ("Astroalign",     "Automatic frame alignment"),
            ("PyQt6",          "Graphical interface"),
            ("scikit-image",   "Star detection and image processing"),
            ("SciPy",          "PSF fitting and signal processing"),
            ("NumPy",          "High-performance array operations"),
            ("Astrometry.net", "Online plate solving engine"),
        ]
        fl2 = QFont()
        fl2.setPointSize(12)
        fl2b = QFont()
        fl2b.setPointSize(12)
        fl2b.setBold(True)

        for lib, lib_desc in libs:
            row = QHBoxLayout()
            row.setSpacing(0)
            lib_lbl = QLabel(lib)
            lib_lbl.setFont(fl2b)
            row.addWidget(lib_lbl)
            sep = QLabel(f"  —  {lib_desc}")
            sep.setObjectName("dim")
            sep.setFont(fl2)
            row.addWidget(sep)
            row.addStretch()
            root.addLayout(row)
            root.addSpacing(4)

        root.addSpacing(18)
        root.addWidget(_divider())
        root.addSpacing(18)

        # ── Build / system info ───────────────────────────────────────
        root.addWidget(_section_label("Build Info"))
        root.addSpacing(8)

        fb = QFont()
        fb.setPointSize(12)

        py_ver  = sys.version.split()[0]
        os_info = f"{platform.system()} {platform.release()} ({platform.machine()})"

        for label, value in [("Platform", os_info), ("Python", py_ver)]:
            row = QHBoxLayout()
            lbl = QLabel(f"{label}:")
            lbl.setObjectName("dim")
            lbl.setFont(fb)
            row.addWidget(lbl)
            val = QLabel(value)
            val.setFont(fb)
            row.addWidget(val)
            row.addStretch()
            root.addLayout(row)
            root.addSpacing(4)

        root.addStretch()

        scroll.setWidget(content)
        outer.addWidget(scroll, stretch=1)

        # ── Close button (outside scroll) ─────────────────────────────
        btn_area = QWidget()
        btn_area.setStyleSheet(
            f"background-color: {_BG};"
            "border-top: 1px solid rgba(255,255,255,0.08);"
        )
        btn_layout = QHBoxLayout(btn_area)
        btn_layout.setContentsMargins(20, 12, 20, 12)

        close_btn = QPushButton("Close")
        close_btn.setMinimumWidth(90)
        close_btn.clicked.connect(self.accept)
        btn_layout.addStretch()
        btn_layout.addWidget(close_btn)

        outer.addWidget(btn_area)

    @staticmethod
    def _load_icon(size: int) -> QPixmap | None:
        candidates = [
            Path(sys.executable).parent / "icon.png",
            Path(__file__).parent.parent.parent.parent / "icon.png",
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
