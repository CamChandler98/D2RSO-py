"""Device-agnostic input event contract and normalization helpers."""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class InputSource(StrEnum):
    """Supported input device families."""

    KEYBOARD = "keyboard"
    MOUSE = "mouse"
    GAMEPAD = "gamepad"


_FUNCTION_KEY_RE = re.compile(r"^f(?P<number>\d{1,2})$")
_NUMPAD_KEY_RE = re.compile(r"^(?:numpad|num)(?P<number>\d)$")
_D_KEY_RE = re.compile(r"^d(?P<number>\d)$")
_BUTTONS_CODE_RE = re.compile(r"^buttons(?P<number>\d+)$")
_GAMEPAD_BUTTON_RE = re.compile(r"^(?:gamepad)?button(?P<number>\d+)$")
_DIRECT_INPUT_BUTTON_RE = re.compile(r"^joystickoffsetbuttons(?P<number>\d+)$")
_KEYCODE_CHAR_RE = re.compile(r"""^keycode\(char=['"](?P<char>.)['"]\)$""", re.I)
_KEYCODE_VK_RE = re.compile(r"^keycode\(vk=(?P<vk>\d+)\)$", re.I)

_KEYBOARD_PUNCTUATION_ALIASES = {
    ",": "OemComma",
    "~": "OemTilde",
    "[": "OemOpenBrackets",
    "]": "OemCloseBrackets",
    ":": "OemSemicolon",
    ";": "OemSemicolon",
    "'": "OemQuotes",
    "+": "Add",
    "-": "Subtract",
}

_KEYBOARD_ALIASES = {
    "esc": "Escape",
    "escape": "Escape",
    "enter": "Return",
    "return": "Return",
    "tab": "Tab",
    "back": "Back",
    "backspace": "Back",
    "lshift": "LShiftKey",
    "leftshift": "LShiftKey",
    "shiftl": "LShiftKey",
    "shiftleft": "LShiftKey",
    "shiftlkey": "LShiftKey",
    "rshift": "RShiftKey",
    "rightshift": "RShiftKey",
    "shiftr": "RShiftKey",
    "shiftright": "RShiftKey",
    "shiftrkey": "RShiftKey",
    "lalt": "LMenu",
    "leftalt": "LMenu",
    "altleft": "LMenu",
    "altl": "LMenu",
    "lmenu": "LMenu",
    "ralt": "RMenu",
    "rightalt": "RMenu",
    "altright": "RMenu",
    "altr": "RMenu",
    "rmenu": "RMenu",
    "lcontrol": "LControlKey",
    "leftcontrol": "LControlKey",
    "controlleft": "LControlKey",
    "lctrl": "LControlKey",
    "ctrll": "LControlKey",
    "lcontrolkey": "LControlKey",
    "rcontrol": "RControlKey",
    "rightcontrol": "RControlKey",
    "controlright": "RControlKey",
    "rctrl": "RControlKey",
    "ctrlr": "RControlKey",
    "rcontrolkey": "RControlKey",
    "comma": "OemComma",
    "oemcomma": "OemComma",
    "tilde": "OemTilde",
    "oemtilde": "OemTilde",
    "openbracket": "OemOpenBrackets",
    "leftbracket": "OemOpenBrackets",
    "oemopenbrackets": "OemOpenBrackets",
    "closebracket": "OemCloseBrackets",
    "rightbracket": "OemCloseBrackets",
    "oemclosebrackets": "OemCloseBrackets",
    "semicolon": "OemSemicolon",
    "oemsemicolon": "OemSemicolon",
    "quote": "OemQuotes",
    "apostrophe": "OemQuotes",
    "oemquotes": "OemQuotes",
    "add": "Add",
    "plus": "Add",
    "subtract": "Subtract",
    "minus": "Subtract",
}

_MOUSE_INDEX_TO_CODE = {
    0: "MOUSE1",
    1: "MOUSE2",
    2: "MOUSE3",
    3: "MOUSEX1",
    4: "MOUSEX2",
}

_MOUSE_ALIASES = {
    "mouse1": "MOUSE1",
    "left": "MOUSE1",
    "lbutton": "MOUSE1",
    "buttonleft": "MOUSE1",
    "button1": "MOUSE1",
    "mouse2": "MOUSE2",
    "right": "MOUSE2",
    "rbutton": "MOUSE2",
    "buttonright": "MOUSE2",
    "button2": "MOUSE2",
    "mouse3": "MOUSE3",
    "middle": "MOUSE3",
    "mbutton": "MOUSE3",
    "buttonmiddle": "MOUSE3",
    "button3": "MOUSE3",
    "mousex1": "MOUSEX1",
    "x1": "MOUSEX1",
    "xbutton1": "MOUSEX1",
    "buttonx1": "MOUSEX1",
    "button4": "MOUSEX1",
    "mousex2": "MOUSEX2",
    "x2": "MOUSEX2",
    "xbutton2": "MOUSEX2",
    "buttonx2": "MOUSEX2",
    "button5": "MOUSEX2",
}

_SOURCE_ALIASES = {
    "keyboard": InputSource.KEYBOARD,
    "key": InputSource.KEYBOARD,
    "keys": InputSource.KEYBOARD,
    "kbd": InputSource.KEYBOARD,
    "mouse": InputSource.MOUSE,
    "gamepad": InputSource.GAMEPAD,
    "controller": InputSource.GAMEPAD,
    "joystick": InputSource.GAMEPAD,
    "pad": InputSource.GAMEPAD,
}


def _simplify_token(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.strip().lower())


def _extract_raw_code(value: Any) -> str | int | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (str, int)):
        return value

    for attribute in ("char", "name"):
        attribute_value = getattr(value, attribute, None)
        if isinstance(attribute_value, str) and attribute_value.strip():
            return attribute_value

    attribute_value = getattr(value, "value", None)
    if isinstance(attribute_value, int):
        return attribute_value
    if isinstance(attribute_value, str) and attribute_value.strip():
        return attribute_value

    return str(value)


def normalize_input_source(source: InputSource | str) -> InputSource:
    """Normalize source aliases to one of the supported input sources."""
    if isinstance(source, InputSource):
        return source

    key = _simplify_token(str(source))
    if not key:
        raise ValueError("Input source cannot be empty.")

    resolved = _SOURCE_ALIASES.get(key)
    if resolved is None:
        raise ValueError(f"Unsupported input source: {source!r}")
    return resolved


def _normalize_buttons_index(value: int) -> str | None:
    if 48 <= value <= 57:
        return f"Buttons{value - 48}"
    if value >= 0:
        return f"Buttons{value}"
    return None


def infer_input_source_from_code(code: Any) -> InputSource | None:
    """Infer input source from a raw code shape."""
    raw = _extract_raw_code(code)
    if raw is None:
        return None

    if isinstance(raw, int):
        if raw in _MOUSE_INDEX_TO_CODE:
            return InputSource.MOUSE
        if _normalize_buttons_index(raw) is not None:
            return InputSource.GAMEPAD
        return None

    text = raw.strip()
    if not text:
        return None
    token = _simplify_token(text.removeprefix("Key.").removeprefix("key."))

    if token in _MOUSE_ALIASES or token.startswith("mouse"):
        return InputSource.MOUSE
    if (
        _BUTTONS_CODE_RE.fullmatch(token)
        or _GAMEPAD_BUTTON_RE.fullmatch(token)
        or _DIRECT_INPUT_BUTTON_RE.fullmatch(token)
    ):
        return InputSource.GAMEPAD
    if token.startswith("joystickoffsetbuttons"):
        return InputSource.GAMEPAD

    return InputSource.KEYBOARD


def normalize_keyboard_code(raw_code: Any) -> str | None:
    """Normalize raw keyboard key identifiers to canonical tracker names."""
    raw = _extract_raw_code(raw_code)
    if raw is None:
        return None

    if isinstance(raw, int):
        if 65 <= raw <= 90:
            return chr(raw)
        if 48 <= raw <= 57:
            return f"D{raw - 48}"
        return None

    text = raw.strip()
    if not text:
        return None

    if text in _KEYBOARD_PUNCTUATION_ALIASES:
        return _KEYBOARD_PUNCTUATION_ALIASES[text]

    lowered = text.lower()
    for prefix in ("key.", "keys.", "keyboard."):
        if lowered.startswith(prefix):
            text = text[len(prefix) :]
            lowered = text.lower()
            break

    keycode_char_match = _KEYCODE_CHAR_RE.fullmatch(lowered)
    if keycode_char_match is not None:
        text = keycode_char_match.group("char")
    else:
        keycode_vk_match = _KEYCODE_VK_RE.fullmatch(lowered)
        if keycode_vk_match is not None:
            return normalize_keyboard_code(int(keycode_vk_match.group("vk")))

    if len(text) == 3 and text[0] == text[-1] and text[0] in {"'", '"'}:
        text = text[1]

    if text in _KEYBOARD_PUNCTUATION_ALIASES:
        return _KEYBOARD_PUNCTUATION_ALIASES[text]

    token = _simplify_token(text)
    if not token:
        return None

    alias = _KEYBOARD_ALIASES.get(token)
    if alias is not None:
        return alias

    function_match = _FUNCTION_KEY_RE.fullmatch(token)
    if function_match is not None:
        return f"F{int(function_match.group('number'))}"

    numpad_match = _NUMPAD_KEY_RE.fullmatch(token)
    if numpad_match is not None:
        return f"NumPad{int(numpad_match.group('number'))}"

    d_key_match = _D_KEY_RE.fullmatch(token)
    if d_key_match is not None:
        return f"D{int(d_key_match.group('number'))}"

    if len(token) == 1 and token.isalpha():
        return token.upper()
    if len(token) == 1 and token.isdigit():
        return f"D{token}"

    if token.startswith("vk") and token[2:].isdigit():
        return normalize_keyboard_code(int(token[2:]))

    return None


def normalize_mouse_code(raw_code: Any) -> str | None:
    """Normalize raw mouse button identifiers to MOUSE1..MOUSEX2."""
    raw = _extract_raw_code(raw_code)
    if raw is None:
        return None

    if isinstance(raw, int):
        return _MOUSE_INDEX_TO_CODE.get(raw)

    token = _simplify_token(raw)
    if not token:
        return None

    if token in _MOUSE_ALIASES:
        return _MOUSE_ALIASES[token]

    if token.isdigit():
        return _MOUSE_INDEX_TO_CODE.get(int(token))

    if token.startswith("mousex") and token[6:].isdigit():
        index = int(token[6:])
        if index in {1, 2}:
            return f"MOUSEX{index}"

    if token.startswith("mouse") and token[5:].isdigit():
        index = int(token[5:])
        return _MOUSE_INDEX_TO_CODE.get(index - 1)

    return None


def normalize_gamepad_code(raw_code: Any) -> str | None:
    """Normalize raw gamepad button identifiers to Buttons0..ButtonsN."""
    raw = _extract_raw_code(raw_code)
    if raw is None:
        return None

    if isinstance(raw, int):
        return _normalize_buttons_index(raw)

    token = _simplify_token(raw)
    if not token:
        return None

    if token.startswith("joystickoffset"):
        token = token[len("joystickoffset") :]

    buttons_match = _BUTTONS_CODE_RE.fullmatch(token)
    if buttons_match is not None:
        return _normalize_buttons_index(int(buttons_match.group("number")))

    gamepad_match = _GAMEPAD_BUTTON_RE.fullmatch(token)
    if gamepad_match is not None:
        return _normalize_buttons_index(int(gamepad_match.group("number")))

    direct_input_match = _DIRECT_INPUT_BUTTON_RE.fullmatch(token)
    if direct_input_match is not None:
        return _normalize_buttons_index(int(direct_input_match.group("number")))

    if token.startswith("button") and token[6:].isdigit():
        return _normalize_buttons_index(int(token[6:]))

    if token.isdigit():
        return _normalize_buttons_index(int(token))

    return None


def normalize_input_code(
    raw_code: Any,
    *,
    source: InputSource | str | None = None,
) -> str | None:
    """Normalize a raw input code, optionally with explicit source hint."""
    resolved_source = (
        normalize_input_source(source)
        if source is not None
        else infer_input_source_from_code(raw_code)
    )
    if resolved_source is None:
        return None

    if resolved_source == InputSource.KEYBOARD:
        return normalize_keyboard_code(raw_code)
    if resolved_source == InputSource.MOUSE:
        return normalize_mouse_code(raw_code)
    return normalize_gamepad_code(raw_code)


@dataclass(frozen=True, slots=True)
class InputEvent:
    """Normalized event shape consumed by tracker logic."""

    code: str
    source: InputSource | str
    timestamp: float = field(default_factory=time.time)
    pressed: bool = True

    def __post_init__(self) -> None:
        normalized_source = normalize_input_source(self.source)
        normalized_code = normalize_input_code(self.code, source=normalized_source)
        if normalized_code is None:
            raise ValueError(
                f"Could not normalize input code {self.code!r} for {normalized_source}."
            )
        object.__setattr__(self, "source", normalized_source)
        object.__setattr__(self, "code", normalized_code)
        object.__setattr__(self, "timestamp", float(self.timestamp))
        object.__setattr__(self, "pressed", bool(self.pressed))


def make_input_event(
    code: Any,
    *,
    source: InputSource | str,
    timestamp: float | None = None,
    pressed: bool = True,
) -> InputEvent:
    """Create a normalized input event."""
    if timestamp is None:
        return InputEvent(code=code, source=source, pressed=pressed)
    return InputEvent(code=code, source=source, timestamp=timestamp, pressed=pressed)


def keyboard_event(
    code: Any,
    *,
    timestamp: float | None = None,
    pressed: bool = True,
) -> InputEvent:
    """Build an InputEvent from a keyboard adapter payload."""
    return make_input_event(
        code,
        source=InputSource.KEYBOARD,
        timestamp=timestamp,
        pressed=pressed,
    )


def mouse_event(
    code: Any,
    *,
    timestamp: float | None = None,
    pressed: bool = True,
) -> InputEvent:
    """Build an InputEvent from a mouse adapter payload."""
    return make_input_event(
        code,
        source=InputSource.MOUSE,
        timestamp=timestamp,
        pressed=pressed,
    )


def gamepad_event(
    code: Any,
    *,
    timestamp: float | None = None,
    pressed: bool = True,
) -> InputEvent:
    """Build an InputEvent from a gamepad adapter payload."""
    return make_input_event(
        code,
        source=InputSource.GAMEPAD,
        timestamp=timestamp,
        pressed=pressed,
    )


__all__ = [
    "InputEvent",
    "InputSource",
    "gamepad_event",
    "infer_input_source_from_code",
    "keyboard_event",
    "make_input_event",
    "mouse_event",
    "normalize_gamepad_code",
    "normalize_input_code",
    "normalize_input_source",
    "normalize_keyboard_code",
    "normalize_mouse_code",
]
