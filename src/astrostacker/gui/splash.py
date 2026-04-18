"""Startup splash screen for Haysey's Astrostacker."""

from __future__ import annotations

import random

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import (
    QColor,
    QFont,
    QLinearGradient,
    QPainter,
    QPixmap,
    QRadialGradient,
)
from PyQt6.QtWidgets import QApplication, QSplashScreen

from astrostacker.config import APP_CODENAME, APP_NAME, APP_VERSION

# Bronze / gold palette
_BRONZE_BRIGHT = QColor(232, 160, 68)
_BRONZE_MID    = QColor(205, 127, 50)
_BRONZE_DARK   = QColor(138,  93, 41)

_W, _H = 520, 310


class SplashScreen(QSplashScreen):
    """Bronze-themed startup splash screen.

    Shows the app name, version, and Beta Bronze codename pill badge
    over a deep-space starfield background. Auto-closes after the main
    window is ready.
    """

    def __init__(self) -> None:
        px = _build_pixmap()
        super().__init__(px, Qt.WindowType.WindowStaysOnTopHint)
        self.setWindowFlag(Qt.WindowType.FramelessWindowHint)

    @staticmethod
    def show_for(app: QApplication, duration_ms: int = 7000) -> "SplashScreen":
        """Display the splash and schedule auto-close.

        Args:
            app: The running QApplication (used to flush events so the
                 splash actually appears before the main window loads).
            duration_ms: Milliseconds to display if finish() is not
                         called first.

        Returns:
            The SplashScreen instance (pass to ``finish(window)``).
        """
        splash = SplashScreen()
        splash.show()
        app.processEvents()
        QTimer.singleShot(duration_ms, splash.close)
        return splash


def _build_pixmap() -> QPixmap:
    """Render the splash pixmap."""
    px = QPixmap(_W, _H)
    p = QPainter(px)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)

    w, h = _W, _H

    # ── Deep-space background ──────────────────────────────────────────
    bg = QRadialGradient(w * 0.5, h * 0.38, w * 0.80)
    bg.setColorAt(0.0, QColor(22, 28, 54))
    bg.setColorAt(1.0, QColor(4,  6,  16))
    p.fillRect(0, 0, w, h, bg)

    # Subtle warm nebula glow (upper-centre)
    neb = QRadialGradient(w * 0.48, h * 0.30, 160)
    neb.setColorAt(0.0, QColor(100, 60, 20, 45))
    neb.setColorAt(1.0, QColor(0, 0, 0, 0))
    p.fillRect(0, 0, w, h, neb)

    # ── Starfield ─────────────────────────────────────────────────────
    rng = random.Random(42)
    for _ in range(140):
        x = rng.randint(5, w - 5)
        y = rng.randint(5, h - 5)
        brightness = rng.randint(50, 200)
        size = rng.choice([0, 0, 0, 1])
        p.setPen(QColor(255, 255, 255, brightness))
        if size == 0:
            p.drawPoint(x, y)
        else:
            p.drawEllipse(x - 1, y - 1, 2, 2)

    # ── Bronze top accent bar (fades at edges) ─────────────────────────
    accent = QLinearGradient(0, 0, w, 0)
    accent.setColorAt(0.00, QColor(138, 93, 41, 0))
    accent.setColorAt(0.25, _BRONZE_BRIGHT)
    accent.setColorAt(0.75, _BRONZE_BRIGHT)
    accent.setColorAt(1.00, QColor(138, 93, 41, 0))
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(accent)
    p.drawRect(0, 0, w, 4)

    # Matching bottom bar (dimmer)
    accent_bot = QLinearGradient(0, 0, w, 0)
    accent_bot.setColorAt(0.00, QColor(138, 93, 41, 0))
    accent_bot.setColorAt(0.35, QColor(138, 93, 41, 80))
    accent_bot.setColorAt(0.65, QColor(138, 93, 41, 80))
    accent_bot.setColorAt(1.00, QColor(138, 93, 41, 0))
    p.setBrush(accent_bot)
    p.drawRect(0, h - 4, w, 4)

    # ── App name ──────────────────────────────────────────────────────
    fn = QFont()
    fn.setFamilies(["SF Pro Display", "Helvetica Neue", "Segoe UI", "Arial"])
    fn.setPointSize(28)
    fn.setBold(True)
    p.setFont(fn)
    p.setPen(QColor(240, 245, 255))
    p.drawText(0, 60, w, 50, Qt.AlignmentFlag.AlignHCenter, APP_NAME)

    # ── Version number ────────────────────────────────────────────────
    fv = QFont()
    fv.setFamilies(["SF Pro Display", "Helvetica Neue", "Segoe UI", "Arial"])
    fv.setPointSize(14)
    p.setFont(fv)
    p.setPen(QColor(155, 170, 200))
    p.drawText(0, 115, w, 30, Qt.AlignmentFlag.AlignHCenter, f"v{APP_VERSION}")

    # ── "Beta Bronze" pill badge ───────────────────────────────────────
    badge_w, badge_h = 168, 34
    badge_x = (w - badge_w) // 2
    badge_y = 152

    badge_fill = QLinearGradient(badge_x, badge_y, badge_x + badge_w, badge_y)
    badge_fill.setColorAt(0.0, QColor(138,  93, 41, 210))
    badge_fill.setColorAt(0.5, QColor(205, 127, 50, 230))
    badge_fill.setColorAt(1.0, QColor(138,  93, 41, 210))
    p.setBrush(badge_fill)
    p.setPen(QColor(232, 160, 68, 160))
    p.drawRoundedRect(badge_x, badge_y, badge_w, badge_h, badge_h // 2, badge_h // 2)

    fb = QFont()
    fb.setFamilies(["SF Pro Display", "Helvetica Neue", "Segoe UI", "Arial"])
    fb.setPointSize(13)
    fb.setBold(True)
    p.setFont(fb)
    p.setPen(QColor(255, 240, 210))
    p.drawText(badge_x, badge_y, badge_w, badge_h, Qt.AlignmentFlag.AlignCenter,
               APP_CODENAME)

    # ── Footer divider ────────────────────────────────────────────────
    div = QLinearGradient(0, 0, w, 0)
    div.setColorAt(0.0,  QColor(255, 255, 255, 0))
    div.setColorAt(0.35, QColor(255, 255, 255, 35))
    div.setColorAt(0.65, QColor(255, 255, 255, 35))
    div.setColorAt(1.0,  QColor(255, 255, 255, 0))
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(div)
    p.drawRect(40, h - 50, w - 80, 1)

    # ── Footer text ───────────────────────────────────────────────────
    ff = QFont()
    ff.setFamilies(["SF Pro Display", "Helvetica Neue", "Segoe UI", "Arial"])
    ff.setPointSize(10)
    p.setFont(ff)
    p.setPen(QColor(95, 110, 140))
    p.drawText(0, h - 44, w, 28, Qt.AlignmentFlag.AlignHCenter,
               "Astronomical Society of Victoria  ·  © 2024 Andrew Hayes")

    p.end()
    return px
