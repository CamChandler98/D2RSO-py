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
pip install -e .[dev]
python -m d2rso
pytest
./scripts/pre_ci_core_logic.sh
ruff check .
black --check .
```

See `planning/documents/windows_dev_environment_guide.md` for a detailed step-by-step guide for setting up a fresh Windows development/test environment.

## Project layout
- `src/d2rso` – package with placeholder GUI entrypoint
- `tests/` – basic import/run sanity tests
- `pyproject.toml` – metadata plus tool configs (black, ruff, mypy)
- `ruff.toml`, `pytest.ini`, `Pipfile` – linting, testing, and Pipenv env setup

## Validation checklist
- `pipenv run python -m d2rso` shows the placeholder window without errors.
- `pipenv run pytest` passes.
- `./scripts/pre_ci_core_logic.sh` passes core logic tests used before CI.
- `pipenv run ruff check .` and `pipenv run black --check .` succeed.
