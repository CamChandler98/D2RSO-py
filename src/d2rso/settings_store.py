"""JSON persistence for D2RSO settings."""

from __future__ import annotations

import json
import os
from pathlib import Path
from tempfile import NamedTemporaryFile

from .models import Settings


def default_settings_dir(app_name: str = "D2RSO") -> Path:
    """Return the default settings directory."""
    if os.name == "nt":
        local_app_data = os.environ.get("LOCALAPPDATA")
        if local_app_data:
            return Path(local_app_data) / app_name
        return Path.home() / "AppData" / "Local" / app_name
    return Path.home() / ".config" / app_name


def default_settings_path(
    app_name: str = "D2RSO", file_name: str = "settings.json"
) -> Path:
    """Return the full default settings file path."""
    return default_settings_dir(app_name=app_name) / file_name


class SettingsStore:
    """Load/save settings with graceful fallback behavior."""

    def __init__(
        self, file_path: str | Path | None = None, *, app_name: str = "D2RSO"
    ) -> None:
        self.file_path = (
            Path(file_path)
            if file_path is not None
            else default_settings_path(app_name=app_name)
        )

    def load(self) -> Settings:
        """Load settings from disk or return defaults on failure."""
        try:
            raw_content = self.file_path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return Settings.default()
        except OSError:
            return Settings.default()

        try:
            payload = json.loads(raw_content)
        except json.JSONDecodeError:
            return Settings.default()

        if not isinstance(payload, dict):
            return Settings.default()

        try:
            return Settings.from_dict(payload)
        except Exception:
            return Settings.default()

    def save(self, settings: Settings) -> None:
        """Persist settings atomically to reduce corruption risk."""
        settings.ensure_defaults()
        payload = settings.to_dict()
        serialized = json.dumps(payload, indent=2, sort_keys=True)

        self.file_path.parent.mkdir(parents=True, exist_ok=True)

        temp_file_path: Path | None = None
        try:
            with NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=self.file_path.parent,
                delete=False,
            ) as temp_file:
                temp_file_path = Path(temp_file.name)
                temp_file.write(serialized)
                temp_file.write("\n")

            os.replace(temp_file_path, self.file_path)
        finally:
            if temp_file_path is not None and temp_file_path.exists():
                temp_file_path.unlink(missing_ok=True)


def load_settings(
    file_path: str | Path | None = None, *, app_name: str = "D2RSO"
) -> Settings:
    """Convenience helper for one-shot settings load."""
    return SettingsStore(file_path=file_path, app_name=app_name).load()


def save_settings(
    settings: Settings, file_path: str | Path | None = None, *, app_name: str = "D2RSO"
) -> None:
    """Convenience helper for one-shot settings save."""
    SettingsStore(file_path=file_path, app_name=app_name).save(settings)


__all__ = [
    "SettingsStore",
    "default_settings_dir",
    "default_settings_path",
    "load_settings",
    "save_settings",
]
