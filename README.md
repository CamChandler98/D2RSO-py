# D2RSO Python Skeleton

Placeholder GUI shell for the D2RSO MVP. Targets Python 3.11+ and Windows first, with a minimal tkinter window that can be replaced later.

## Prerequisites
- Python 3.11+
- Pipenv installed (`pip install pipenv`)

## Core dependencies
- UI: `PySide6`
- Input: `pynput` (keyboard/mouse), `pygame` (gamepad)
- Windows APIs: `pywin32` (Windows only)
- Dev tools: `pytest`, `ruff`, `black`, optional `mypy`
- Packaging: `PyInstaller`

See `planning/documents/dependency_rationale.md` for version pins and rationale.

## Quickstart (Pipenv)
```bash
pipenv --python 3.11
pipenv install --dev
pipenv run python -m d2rso
pipenv run pytest
./scripts/pre_ci_core_logic.sh
pipenv run ruff check .
pipenv run black --check .
```

## Pip fallback (no Pipenv)
```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\\Scripts\\activate
pip install -e ".[dev]"
python -m d2rso
pytest
./scripts/pre_ci_core_logic.sh
ruff check .
black --check .
```

Additional guides:
- `planning/documents/windows_dev_environment_guide.md` for a fresh Windows development/test environment
- `planning/documents/windows_install_uninstall_guide.md` for end-user install, update, and uninstall steps
- `planning/documents/github_actions_guide.md` for CI, PR checks, and release workflow usage

## Project layout
- `src/d2rso` – package with placeholder GUI entrypoint
- `tests/` – basic import/run sanity tests
- `pyproject.toml` – metadata plus tool configs (black, ruff, mypy)
- `ruff.toml`, `pytest.ini`, `Pipfile` – linting, testing, and Pipenv env setup
- `.github/workflows/` – PR validation and Windows release packaging
- `packaging/d2rso.spec` – checked-in PyInstaller spec for the Windows bundle

## CI and release flow
- Pull requests run `ruff`, `black --check`, `pytest`, and a Windows PyInstaller smoke build.
- Tagged releases (`v*`) rebuild the Windows bundle, launch the packaged executable in smoke-test mode, and publish a deterministic ZIP plus SHA-256 checksum.
- The packaged smoke test uses `D2RSO_AUTO_EXIT_MS` so CI can confirm the GUI launches cleanly without hanging.

## Local packaging
Windows-only packaging is scripted because PyInstaller does not cross-compile the app from macOS or Linux.

```bash
python -m pip install -e ".[dev,build]"
python scripts/build_windows_bundle.py
python scripts/smoke_test_packaged_app.py
python scripts/archive_dist.py
```

## Validation checklist
- `pipenv run python -m d2rso` shows the placeholder window without errors.
- `pipenv run pytest` passes.
- `./scripts/pre_ci_core_logic.sh` passes core logic tests used before CI.
- `pipenv run ruff check .` and `pipenv run black --check .` succeed.
- On Windows, `python scripts/build_windows_bundle.py` produces `dist/d2rso/d2rso.exe`.
- On Windows, `python scripts/smoke_test_packaged_app.py` exits with code `0`.
