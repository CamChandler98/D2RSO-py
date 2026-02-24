# D2RSO Python Skeleton

Placeholder GUI shell for the D2RSO MVP. Targets Python 3.11+ and Windows first, with a minimal tkinter window that can be replaced later.

## Prerequisites
- Python 3.11+
- Pipenv installed (`pip install pipenv`)

## Quickstart (Pipenv)
```bash
pipenv --python 3.11
pipenv install --dev
pipenv run python -m d2rso
pipenv run pytest
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
ruff check .
black --check .
```

## Project layout
- `src/d2rso` – package with placeholder GUI entrypoint
- `tests/` – basic import/run sanity tests
- `pyproject.toml` – metadata plus tool configs (black, ruff, mypy)
- `ruff.toml`, `pytest.ini`, `Pipfile` – linting, testing, and Pipenv env setup

## Validation checklist
- `pipenv run python -m d2rso` shows the placeholder window without errors.
- `pipenv run pytest` passes.
- `pipenv run ruff check .` and `pipenv run black --check .` succeed.
