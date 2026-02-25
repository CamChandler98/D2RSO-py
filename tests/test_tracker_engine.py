from d2rso.input_events import gamepad_event, keyboard_event, mouse_event
from d2rso.models import SkillItem
from d2rso.tracker_engine import TrackerInputEngine


def test_tracker_engine_consumes_unified_input_event_contract():
    engine = TrackerInputEngine(
        skill_items=[
            SkillItem(id=1, select_key=None, skill_key="F1"),
            SkillItem(id=2, select_key=None, skill_key="MOUSE2"),
            SkillItem(id=3, select_key=None, skill_key="Buttons0"),
        ]
    )

    assert [item.id for item in engine.process_event(keyboard_event("f1"))] == [1]
    assert [item.id for item in engine.process_event(mouse_event("right"))] == [2]
    assert [item.id for item in engine.process_event(gamepad_event(0))] == [3]


def test_tracker_engine_preserves_select_then_skill_sequence():
    skill = SkillItem(id=10, select_key="F8", skill_key="MOUSE2")
    engine = TrackerInputEngine(skill_items=[skill])

    assert engine.process_event(mouse_event("right")) == []
    assert engine.process_event(keyboard_event("f8")) == []
    assert [item.id for item in engine.process_event(mouse_event("right"))] == [10]
    assert engine.process_event(mouse_event("right")) == []


def test_unmatched_input_resets_partial_sequence_state():
    skill = SkillItem(id=11, select_key="F8", skill_key="MOUSE2")
    engine = TrackerInputEngine(skill_items=[skill])

    assert engine.process_event(keyboard_event("f8")) == []
    assert engine.process_event(keyboard_event("f1")) == []
    assert engine.process_event(mouse_event("right")) == []


def test_legacy_gamepad_label_matches_normalized_button_code():
    engine = TrackerInputEngine(
        skill_items=[SkillItem(id=12, select_key=None, skill_key="GamePad Button 0")]
    )

    assert [item.id for item in engine.process_event(gamepad_event("buttons0"))] == [12]


def test_disabled_skill_is_ignored_when_matching_skill_key():
    disabled = SkillItem(id=20, is_enabled=False, select_key=None, skill_key="F1")
    enabled = SkillItem(id=21, is_enabled=True, select_key=None, skill_key="F1")
    engine = TrackerInputEngine(skill_items=[disabled, enabled])

    assert [item.id for item in engine.process_event(keyboard_event("f1"))] == [21]


def test_disabled_sequence_skill_does_not_capture_select_state_until_reenabled():
    skill = SkillItem(id=22, is_enabled=False, select_key="F8", skill_key="MOUSE2")
    engine = TrackerInputEngine(skill_items=[skill])

    # Edge case: while disabled, select input should not arm the sequence state.
    assert engine.process_event(keyboard_event("f8")) == []

    skill.is_enabled = True
    assert engine.process_event(mouse_event("right")) == []
    assert engine.process_event(keyboard_event("f8")) == []
    assert [item.id for item in engine.process_event(mouse_event("right"))] == [22]
