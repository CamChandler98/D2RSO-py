"""D2RSO package exports."""

from __future__ import annotations

from importlib import import_module
from typing import Any

_LAZY_EXPORTS: dict[str, tuple[str, str]] = {
    "ActiveCountdown": ("countdown_service", "ActiveCountdown"),
    "CountdownEvent": ("countdown_service", "CountdownEvent"),
    "CountdownEventType": ("countdown_service", "CountdownEventType"),
    "CountdownService": ("countdown_service", "CountdownService"),
    "InputEvent": ("input_events", "InputEvent"),
    "InputSource": ("input_events", "InputSource"),
    "gamepad_event": ("input_events", "gamepad_event"),
    "infer_input_source_from_code": ("input_events", "infer_input_source_from_code"),
    "keyboard_event": ("input_events", "keyboard_event"),
    "make_input_event": ("input_events", "make_input_event"),
    "mouse_event": ("input_events", "mouse_event"),
    "normalize_gamepad_code": ("input_events", "normalize_gamepad_code"),
    "normalize_input_code": ("input_events", "normalize_input_code"),
    "normalize_input_source": ("input_events", "normalize_input_source"),
    "normalize_keyboard_code": ("input_events", "normalize_keyboard_code"),
    "normalize_mouse_code": ("input_events", "normalize_mouse_code"),
    "GamepadInputAdapter": ("input_router", "GamepadInputAdapter"),
    "InputAdapter": ("input_router", "InputAdapter"),
    "InputRouter": ("input_router", "InputRouter"),
    "KeyboardInputAdapter": ("input_router", "KeyboardInputAdapter"),
    "MouseInputAdapter": ("input_router", "MouseInputAdapter"),
    "IconAsset": ("key_icon_registry", "IconAsset"),
    "KeyEntry": ("key_icon_registry", "KeyEntry"),
    "KeyIconRegistry": ("key_icon_registry", "KeyIconRegistry"),
    "get_key_icon_registry": ("key_icon_registry", "get_key_icon_registry"),
    "MainWindow": ("main_window", "MainWindow"),
    "Profile": ("models", "Profile"),
    "Settings": ("models", "Settings"),
    "SkillItem": ("models", "SkillItem"),
    "TrackerProfile": ("models", "TrackerProfile"),
    "OptionsDialog": ("options_dialog", "OptionsDialog"),
    "CooldownOverlayWindow": ("overlay_window", "CooldownOverlayWindow"),
    "OverlayTrackerSnapshot": ("overlay_window", "OverlayTrackerSnapshot"),
    "format_remaining_seconds": ("overlay_window", "format_remaining_seconds"),
    "SettingsStore": ("settings_store", "SettingsStore"),
    "default_settings_dir": ("settings_store", "default_settings_dir"),
    "default_settings_path": ("settings_store", "default_settings_path"),
    "load_settings": ("settings_store", "load_settings"),
    "save_settings": ("settings_store", "save_settings"),
    "TrackerInputEngine": ("tracker_engine", "TrackerInputEngine"),
    "process_input_event": ("tracker_engine", "process_input_event"),
    "TrackerRuntimeController": ("tracker_runtime", "TrackerRuntimeController"),
}

__all__ = [
    *_LAZY_EXPORTS,
    "run",
]


def __getattr__(name: str) -> Any:
    try:
        module_name, attr_name = _LAZY_EXPORTS[name]
    except KeyError as exc:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}") from exc

    module = import_module(f".{module_name}", __name__)
    value = getattr(module, attr_name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted([*globals(), *__all__])


def run() -> None:
    """Launch the desktop UI."""
    from .main import run as _run

    _run()
