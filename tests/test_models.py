from d2rso.models import SkillItem


def test_select_then_skill_sequence_works():
    item = SkillItem(select_key="F8", skill_key="MOUSE2")

    assert item.skill_key_pressed() is False
    item.select_key_pressed()
    assert item.skill_key_pressed() is True
    assert item.skill_key_pressed() is False


def test_skill_only_works_when_select_key_is_unset():
    item = SkillItem(select_key=None, skill_key="MOUSE2")

    assert item.skill_key_pressed() is True
    assert item.skill_key_pressed() is True


def test_reset_clears_partial_sequence():
    item = SkillItem(select_key="F8", skill_key="MOUSE2")

    item.select_key_pressed()
    item.reset_keys()

    assert item.skill_key_pressed() is False
