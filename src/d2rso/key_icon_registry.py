"""Centralized key catalog and icon loading/lookup service."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Mapping

# Mirrors the key list from the original C# DataClass.KEYS constant.
_KEYS_SPEC = (
    "A,B,C,D,E,F,G,H,I,J,K,L,M,N,O,P,Q,R,S,T,U,V,W,X,Y,Z,"
    "Comma|OemComma,~|OemTilde,[|OemOpenBrackets,]|OemCloseBrackets,"
    ":|OemSemicolon,'|OemQuotes,1|D1,2|D2,3|D3,4|D4,5|D5,6|D6,7|D7,8|D8,"
    "9|D9,0|D0,+|Add,-|Subtract,Esc|Escape,Enter,Return,Left Shift|LShiftKey,"
    "Right Shift|RShiftKey,Left Alt|LMenu,Right Alt|RMenu,"
    "Left Control|LControlKey,Right Control|RControlKey,F1,F2,F3,F4,F5,F6,F7,"
    "F8,F9,F10,F11,F12,NumPad0,NumPad1,NumPad2,NumPad3,NumPad4,NumPad5,"
    "NumPad6,NumPad7,NumPad8,NumPad9,Tab,Back,MOUSE1,MOUSE2,MOUSE3,MOUSEX1,"
    "MOUSEX2,GamePad Button 0|Buttons0,GamePad Button 1|Buttons1,"
    "GamePad Button 2|Buttons2,GamePad Button 3|Buttons3,"
    "GamePad Button 4|Buttons4,GamePad Button 5|Buttons5,"
    "GamePad Button 6|Buttons6,GamePad Button 7|Buttons7,"
    "GamePad Button 8|Buttons8,GamePad Button 9|Buttons9"
)

_DEFAULT_ASSETS_DIR = Path("assets") / "skills"
_IMAGE_EXTENSIONS = {".bmp", ".gif", ".ico", ".jpeg", ".jpg", ".png", ".webp"}


def _normalize_lookup(value: str) -> str:
    return value.replace("\\", "/").strip().lower()


def _can_read_image_file(path: Path) -> bool:
    """Return True when Qt can decode the image file."""
    try:
        from PySide6.QtGui import QImageReader
    except Exception:
        # If Qt is unavailable in a constrained runtime, fall back to extension checks.
        return True

    reader = QImageReader(str(path))
    return reader.canRead()


def _parse_key_entries(spec: str) -> tuple["KeyEntry", ...]:
    result: list[KeyEntry] = []
    for raw_item in spec.split(","):
        item = raw_item.strip()
        if not item:
            continue
        parts = item.split("|", maxsplit=1)
        if len(parts) == 1:
            result.append(KeyEntry(name=parts[0], code=parts[0]))
        else:
            result.append(KeyEntry(name=parts[0], code=parts[1]))

    # Match C# behavior where null is included as an available key entry.
    result.append(KeyEntry(name=None, code=None))
    return tuple(result)


@dataclass(frozen=True, slots=True)
class KeyEntry:
    """Display/value pair used by key dropdowns."""

    name: str | None
    code: str | None

    def __str__(self) -> str:
        return self.code or ""


@dataclass(frozen=True, slots=True)
class IconAsset:
    """Loaded icon metadata and bytes."""

    key: str
    path: Path
    data: bytes


class KeyIconRegistry:
    """Provides centralized key list and icon lookup helpers."""

    def __init__(self, assets_dir: str | Path | None = None) -> None:
        if assets_dir is None:
            project_root = Path(__file__).resolve().parents[2]
            self.assets_dir = project_root / _DEFAULT_ASSETS_DIR
        else:
            self.assets_dir = Path(assets_dir)

        self._available_keys = _parse_key_entries(_KEYS_SPEC)
        self._null_key = next(
            (entry for entry in self._available_keys if entry.code is None), None
        )
        self._keys_by_code = {
            _normalize_lookup(entry.code): entry
            for entry in self._available_keys
            if entry.code is not None
        }

        self._icons_by_key: dict[str, IconAsset] = {}
        self._icons_by_lookup: dict[str, IconAsset] = {}
        self.reload_icons()

    @property
    def available_keys(self) -> tuple[KeyEntry, ...]:
        return self._available_keys

    @property
    def icons(self) -> Mapping[str, IconAsset]:
        return MappingProxyType(self._icons_by_key)

    def list_key_entries(self, *, include_empty: bool = True) -> tuple[KeyEntry, ...]:
        if include_empty:
            return self._available_keys
        return tuple(entry for entry in self._available_keys if entry.code is not None)

    def get_key(self, code: str | None) -> KeyEntry | None:
        if code is None:
            return self._null_key
        normalized = _normalize_lookup(code)
        if not normalized:
            return self._null_key
        return self._keys_by_code.get(normalized)

    def list_icons(self) -> tuple[IconAsset, ...]:
        return tuple(
            sorted(
                self._icons_by_key.values(),
                key=lambda asset: asset.path.name.lower(),
            )
        )

    def reload_icons(self) -> None:
        self._icons_by_key.clear()
        self._icons_by_lookup.clear()

        if not self.assets_dir.exists() or not self.assets_dir.is_dir():
            return

        for path in sorted(
            self.assets_dir.iterdir(),
            key=lambda item: item.name.lower(),
        ):
            if not path.is_file() or path.suffix.lower() not in _IMAGE_EXTENSIONS:
                continue
            if not _can_read_image_file(path):
                continue

            try:
                raw = path.read_bytes()
            except OSError:
                continue

            resolved_path = path.resolve()
            key = _normalize_lookup(str(resolved_path))
            asset = IconAsset(key=key, path=resolved_path, data=raw)
            self._icons_by_key[key] = asset

            self._icons_by_lookup[key] = asset
            self._icons_by_lookup[_normalize_lookup(str(path))] = asset
            self._icons_by_lookup[_normalize_lookup(path.name)] = asset
            self._icons_by_lookup[_normalize_lookup(path.as_posix())] = asset

    def get_icon(self, icon_ref: str | Path | None) -> IconAsset | None:
        if icon_ref is None:
            return None

        candidate = _normalize_lookup(str(icon_ref))
        if not candidate:
            return None

        if candidate in self._icons_by_lookup:
            return self._icons_by_lookup[candidate]

        possible_path = Path(str(icon_ref))
        if possible_path.exists() and possible_path.is_file():
            if not _can_read_image_file(possible_path):
                return None
            try:
                raw = possible_path.read_bytes()
            except OSError:
                return None
            resolved = possible_path.resolve()
            return IconAsset(
                key=_normalize_lookup(str(resolved)),
                path=resolved,
                data=raw,
            )

        file_name_candidate = _normalize_lookup(Path(candidate).name)
        if file_name_candidate in self._icons_by_lookup:
            return self._icons_by_lookup[file_name_candidate]

        return None

    def get_icon_path(self, icon_ref: str | Path | None) -> Path | None:
        icon = self.get_icon(icon_ref)
        return icon.path if icon is not None else None

    def get_icon_bytes(self, icon_ref: str | Path | None) -> bytes | None:
        icon = self.get_icon(icon_ref)
        return icon.data if icon is not None else None


_default_registry: KeyIconRegistry | None = None


def get_key_icon_registry(*, reload_icons: bool = False) -> KeyIconRegistry:
    """Return the default process-wide key/icon registry."""
    global _default_registry
    if _default_registry is None:
        _default_registry = KeyIconRegistry()
    elif reload_icons:
        _default_registry.reload_icons()
    return _default_registry


__all__ = [
    "IconAsset",
    "KeyEntry",
    "KeyIconRegistry",
    "get_key_icon_registry",
]
