#!/usr/bin/env python3
"""Launch the packaged app and verify it exits cleanly."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_EXE_PATH = ROOT_DIR / "dist" / "d2rso" / "d2rso.exe"
DEFAULT_AUTO_EXIT_MS = 1500
DEFAULT_TIMEOUT_SECONDS = 30


def main() -> int:
    exe_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_EXE_PATH
    if not exe_path.exists():
        raise SystemExit(f"Missing executable: {exe_path}")

    env = os.environ.copy()
    env.setdefault("D2RSO_AUTO_EXIT_MS", str(DEFAULT_AUTO_EXIT_MS))

    completed = subprocess.run(
        [str(exe_path)],
        cwd=exe_path.parent,
        env=env,
        timeout=DEFAULT_TIMEOUT_SECONDS,
        check=False,
    )
    return int(completed.returncode)


if __name__ == "__main__":
    raise SystemExit(main())
