import os
import threading
import time
from dataclasses import dataclass
from types import SimpleNamespace

import pytest

from d2rso import input_router as input_router_module
from d2rso.input_events import InputSource, gamepad_event, keyboard_event, mouse_event
from d2rso.input_router import (
    GamepadDeviceInfo,
    GamepadInputAdapter,
    InputRouter,
    KeyboardInputAdapter,
    MouseInputAdapter,
    list_connected_gamepads,
)
from d2rso.models import SkillItem
from d2rso.tracker_engine import TrackerInputEngine


def _wait_until(
    predicate,
    *,
    timeout_seconds: float = 0.5,
    interval_seconds: float = 0.005,
) -> bool:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(interval_seconds)
    return predicate()


class _FakeListener:
    def __init__(
        self,
        *,
        on_press=None,
        on_release=None,
        on_click=None,
    ) -> None:
        self.on_press = on_press
        self.on_release = on_release
        self.on_click = on_click
        self.start_count = 0
        self.stop_count = 0
        self.join_count = 0
        self.join_timeouts: list[float | None] = []

    def start(self) -> None:
        self.start_count += 1

    def stop(self) -> None:
        self.stop_count += 1

    def join(self, timeout: float | None = None) -> None:
        self.join_count += 1
        self.join_timeouts.append(timeout)


class _StartFailingListener(_FakeListener):
    def start(self) -> None:
        super().start()
        raise RuntimeError("listener start failed")


class _FakeAdapter:
    def __init__(self) -> None:
        self._callback = None
        self.start_count = 0
        self.stop_count = 0
        self._is_running = False

    @property
    def is_running(self) -> bool:
        return self._is_running

    def set_event_callback(self, callback) -> None:
        self._callback = callback

    def start(self) -> None:
        self.start_count += 1
        self._is_running = True

    def stop(self) -> None:
        self.stop_count += 1
        self._is_running = False

    def emit(self, event) -> None:
        if self._callback is not None:
            self._callback(event)


class _StartFailingAdapter(_FakeAdapter):
    def start(self) -> None:
        self.start_count += 1
        raise RuntimeError("adapter start failed")


class _StopFailingAdapter(_FakeAdapter):
    def stop(self) -> None:
        super().stop()
        raise RuntimeError("adapter stop failed")


@dataclass(slots=True)
class _FakePygameEvent:
    type: int
    button: int | None = None
    axis: int | None = None
    value: float | None = None


class _FakeEventQueue:
    def __init__(self) -> None:
        self._events: list[_FakePygameEvent] = []
        self._lock = threading.Lock()

    def push(self, event: _FakePygameEvent) -> None:
        with self._lock:
            self._events.append(event)

    def get(self) -> list[_FakePygameEvent]:
        with self._lock:
            items = list(self._events)
            self._events.clear()
        return items


class _FakeJoystick:
    def __init__(
        self,
        index: int,
        *,
        name: str | None = None,
        button_count: int = 10,
    ) -> None:
        self.index = index
        self.name = name or f"Gamepad {index}"
        self.button_count = button_count
        self.init_count = 0
        self.quit_count = 0

    def init(self) -> None:
        self.init_count += 1

    def quit(self) -> None:
        self.quit_count += 1

    def get_name(self) -> str:
        return self.name

    def get_numbuttons(self) -> int:
        return self.button_count


class _FakeJoystickModule:
    def __init__(
        self,
        *,
        count: int,
        specs: list[tuple[str, int]] | None = None,
    ) -> None:
        self._count = count
        self._specs = list(specs or [])
        self._is_initialized = False
        self.instances: dict[int, _FakeJoystick] = {}

    def get_init(self) -> bool:
        return self._is_initialized

    def init(self) -> None:
        self._is_initialized = True

    def quit(self) -> None:
        self._is_initialized = False

    def get_count(self) -> int:
        return self._count

    def Joystick(self, index: int) -> _FakeJoystick:
        if 0 <= index < len(self._specs):
            name, button_count = self._specs[index]
        else:
            name, button_count = f"Gamepad {index}", 10
        joystick = _FakeJoystick(
            index,
            name=name,
            button_count=button_count,
        )
        self.instances[index] = joystick
        return joystick


class _FakePygame:
    JOYBUTTONDOWN = 10
    JOYBUTTONUP = 11
    JOYAXISMOTION = 12
    JOYDEVICEADDED = 13
    JOYDEVICEREMOVED = 14

    def __init__(
        self,
        *,
        joystick_count: int,
        joystick_specs: list[tuple[str, int]] | None = None,
    ) -> None:
        self._is_initialized = False
        self.init_count = 0
        self.quit_count = 0
        self.event = _FakeEventQueue()
        self.joystick = _FakeJoystickModule(
            count=joystick_count,
            specs=joystick_specs,
        )

    def get_init(self) -> bool:
        return self._is_initialized

    def init(self) -> None:
        self._is_initialized = True
        self.init_count += 1

    def quit(self) -> None:
        self._is_initialized = False
        self.quit_count += 1


class _FailingThread:
    def start(self) -> None:
        raise RuntimeError("thread start failed")


def test_pygame_headless_guard_sets_dummy_video_driver_on_macos(monkeypatch) -> None:
    monkeypatch.setattr(input_router_module.platform, "system", lambda: "Darwin")
    monkeypatch.delenv("SDL_VIDEODRIVER", raising=False)

    input_router_module._configure_pygame_headless_if_needed()

    assert os.environ["SDL_VIDEODRIVER"] == "dummy"


def test_pygame_headless_guard_keeps_existing_video_driver(monkeypatch) -> None:
    monkeypatch.setattr(input_router_module.platform, "system", lambda: "Darwin")
    monkeypatch.setenv("SDL_VIDEODRIVER", "cocoa")

    input_router_module._configure_pygame_headless_if_needed()

    assert os.environ["SDL_VIDEODRIVER"] == "cocoa"


def test_pygame_headless_guard_is_noop_off_macos(monkeypatch) -> None:
    monkeypatch.setattr(input_router_module.platform, "system", lambda: "Linux")
    monkeypatch.delenv("SDL_VIDEODRIVER", raising=False)

    input_router_module._configure_pygame_headless_if_needed()

    assert "SDL_VIDEODRIVER" not in os.environ


def test_darwin_keyboard_workaround_patches_backend_keycode_context(
    monkeypatch,
) -> None:
    monkeypatch.setattr(input_router_module.platform, "system", lambda: "Darwin")

    sentinel = object()

    def _original_context():
        return sentinel

    backend = SimpleNamespace(keycode_context=_original_context)
    keyboard_module = SimpleNamespace(_darwin=backend)

    input_router_module._apply_darwin_pynput_keyboard_workaround(keyboard_module)

    with backend.keycode_context() as context:
        assert context == (None, None)


def test_darwin_keyboard_workaround_is_noop_off_macos(monkeypatch) -> None:
    monkeypatch.setattr(input_router_module.platform, "system", lambda: "Linux")

    sentinel = object()

    def _original_context():
        return sentinel

    backend = SimpleNamespace(keycode_context=_original_context)
    keyboard_module = SimpleNamespace(_darwin=backend)

    input_router_module._apply_darwin_pynput_keyboard_workaround(keyboard_module)

    assert backend.keycode_context is _original_context


def test_list_connected_gamepads_reports_names_and_button_counts() -> None:
    fake_pygame = _FakePygame(
        joystick_count=2,
        joystick_specs=[
            ("8BitDo Pro 2", 14),
            ("Xbox Wireless Controller", 10),
        ],
    )

    devices = list_connected_gamepads(pygame_module=fake_pygame)

    assert devices == (
        GamepadDeviceInfo(index=0, name="8BitDo Pro 2", button_count=14),
        GamepadDeviceInfo(
            index=1,
            name="Xbox Wireless Controller",
            button_count=10,
        ),
    )
    assert fake_pygame.init_count == 1
    assert fake_pygame.quit_count == 1
    assert fake_pygame.joystick.instances[0].init_count == 1
    assert fake_pygame.joystick.instances[0].quit_count == 1
    assert fake_pygame.joystick.instances[1].init_count == 1
    assert fake_pygame.joystick.instances[1].quit_count == 1


def test_keyboard_adapter_emits_standardized_event() -> None:
    holder: dict[str, _FakeListener] = {}

    def _factory(on_press, on_release):
        listener = _FakeListener(on_press=on_press, on_release=on_release)
        holder["listener"] = listener
        return listener

    received = []
    adapter = KeyboardInputAdapter(listener_factory=_factory)
    adapter.set_event_callback(received.append)
    adapter.start()

    holder["listener"].on_press("f8")
    adapter.stop()

    assert adapter.is_running is False
    assert holder["listener"].start_count == 1
    assert holder["listener"].stop_count == 1
    assert len(received) == 1
    assert received[0].code == "F8"
    assert received[0].source == InputSource.KEYBOARD
    assert received[0].pressed is True


def test_keyboard_adapter_emits_release_events() -> None:
    holder: dict[str, _FakeListener] = {}

    def _factory(on_press, on_release):
        listener = _FakeListener(on_press=on_press, on_release=on_release)
        holder["listener"] = listener
        return listener

    received = []
    adapter = KeyboardInputAdapter(listener_factory=_factory)
    adapter.set_event_callback(received.append)
    adapter.start()

    holder["listener"].on_release("f8")
    adapter.stop()

    assert len(received) == 1
    assert received[0].code == "F8"
    assert received[0].source == InputSource.KEYBOARD
    assert received[0].pressed is False


def test_keyboard_adapter_rolls_back_if_listener_start_fails() -> None:
    holder: dict[str, _StartFailingListener] = {}

    def _factory(on_press, on_release):
        listener = _StartFailingListener(on_press=on_press, on_release=on_release)
        holder["listener"] = listener
        return listener

    adapter = KeyboardInputAdapter(listener_factory=_factory)

    with pytest.raises(RuntimeError, match="listener start failed"):
        adapter.start()

    assert adapter.is_running is False
    assert holder["listener"].start_count == 1
    assert holder["listener"].stop_count == 1
    assert holder["listener"].join_count == 1


def test_keyboard_adapter_start_stop_are_idempotent_and_join_listener() -> None:
    holder: dict[str, _FakeListener] = {}

    def _factory(on_press, on_release):
        listener = _FakeListener(on_press=on_press, on_release=on_release)
        holder["listener"] = listener
        return listener

    adapter = KeyboardInputAdapter(listener_factory=_factory)

    adapter.start()
    adapter.start()
    adapter.stop()
    adapter.stop()

    assert adapter.is_running is False
    assert holder["listener"].start_count == 1
    assert holder["listener"].stop_count == 1
    assert holder["listener"].join_count == 1
    assert holder["listener"].join_timeouts == [1.0]


def test_mouse_adapter_maps_button_press_and_release_to_standard_events() -> None:
    holder: dict[str, _FakeListener] = {}

    def _factory(on_click):
        listener = _FakeListener(on_click=on_click)
        holder["listener"] = listener
        return listener

    received = []
    adapter = MouseInputAdapter(listener_factory=_factory)
    adapter.set_event_callback(received.append)
    adapter.start()

    holder["listener"].on_click(0, 0, "button.right", True)
    holder["listener"].on_click(0, 0, "button.right", False)
    adapter.stop()

    assert len(received) == 2
    assert received[0].code == "MOUSE2"
    assert received[0].source == InputSource.MOUSE
    assert received[0].pressed is True
    assert received[1].code == "MOUSE2"
    assert received[1].source == InputSource.MOUSE
    assert received[1].pressed is False
    assert holder["listener"].join_count == 1


@pytest.mark.parametrize(
    ("raw_button", "expected_code"),
    [
        pytest.param(SimpleNamespace(name="left"), "MOUSE1", id="left"),
        pytest.param(SimpleNamespace(name="right"), "MOUSE2", id="right"),
        pytest.param(SimpleNamespace(name="middle"), "MOUSE3", id="middle"),
        pytest.param(SimpleNamespace(name="x1"), "MOUSEX1", id="x1"),
        pytest.param(SimpleNamespace(name="x2"), "MOUSEX2", id="x2"),
    ],
)
def test_mouse_adapter_maps_supported_button_names_to_tracker_codes(
    raw_button,
    expected_code: str,
) -> None:
    holder: dict[str, _FakeListener] = {}

    def _factory(on_click):
        listener = _FakeListener(on_click=on_click)
        holder["listener"] = listener
        return listener

    received = []
    adapter = MouseInputAdapter(listener_factory=_factory)
    adapter.set_event_callback(received.append)
    adapter.start()

    holder["listener"].on_click(320, 240, raw_button, True)
    adapter.stop()

    assert len(received) == 1
    assert received[0].code == expected_code
    assert received[0].source == InputSource.MOUSE
    assert received[0].pressed is True
    assert holder["listener"].join_count == 1


def test_mouse_adapter_ignores_unsupported_extra_buttons_without_error() -> None:
    holder: dict[str, _FakeListener] = {}

    def _factory(on_click):
        listener = _FakeListener(on_click=on_click)
        holder["listener"] = listener
        return listener

    received = []
    errors = []
    adapter = MouseInputAdapter(
        listener_factory=_factory,
        error_callback=errors.append,
    )
    adapter.set_event_callback(received.append)
    adapter.start()

    holder["listener"].on_click(0, 0, SimpleNamespace(name="button8"), True)
    holder["listener"].on_click(0, 0, SimpleNamespace(name="x3"), True)
    adapter.stop()

    assert received == []
    assert errors == []
    assert holder["listener"].join_count == 1


def test_gamepad_adapter_gracefully_starts_without_connected_device() -> None:
    fake_pygame = _FakePygame(joystick_count=0)
    received = []
    adapter = GamepadInputAdapter(
        pygame_module=fake_pygame,
        poll_interval_seconds=0.001,
    )
    adapter.set_event_callback(received.append)

    adapter.start()
    time.sleep(0.02)
    adapter.stop()

    assert received == []
    assert fake_pygame.init_count == 1
    assert fake_pygame.quit_count == 1
    assert adapter.is_running is False


def test_gamepad_adapter_emits_standardized_button_events() -> None:
    fake_pygame = _FakePygame(joystick_count=1)
    received = []
    adapter = GamepadInputAdapter(
        pygame_module=fake_pygame,
        poll_interval_seconds=0.001,
    )
    adapter.set_event_callback(received.append)

    adapter.start()
    fake_pygame.event.push(_FakePygameEvent(type=fake_pygame.JOYBUTTONDOWN, button=7))

    assert _wait_until(lambda: len(received) == 1)
    adapter.stop()

    assert received[0].code == "Buttons7"
    assert received[0].source == InputSource.GAMEPAD
    assert received[0].pressed is True


def test_gamepad_adapter_emits_button_release_events() -> None:
    fake_pygame = _FakePygame(joystick_count=1)
    received = []
    adapter = GamepadInputAdapter(
        pygame_module=fake_pygame,
        poll_interval_seconds=0.001,
    )
    adapter.set_event_callback(received.append)

    adapter.start()
    fake_pygame.event.push(_FakePygameEvent(type=fake_pygame.JOYBUTTONUP, button=7))

    assert _wait_until(lambda: len(received) == 1)
    adapter.stop()

    assert received[0].code == "Buttons7"
    assert received[0].source == InputSource.GAMEPAD
    assert received[0].pressed is False


def test_gamepad_adapter_maps_trigger_axis_motion_to_virtual_button_events() -> None:
    fake_pygame = _FakePygame(joystick_count=1)
    received = []
    adapter = GamepadInputAdapter(
        pygame_module=fake_pygame,
        poll_interval_seconds=0.001,
    )
    adapter.set_event_callback(received.append)

    adapter.start()
    fake_pygame.event.push(
        _FakePygameEvent(type=fake_pygame.JOYAXISMOTION, axis=4, value=0.49)
    )
    fake_pygame.event.push(
        _FakePygameEvent(type=fake_pygame.JOYAXISMOTION, axis=4, value=0.6)
    )
    fake_pygame.event.push(
        _FakePygameEvent(type=fake_pygame.JOYAXISMOTION, axis=4, value=0.9)
    )
    fake_pygame.event.push(
        _FakePygameEvent(type=fake_pygame.JOYAXISMOTION, axis=4, value=0.2)
    )

    assert _wait_until(lambda: len(received) == 2)
    adapter.stop()

    assert [event.code for event in received] == ["Buttons4", "Buttons4"]
    assert [event.pressed for event in received] == [True, False]


def test_gamepad_adapter_routes_trigger_axis_motion_to_tracker_engine() -> None:
    fake_pygame = _FakePygame(joystick_count=1)
    adapter = GamepadInputAdapter(
        pygame_module=fake_pygame,
        poll_interval_seconds=0.001,
    )
    engine = TrackerInputEngine(
        skill_items=[SkillItem(id=32, select_key=None, skill_key="Buttons4")]
    )
    routed: list[tuple[str, bool, list[int]]] = []
    router = InputRouter(
        tracker_engine=engine,
        adapters=[adapter],
        on_triggered=lambda event, items: routed.append(
            (event.code, event.pressed, [item.id for item in items])
        ),
    )

    router.start()
    fake_pygame.event.push(
        _FakePygameEvent(type=fake_pygame.JOYAXISMOTION, axis=4, value=0.7)
    )
    fake_pygame.event.push(
        _FakePygameEvent(type=fake_pygame.JOYAXISMOTION, axis=4, value=0.2)
    )

    assert _wait_until(
        lambda: routed == [("Buttons4", True, [32]), ("Buttons4", False, [])]
    )
    router.stop()


def test_gamepad_adapter_routes_controller_input_to_tracker_engine() -> None:
    fake_pygame = _FakePygame(joystick_count=1)
    adapter = GamepadInputAdapter(
        pygame_module=fake_pygame,
        poll_interval_seconds=0.001,
    )
    engine = TrackerInputEngine(
        skill_items=[SkillItem(id=31, select_key=None, skill_key="Buttons7")]
    )
    routed: list[tuple[str, list[int]]] = []
    router = InputRouter(
        tracker_engine=engine,
        adapters=[adapter],
        on_triggered=lambda event, items: routed.append(
            (event.code, [item.id for item in items])
        ),
    )

    router.start()
    fake_pygame.event.push(_FakePygameEvent(type=fake_pygame.JOYBUTTONDOWN, button=7))

    assert _wait_until(lambda: routed == [("Buttons7", [31])])
    router.stop()

    assert adapter.is_running is False
    assert fake_pygame.init_count == 1
    assert fake_pygame.quit_count == 1


def test_gamepad_adapter_emits_double_digit_button_indices() -> None:
    fake_pygame = _FakePygame(joystick_count=1)
    received = []
    errors = []
    adapter = GamepadInputAdapter(
        pygame_module=fake_pygame,
        error_callback=errors.append,
        poll_interval_seconds=0.001,
    )
    adapter.set_event_callback(received.append)

    adapter.start()
    fake_pygame.event.push(_FakePygameEvent(type=fake_pygame.JOYBUTTONDOWN, button=10))
    time.sleep(0.02)
    adapter.stop()

    assert [event.code for event in received] == ["Buttons10"]
    assert [event.pressed for event in received] == [True]
    assert errors == []
    assert adapter.is_running is False


def test_gamepad_adapter_cleans_up_when_thread_start_fails() -> None:
    fake_pygame = _FakePygame(joystick_count=0)
    adapter = GamepadInputAdapter(
        pygame_module=fake_pygame,
        thread_factory=lambda **_kwargs: _FailingThread(),
    )

    with pytest.raises(RuntimeError, match="thread start failed"):
        adapter.start()

    assert adapter.is_running is False
    assert fake_pygame.init_count == 1
    assert fake_pygame.quit_count == 1


def test_input_router_routes_all_device_events_to_tracker_engine() -> None:
    keyboard = _FakeAdapter()
    mouse = _FakeAdapter()
    gamepad = _FakeAdapter()
    engine = TrackerInputEngine(
        skill_items=[
            SkillItem(id=1, select_key=None, skill_key="F1"),
            SkillItem(id=2, select_key=None, skill_key="MOUSE2"),
            SkillItem(id=3, select_key=None, skill_key="Buttons0"),
        ]
    )

    routed: list[tuple[str, list[int]]] = []
    router = InputRouter(
        tracker_engine=engine,
        adapters=[keyboard, mouse, gamepad],
        on_triggered=lambda event, items: routed.append(
            (event.code, [item.id for item in items])
        ),
    )

    router.start()
    keyboard.emit(keyboard_event("f1"))
    mouse.emit(mouse_event("right"))
    gamepad.emit(gamepad_event(0))

    assert _wait_until(lambda: len(routed) == 3)
    router.stop()

    assert routed == [
        ("F1", [1]),
        ("MOUSE2", [2]),
        ("Buttons0", [3]),
    ]
    assert keyboard.start_count == 1
    assert mouse.start_count == 1
    assert gamepad.start_count == 1
    assert keyboard.stop_count == 1
    assert mouse.stop_count == 1
    assert gamepad.stop_count == 1


def test_input_router_uses_release_events_to_end_gamepad_combo_hold() -> None:
    gamepad = _FakeAdapter()
    engine = TrackerInputEngine(
        skill_items=[SkillItem(id=41, select_key="Buttons4", skill_key="Buttons0")]
    )
    routed: list[tuple[str, bool, list[int]]] = []
    router = InputRouter(
        tracker_engine=engine,
        adapters=[gamepad],
        on_triggered=lambda event, items: routed.append(
            (event.code, event.pressed, [item.id for item in items])
        ),
    )

    router.start()
    gamepad.emit(gamepad_event(4))
    gamepad.emit(gamepad_event(0))
    gamepad.emit(gamepad_event(4, pressed=False))
    gamepad.emit(gamepad_event(0))

    assert _wait_until(
        lambda: routed
        == [
            ("Buttons4", True, []),
            ("Buttons0", True, [41]),
            ("Buttons4", False, []),
            ("Buttons0", True, []),
        ]
    )
    router.stop()


def test_input_router_start_stop_are_idempotent() -> None:
    adapter = _FakeAdapter()
    router = InputRouter(adapters=[adapter])

    router.start()
    router.start()
    router.route_input_event(keyboard_event("f1"))
    router.stop()
    router.stop()

    assert adapter.start_count == 1
    assert adapter.stop_count == 1
    assert router.is_running is False


def test_input_router_rolls_back_started_adapters_on_start_failure() -> None:
    started = _FakeAdapter()
    failing = _StartFailingAdapter()
    router = InputRouter(adapters=[started, failing])

    with pytest.raises(RuntimeError, match="adapter start failed"):
        router.start()

    assert started.start_count == 1
    assert started.stop_count == 1
    assert failing.start_count == 1
    assert failing.stop_count == 0
    assert router.is_running is False


def test_input_router_reports_stop_failure_after_shutdown() -> None:
    adapter = _StopFailingAdapter()
    router = InputRouter(adapters=[adapter])
    router.start()

    with pytest.raises(RuntimeError, match="failed to stop cleanly"):
        router.stop()

    assert adapter.start_count == 1
    assert adapter.stop_count == 1
    assert router.is_running is False
