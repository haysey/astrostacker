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

    # Show Beta Bronze splash screen while the main window loads
    splash = SplashScreen.show_for(app, duration_ms=5000)

    window = MainWindow()
    window.show()

    # Close splash as soon as main window is ready
    splash.finish(window)

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
