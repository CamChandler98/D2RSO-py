# D2RSO Python MVP Manual Test Checklist

Snapshot date: February 25, 2026
Milestone: MVP

## Session Info

- Tester:
- Date:
- OS:
- Python version:
- Install mode: `pipenv` / `venv`
- Build/commit under test:

## Exit Criteria

- [ ] All MVP checklist cases executed
- [ ] No open P0 defects (crash/data loss)
- [ ] No open P1 defects (core behavior mismatch)
- [ ] Regression checks pass (`pytest`, pre-CI script, lint, format)

## Scope

In scope:
- Foundation/app skeleton
- Dependency baseline
- Core models and persistence
- Key catalog and icon registry
- Input event normalization contract
- Tracker input engine
- Countdown lifecycle service

Out of scope:
- Parity and Release milestone features

## Environment Setup

- [ ] `pipenv --python 3.11`
- [ ] `pipenv install --dev`
- [ ] Create icon test files under `assets/skills`:
- [ ] 2 valid image files (`orb.png`, `shield.png`)
- [ ] 1 invalid image file (`corrupt.png`, random bytes)
- [ ] 1 non-image file (`ignore.txt`)

## Foundation and Dependency Baseline

### MVP-01 App launch smoke test
- [ ] Run `pipenv run python -m d2rso`
- [ ] Placeholder window opens with title `D2RSO`
- [ ] Closing window exits cleanly with no traceback
- Notes / Defect ID:

### MVP-02 Dependency import validation
- [ ] Run `pipenv run pytest tests/test_imports.py`
- [ ] PySide6 import passes
- [ ] `pynput` import passes
- [ ] `pygame` import passes
- [ ] `pywin32` import passes on Windows (or is skipped on non-Windows)
- Notes / Defect ID:

## Core Models and Persistence

### MVP-03 Sequence skill state machine
- [ ] In REPL, create `SkillItem(select_key="F8", skill_key="MOUSE2")`
- [ ] Calling `skill_key_pressed()` before select returns `False`
- [ ] After `select_key_pressed()`, `skill_key_pressed()` returns `True`
- [ ] Immediate extra `skill_key_pressed()` returns `False`
- Notes / Defect ID:

### MVP-04 Skill-only mode
- [ ] In REPL, create `SkillItem(select_key=None, skill_key="MOUSE2")`
- [ ] Consecutive `skill_key_pressed()` calls return `True`, `True`
- Notes / Defect ID:

### MVP-05 Reset behavior
- [ ] For sequence skill, call `select_key_pressed()`
- [ ] Call `reset_keys()`
- [ ] Next `skill_key_pressed()` returns `False`
- Notes / Defect ID:

### MVP-06 Settings save/load round-trip
- [ ] Build non-default `Settings` object
- [ ] Save using `SettingsStore.save(...)`
- [ ] Load using `SettingsStore.load()`
- [ ] `loaded.to_dict()` exactly matches original
- Notes / Defect ID:

### MVP-07 Missing settings fallback
- [ ] Load from a path that does not exist
- [ ] Defaults returned with one `Default` profile
- [ ] No crash/exception at call site
- Notes / Defect ID:

### MVP-08 Corrupt JSON fallback
- [ ] Write invalid JSON to settings path
- [ ] Load using `SettingsStore.load()`
- [ ] Defaults returned, no crash
- Notes / Defect ID:

### MVP-09 Default profile auto-repair
- [ ] Load JSON with empty profiles or missing profile id `0`
- [ ] `Default` profile is present after load
- [ ] `last_selected_profile_id` is repaired when invalid
- Notes / Defect ID:

### MVP-10 Legacy JSON shape compatibility
- [ ] Load PascalCase payload (`SkillItems`, `SelectKey`, `ProfileId`, etc.)
- [ ] Data maps correctly to Python models
- [ ] `select_key` and `skill_key` code values resolve correctly
- Notes / Defect ID:

## Key Catalog and Icon Registry

### MVP-11 Key catalog coverage
- [ ] Instantiate `KeyIconRegistry(...)`
- [ ] Keyboard entries present (example: `F8`)
- [ ] Mouse entries present (example: `MOUSE2`)
- [ ] Gamepad entries present (example: `Buttons7`)
- [ ] Empty/null key entry present
- Notes / Defect ID:

### MVP-12 Icon loading and lookup
- [ ] Load registry with prepared `assets/skills`
- [ ] Only valid images are indexed
- [ ] Lookup by filename works (`orb.png`)
- [ ] Lookup by full path works
- [ ] `get_icon_path` and `get_icon_bytes` return expected values
- Notes / Defect ID:

### MVP-13 Missing/invalid icon handling
- [ ] `get_icon("missing.png")` returns `None`
- [ ] Invalid/corrupt image is skipped gracefully
- [ ] Non-image file is ignored
- [ ] No crash/exception during `reload_icons()`
- Notes / Defect ID:

## Input Event Contract and Tracker Engine

### MVP-14 Input event normalization
- [ ] Create keyboard event from `f1` -> code resolves to `F1`
- [ ] Create mouse event from `button.right` -> code resolves to `MOUSE2`
- [ ] Create gamepad event from `GamePad Button 0` -> code resolves to `Buttons0`
- [ ] Event shape is consistent (`code`, `source`, `timestamp`)
- Notes / Defect ID:

### MVP-15 Source inference
- [ ] `infer_input_source_from_code("F1")` => keyboard
- [ ] `infer_input_source_from_code("MOUSE2")` => mouse
- [ ] `infer_input_source_from_code("Buttons9")` => gamepad
- Notes / Defect ID:

### MVP-16 Invalid input code rejection
- [ ] Attempt `mouse_event("scroll-wheel")`
- [ ] `ValueError` is raised
- Notes / Defect ID:

### MVP-17 Unified tracker input contract
- [ ] Configure skills for `F1`, `MOUSE2`, `Buttons0`
- [ ] Feed one keyboard event and only keyboard skill triggers
- [ ] Feed one mouse event and only mouse skill triggers
- [ ] Feed one gamepad event and only gamepad skill triggers
- Notes / Defect ID:

### MVP-18 Sequence + reset in tracker engine
- [ ] Configure sequence skill (`select_key="F8"`, `skill_key="MOUSE2"`)
- [ ] Skill key alone does not trigger
- [ ] Select then skill triggers once
- [ ] Unrelated event between select and skill resets sequence
- Notes / Defect ID:

### MVP-19 Disabled skill handling
- [ ] Include one disabled and one enabled skill with same key
- [ ] Matching input triggers enabled skill only
- [ ] Disabled sequence skill does not arm while disabled
- Notes / Defect ID:

## Countdown Lifecycle Service

### MVP-20 Retrigger refresh behavior
- [ ] Start timer for a `skill_id`
- [ ] Advance clock and confirm countdown decreases
- [ ] Retrigger same `skill_id`
- [ ] Remaining time resets and active timer count stays at 1
- Notes / Defect ID:

### MVP-21 Completion removal behavior
- [ ] Start short timer
- [ ] Advance time beyond completion and call `emit_updates()`
- [ ] Service emits `REMOVED` event with `completed=True`
- [ ] Timer removed from active state
- Notes / Defect ID:

### MVP-22 Manual remove behavior
- [ ] Start timer and call `remove(skill_id=...)`
- [ ] Removal event emitted
- [ ] Active timer count decremented
- Notes / Defect ID:

### MVP-23 Zero/negative duration handling
- [ ] Refresh with `duration_seconds=0` emits completed removal
- [ ] Refresh with negative duration raises `ValueError`
- Notes / Defect ID:

### MVP-24 Callback/subscriber behavior
- [ ] Subscribe callback function
- [ ] Trigger refresh and update cycle
- [ ] Callback receives update/removal events in order
- [ ] Works without GUI thread dependency
- Notes / Defect ID:

## Final Regression Gate

### MVP-25 Regression checks
- [ ] `pipenv run pytest`
- [ ] `./scripts/pre_ci_core_logic.sh`
- [ ] `pipenv run ruff check .`
- [ ] `pipenv run black --check .`
- Notes / Defect ID:

## Sign-off

- Overall result: PASS / FAIL
- Open defects:
- Follow-ups for next milestone:
- Approved by:

