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
DEFAULT_TIMEOUT_SECONDS = 60
_TIMEOUT_SECONDS_ENV_VAR = "D2RSO_SMOKE_TIMEOUT_SECONDS"


def _get_timeout_seconds() -> float:
    raw_value = os.environ.get(_TIMEOUT_SECONDS_ENV_VAR)
    if raw_value is None:
        return float(DEFAULT_TIMEOUT_SECONDS)

    try:
        timeout_seconds = float(raw_value)
    except ValueError:
        return float(DEFAULT_TIMEOUT_SECONDS)

    if timeout_seconds <= 0:
        return float(DEFAULT_TIMEOUT_SECONDS)

    return timeout_seconds


def _format_output_block(label: str, content: str | bytes | None) -> str:
    if content is None:
        return f"{label}: <none>"
    if isinstance(content, bytes):
        content = content.decode("utf-8", errors="replace")
    normalized = content.strip()
    if not normalized:
        return f"{label}: <empty>"
    return f"{label}:\n{normalized}"


def main() -> int:
    exe_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_EXE_PATH
    if not exe_path.exists():
        raise SystemExit(f"Missing executable: {exe_path}")

    env = os.environ.copy()
    env.setdefault("D2RSO_AUTO_EXIT_MS", str(DEFAULT_AUTO_EXIT_MS))
    env.setdefault("D2RSO_DISABLE_TRAY", "1")
    timeout_seconds = _get_timeout_seconds()

    try:
        completed = subprocess.run(
            [str(exe_path)],
            cwd=exe_path.parent,
            env=env,
            timeout=timeout_seconds,
            capture_output=True,
            text=True,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise SystemExit(
            "\n".join(
                [
                    (
                        "Packaged app timed out after "
                        f"{timeout_seconds:.1f} seconds: {exe_path}"
                    ),
                    _format_output_block("stdout", exc.stdout),
                    _format_output_block("stderr", exc.stderr),
                ]
            )
        ) from exc

    if completed.returncode != 0:
        raise SystemExit(
            "\n".join(
                [
                    f"Packaged app exited with code {completed.returncode}: {exe_path}",
                    _format_output_block("stdout", completed.stdout),
                    _format_output_block("stderr", completed.stderr),
                ]
            )
        )

    return int(completed.returncode)


if __name__ == "__main__":
    raise SystemExit(main())
