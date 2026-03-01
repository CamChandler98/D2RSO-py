# Changelog

## 0.1.1 - 2026-03-01
- Fixed Windows gamepad trigger bindings by mapping trigger axis motion to virtual `Buttons4` and `Buttons5` events.
- Updated combo handling so select inputs behave as held modifiers instead of one-shot sequence state.
- Added regression coverage for trigger-only gamepad skills and trigger-based combos.

## 0.1.0 - 2026-03-01
- First tagged release of the Python port.
- Added the PySide6 desktop configuration app with profile management, skill rows, options, preview mode, and runtime start/stop controls.
- Added the cooldown overlay runtime with persisted settings, icon loading, and countdown updates.
- Added normalized global input routing for keyboard, mouse, and gamepad bindings, including controller-aware button labels in the key dropdowns.
- Added packaging and CI support for Windows builds, smoke testing, deterministic ZIP artifacts, and tagged GitHub releases.
