"""Global input adapters and unified router lifecycle control."""

from __future__ import annotations

import contextlib
import os
import platform
import threading
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from queue import Empty, Queue
from typing import Any, Protocol

from .input_events import InputEvent, gamepad_event, keyboard_event, mouse_event
from .models import SkillItem
from .tracker_engine import TrackerInputEngine

_QUEUE_TIMEOUT_SECONDS = 0.05
_GAMEPAD_POLL_INTERVAL_SECONDS = 0.01
_LISTENER_JOIN_TIMEOUT_SECONDS = 1.0
_GAMEPAD_TRIGGER_AXIS_TO_BUTTON = {
    4: 4,
    5: 5,
}
_GAMEPAD_TRIGGER_PRESS_THRESHOLD = 0.5
_GAMEPAD_TRIGGER_RELEASE_THRESHOLD = 0.25


def _apply_darwin_pynput_keyboard_workaround(keyboard_module: Any) -> None:
    """
    Patch pynput's Darwin keyboard listener to avoid background-thread TIS calls.

    On newer macOS versions, calling TSM/TIS keyboard input-source APIs from the
    pynput listener thread can trigger a hard abort in libdispatch. We only need
    the listener path (not the key injection controller), so using a no-op
    keycode context is sufficient for this app's global key tracking use case.
    """
    if platform.system() != "Darwin":
        return

    backend = getattr(keyboard_module, "_darwin", None)
    if backend is None:
        return

    @contextlib.contextmanager
    def _safe_keycode_context():
        yield (None, None)

    backend.keycode_context = _safe_keycode_context


def _configure_pygame_headless_if_needed(pygame_module: Any | None = None) -> None:
    """
    Apply a safe SDL video backend on macOS before pygame initialization.

    Some macOS setups crash with an illegal hardware instruction during
    ``pygame.init()`` unless a dummy video driver is selected first.
    """
    if platform.system() != "Darwin":
        return
    if os.environ.get("SDL_VIDEODRIVER"):
        return

    display_module = getattr(pygame_module, "display", None)
    get_display_init = getattr(display_module, "get_init", None)
    if callable(get_display_init):
        try:
            if get_display_init():
                return
        except Exception:
            return

    os.environ["SDL_VIDEODRIVER"] = "dummy"


def _resolve_pygame_module(pygame_module: Any | None = None) -> Any:
    if pygame_module is None:
        _configure_pygame_headless_if_needed()
        import pygame

        return pygame
    return pygame_module


@dataclass(frozen=True, slots=True)
class GamepadDeviceInfo:
    """Connected gamepad metadata used for UI labeling."""

    index: int
    name: str
    button_count: int


def list_connected_gamepads(
    *,
    pygame_module: Any | None = None,
) -> tuple[GamepadDeviceInfo, ...]:
    """Return connected gamepads with their reported button counts."""
    owns_pygame_init = False
    owns_joystick_init = False
    joystick_module: Any | None = None
    joysticks: list[Any] = []

    try:
        pygame_module = _resolve_pygame_module(pygame_module)
        _configure_pygame_headless_if_needed(pygame_module)

        if hasattr(pygame_module, "get_init") and not pygame_module.get_init():
            pygame_module.init()
            owns_pygame_init = True

        joystick_module = getattr(pygame_module, "joystick", None)
        if joystick_module is None:
            return ()

        if hasattr(joystick_module, "get_init"):
            if not joystick_module.get_init():
                joystick_module.init()
                owns_joystick_init = True
        else:
            init_fn = getattr(joystick_module, "init", None)
            if callable(init_fn):
                init_fn()
                owns_joystick_init = True

        count = max(0, int(joystick_module.get_count()))
        devices: list[GamepadDeviceInfo] = []
        for index in range(count):
            joystick = joystick_module.Joystick(index)
            joysticks.append(joystick)

            init_fn = getattr(joystick, "init", None)
            if callable(init_fn):
                init_fn()

            name = f"Gamepad {index}"
            get_name = getattr(joystick, "get_name", None)
            if callable(get_name):
                try:
                    candidate = str(get_name()).strip()
                except Exception:
                    candidate = ""
                if candidate:
                    name = candidate

            button_count = 0
            get_numbuttons = getattr(joystick, "get_numbuttons", None)
            if callable(get_numbuttons):
                try:
                    button_count = max(0, int(get_numbuttons()))
                except Exception:
                    button_count = 0

            devices.append(
                GamepadDeviceInfo(
                    index=index,
                    name=name,
                    button_count=button_count,
                )
            )

        return tuple(devices)
    except Exception:
        return ()
    finally:
        for joystick in reversed(joysticks):
            quit_fn = getattr(joystick, "quit", None)
            if callable(quit_fn):
                try:
                    quit_fn()
                except Exception:
                    pass

        if joystick_module is not None and owns_joystick_init:
            quit_fn = getattr(joystick_module, "quit", None)
            if callable(quit_fn):
                try:
                    quit_fn()
                except Exception:
                    pass

        if owns_pygame_init:
            quit_fn = getattr(pygame_module, "quit", None)
            if callable(quit_fn):
                try:
                    quit_fn()
                except Exception:
                    pass


class InputAdapter(Protocol):
    """Interface implemented by input adapters managed by InputRouter."""

    @property
    def is_running(self) -> bool: ...

    def set_event_callback(
        self, callback: Callable[[InputEvent], None] | None
    ) -> None: ...

    def start(self) -> None: ...

    def stop(self) -> None: ...


class KeyboardInputAdapter:
    """Global keyboard press/release adapter backed by pynput."""

    def __init__(
        self,
        *,
        listener_factory: (
            Callable[[Callable[[Any], None], Callable[[Any], None]], Any] | None
        ) = None,
        event_factory: Callable[..., InputEvent] = keyboard_event,
        event_callback: Callable[[InputEvent], None] | None = None,
        error_callback: Callable[[Exception], None] | None = None,
    ) -> None:
        self._listener_factory = listener_factory or _default_keyboard_listener_factory
        self._event_factory = event_factory
        self._event_callback = event_callback
        self._error_callback = error_callback
        self._listener: Any | None = None
        self._is_running = False

    @property
    def is_running(self) -> bool:
        return self._is_running

    def set_event_callback(self, callback: Callable[[InputEvent], None] | None) -> None:
        self._event_callback = callback

    def start(self) -> None:
        if self._is_running:
            return
        listener = self._listener_factory(self._on_press, self._on_release)
        try:
            listener.start()
        except Exception:
            _stop_listener(listener, suppress_exceptions=True)
            raise
        self._listener = listener
        self._is_running = True

    def stop(self) -> None:
        if not self._is_running:
            return
        listener = self._listener
        self._listener = None
        self._is_running = False
        if listener is None:
            return
        _stop_listener(listener)

    def _on_press(self, key: Any) -> None:
        self._emit_normalized(key, pressed=True)

    def _on_release(self, key: Any) -> None:
        self._emit_normalized(key, pressed=False)

    def _emit_normalized(self, raw_code: Any, *, pressed: bool) -> None:
        callback = self._event_callback
        if callback is None:
            return
        try:
            callback(self._event_factory(raw_code, pressed=pressed))
        except ValueError:
            return
        except Exception as exc:
            _handle_adapter_exception(exc, self._error_callback)


class MouseInputAdapter:
    """Global mouse button press/release adapter backed by pynput."""

    def __init__(
        self,
        *,
        listener_factory: (
            Callable[[Callable[[int, int, Any, bool], None]], Any] | None
        ) = None,
        event_factory: Callable[..., InputEvent] = mouse_event,
        event_callback: Callable[[InputEvent], None] | None = None,
        error_callback: Callable[[Exception], None] | None = None,
    ) -> None:
        self._listener_factory = listener_factory or _default_mouse_listener_factory
        self._event_factory = event_factory
        self._event_callback = event_callback
        self._error_callback = error_callback
        self._listener: Any | None = None
        self._is_running = False

    @property
    def is_running(self) -> bool:
        return self._is_running

    def set_event_callback(self, callback: Callable[[InputEvent], None] | None) -> None:
        self._event_callback = callback

    def start(self) -> None:
        if self._is_running:
            return
        listener = self._listener_factory(self._on_click)
        try:
            listener.start()
        except Exception:
            _stop_listener(listener, suppress_exceptions=True)
            raise
        self._listener = listener
        self._is_running = True

    def stop(self) -> None:
        if not self._is_running:
            return
        listener = self._listener
        self._listener = None
        self._is_running = False
        if listener is None:
            return
        _stop_listener(listener)

    def _on_click(self, _x: int, _y: int, button: Any, pressed: bool) -> None:
        self._emit_normalized(button, pressed=pressed)

    def _emit_normalized(self, raw_code: Any, *, pressed: bool) -> None:
        callback = self._event_callback
        if callback is None:
            return
        try:
            callback(self._event_factory(raw_code, pressed=pressed))
        except ValueError:
            return
        except Exception as exc:
            _handle_adapter_exception(exc, self._error_callback)


class GamepadInputAdapter:
    """Global gamepad adapter backed by pygame event polling."""

    def __init__(
        self,
        *,
        pygame_module: Any | None = None,
        thread_factory: Callable[..., threading.Thread] = threading.Thread,
        event_factory: Callable[..., InputEvent] = gamepad_event,
        event_callback: Callable[[InputEvent], None] | None = None,
        error_callback: Callable[[Exception], None] | None = None,
        poll_interval_seconds: float = _GAMEPAD_POLL_INTERVAL_SECONDS,
    ) -> None:
        self._pygame_module = pygame_module
        self._thread_factory = thread_factory
        self._event_factory = event_factory
        self._event_callback = event_callback
        self._error_callback = error_callback
        self._poll_interval_seconds = max(0.001, float(poll_interval_seconds))
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._is_running = False
        self._joysticks: list[Any] = []
        self._owns_pygame_init = False
        self._owns_joystick_init = False
        self._axis_button_states: dict[int, bool] = {}

    @property
    def is_running(self) -> bool:
        return self._is_running

    def set_event_callback(self, callback: Callable[[InputEvent], None] | None) -> None:
        self._event_callback = callback

    def start(self) -> None:
        if self._is_running:
            return

        self._stop_event.clear()
        thread: threading.Thread | None = None
        try:
            self._initialize_runtime()
            thread = self._thread_factory(
                target=self._run_loop,
                name="d2rso-gamepad-adapter",
                daemon=True,
            )
            thread.start()
        except Exception:
            self._is_running = False
            self._thread = None
            self._stop_event.set()
            self._cleanup_runtime()
            raise

        self._is_running = True
        self._thread = thread

    def stop(self) -> None:
        if not self._is_running:
            return

        self._is_running = False
        self._stop_event.set()

        thread = self._thread
        self._thread = None
        if thread is not None and thread.is_alive():
            thread.join(timeout=1.0)

        self._cleanup_runtime()

    def _initialize_runtime(self) -> None:
        self._axis_button_states.clear()
        pygame_module = self._resolve_pygame_module()
        _configure_pygame_headless_if_needed(pygame_module)
        if hasattr(pygame_module, "get_init") and not pygame_module.get_init():
            pygame_module.init()
            self._owns_pygame_init = True

        joystick_module = pygame_module.joystick
        if hasattr(joystick_module, "get_init"):
            if not joystick_module.get_init():
                joystick_module.init()
                self._owns_joystick_init = True
        else:
            joystick_module.init()
            self._owns_joystick_init = True

        self._refresh_joysticks()

    def _resolve_pygame_module(self) -> Any:
        if self._pygame_module is None:
            self._pygame_module = _resolve_pygame_module()
        return self._pygame_module

    def _run_loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                self._poll_once()
            except Exception as exc:
                _handle_adapter_exception(exc, self._error_callback)
            if self._stop_event.wait(self._poll_interval_seconds):
                break

    def _poll_once(self) -> None:
        pygame_module = self._resolve_pygame_module()
        events = tuple(pygame_module.event.get())
        joy_button_down = getattr(pygame_module, "JOYBUTTONDOWN", None)
        joy_button_up = getattr(pygame_module, "JOYBUTTONUP", None)
        joy_axis_motion = getattr(pygame_module, "JOYAXISMOTION", None)
        joy_device_added = getattr(pygame_module, "JOYDEVICEADDED", None)
        joy_device_removed = getattr(pygame_module, "JOYDEVICEREMOVED", None)
        for event in events:
            event_type = getattr(event, "type", None)

            if event_type == joy_button_down:
                self._emit_normalized(getattr(event, "button", None), pressed=True)
                continue

            if event_type == joy_button_up:
                self._emit_normalized(getattr(event, "button", None), pressed=False)
                continue

            if event_type == joy_axis_motion:
                self._handle_axis_motion(
                    getattr(event, "axis", None),
                    getattr(event, "value", None),
                )
                continue

            if event_type in {joy_device_added, joy_device_removed}:
                self._refresh_joysticks()

    def _emit_normalized(self, raw_code: Any, *, pressed: bool) -> None:
        callback = self._event_callback
        if callback is None or raw_code is None:
            return
        try:
            callback(self._event_factory(raw_code, pressed=pressed))
        except ValueError:
            return
        except Exception as exc:
            _handle_adapter_exception(exc, self._error_callback)

    def _handle_axis_motion(self, axis: Any, value: Any) -> None:
        try:
            axis_index = int(axis)
            axis_value = float(value)
        except (TypeError, ValueError):
            return

        virtual_button = _GAMEPAD_TRIGGER_AXIS_TO_BUTTON.get(axis_index)
        if virtual_button is None:
            return

        is_pressed = self._axis_button_states.get(virtual_button, False)
        if not is_pressed and axis_value >= _GAMEPAD_TRIGGER_PRESS_THRESHOLD:
            self._axis_button_states[virtual_button] = True
            self._emit_normalized(virtual_button, pressed=True)
            return

        if is_pressed and axis_value <= _GAMEPAD_TRIGGER_RELEASE_THRESHOLD:
            self._axis_button_states[virtual_button] = False
            self._emit_normalized(virtual_button, pressed=False)

    def _refresh_joysticks(self) -> None:
        pygame_module = self._resolve_pygame_module()
        joystick_module = pygame_module.joystick
        count = max(0, int(joystick_module.get_count()))

        while len(self._joysticks) > count:
            joystick = self._joysticks.pop()
            quit_fn = getattr(joystick, "quit", None)
            if callable(quit_fn):
                quit_fn()

        for index in range(len(self._joysticks), count):
            joystick = joystick_module.Joystick(index)
            init_fn = getattr(joystick, "init", None)
            if callable(init_fn):
                init_fn()
            self._joysticks.append(joystick)

    def _cleanup_runtime(self) -> None:
        pygame_module = self._pygame_module
        if pygame_module is None:
            return

        for joystick in reversed(self._joysticks):
            quit_fn = getattr(joystick, "quit", None)
            if callable(quit_fn):
                try:
                    quit_fn()
                except Exception:
                    pass
        self._joysticks.clear()

        joystick_module = None
        if hasattr(pygame_module, "joystick"):
            joystick_module = pygame_module.joystick
        if joystick_module is not None and self._owns_joystick_init:
            quit_fn = getattr(joystick_module, "quit", None)
            if callable(quit_fn):
                try:
                    quit_fn()
                except Exception:
                    pass

        if self._owns_pygame_init:
            quit_fn = getattr(pygame_module, "quit", None)
            if callable(quit_fn):
                try:
                    quit_fn()
                except Exception:
                    pass

        self._owns_pygame_init = False
        self._owns_joystick_init = False
        self._axis_button_states.clear()


class InputRouter:
    """Unified lifecycle controller that routes global input into tracker logic."""

    def __init__(
        self,
        *,
        tracker_engine: TrackerInputEngine | None = None,
        adapters: Sequence[InputAdapter] | None = None,
        on_event: Callable[[InputEvent], None] | None = None,
        on_triggered: Callable[[InputEvent, list[SkillItem]], None] | None = None,
        on_error: Callable[[Exception], None] | None = None,
    ) -> None:
        self._tracker_engine = tracker_engine or TrackerInputEngine()
        self._on_event = on_event
        self._on_triggered = on_triggered
        self._on_error = on_error

        self._adapters: list[InputAdapter] = (
            list(adapters)
            if adapters is not None
            else [
                KeyboardInputAdapter(error_callback=on_error),
                MouseInputAdapter(error_callback=on_error),
                GamepadInputAdapter(error_callback=on_error),
            ]
        )
        for adapter in self._adapters:
            adapter.set_event_callback(self.route_input_event)

        self._event_queue: Queue[InputEvent | None] = Queue()
        self._worker_stop_event = threading.Event()
        self._worker_thread: threading.Thread | None = None
        self._is_running = False
        self._accepting_events = False
        self._state_lock = threading.Lock()

    @property
    def is_running(self) -> bool:
        return self._is_running

    @property
    def adapters(self) -> tuple[InputAdapter, ...]:
        return tuple(self._adapters)

    def set_skill_items(self, skill_items: Sequence[SkillItem]) -> None:
        self._tracker_engine.set_skill_items(skill_items)

    def start(self) -> None:
        with self._state_lock:
            if self._is_running:
                return

            self._drain_queue()
            self._worker_stop_event.clear()
            self._accepting_events = True
            self._is_running = True
            self._worker_thread = threading.Thread(
                target=self._run_worker,
                name="d2rso-input-router",
                daemon=True,
            )
            self._worker_thread.start()

        started_adapters: list[InputAdapter] = []
        try:
            for adapter in self._adapters:
                adapter.start()
                started_adapters.append(adapter)
        except Exception:
            for adapter in reversed(started_adapters):
                try:
                    adapter.stop()
                except Exception:
                    pass
            self._shutdown_worker()
            raise

    def stop(self) -> None:
        with self._state_lock:
            if not self._is_running:
                return
            self._accepting_events = False

        adapter_errors: list[Exception] = []
        for adapter in reversed(self._adapters):
            try:
                adapter.stop()
            except Exception as exc:
                adapter_errors.append(exc)

        self._shutdown_worker()

        if adapter_errors:
            error = RuntimeError("One or more input adapters failed to stop cleanly.")
            error.__cause__ = adapter_errors[0]
            raise error

    def route_input_event(self, event: InputEvent) -> None:
        if not isinstance(event, InputEvent):
            raise TypeError("event must be an InputEvent.")
        if not self._accepting_events:
            return
        self._event_queue.put(event)

    def _run_worker(self) -> None:
        while True:
            if self._worker_stop_event.is_set() and self._event_queue.empty():
                return
            try:
                event = self._event_queue.get(timeout=_QUEUE_TIMEOUT_SECONDS)
            except Empty:
                continue
            if event is None:
                continue

            try:
                self._dispatch_event(event)
            except Exception as exc:
                if self._on_error is not None:
                    self._on_error(exc)

    def _dispatch_event(self, event: InputEvent) -> list[SkillItem]:
        triggered = self._tracker_engine.process_event(event)
        if self._on_event is not None:
            self._on_event(event)
        if self._on_triggered is not None:
            self._on_triggered(event, triggered)
        return triggered

    def _shutdown_worker(self) -> None:
        self._worker_stop_event.set()
        self._event_queue.put(None)
        worker = self._worker_thread
        self._worker_thread = None
        if worker is not None and worker.is_alive():
            worker.join(timeout=1.0)

        with self._state_lock:
            self._is_running = False
            self._accepting_events = False

        self._drain_queue()

    def _drain_queue(self) -> None:
        while True:
            try:
                self._event_queue.get_nowait()
            except Empty:
                break


def _default_keyboard_listener_factory(
    on_press: Callable[[Any], None],
    on_release: Callable[[Any], None],
) -> Any:
    from pynput import keyboard

    _apply_darwin_pynput_keyboard_workaround(keyboard)
    return keyboard.Listener(on_press=on_press, on_release=on_release)


def _default_mouse_listener_factory(
    on_click: Callable[[int, int, Any, bool], None],
) -> Any:
    from pynput import mouse

    return mouse.Listener(on_click=on_click)


def _handle_adapter_exception(
    exception: Exception,
    callback: Callable[[Exception], None] | None,
) -> None:
    if callback is not None:
        callback(exception)


def _stop_listener(
    listener: Any,
    *,
    suppress_exceptions: bool = False,
    join_timeout_seconds: float = _LISTENER_JOIN_TIMEOUT_SECONDS,
) -> None:
    stop_fn = getattr(listener, "stop", None)
    join_fn = getattr(listener, "join", None)
    pending_exception: Exception | None = None

    if callable(stop_fn):
        try:
            stop_fn()
        except Exception as exc:
            if not suppress_exceptions:
                pending_exception = exc

    if callable(join_fn) and listener is not threading.current_thread():
        try:
            join_fn(timeout=join_timeout_seconds)
        except Exception as exc:
            if pending_exception is None and not suppress_exceptions:
                pending_exception = exc

    if pending_exception is not None:
        raise pending_exception


__all__ = [
    "GamepadInputAdapter",
    "GamepadDeviceInfo",
    "InputAdapter",
    "InputRouter",
    "KeyboardInputAdapter",
    "MouseInputAdapter",
    "list_connected_gamepads",
]
