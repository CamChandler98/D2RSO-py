"""Qt-side runtime controller for router and countdown lifecycle."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any

from PySide6 import QtCore

from .countdown_service import CountdownService
from .input_events import InputEvent
from .input_router import InputRouter
from .models import SkillItem


def _default_input_router_factory(
    *,
    on_triggered: Callable[[InputEvent, list[SkillItem]], None],
    on_error: Callable[[Exception], None],
) -> InputRouter:
    return InputRouter(on_triggered=on_triggered, on_error=on_error)


def _reset_skill_sequence_state(skill_items: Sequence[SkillItem]) -> None:
    for item in skill_items:
        if isinstance(item, SkillItem):
            item.reset_keys()


class TrackerRuntimeController(QtCore.QObject):
    """Owns runtime router start/stop and active countdown service state."""

    error_occurred = QtCore.Signal(str)
    _triggered_skills_signal = QtCore.Signal(object)

    def __init__(
        self,
        *,
        input_router_factory: Callable[..., Any] | None = None,
        countdown_service_factory: Callable[[], CountdownService] | None = None,
        parent: QtCore.QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._countdown_service_factory = countdown_service_factory or CountdownService
        self._countdown_service: CountdownService | None = None
        self._skill_items: list[SkillItem] = []

        router_factory = input_router_factory or _default_input_router_factory
        self._input_router = router_factory(
            on_triggered=self._on_router_triggered,
            on_error=self._on_router_error,
        )

        self._triggered_skills_signal.connect(self._handle_triggered_skills)

    @property
    def is_running(self) -> bool:
        return bool(getattr(self._input_router, "is_running", False))

    @property
    def countdown_service(self) -> CountdownService | None:
        return self._countdown_service

    @property
    def input_router(self) -> Any:
        return self._input_router

    def set_skill_items(self, skill_items: Sequence[SkillItem]) -> None:
        self._skill_items = [
            item for item in skill_items if isinstance(item, SkillItem)
        ]
        if self.is_running:
            self._input_router.set_skill_items(self._skill_items)

    def start(self, skill_items: Sequence[SkillItem] | None = None) -> CountdownService:
        if skill_items is not None:
            self.set_skill_items(skill_items)

        if self.is_running and self._countdown_service is not None:
            return self._countdown_service

        _reset_skill_sequence_state(self._skill_items)
        self._input_router.set_skill_items(self._skill_items)

        countdown_service = self._countdown_service_factory()
        self._countdown_service = countdown_service

        try:
            self._input_router.start()
        except Exception:
            self._input_router.set_skill_items(())
            _reset_skill_sequence_state(self._skill_items)
            self._countdown_service = None
            raise

        return countdown_service

    def stop(self) -> None:
        pending_error: Exception | None = None
        try:
            if self.is_running:
                self._input_router.stop()
        except Exception as exc:
            pending_error = exc
        finally:
            self._input_router.set_skill_items(())
            _reset_skill_sequence_state(self._skill_items)
            self._countdown_service = None

        if pending_error is not None:
            raise pending_error

    def _on_router_triggered(
        self, _event: InputEvent, skill_items: list[SkillItem]
    ) -> None:
        payload: list[tuple[int, float]] = []
        for item in skill_items:
            if not isinstance(item, SkillItem):
                continue
            payload.append((item.id, max(0.0, float(item.time_length))))
        if payload:
            self._triggered_skills_signal.emit(payload)

    def _on_router_error(self, exc: Exception) -> None:
        message = str(exc).strip()
        if message:
            self.error_occurred.emit(message)

    @QtCore.Slot(object)
    def _handle_triggered_skills(self, payload: object) -> None:
        if self._countdown_service is None:
            return
        if not isinstance(payload, list):
            return

        for row in payload:
            if not isinstance(row, tuple) or len(row) != 2:
                continue
            skill_id, duration = row
            self._countdown_service.refresh(
                skill_id=int(skill_id),
                duration_seconds=max(0.0, float(duration)),
            )


__all__ = ["TrackerRuntimeController"]
