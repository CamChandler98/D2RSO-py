#!/usr/bin/env python3
"""Build the Windows desktop bundle with PyInstaller."""

from __future__ import annotations

import platform
import subprocess
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
SPEC_PATH = ROOT_DIR / "packaging" / "d2rso.spec"


def main() -> int:
    if platform.system() != "Windows":
        raise SystemExit(
            "Windows packaging must run on Windows. PyInstaller does not cross-compile "
            "the D2RSO executable from other platforms."
        )

    command = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        str(SPEC_PATH),
    ]
    completed = subprocess.run(command, cwd=ROOT_DIR, check=False)
    return int(completed.returncode)


if __name__ == "__main__":
    raise SystemExit(main())
