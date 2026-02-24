import importlib
import platform

import pytest


def test_ui_imports():
    import PySide6
    from PySide6 import QtWidgets  # noqa: F401


def test_pygame_imports():
    import pygame

    assert pygame.get_sdl_version()  # ensures pygame initialized its core bindings


def test_pynput_imports():
    from pynput import keyboard, mouse  # noqa: F401


@pytest.mark.skipif(platform.system() != "Windows", reason="pywin32 is Windows-only")
def test_pywin32_imports_on_windows():
    import win32api  # noqa: F401
    import win32con  # noqa: F401


def test_run_is_callable():
    from d2rso import run

    assert callable(run)


def test_dunder_main_import_is_safe():
    module = importlib.import_module("d2rso.__main__")

    assert hasattr(module, "run")
    assert callable(module.run)
