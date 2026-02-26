import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6 import QtCore, QtGui, QtWidgets

from d2rso.input_events import keyboard_event
from d2rso.key_icon_registry import KeyIconRegistry
from d2rso.main_window import MainWindow
from d2rso.models import Profile, Settings, SkillItem


class _MemorySettingsStore:
    def __init__(self, settings: Settings) -> None:
        self._payload = settings.to_dict()

    def load(self) -> Settings:
        return Settings.from_dict(self._payload)

    def save(self, settings: Settings) -> None:
        self._payload = settings.to_dict()

    @property
    def saved_settings(self) -> Settings:
        return Settings.from_dict(self._payload)


class _FakeInputRouter:
    def __init__(self, *, on_triggered, on_error) -> None:
        self._on_triggered = on_triggered
        self._on_error = on_error
        self.is_running = False
        self.skill_items: list[SkillItem] = []

    def set_skill_items(self, skill_items) -> None:
        self.skill_items = list(skill_items)

    def start(self) -> None:
        self.is_running = True

    def stop(self) -> None:
        self.is_running = False

    def emit_trigger(self, skill_items: list[SkillItem]) -> None:
        self._on_triggered(keyboard_event("f1"), list(skill_items))


def _get_qapp() -> QtWidgets.QApplication:
    app = QtWidgets.QApplication.instance()
    if app is None:
        app = QtWidgets.QApplication(["pytest", "-platform", "offscreen"])
    return app


def _flush_events() -> None:
    app = _get_qapp()
    for _ in range(4):
        app.processEvents(
            QtCore.QEventLoop.ProcessEventsFlag.AllEvents,
            50,
        )


def _build_window(
    settings: Settings,
) -> tuple[MainWindow, _MemorySettingsStore, _FakeInputRouter]:
    _get_qapp()
    store = _MemorySettingsStore(settings)
    holder: dict[str, _FakeInputRouter] = {}

    def _router_factory(*, on_triggered, on_error):
        router = _FakeInputRouter(on_triggered=on_triggered, on_error=on_error)
        holder["router"] = router
        return router

    window = MainWindow(
        settings_store=store,
        icon_registry=KeyIconRegistry(assets_dir="does-not-exist"),
        input_router_factory=_router_factory,
    )
    window.show()
    _flush_events()
    return window, store, holder["router"]


def _checkbox_from_cell(wrapper: QtWidgets.QWidget) -> QtWidgets.QCheckBox:
    item = wrapper.layout().itemAt(0)
    checkbox = item.widget()
    assert isinstance(checkbox, QtWidgets.QCheckBox)
    return checkbox


def test_profiles_crud_and_switching_persist_cleanly():
    settings = Settings(
        last_selected_profile_id=0,
        profiles=[Profile(id=0, name="Default"), Profile(id=2, name="Sorc")],
        skill_items=[
            SkillItem(id=1, profile_id=0, skill_key="F1"),
            SkillItem(id=2, profile_id=2, skill_key="F2"),
        ],
    )
    window, store, _router = _build_window(settings)

    created = window.add_profile("Test Profile")
    assert created is not None
    assert created.name == "Test Profile"

    assert window.rename_current_profile("Renamed Profile") is True
    assert window._current_profile() is not None
    assert window._current_profile().name == "Renamed Profile"

    sorc_index = window.profile_combo.findData(2)
    assert sorc_index >= 0
    window.profile_combo.setCurrentIndex(sorc_index)
    _flush_events()

    assert window.selected_profile_id() == 2
    assert window.skill_table.rowCount() == 1
    assert store.saved_settings.last_selected_profile_id == 2

    assert window.remove_current_profile() is True
    remaining_ids = {profile.id for profile in window.settings.profiles}
    assert 2 not in remaining_ids
    assert all(item.profile_id != 2 for item in window.settings.skill_items)

    window.close()


def test_skill_row_changes_save_back_to_settings_store():
    settings = Settings(
        last_selected_profile_id=0,
        profiles=[Profile(id=0, name="Default")],
        skill_items=[
            SkillItem(
                id=10,
                profile_id=0,
                icon_file_name="",
                time_length=5.0,
                is_enabled=True,
                select_key=None,
                skill_key="F1",
            )
        ],
    )
    window, store, _router = _build_window(settings)
    assert window.skill_table.rowCount() == 1

    enabled_wrapper = window.skill_table.cellWidget(0, 0)
    enabled_checkbox = _checkbox_from_cell(enabled_wrapper)
    enabled_checkbox.setChecked(False)

    duration_spin = window.skill_table.cellWidget(0, 2)
    assert isinstance(duration_spin, QtWidgets.QDoubleSpinBox)
    duration_spin.setValue(9.5)

    select_combo = window.skill_table.cellWidget(0, 3)
    assert isinstance(select_combo, QtWidgets.QComboBox)
    select_combo.setCurrentIndex(select_combo.findData("F8"))

    use_combo = window.skill_table.cellWidget(0, 4)
    assert isinstance(use_combo, QtWidgets.QComboBox)
    use_combo.setCurrentIndex(use_combo.findData("MOUSE2"))
    _flush_events()

    saved = store.saved_settings
    item = next(skill for skill in saved.skill_items if skill.id == 10)
    assert item.is_enabled is False
    assert item.time_length == 9.5
    assert item.select_key == "F8"
    assert item.skill_key == "MOUSE2"

    window.close()


def test_play_stop_and_preview_buttons_reflect_runtime_state():
    settings = Settings(
        last_selected_profile_id=0,
        profiles=[Profile(id=0, name="Default")],
        skill_items=[SkillItem(id=11, profile_id=0, skill_key="F1", time_length=4.0)],
    )
    window, _store, router = _build_window(settings)

    assert window.is_playing is False
    assert window.is_preview_visible is False
    assert window.play_button.text() == "Play"

    window._toggle_preview()
    _flush_events()
    assert window.is_preview_visible is True
    assert window.preview_button.text() == "Hide Preview"

    window._toggle_playback()
    _flush_events()
    assert router.is_running is True
    assert window.is_playing is True
    assert window.is_preview_visible is False
    assert window.play_button.text() == "Stop"
    assert window.preview_button.isEnabled() is False
    assert window.show_digits_checkbox.isEnabled() is True
    assert window.red_overlay_seconds_spin.isEnabled() is True
    assert window.profile_combo.isEnabled() is False
    assert window.skill_table.isEnabled() is False
    assert window.status_label.text() == "Running"

    router.emit_trigger(window.selected_skill_items())
    _flush_events()
    assert window._countdown_service is not None
    assert window._countdown_service.active_count == 1

    window._toggle_playback()
    _flush_events()
    assert router.is_running is False
    assert window.is_playing is False
    assert window.play_button.text() == "Play"
    assert window.preview_button.isEnabled() is True
    assert window.profile_combo.isEnabled() is True

    window.close()


def test_overlay_option_controls_save_back_to_settings_store():
    settings = Settings(
        show_digits_in_tracker=False,
        red_overlay_seconds=0,
        last_selected_profile_id=0,
        profiles=[Profile(id=0, name="Default")],
        skill_items=[SkillItem(id=31, profile_id=0, skill_key="F1", time_length=4.0)],
    )
    window, store, _router = _build_window(settings)

    assert window.show_digits_checkbox.isChecked() is False
    assert window.red_overlay_seconds_spin.value() == 0

    window.show_digits_checkbox.setChecked(True)
    window.red_overlay_seconds_spin.setValue(3)
    _flush_events()

    saved = store.saved_settings
    assert saved.show_digits_in_tracker is True
    assert saved.red_overlay_seconds == 3
    assert saved.red_tracker_overlay_sec == 3

    window.close()


def test_runtime_overlay_receives_triggered_skill_updates():
    settings = Settings(
        show_digits_in_tracker=True,
        last_selected_profile_id=0,
        profiles=[Profile(id=0, name="Default")],
        skill_items=[SkillItem(id=21, profile_id=0, skill_key="F1", time_length=4.0)],
    )
    window, _store, router = _build_window(settings)

    window._toggle_playback()
    _flush_events()
    assert window.is_playing is True
    assert window._runtime_overlay is not None

    router.emit_trigger(window.selected_skill_items())
    _flush_events()
    snapshots = window._runtime_overlay.snapshot_active_trackers()
    assert [snapshot.skill_id for snapshot in snapshots] == [21]
    assert snapshots[0].digits_visible is True
    assert snapshots[0].digits_text == "4"

    window.close()


def test_preview_reposition_updates_saved_tracker_coordinates():
    settings = Settings(
        tracker_x=5,
        tracker_y=9,
        last_selected_profile_id=0,
        profiles=[Profile(id=0, name="Default")],
        skill_items=[SkillItem(id=22, profile_id=0, skill_key="F1", time_length=4.0)],
    )
    window, store, _router = _build_window(settings)

    window._toggle_preview()
    _flush_events()
    assert window._preview_overlay is not None

    window._preview_overlay.move(210, 330)
    _flush_events()

    assert window.settings.tracker_x == 210
    assert window.settings.tracker_y == 330

    window._toggle_preview()
    _flush_events()

    saved = store.saved_settings
    assert saved.tracker_x == 210
    assert saved.tracker_y == 330

    window.close()


def test_close_event_tolerates_keyboard_interrupt_during_shutdown(monkeypatch):
    settings = Settings(
        last_selected_profile_id=0,
        profiles=[Profile(id=0, name="Default")],
        skill_items=[SkillItem(id=30, profile_id=0, skill_key="F1", time_length=4.0)],
    )
    window, _store, _router = _build_window(settings)

    def _raise_keyboard_interrupt() -> None:
        raise KeyboardInterrupt

    monkeypatch.setattr(window, "_stop_tracking", _raise_keyboard_interrupt)
    event = QtGui.QCloseEvent()
    window.closeEvent(event)
    assert event.isAccepted() is True

    window.close()
