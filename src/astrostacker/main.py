"""Application entry point."""

import sys

from PyQt6.QtWidgets import QApplication

from astrostacker.config import APP_NAME, APP_VERSION
from astrostacker.gui.main_window import MainWindow
from astrostacker.gui.splash import SplashScreen
from astrostacker.utils.splash_audio import play_splash_melody


def main():
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(APP_VERSION)

    # Show Beta Bronze splash screen for 7 seconds, then auto-close.
    # _splash must be kept assigned — if discarded Python garbage-collects
    # the object immediately and the window vanishes in a split second.
    _splash = SplashScreen.show_for(app, duration_ms=7000)

    # Play the launch jingle while the splash is visible.  Non-blocking —
    # runs in a daemon thread, silently skipped if audio is unavailable.
    play_splash_melody()

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
