"""Core domain models for D2RSO."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

DEFAULT_PROFILE_ID = 0
DEFAULT_PROFILE_NAME = "Default"
DEFAULT_SKILL_KEY = "MOUSE2"
DEFAULT_SKILL_DURATION_SECONDS = 5.0
DEFAULT_FORM_SCALE = 1.0


def _has_key(data: Mapping[str, Any], *keys: str) -> bool:
    return any(key in data for key in keys)


def _get_value(data: Mapping[str, Any], *keys: str, default: Any) -> Any:
    for key in keys:
        if key in data:
            return data[key]
    return default


def _as_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _as_float(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _as_bool(value: Any, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"1", "true", "yes", "y", "on"}:
            return True
        if lowered in {"0", "false", "no", "n", "off"}:
            return False
    return default


def _as_str(value: Any, default: str) -> str:
    if isinstance(value, str):
        return value
    return default


def _as_key_code(value: Any, default: str | None) -> str | None:
    if isinstance(value, Mapping):
        value = _get_value(value, "code", "Code", default=None)
    if value is None:
        return default
    if isinstance(value, str):
        stripped = value.strip()
        return stripped or None
    return default


@dataclass(slots=True)
class Profile:
    """A user profile that groups skill items."""

    id: int = DEFAULT_PROFILE_ID
    name: str = DEFAULT_PROFILE_NAME

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "name": self.name}

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "Profile":
        if not isinstance(data, Mapping):
            raise TypeError("Profile payload must be a mapping.")
        return cls(
            id=_as_int(
                _get_value(data, "id", "Id", default=DEFAULT_PROFILE_ID),
                DEFAULT_PROFILE_ID,
            ),
            name=_as_str(
                _get_value(data, "name", "Name", default=DEFAULT_PROFILE_NAME),
                DEFAULT_PROFILE_NAME,
            ),
        )


# Backwards-compatible alias with the original C# name.
TrackerProfile = Profile


@dataclass(slots=True)
class SkillItem:
    """A skill configuration row with select/use hold-state behavior."""

    id: int = 0
    profile_id: int = DEFAULT_PROFILE_ID
    icon_file_name: str = ""
    time_length: float = DEFAULT_SKILL_DURATION_SECONDS
    is_enabled: bool = True
    select_key: str | None = None
    skill_key: str | None = DEFAULT_SKILL_KEY
    _select_key_held: bool = field(default=False, init=False, repr=False, compare=False)

    def skill_key_pressed(self) -> bool:
        """Return True when this press should trigger the cooldown."""
        return self.select_key is None or self._select_key_held

    def select_key_pressed(self) -> None:
        """Mark the select key as held for combo-enabled skills."""
        if self.select_key is not None:
            self._select_key_held = True

    def select_key_released(self) -> None:
        """Mark the select key as no longer held."""
        self._select_key_held = False

    def reset_keys(self) -> None:
        """Clear any held-key state."""
        self._select_key_held = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "profile_id": self.profile_id,
            "icon_file_name": self.icon_file_name,
            "time_length": self.time_length,
            "is_enabled": self.is_enabled,
            "select_key": self.select_key,
            "skill_key": self.skill_key,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "SkillItem":
        if not isinstance(data, Mapping):
            raise TypeError("SkillItem payload must be a mapping.")

        select_key = (
            _as_key_code(
                _get_value(data, "select_key", "SelectKey", default=None), default=None
            )
            if _has_key(data, "select_key", "SelectKey")
            else None
        )
        skill_key = (
            _as_key_code(
                _get_value(data, "skill_key", "SkillKey", default=None), default=None
            )
            if _has_key(data, "skill_key", "SkillKey")
            else DEFAULT_SKILL_KEY
        )

        item = cls(
            id=_as_int(_get_value(data, "id", "Id", default=0), 0),
            profile_id=_as_int(
                _get_value(data, "profile_id", "ProfileId", default=DEFAULT_PROFILE_ID),
                DEFAULT_PROFILE_ID,
            ),
            icon_file_name=_as_str(
                _get_value(data, "icon_file_name", "IconFileName", default=""), ""
            ),
            time_length=_as_float(
                _get_value(
                    data,
                    "time_length",
                    "TimeLength",
                    default=DEFAULT_SKILL_DURATION_SECONDS,
                ),
                DEFAULT_SKILL_DURATION_SECONDS,
            ),
            is_enabled=_as_bool(
                _get_value(data, "is_enabled", "IsEnabled", default=True), True
            ),
            select_key=select_key,
            skill_key=skill_key,
        )
        if item.time_length < 0:
            item.time_length = DEFAULT_SKILL_DURATION_SECONDS
        return item


@dataclass(slots=True)
class Settings:
    """Persisted application settings + domain data collections."""

    last_selected_profile_id: int = DEFAULT_PROFILE_ID
    skill_items: list[SkillItem] = field(default_factory=list)
    profiles: list[Profile] = field(default_factory=lambda: [Profile()])
    tracker_x: int = 0
    tracker_y: int = 0
    form_scale_x: float = DEFAULT_FORM_SCALE
    form_scale_y: float = DEFAULT_FORM_SCALE
    is_tracker_insert_to_left: bool = False
    is_tracker_vertical: bool = False
    show_digits_in_tracker: bool = False
    red_overlay_seconds: int = 0
    red_tracker_overlay_sec: int = 0
    start_tracker_on_app_run: bool = False
    minimize_to_tray: bool = False

    def __post_init__(self) -> None:
        if (
            _as_int(self.red_overlay_seconds, 0) <= 0
            and _as_int(self.red_tracker_overlay_sec, 0) > 0
        ):
            self.red_overlay_seconds = _as_int(self.red_tracker_overlay_sec, 0)
        self.ensure_defaults()

    @property
    def is_red_tracker_overlay_enabled(self) -> bool:
        return self.red_overlay_seconds_effective > 0

    @property
    def red_overlay_seconds_effective(self) -> int:
        return max(0, _as_int(self.red_overlay_seconds, 0))

    def ensure_defaults(self) -> None:
        """Repair invalid or partial state while preserving usable data."""
        self.profiles = [
            profile for profile in self.profiles if isinstance(profile, Profile)
        ]
        self.skill_items = [
            item for item in self.skill_items if isinstance(item, SkillItem)
        ]

        if not self.profiles:
            self.profiles = [Profile()]
        elif not any(profile.id == DEFAULT_PROFILE_ID for profile in self.profiles):
            self.profiles.insert(0, Profile())

        profile_ids = {profile.id for profile in self.profiles}
        if self.last_selected_profile_id not in profile_ids:
            self.last_selected_profile_id = DEFAULT_PROFILE_ID

        for item in self.skill_items:
            if item.profile_id not in profile_ids:
                item.profile_id = self.last_selected_profile_id
            if item.time_length < 0:
                item.time_length = DEFAULT_SKILL_DURATION_SECONDS

        if self.form_scale_x <= 0:
            self.form_scale_x = DEFAULT_FORM_SCALE
        if self.form_scale_y <= 0:
            self.form_scale_y = DEFAULT_FORM_SCALE
        self.start_tracker_on_app_run = _as_bool(self.start_tracker_on_app_run, False)
        self.minimize_to_tray = _as_bool(self.minimize_to_tray, False)
        red_overlay_seconds = self.red_overlay_seconds_effective
        self.red_overlay_seconds = red_overlay_seconds
        self.red_tracker_overlay_sec = red_overlay_seconds

    def to_dict(self) -> dict[str, Any]:
        red_overlay_seconds = self.red_overlay_seconds_effective
        return {
            "last_selected_profile_id": self.last_selected_profile_id,
            "skill_items": [item.to_dict() for item in self.skill_items],
            "profiles": [profile.to_dict() for profile in self.profiles],
            "tracker_x": self.tracker_x,
            "tracker_y": self.tracker_y,
            "form_scale_x": self.form_scale_x,
            "form_scale_y": self.form_scale_y,
            "is_tracker_insert_to_left": self.is_tracker_insert_to_left,
            "is_tracker_vertical": self.is_tracker_vertical,
            "show_digits_in_tracker": self.show_digits_in_tracker,
            "red_overlay_seconds": red_overlay_seconds,
            "red_tracker_overlay_sec": red_overlay_seconds,
            "start_tracker_on_app_run": self.start_tracker_on_app_run,
            "minimize_to_tray": self.minimize_to_tray,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "Settings":
        if not isinstance(data, Mapping):
            raise TypeError("Settings payload must be a mapping.")

        profiles_payload = _get_value(data, "profiles", "Profiles", default=[])
        skill_items_payload = _get_value(data, "skill_items", "SkillItems", default=[])

        profiles: list[Profile] = []
        if isinstance(profiles_payload, list):
            for profile_data in profiles_payload:
                if isinstance(profile_data, Mapping):
                    profiles.append(Profile.from_dict(profile_data))

        skill_items: list[SkillItem] = []
        if isinstance(skill_items_payload, list):
            for item_data in skill_items_payload:
                if isinstance(item_data, Mapping):
                    skill_items.append(SkillItem.from_dict(item_data))

        red_overlay_seconds = _as_int(
            _get_value(
                data,
                "red_overlay_seconds",
                "RedOverlaySeconds",
                "red_tracker_overlay_sec",
                "RedTrackerOverlaySec",
                default=0,
            ),
            0,
        )

        return cls(
            last_selected_profile_id=_as_int(
                _get_value(
                    data,
                    "last_selected_profile_id",
                    "LastSelectedProfileId",
                    default=DEFAULT_PROFILE_ID,
                ),
                DEFAULT_PROFILE_ID,
            ),
            skill_items=skill_items,
            profiles=profiles,
            tracker_x=_as_int(_get_value(data, "tracker_x", "TrackerX", default=0), 0),
            tracker_y=_as_int(_get_value(data, "tracker_y", "TrackerY", default=0), 0),
            form_scale_x=_as_float(
                _get_value(
                    data, "form_scale_x", "FormScaleX", default=DEFAULT_FORM_SCALE
                ),
                DEFAULT_FORM_SCALE,
            ),
            form_scale_y=_as_float(
                _get_value(
                    data, "form_scale_y", "FormScaleY", default=DEFAULT_FORM_SCALE
                ),
                DEFAULT_FORM_SCALE,
            ),
            is_tracker_insert_to_left=_as_bool(
                _get_value(
                    data,
                    "is_tracker_insert_to_left",
                    "IsTrackerInsertToLeft",
                    default=False,
                ),
                False,
            ),
            is_tracker_vertical=_as_bool(
                _get_value(
                    data, "is_tracker_vertical", "IsTrackerVertical", default=False
                ),
                False,
            ),
            show_digits_in_tracker=_as_bool(
                _get_value(
                    data, "show_digits_in_tracker", "ShowDigitsInTracker", default=False
                ),
                False,
            ),
            red_overlay_seconds=red_overlay_seconds,
            red_tracker_overlay_sec=red_overlay_seconds,
            start_tracker_on_app_run=_as_bool(
                _get_value(
                    data,
                    "start_tracker_on_app_run",
                    "StartTrackerOnAppRun",
                    default=False,
                ),
                False,
            ),
            minimize_to_tray=_as_bool(
                _get_value(
                    data,
                    "minimize_to_tray",
                    "MinimizeToTray",
                    default=False,
                ),
                False,
            ),
        )

    @classmethod
    def default(cls) -> "Settings":
        return cls()


__all__ = [
    "DEFAULT_PROFILE_ID",
    "DEFAULT_PROFILE_NAME",
    "DEFAULT_SKILL_DURATION_SECONDS",
    "DEFAULT_SKILL_KEY",
    "Profile",
    "Settings",
    "SkillItem",
    "TrackerProfile",
]
