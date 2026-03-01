from d2rso.models import SkillItem


def test_select_hold_enables_skill_while_held():
    item = SkillItem(select_key="F8", skill_key="MOUSE2")

    assert item.skill_key_pressed() is False
    item.select_key_pressed()
    assert item.skill_key_pressed() is True
    assert item.skill_key_pressed() is True


def test_select_release_disarms_skill_combo():
    item = SkillItem(select_key="F8", skill_key="MOUSE2")

    item.select_key_pressed()
    item.select_key_released()

    assert item.skill_key_pressed() is False


def test_skill_only_works_when_select_key_is_unset():
    item = SkillItem(select_key=None, skill_key="MOUSE2")

    assert item.skill_key_pressed() is True
    assert item.skill_key_pressed() is True


def test_reset_clears_held_select_state():
    item = SkillItem(select_key="F8", skill_key="MOUSE2")

    item.select_key_pressed()
    item.reset_keys()

    assert item.skill_key_pressed() is False


def test_repeated_select_presses_keep_skill_armed():
    item = SkillItem(select_key="F8", skill_key="MOUSE2")

    item.select_key_pressed()
    item.select_key_pressed()

    assert item.skill_key_pressed() is True
    assert item.skill_key_pressed() is True


def test_combo_skill_press_without_select_never_triggers():
    item = SkillItem(select_key="F8", skill_key="MOUSE2")

    assert item.skill_key_pressed() is False
    assert item.skill_key_pressed() is False
