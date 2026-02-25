import json

from d2rso.models import Profile, Settings, SkillItem
from d2rso.settings_store import SettingsStore


def test_save_then_load_round_trip(tmp_path):
    file_path = tmp_path / "settings.json"
    store = SettingsStore(file_path=file_path)
    original = Settings(
        last_selected_profile_id=2,
        profiles=[Profile(id=0, name="Default"), Profile(id=2, name="Sorc")],
        skill_items=[
            SkillItem(
                id=11,
                profile_id=2,
                icon_file_name="orb.png",
                time_length=7.5,
                is_enabled=True,
                select_key="F8",
                skill_key="MOUSE2",
            ),
            SkillItem(
                id=12,
                profile_id=0,
                icon_file_name="buff.png",
                time_length=3.0,
                is_enabled=False,
                select_key=None,
                skill_key="F1",
            ),
        ],
        tracker_x=150,
        tracker_y=250,
        form_scale_x=1.2,
        form_scale_y=1.1,
        is_tracker_insert_to_left=True,
        is_tracker_vertical=True,
        show_digits_in_tracker=True,
        red_tracker_overlay_sec=2,
        start_tracker_on_app_run=True,
    )

    store.save(original)
    loaded = SettingsStore(file_path=file_path).load()

    assert loaded.to_dict() == original.to_dict()


def test_missing_settings_file_returns_defaults(tmp_path):
    store = SettingsStore(file_path=tmp_path / "missing.json")

    loaded = store.load()

    assert len(loaded.profiles) == 1
    assert loaded.profiles[0].name == "Default"
    assert loaded.last_selected_profile_id == loaded.profiles[0].id


def test_corrupt_json_file_falls_back_to_defaults(tmp_path):
    file_path = tmp_path / "settings.json"
    file_path.write_text("{ bad json", encoding="utf-8")
    store = SettingsStore(file_path=file_path)

    loaded = store.load()

    assert len(loaded.profiles) == 1
    assert loaded.profiles[0].name == "Default"
    assert loaded.skill_items == []


def test_default_profile_is_created_when_missing(tmp_path):
    file_path = tmp_path / "settings.json"
    file_path.write_text(
        json.dumps(
            {
                "last_selected_profile_id": 999,
                "profiles": [],
                "skill_items": [],
            }
        ),
        encoding="utf-8",
    )
    store = SettingsStore(file_path=file_path)

    loaded = store.load()

    assert len(loaded.profiles) == 1
    assert loaded.profiles[0].id == 0
    assert loaded.profiles[0].name == "Default"
    assert loaded.last_selected_profile_id == 0


def test_default_profile_is_added_when_missing_from_non_empty_profiles(tmp_path):
    file_path = tmp_path / "settings.json"
    file_path.write_text(
        json.dumps(
            {
                "last_selected_profile_id": 5,
                "profiles": [{"id": 5, "name": "Sorc"}],
                "skill_items": [],
            }
        ),
        encoding="utf-8",
    )
    store = SettingsStore(file_path=file_path)

    loaded = store.load()

    profile_ids = {profile.id for profile in loaded.profiles}
    assert 0 in profile_ids
    assert 5 in profile_ids
    assert loaded.last_selected_profile_id == 5


def test_legacy_csharp_json_shape_is_supported(tmp_path):
    file_path = tmp_path / "settings.json"
    file_path.write_text(
        json.dumps(
            {
                "LastSelectedProfileId": 5,
                "Profiles": [{"Id": 5, "Name": "Legacy"}],
                "SkillItems": [
                    {
                        "Id": 42,
                        "ProfileId": 5,
                        "IconFileName": "legacy.png",
                        "TimeLength": 8,
                        "IsEnabled": True,
                        "SelectKey": {"Name": "F8", "Code": "F8"},
                        "SkillKey": {"Name": "MOUSE2", "Code": "MOUSE2"},
                    }
                ],
                "TrackerX": 22,
                "TrackerY": 44,
                "FormScaleX": 1.3,
                "FormScaleY": 1.2,
                "IsTrackerInsertToLeft": True,
                "IsTrackerVertical": False,
                "ShowDigitsInTracker": True,
                "RedTrackerOverlaySec": 3,
                "StartTrackerOnAppRun": True,
            }
        ),
        encoding="utf-8",
    )
    store = SettingsStore(file_path=file_path)

    loaded = store.load()

    assert loaded.last_selected_profile_id == 5
    assert any(
        profile.id == 5 and profile.name == "Legacy" for profile in loaded.profiles
    )
    assert loaded.skill_items[0].id == 42
    assert loaded.skill_items[0].select_key == "F8"
    assert loaded.skill_items[0].skill_key == "MOUSE2"
    assert loaded.tracker_x == 22
    assert loaded.red_tracker_overlay_sec == 3
