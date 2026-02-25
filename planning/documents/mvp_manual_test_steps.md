# D2RSO Python MVP Manual Test — Detailed Execution Steps

This guide expands `mvp_manual_test_checklist.md` into concrete, repeatable manual actions.
Use it side-by-side with the checklist and record pass/fail + notes for each case.

## 1) Before You Start

1. Open a terminal in repo root:
   ```bash
   cd /workspace/D2RSO-py
   ```
2. Confirm Python version target:
   ```bash
   python --version
   ```
   Expected: Python 3.11.x.
3. Create the environment and install dev deps:
   ```bash
   pipenv --python 3.11
   pipenv install --dev
   ```
4. Prepare icon test fixtures:
   ```bash
   mkdir -p assets/skills
   cp <path-to-valid-image> assets/skills/orb.png
   cp <path-to-valid-image> assets/skills/shield.png
   printf 'not-an-image' > assets/skills/ignore.txt
   python - <<'PY'
from pathlib import Path
Path('assets/skills/corrupt.png').write_bytes(b'\x89PNG\r\n\x1a\nBROKEN')
print('wrote assets/skills/corrupt.png')
PY
   ```

## 2) Foundation and Dependency Baseline (MVP-01 to MVP-02)

### MVP-01 App launch smoke test
1. Run:
   ```bash
   pipenv run python -m d2rso
   ```
2. Verify a window opens titled **D2RSO**.
3. Close the window.
4. Confirm process exits and terminal shows no traceback.

### MVP-02 Dependency import validation
1. Run:
   ```bash
   pipenv run pytest tests/test_imports.py -q
   ```
2. Verify imports pass for PySide6 / pynput / pygame.
3. On non-Windows, confirm pywin32 is skipped (not failed).

## 3) Core Models and Persistence (MVP-03 to MVP-10)

Use a Python shell for quick checks:
```bash
pipenv run python
```

### MVP-03 Sequence skill state machine
```python
from d2rso.domain.models import SkillItem
s = SkillItem(select_key='F8', skill_key='MOUSE2')
print(s.skill_key_pressed())      # False
s.select_key_pressed()
print(s.skill_key_pressed())      # True
print(s.skill_key_pressed())      # False
```

### MVP-04 Skill-only mode
```python
s = SkillItem(select_key=None, skill_key='MOUSE2')
print(s.skill_key_pressed())      # True
print(s.skill_key_pressed())      # True
```

### MVP-05 Reset behavior
```python
s = SkillItem(select_key='F8', skill_key='MOUSE2')
s.select_key_pressed()
s.reset_keys()
print(s.skill_key_pressed())      # False
```

### MVP-06 Settings save/load round-trip
```python
from pathlib import Path
from d2rso.domain.models import Settings, Profile
from d2rso.persistence.settings_store import SettingsStore

p = Path('tmp/manual_settings.json')
settings = Settings(
    profiles=[Profile(profile_id=0, name='Default'), Profile(profile_id=1, name='Test')],
    last_selected_profile_id=1,
)
SettingsStore(p).save(settings)
loaded = SettingsStore(p).load()
print(loaded.to_dict() == settings.to_dict())  # True
```

### MVP-07 Missing settings fallback
```python
from pathlib import Path
from d2rso.persistence.settings_store import SettingsStore
missing = Path('tmp/does_not_exist.json')
loaded = SettingsStore(missing).load()
print(len(loaded.profiles) >= 1, loaded.profiles[0].name)
```

### MVP-08 Corrupt JSON fallback
```python
from pathlib import Path
from d2rso.persistence.settings_store import SettingsStore
p = Path('tmp/corrupt_settings.json')
p.parent.mkdir(parents=True, exist_ok=True)
p.write_text('{invalid json', encoding='utf-8')
loaded = SettingsStore(p).load()
print(len(loaded.profiles) >= 1)
```

### MVP-09 Default profile auto-repair
1. Create a JSON payload with empty profiles or no id `0`.
2. Load via `SettingsStore.load()`.
3. Verify a `Default` profile exists and `last_selected_profile_id` is valid.

### MVP-10 Legacy JSON shape compatibility
1. Build legacy PascalCase sample JSON (for example `SkillItems`, `SelectKey`).
2. Load it with `SettingsStore.load()`.
3. Confirm keys map to current model fields and key codes resolve.

## 4) Key Catalog and Icon Registry (MVP-11 to MVP-13)

### MVP-11 Key catalog coverage
1. Instantiate `KeyIconRegistry(...)` in REPL.
2. Assert keys exist for:
   - keyboard: `F8`
   - mouse: `MOUSE2`
   - gamepad: `Buttons7`
   - empty/null entry

### MVP-12 Icon loading and lookup
1. Point registry at `assets/skills`.
2. Call `reload_icons()`.
3. Verify:
   - `orb.png` is indexed
   - lookup works by basename and full path
   - bytes/path accessors return expected values

### MVP-13 Missing/invalid icon handling
1. Query `get_icon('missing.png')` and verify `None`.
2. Verify `corrupt.png` is skipped.
3. Verify `ignore.txt` is ignored.
4. Ensure no crash during reload.

## 5) Input Event Contract + Tracker Engine (MVP-14 to MVP-19)

### MVP-14 Input event normalization
1. Create keyboard event from `f1` and verify code `F1`.
2. Create mouse event from `button.right` and verify `MOUSE2`.
3. Create gamepad event from `GamePad Button 0` and verify `Buttons0`.
4. Confirm shape: `code`, `source`, `timestamp`.

### MVP-15 Source inference
1. Validate:
   - `infer_input_source_from_code('F1') -> keyboard`
   - `...('MOUSE2') -> mouse`
   - `...('Buttons9') -> gamepad`

### MVP-16 Invalid input code rejection
1. Call mouse event factory with invalid value `scroll-wheel`.
2. Confirm `ValueError`.

### MVP-17 Unified tracker input contract
1. Configure 3 skills: one each for keyboard/mouse/gamepad.
2. Feed one event per source.
3. Verify only matching source/skill triggers each time.

### MVP-18 Sequence + reset behavior
1. Configure sequence skill (`F8` then `MOUSE2`).
2. Confirm skill key alone does nothing.
3. Confirm select then skill triggers once.
4. Send unrelated event between select/skill and verify reset.

### MVP-19 Disabled skill handling
1. Configure one disabled and one enabled skill sharing key.
2. Trigger input and verify enabled fires, disabled does not.
3. For disabled sequence skill, ensure select does not arm.

## 6) Countdown Lifecycle Service (MVP-20 to MVP-24)

### MVP-20 Retrigger refresh behavior
1. Start timer for one `skill_id`.
2. Advance mocked clock; verify countdown decreases.
3. Retrigger same `skill_id`; verify remaining time resets.
4. Confirm active timer count remains 1.

### MVP-21 Completion removal behavior
1. Start a short timer.
2. Advance beyond end; call `emit_updates()`.
3. Verify emitted `REMOVED` with `completed=True`.
4. Confirm timer no longer active.

### MVP-22 Manual remove behavior
1. Start timer.
2. Call `remove(skill_id=...)`.
3. Confirm removal event and active count decrement.

### MVP-23 Zero/negative duration behavior
1. Refresh with `0` seconds; verify completed removal behavior.
2. Refresh with negative duration; verify `ValueError`.

### MVP-24 Callback/subscriber behavior
1. Register callback collector (append events to list).
2. Trigger refresh/update/remove lifecycle.
3. Verify callback order and payload shape.
4. Confirm this works in non-GUI context.

## 7) Final Regression Gate (MVP-25)

Run in this order:
```bash
pipenv run pytest
./scripts/pre_ci_core_logic.sh
pipenv run ruff check .
pipenv run black --check .
```

Mark checklist complete only if all commands pass and no open P0/P1 defects remain.

## 8) Suggested Defect Logging Template

For each failed case, record:
- Checklist ID (example: `MVP-18`)
- Short title
- Repro steps
- Expected vs actual
- Logs/tracebacks
- Environment details
- Severity (P0/P1/P2)

