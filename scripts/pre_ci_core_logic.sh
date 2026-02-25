#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if command -v pipenv >/dev/null 2>&1 && pipenv --venv >/dev/null 2>&1; then
  pipenv run pytest \
    tests/test_models.py \
    tests/test_tracker_engine.py \
    tests/test_countdown_service.py \
    -m "not gui"
else
  python -m pytest \
    tests/test_models.py \
    tests/test_tracker_engine.py \
    tests/test_countdown_service.py \
    -m "not gui"
fi
