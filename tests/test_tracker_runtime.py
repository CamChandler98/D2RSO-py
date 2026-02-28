import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6 import QtWidgets

import pytest

from d2rso.input_events import keyboard_event
from d2rso.models import SkillItem
from d2rso.tracker_runtime import TrackerRuntimeController


def _get_qapp() -> QtWidgets.QApplication:
    app = QtWidgets.QApplication.instance()
    if app is None:
        app = QtWidgets.QApplication(["pytest", "-platform", "offscreen"])
    return app


class _FakeInputRouter:
    def __init__(self, *, on_triggered, on_error) -> None:
        self._on_triggered = on_triggered
        self._on_error = on_error
        self.is_running = False
        self.skill_items: list[SkillItem] = []
        self.start_count = 0
        self.stop_count = 0
        self.set_skill_items_history: list[list[SkillItem]] = []

    def set_skill_items(self, skill_items) -> None:
        self.skill_items = list(skill_items)
        self.set_skill_items_history.append(list(self.skill_items))

    def start(self) -> None:
        self.start_count += 1
        self.is_running = True

    def stop(self) -> None:
        self.stop_count += 1
        self.is_running = False

    def emit_trigger(self, skill_items: list[SkillItem] | None = None) -> None:
        payload = self.skill_items if skill_items is None else list(skill_items)
        self._on_triggered(keyboard_event("f1"), payload)

    def emit_error(self, exc: Exception) -> None:
        self._on_error(exc)


class _StartFailingInputRouter(_FakeInputRouter):
    def start(self) -> None:
        self.start_count += 1
        raise RuntimeError("router start failed")


class _StopFailingInputRouter(_FakeInputRouter):
    def stop(self) -> None:
        super().stop()
        raise RuntimeError("router stop failed")


def test_tracker_runtime_start_starts_router_and_exposes_countdown_service() -> None:
    _get_qapp()
    holder: dict[str, _FakeInputRouter] = {}

    def _router_factory(*, on_triggered, on_error):
        router = _FakeInputRouter(on_triggered=on_triggered, on_error=on_error)
        holder["router"] = router
        return router

    controller = TrackerRuntimeController(input_router_factory=_router_factory)
    skill = SkillItem(id=1, select_key="F8", skill_key="F1", time_length=4.0)

    countdown_service = controller.start([skill])

    assert countdown_service is controller.countdown_service
    assert controller.is_running is True
    assert holder["router"].start_count == 1
    assert [item.id for item in holder["router"].skill_items] == [1]


def test_tracker_runtime_routes_triggered_skills_into_countdown_service() -> None:
    _get_qapp()
    holder: dict[str, _FakeInputRouter] = {}

    def _router_factory(*, on_triggered, on_error):
        router = _FakeInputRouter(on_triggered=on_triggered, on_error=on_error)
        holder["router"] = router
        return router

    controller = TrackerRuntimeController(input_router_factory=_router_factory)
    skill = SkillItem(id=2, select_key=None, skill_key="F1", time_length=6.0)
    countdown_service = controller.start([skill])

    holder["router"].emit_trigger([skill])

    assert countdown_service.active_count == 1
    assert countdown_service.get_active(skill_id=2) is not None

    holder["router"].emit_trigger([skill])

    assert countdown_service.active_count == 1


def test_tracker_runtime_stop_clears_service_router_bindings_and_sequence_state() -> None:
    _get_qapp()
    holder: dict[str, _FakeInputRouter] = {}

    def _router_factory(*, on_triggered, on_error):
        router = _FakeInputRouter(on_triggered=on_triggered, on_error=on_error)
        holder["router"] = router
        return router

    controller = TrackerRuntimeController(input_router_factory=_router_factory)
    skill = SkillItem(id=3, select_key="F8", skill_key="F1", time_length=5.0)
    countdown_service = controller.start([skill])

    skill.select_key_pressed()
    controller.stop()

    assert controller.countdown_service is None
    assert controller.is_running is False
    assert holder["router"].stop_count == 1
    assert holder["router"].skill_items == []
    assert countdown_service.active_count == 0
    assert skill.skill_key_pressed() is False


def test_tracker_runtime_ignores_triggers_after_stop() -> None:
    _get_qapp()
    holder: dict[str, _FakeInputRouter] = {}

    def _router_factory(*, on_triggered, on_error):
        router = _FakeInputRouter(on_triggered=on_triggered, on_error=on_error)
        holder["router"] = router
        return router

    controller = TrackerRuntimeController(input_router_factory=_router_factory)
    skill = SkillItem(id=4, select_key=None, skill_key="F1", time_length=5.0)
    countdown_service = controller.start([skill])

    controller.stop()
    holder["router"].emit_trigger([skill])

    assert countdown_service.active_count == 0


def test_tracker_runtime_rolls_back_countdown_service_when_router_start_fails() -> None:
    _get_qapp()
    holder: dict[str, _StartFailingInputRouter] = {}

    def _router_factory(**kwargs):
        router = _StartFailingInputRouter(**kwargs)
        holder["router"] = router
        return router

    controller = TrackerRuntimeController(input_router_factory=_router_factory)

    with pytest.raises(RuntimeError, match="router start failed"):
        controller.start([SkillItem(id=5, select_key=None, skill_key="F1")])

    assert controller.countdown_service is None
    assert controller.is_running is False
    assert holder["router"].skill_items == []


def test_tracker_runtime_reports_router_stop_failure_after_cleanup() -> None:
    _get_qapp()

    controller = TrackerRuntimeController(
        input_router_factory=lambda **kwargs: _StopFailingInputRouter(**kwargs)
    )
    skill = SkillItem(id=6, select_key=None, skill_key="F1")
    controller.start([skill])

    with pytest.raises(RuntimeError, match="router stop failed"):
        controller.stop()

    assert controller.countdown_service is None
    assert controller.is_running is False
