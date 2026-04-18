"""Application entry point."""

import sys

from PyQt6.QtWidgets import QApplication

from astrostacker.config import APP_NAME, APP_VERSION
from astrostacker.gui.main_window import MainWindow
from astrostacker.gui.splash import SplashScreen


def main():
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(APP_VERSION)

    # Show Beta Bronze splash screen for 7 seconds, then auto-close
    SplashScreen.show_for(app, duration_ms=7000)

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
