"""Application entrypoint for the D2RSO desktop UI."""

from __future__ import annotations

import sys

from PySide6 import QtWidgets

from .main_window import MainWindow


def build_window() -> MainWindow:
    """Create the application window."""
    return MainWindow()


def run() -> None:
    """Launch the desktop UI."""
    app = QtWidgets.QApplication.instance()
    owns_app = app is None
    if app is None:
        app = QtWidgets.QApplication(sys.argv)

    window = build_window()
    window.show()

    if owns_app:
        app.exec()


if __name__ == "__main__":
    run()
