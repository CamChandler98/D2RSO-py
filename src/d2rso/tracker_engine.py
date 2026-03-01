"""Input-event driven tracker matching service."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

from .input_events import InputEvent, infer_input_source_from_code, normalize_input_code
from .models import SkillItem


def _matches_event_code(config_code: str | None, event: InputEvent) -> bool:
    if config_code is None:
        return False

    source = infer_input_source_from_code(config_code) or event.source
    normalized = normalize_input_code(config_code, source=source)
    if normalized is None:
        return False
    return normalized.casefold() == event.code.casefold()


@dataclass(slots=True)
class TrackerInputEngine:
    """
    Applies skill select/use hold rules against normalized InputEvent values.

    For combo-enabled skills, the select key acts as a held modifier. A skill
    triggers when its skill key is pressed while the configured select key is
    currently held.
    """

    skill_items: list[SkillItem] = field(default_factory=list)

    def set_skill_items(self, skill_items: Iterable[SkillItem]) -> None:
        """Replace tracked skill items with a validated list."""
        self.skill_items = [item for item in skill_items if isinstance(item, SkillItem)]

    def process_event(self, event: InputEvent) -> list[SkillItem]:
        """Consume one normalized event and return skills that should trigger."""
        if not isinstance(event, InputEvent):
            raise TypeError("event must be an InputEvent")

        triggered: list[SkillItem] = []

        if not event.pressed:
            for item in self.skill_items:
                if not item.is_enabled:
                    continue
                if _matches_event_code(item.select_key, event):
                    item.select_key_released()
            return triggered

        for item in self.skill_items:
            if not item.is_enabled:
                continue
            if _matches_event_code(item.skill_key, event):
                if item.skill_key_pressed():
                    triggered.append(item)

        for item in self.skill_items:
            if not item.is_enabled:
                continue
            if _matches_event_code(item.select_key, event):
                item.select_key_pressed()

        return triggered


def process_input_event(
    event: InputEvent, skill_items: Iterable[SkillItem]
) -> list[SkillItem]:
    """Stateless helper for one-shot event processing."""
    engine = TrackerInputEngine()
    engine.set_skill_items(skill_items)
    return engine.process_event(event)


__all__ = ["TrackerInputEngine", "process_input_event"]
