import pytest

from d2rso.input_events import (
    InputEvent,
    InputSource,
    gamepad_event,
    infer_input_source_from_code,
    keyboard_event,
    mouse_event,
    normalize_gamepad_code,
    normalize_input_code,
    normalize_keyboard_code,
    normalize_mouse_code,
)


def test_keyboard_mouse_gamepad_emit_same_event_shape():
    keyboard = keyboard_event("f1", timestamp=101.0)
    mouse = mouse_event("button.right", timestamp=102.0)
    gamepad = gamepad_event("GamePad Button 0", timestamp=103.0)

    events = [keyboard, mouse, gamepad]
    assert all(isinstance(event, InputEvent) for event in events)
    assert keyboard.code == "F1"
    assert keyboard.source == InputSource.KEYBOARD
    assert keyboard.timestamp == 101.0
    assert mouse.code == "MOUSE2"
    assert mouse.source == InputSource.MOUSE
    assert mouse.timestamp == 102.0
    assert gamepad.code == "Buttons0"
    assert gamepad.source == InputSource.GAMEPAD
    assert gamepad.timestamp == 103.0


def test_code_normalizers_standardize_keyboard_mouse_and_gamepad_names():
    assert normalize_keyboard_code("f8") == "F8"
    assert normalize_keyboard_code("1") == "D1"
    assert normalize_keyboard_code("left shift") == "LShiftKey"
    assert normalize_keyboard_code("escape") == "Escape"

    assert normalize_mouse_code(1) == "MOUSE2"
    assert normalize_mouse_code("xbutton2") == "MOUSEX2"

    assert normalize_gamepad_code(48) == "Buttons0"
    assert normalize_gamepad_code(12) == "Buttons12"
    assert normalize_gamepad_code("joystickoffset.buttons7") == "Buttons7"
    assert normalize_gamepad_code("GamePad Button 12") == "Buttons12"


def test_source_inference_and_generic_normalization_follow_tracker_naming():
    assert infer_input_source_from_code("F1") == InputSource.KEYBOARD
    assert infer_input_source_from_code("MOUSE2") == InputSource.MOUSE
    assert infer_input_source_from_code("Buttons9") == InputSource.GAMEPAD

    assert normalize_input_code("f1") == "F1"
    assert normalize_input_code("button.right") == "MOUSE2"
    assert normalize_input_code("GamePad Button 4") == "Buttons4"
    assert normalize_input_code("Buttons12", source=InputSource.GAMEPAD) == "Buttons12"


def test_invalid_device_code_is_rejected_for_event_creation():
    with pytest.raises(ValueError):
        mouse_event("scroll-wheel")
