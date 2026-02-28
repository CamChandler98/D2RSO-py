"""Application entrypoint for the D2RSO desktop UI."""

from __future__ import annotations

import os
import sys

from PySide6 import QtCore, QtWidgets

from .main_window import MainWindow

_AUTO_EXIT_MS_ENV_VAR = "D2RSO_AUTO_EXIT_MS"


def _get_auto_exit_delay_ms() -> int | None:
    raw_value = os.environ.get(_AUTO_EXIT_MS_ENV_VAR)
    if raw_value is None:
        return None

    try:
        delay_ms = int(raw_value)
    except ValueError:
        return None

    if delay_ms <= 0:
        return None

    return delay_ms


def build_window() -> MainWindow:
    """Create the application window."""
    return MainWindow()


def _request_auto_exit(
    app: QtWidgets.QApplication,
    window: MainWindow,
) -> None:
    """Terminate the app reliably for automation and smoke tests."""
    window.exit_to_desktop()
    QtCore.QTimer.singleShot(0, app.quit)


def run() -> None:
    """Launch the desktop UI."""
    app = QtWidgets.QApplication.instance()
    owns_app = app is None
    if app is None:
        app = QtWidgets.QApplication(sys.argv)

    window = build_window()
    window.show()

    if owns_app:
        auto_exit_delay_ms = _get_auto_exit_delay_ms()
        if auto_exit_delay_ms is not None:
            QtCore.QTimer.singleShot(
                auto_exit_delay_ms,
                lambda: _request_auto_exit(app, window),
            )
        app.exec()


if __name__ == "__main__":
    run()
