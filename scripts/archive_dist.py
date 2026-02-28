#!/usr/bin/env python3
"""Create a deterministic ZIP artifact for the packaged Windows app."""

from __future__ import annotations

import hashlib
import os
import tomllib
import zipfile
from datetime import datetime, timezone
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
DIST_DIR = ROOT_DIR / "dist" / "d2rso"
RELEASE_DIR = ROOT_DIR / "release"
PYPROJECT_PATH = ROOT_DIR / "pyproject.toml"
_ZIP_EPOCH_FLOOR = 315532800  # 1980-01-01T00:00:00Z


def _load_version() -> str:
    with PYPROJECT_PATH.open("rb") as handle:
        payload = tomllib.load(handle)
    return str(payload["project"]["version"])


def _normalized_zip_timestamp() -> tuple[int, int, int, int, int, int]:
    raw_epoch = os.environ.get("SOURCE_DATE_EPOCH")
    try:
        epoch = int(raw_epoch) if raw_epoch is not None else _ZIP_EPOCH_FLOOR
    except ValueError:
        epoch = _ZIP_EPOCH_FLOOR

    normalized_epoch = max(epoch, _ZIP_EPOCH_FLOOR)
    timestamp = datetime.fromtimestamp(normalized_epoch, tz=timezone.utc)
    return (
        timestamp.year,
        timestamp.month,
        timestamp.day,
        timestamp.hour,
        timestamp.minute,
        timestamp.second,
    )


def _iter_bundle_files() -> list[Path]:
    return sorted(path for path in DIST_DIR.rglob("*") if path.is_file())


def _write_deterministic_zip(output_path: Path) -> None:
    timestamp = _normalized_zip_timestamp()
    with zipfile.ZipFile(output_path, "w") as archive:
        for path in _iter_bundle_files():
            relative_path = path.relative_to(DIST_DIR).as_posix()
            archive_name = f"{DIST_DIR.name}/{relative_path}"

            info = zipfile.ZipInfo(filename=archive_name, date_time=timestamp)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 3
            info.external_attr = 0o100644 << 16

            archive.writestr(info, path.read_bytes(), compresslevel=9)


def _write_sha256(output_path: Path) -> Path:
    digest = hashlib.sha256(output_path.read_bytes()).hexdigest()
    checksum_path = output_path.with_suffix(output_path.suffix + ".sha256")
    checksum_path.write_text(f"{digest}  {output_path.name}\n", encoding="utf-8")
    return checksum_path


def main() -> int:
    if not DIST_DIR.exists():
        raise SystemExit(f"Missing bundle directory: {DIST_DIR}")

    RELEASE_DIR.mkdir(parents=True, exist_ok=True)
    version = _load_version()
    archive_path = RELEASE_DIR / f"d2rso-{version}-windows-x64.zip"

    _write_deterministic_zip(archive_path)
    checksum_path = _write_sha256(archive_path)

    print(archive_path)
    print(checksum_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
