"""Global input adapters and unified router lifecycle control."""

from __future__ import annotations

import contextlib
import os
import platform
import threading
from collections.abc import Callable, Sequence
from queue import Empty, Queue
from typing import Any, Protocol

from .input_events import InputEvent, gamepad_event, keyboard_event, mouse_event
from .models import SkillItem
from .tracker_engine import TrackerInputEngine

_QUEUE_TIMEOUT_SECONDS = 0.05
_GAMEPAD_POLL_INTERVAL_SECONDS = 0.01


def _apply_darwin_pynput_keyboard_workaround(keyboard_module: Any) -> None:
    """
    Patch pynput's Darwin keyboard listener to avoid background-thread TIS calls.

    On newer macOS versions, calling TSM/TIS keyboard input-source APIs from the
    pynput listener thread can trigger a hard abort in libdispatch. We only need
    the listener path (not the key injection controller), so using a no-op
    keycode context is sufficient for this app's key-down tracking use case.
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
    """Global keyboard key-down adapter backed by pynput."""

    def __init__(
        self,
        *,
        listener_factory: Callable[[Callable[[Any], None]], Any] | None = None,
        event_factory: Callable[[Any], InputEvent] = keyboard_event,
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
        listener = self._listener_factory(self._on_press)
        try:
            listener.start()
        except Exception:
            _stop_listener_safely(listener)
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
        listener.stop()

    def _on_press(self, key: Any) -> None:
        self._emit_normalized(key)

    def _emit_normalized(self, raw_code: Any) -> None:
        callback = self._event_callback
        if callback is None:
            return
        try:
            callback(self._event_factory(raw_code))
        except ValueError:
            return
        except Exception as exc:
            _handle_adapter_exception(exc, self._error_callback)


class MouseInputAdapter:
    """Global mouse button-down adapter backed by pynput."""

    def __init__(
        self,
        *,
        listener_factory: (
            Callable[[Callable[[int, int, Any, bool], None]], Any] | None
        ) = None,
        event_factory: Callable[[Any], InputEvent] = mouse_event,
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
            _stop_listener_safely(listener)
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
        listener.stop()

    def _on_click(self, _x: int, _y: int, button: Any, pressed: bool) -> None:
        if not pressed:
            return
        self._emit_normalized(button)

    def _emit_normalized(self, raw_code: Any) -> None:
        callback = self._event_callback
        if callback is None:
            return
        try:
            callback(self._event_factory(raw_code))
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
        event_factory: Callable[[Any], InputEvent] = gamepad_event,
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
            _configure_pygame_headless_if_needed()
            import pygame

            self._pygame_module = pygame
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
        joy_device_added = getattr(pygame_module, "JOYDEVICEADDED", None)
        joy_device_removed = getattr(pygame_module, "JOYDEVICEREMOVED", None)
        for event in events:
            event_type = getattr(event, "type", None)

            if event_type == joy_button_down:
                self._emit_normalized(getattr(event, "button", None))
                continue

            if event_type in {joy_device_added, joy_device_removed}:
                self._refresh_joysticks()

    def _emit_normalized(self, raw_code: Any) -> None:
        callback = self._event_callback
        if callback is None or raw_code is None:
            return
        try:
            callback(self._event_factory(raw_code))
        except ValueError:
            return
        except Exception as exc:
            _handle_adapter_exception(exc, self._error_callback)

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


def _default_keyboard_listener_factory(on_press: Callable[[Any], None]) -> Any:
    from pynput import keyboard

    _apply_darwin_pynput_keyboard_workaround(keyboard)
    return keyboard.Listener(on_press=on_press)


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


def _stop_listener_safely(listener: Any) -> None:
    stop_fn = getattr(listener, "stop", None)
    if callable(stop_fn):
        try:
            stop_fn()
        except Exception:
            pass


__all__ = [
    "GamepadInputAdapter",
    "InputAdapter",
    "InputRouter",
    "KeyboardInputAdapter",
    "MouseInputAdapter",
]
