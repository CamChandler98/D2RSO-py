# Dependency Rationale (MVP baseline)

Windows-first target, Python 3.11.

## Runtime
- `PySide6==6.10.2` — Qt 6 UI toolkit for main window and overlay work; actively maintained wheels for Py3.11/Windows.
- `pynput==1.8.1` — Cross-platform keyboard/mouse hooks; pairs with pywin32 on Windows.
- `pywin32==311` (Windows only) — Win32 API bindings used by pynput and future shell/behavior integrations (tray, single-instance lock, etc.).
- `pygame==2.6.1` — SDL2-based gamepad support with named buttons/axes and rumble; chosen over `inputs` for fresher maintenance and better controller mapping.

## Dev / QA
- `pytest>=7.4` — unit test runner.
- `ruff>=0.3.0` — linting/format.
- `black>=24.2` — code formatter.
- `mypy>=1.8` — optional type checking.

## Notes
- PySide6 and pygame both touch event loops; integration work should ensure only one GUI/main loop owns the thread.
- Keep `pyproject.toml` and `Pipfile` aligned; regenerate `Pipfile.lock` after any dependency change.
- Import sanity tests live in `tests/test_imports.py` to validate clean-venv installs.
