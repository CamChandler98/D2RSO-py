import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6 import QtCore, QtGui, QtWidgets

from d2rso.input_events import keyboard_event
from d2rso.input_router import GamepadDeviceInfo
from d2rso.key_icon_registry import KeyIconRegistry
from d2rso.main_window import MainWindow
from d2rso.models import (
    DEFAULT_SKILL_DURATION_SECONDS,
    DEFAULT_SKILL_KEY,
    Profile,
    Settings,
    SkillItem,
)
from d2rso.options_dialog import OptionsDialog


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


class _FailingSettingsStore(_MemorySettingsStore):
    def save(self, settings: Settings) -> None:
        raise OSError("disk full")


class _FakeInputRouter:
    def __init__(self, *, on_triggered, on_error) -> None:
        self._on_triggered = on_triggered
        self._on_error = on_error
        self.is_running = False
        self.skill_items: list[SkillItem] = []
        self.stop_count = 0
        self.set_skill_items_history: list[list[SkillItem]] = []

    def set_skill_items(self, skill_items) -> None:
        self.skill_items = list(skill_items)
        self.set_skill_items_history.append(list(self.skill_items))

    def start(self) -> None:
        self.is_running = True

    def stop(self) -> None:
        self.stop_count += 1
        self.is_running = False

    def emit_trigger(self, skill_items: list[SkillItem]) -> None:
        self._on_triggered(keyboard_event("f1"), list(skill_items))


class _FakeSignal:
    def __init__(self) -> None:
        self._callbacks: list = []

    def connect(self, callback) -> None:
        self._callbacks.append(callback)

    def emit(self, *args) -> None:
        for callback in list(self._callbacks):
            callback(*args)


class _FakeTrayIcon:
    def __init__(self, _icon: QtGui.QIcon, _parent: QtWidgets.QWidget | None) -> None:
        self.activated = _FakeSignal()
        self.context_menu: QtWidgets.QMenu | None = None
        self.tooltip = ""
        self.visible = False
        self.hide_count = 0
        self.deleted = False

    def setToolTip(self, text: str) -> None:
        self.tooltip = text

    def setContextMenu(self, menu: QtWidgets.QMenu) -> None:
        self.context_menu = menu

    def show(self) -> None:
        self.visible = True

    def hide(self) -> None:
        self.visible = False
        self.hide_count += 1

    def deleteLater(self) -> None:
        self.deleted = True


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
    *,
    enable_tray: bool = False,
    gamepad_lister=None,
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
        gamepad_lister=gamepad_lister,
        enable_tray=enable_tray,
        tray_icon_factory=_FakeTrayIcon if enable_tray else None,
    )
    window.show()
    _flush_events()
    return window, store, holder["router"]


def _open_options_dialog(window: MainWindow) -> OptionsDialog:
    window.options_button.click()
    _flush_events()
    dialog = window._options_dialog
    assert isinstance(dialog, OptionsDialog)
    return dialog


def _checkbox_from_cell(wrapper: QtWidgets.QWidget) -> QtWidgets.QCheckBox:
    item = wrapper.layout().itemAt(0)
    checkbox = item.widget()
    assert isinstance(checkbox, QtWidgets.QCheckBox)
    return checkbox


def _combo_item_text_for_data(combo: QtWidgets.QComboBox, data: str | None) -> str:
    index = combo.findData(data)
    assert index >= 0
    return combo.itemText(index)


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


def test_last_selected_profile_is_restored_on_window_open():
    settings = Settings(
        last_selected_profile_id=2,
        profiles=[Profile(id=0, name="Default"), Profile(id=2, name="Sorc")],
        skill_items=[
            SkillItem(id=1, profile_id=0, skill_key="F1"),
            SkillItem(id=2, profile_id=2, skill_key="F2"),
        ],
    )
    window, store, _router = _build_window(settings)

    assert window.selected_profile_id() == 2
    assert window.skill_table.rowCount() == 1
    assert store.saved_settings.last_selected_profile_id == 2

    window.close()


def test_add_profile_dialog_creates_and_selects_profile(monkeypatch):
    settings = Settings(
        last_selected_profile_id=0,
        profiles=[Profile(id=0, name="Default")],
    )
    window, store, _router = _build_window(settings)

    monkeypatch.setattr(
        QtWidgets.QInputDialog,
        "getText",
        lambda *args, **kwargs: ("Hammerdin", True),
    )

    window._on_add_profile_clicked()
    _flush_events()

    assert window._current_profile() is not None
    assert window._current_profile().name == "Hammerdin"
    assert window.selected_profile_id() == 1
    assert store.saved_settings.last_selected_profile_id == 1
    assert any(
        profile.id == 1 and profile.name == "Hammerdin"
        for profile in store.saved_settings.profiles
    )

    window.close()


def test_delete_profile_confirmation_gates_removal_and_keeps_neighbor_selected(
    monkeypatch,
):
    settings = Settings(
        last_selected_profile_id=2,
        profiles=[
            Profile(id=0, name="Default"),
            Profile(id=2, name="Sorc"),
            Profile(id=3, name="Necro"),
        ],
        skill_items=[
            SkillItem(id=1, profile_id=0, skill_key="F1"),
            SkillItem(id=2, profile_id=2, skill_key="F2"),
            SkillItem(id=3, profile_id=3, skill_key="F3"),
        ],
    )
    window, store, _router = _build_window(settings)
    prompt: dict[str, str] = {}

    def _decline(*args, **kwargs):
        prompt["title"] = args[1]
        prompt["text"] = args[2]
        return QtWidgets.QMessageBox.StandardButton.No

    monkeypatch.setattr(QtWidgets.QMessageBox, "question", _decline)
    window._on_remove_profile_clicked()
    _flush_events()

    assert "Sorc" in prompt["text"]
    assert "1 skill row" in prompt["text"]
    assert {profile.id for profile in window.settings.profiles} == {0, 2, 3}

    monkeypatch.setattr(
        QtWidgets.QMessageBox,
        "question",
        lambda *args, **kwargs: QtWidgets.QMessageBox.StandardButton.Yes,
    )
    window._on_remove_profile_clicked()
    _flush_events()

    assert {profile.id for profile in window.settings.profiles} == {0, 3}
    assert all(item.profile_id != 2 for item in window.settings.skill_items)
    assert window.selected_profile_id() == 3
    assert window.skill_table.rowCount() == 1
    assert store.saved_settings.last_selected_profile_id == 3

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


def test_add_and_remove_skill_rows_persist_and_refresh_immediately():
    settings = Settings(
        last_selected_profile_id=0,
        profiles=[Profile(id=0, name="Default")],
        skill_items=[],
    )
    window, store, _router = _build_window(settings)

    assert window.skill_table.rowCount() == 0
    assert [
        window.skill_table.horizontalHeaderItem(index).text()
        for index in range(window.skill_table.columnCount())
    ] == ["Enabled", "Icon", "Duration (sec)", "Select Key", "Skill Key", ""]

    window.add_skill_button.click()
    _flush_events()

    assert window.skill_table.rowCount() == 1
    saved = store.saved_settings
    assert len(saved.skill_items) == 1
    added = saved.skill_items[0]
    assert added.profile_id == 0
    assert added.time_length == DEFAULT_SKILL_DURATION_SECONDS
    assert added.skill_key == DEFAULT_SKILL_KEY

    remove_button = window.skill_table.cellWidget(0, 5)
    assert isinstance(remove_button, QtWidgets.QPushButton)
    remove_button.click()
    _flush_events()

    assert window.skill_table.rowCount() == 0
    assert store.saved_settings.skill_items == []

    window.close()


def test_skill_row_validation_normalizes_aliases_and_rejects_invalid_keys():
    settings = Settings(
        last_selected_profile_id=0,
        profiles=[Profile(id=0, name="Default")],
        skill_items=[
            SkillItem(
                id=12,
                profile_id=0,
                select_key="button.right",
                skill_key="f8",
            ),
            SkillItem(
                id=13,
                profile_id=0,
                select_key="not-a-key",
                skill_key="still-not-a-key",
            ),
        ],
    )
    window, store, _router = _build_window(settings)

    select_combo = window.skill_table.cellWidget(0, 3)
    assert isinstance(select_combo, QtWidgets.QComboBox)
    assert select_combo.currentData() == "MOUSE2"

    use_combo = window.skill_table.cellWidget(0, 4)
    assert isinstance(use_combo, QtWidgets.QComboBox)
    assert use_combo.currentData() == "F8"

    invalid_select_combo = window.skill_table.cellWidget(1, 3)
    assert isinstance(invalid_select_combo, QtWidgets.QComboBox)
    assert invalid_select_combo.currentData() is None

    invalid_use_combo = window.skill_table.cellWidget(1, 4)
    assert isinstance(invalid_use_combo, QtWidgets.QComboBox)
    assert invalid_use_combo.currentData() is None

    window._update_skill_value(12, "select_key", "GamePad Button 7")
    window._update_skill_value(12, "skill_key", "not-a-real-key")
    window._update_skill_value(12, "time_length", -4.26)
    _flush_events()

    saved = store.saved_settings
    item = next(skill for skill in saved.skill_items if skill.id == 12)
    assert item.select_key == "Buttons7"
    assert item.skill_key is None
    assert item.time_length == 0.0

    window.close()


def test_key_combos_show_connected_single_controller_button_labels():
    settings = Settings(
        last_selected_profile_id=0,
        profiles=[Profile(id=0, name="Default")],
        skill_items=[
            SkillItem(
                id=14,
                profile_id=0,
                select_key="Buttons1",
                skill_key="Buttons3",
            )
        ],
    )
    window, _store, _router = _build_window(
        settings,
        gamepad_lister=lambda: (
            GamepadDeviceInfo(
                index=0,
                name="8BitDo Pro 2",
                button_count=4,
            ),
        ),
    )

    select_combo = window.skill_table.cellWidget(0, 3)
    assert isinstance(select_combo, QtWidgets.QComboBox)
    assert (
        _combo_item_text_for_data(select_combo, "Buttons0") == "8BitDo Pro 2: Button 0"
    )
    assert (
        _combo_item_text_for_data(select_combo, "Buttons3") == "8BitDo Pro 2: Button 3"
    )
    assert select_combo.findData("Buttons4") == -1
    assert "Detected controller: 8BitDo Pro 2 (4 buttons)." in select_combo.toolTip()

    use_combo = window.skill_table.cellWidget(0, 4)
    assert isinstance(use_combo, QtWidgets.QComboBox)
    assert use_combo.currentData() == "Buttons3"
    assert _combo_item_text_for_data(use_combo, "Buttons3") == "8BitDo Pro 2: Button 3"

    window.close()


def test_saved_gamepad_binding_is_preserved_when_controller_reports_fewer_buttons():
    settings = Settings(
        last_selected_profile_id=0,
        profiles=[Profile(id=0, name="Default")],
        skill_items=[
            SkillItem(
                id=15,
                profile_id=0,
                select_key="Buttons7",
                skill_key="Buttons12",
            )
        ],
    )
    window, _store, _router = _build_window(
        settings,
        gamepad_lister=lambda: (
            GamepadDeviceInfo(
                index=0,
                name="Xbox Wireless Controller",
                button_count=4,
            ),
        ),
    )

    select_combo = window.skill_table.cellWidget(0, 3)
    assert isinstance(select_combo, QtWidgets.QComboBox)
    assert select_combo.currentData() == "Buttons7"
    assert (
        _combo_item_text_for_data(select_combo, "Buttons7")
        == "GamePad Button 7 (saved)"
    )

    use_combo = window.skill_table.cellWidget(0, 4)
    assert isinstance(use_combo, QtWidgets.QComboBox)
    assert use_combo.currentData() == "Buttons12"
    assert (
        _combo_item_text_for_data(use_combo, "Buttons12") == "GamePad Button 12 (saved)"
    )

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
    assert window.options_button.isEnabled() is True
    assert window.profile_combo.isEnabled() is False
    assert window.skill_table.isEnabled() is False
    assert window.status_label.text() == "Running"

    router.emit_trigger(window.selected_skill_items())
    _flush_events()
    assert window._tracker_runtime.countdown_service is not None
    assert window._tracker_runtime.countdown_service.active_count == 1

    window._toggle_playback()
    _flush_events()
    assert router.is_running is False
    assert window.is_playing is False
    assert window.play_button.text() == "Play"
    assert window.preview_button.isEnabled() is True
    assert window.profile_combo.isEnabled() is True
    assert window._tracker_runtime.countdown_service is None
    assert router.set_skill_items_history[-1] == []

    window.close()


def test_runtime_controls_cover_play_stop_preview_acceptance_flow():
    settings = Settings(
        last_selected_profile_id=0,
        profiles=[Profile(id=0, name="Default")],
        skill_items=[SkillItem(id=61, profile_id=0, skill_key="F1", time_length=4.0)],
    )
    window, _store, router = _build_window(settings)

    assert window.status_label.text() == "Idle"
    assert window.play_button.text() == "Play"
    assert window.preview_button.text() == "Preview"
    assert window.preview_button.isEnabled() is True

    window._toggle_preview()
    _flush_events()
    assert window.is_preview_visible is True
    assert window._preview_overlay is not None
    assert window.status_label.text() == "Previewing"
    assert window.preview_button.text() == "Hide Preview"

    window._toggle_playback()
    _flush_events()
    assert router.is_running is True
    assert window.is_playing is True
    assert window._runtime_overlay is not None
    assert window._preview_overlay is None
    assert window.play_button.text() == "Stop"
    assert window.preview_button.isEnabled() is False
    assert window.status_label.text() == "Running"

    window._toggle_playback()
    _flush_events()
    assert router.is_running is False
    assert router.stop_count == 1
    assert window.is_playing is False
    assert window._runtime_overlay is None
    assert window.preview_button.isEnabled() is True
    assert window.play_button.text() == "Play"
    assert window.status_label.text() == "Idle"

    window._toggle_preview()
    _flush_events()
    assert window.is_preview_visible is True
    assert window.status_label.text() == "Previewing"

    window.close()


def test_options_dialog_saves_settings_and_updates_preview_overlay():
    settings = Settings(
        show_digits_in_tracker=False,
        red_overlay_seconds=0,
        form_scale_x=1.0,
        form_scale_y=1.0,
        is_tracker_insert_to_left=False,
        is_tracker_vertical=False,
        start_tracker_on_app_run=False,
        minimize_to_tray=False,
        last_selected_profile_id=0,
        profiles=[Profile(id=0, name="Default")],
        skill_items=[
            SkillItem(id=31, profile_id=0, skill_key="F1", time_length=4.0),
            SkillItem(id=32, profile_id=0, skill_key="F2", time_length=2.0),
        ],
    )
    window, store, _router = _build_window(settings)
    window._toggle_preview()
    _flush_events()

    assert window._preview_overlay is not None
    before_icon_size = window._preview_overlay._widgets_by_skill_id[
        31
    ]._icon_label.size()

    dialog = _open_options_dialog(window)

    dialog.insert_left_checkbox.setChecked(True)
    dialog.vertical_checkbox.setChecked(True)
    dialog.show_digits_checkbox.setChecked(True)
    dialog.start_on_launch_checkbox.setChecked(True)
    dialog.minimize_to_tray_checkbox.setChecked(True)
    dialog.scale_slider.setValue(150)
    dialog.red_overlay_seconds_spin.setValue(3)
    _flush_events()

    assert window._preview_overlay is not None
    assert window._preview_overlay.active_skill_ids() == [32, 31]
    assert (
        window._preview_overlay._items_layout.direction()
        == QtWidgets.QBoxLayout.Direction.TopToBottom
    )
    snapshots = window._preview_overlay.snapshot_active_trackers()
    assert [snapshot.skill_id for snapshot in snapshots] == [32, 31]
    assert all(snapshot.digits_visible is True for snapshot in snapshots)
    assert snapshots[0].warning_active is True
    after_icon_size = window._preview_overlay._widgets_by_skill_id[
        31
    ]._icon_label.size()
    assert after_icon_size.width() > before_icon_size.width()

    saved = store.saved_settings
    assert saved.is_tracker_insert_to_left is True
    assert saved.is_tracker_vertical is True
    assert saved.show_digits_in_tracker is True
    assert saved.start_tracker_on_app_run is True
    assert saved.minimize_to_tray is True
    assert saved.form_scale_x == 1.5
    assert saved.form_scale_y == 1.5
    assert saved.red_overlay_seconds == 3
    assert saved.red_tracker_overlay_sec == 3

    window.close()


def test_options_dialog_updates_runtime_overlay_behavior_live():
    settings = Settings(
        show_digits_in_tracker=True,
        red_overlay_seconds=0,
        form_scale_x=1.0,
        form_scale_y=1.0,
        is_tracker_insert_to_left=False,
        is_tracker_vertical=False,
        last_selected_profile_id=0,
        profiles=[Profile(id=0, name="Default")],
        skill_items=[
            SkillItem(id=51, profile_id=0, skill_key="F1", time_length=2.0),
            SkillItem(id=52, profile_id=0, skill_key="F2", time_length=4.0),
        ],
    )
    window, _store, router = _build_window(settings)

    window._toggle_playback()
    _flush_events()
    router.emit_trigger(window.selected_skill_items())
    _flush_events()

    assert window._runtime_overlay is not None
    before_icon_size = window._runtime_overlay._widgets_by_skill_id[
        51
    ]._icon_label.size()

    dialog = _open_options_dialog(window)
    dialog.insert_left_checkbox.setChecked(True)
    dialog.vertical_checkbox.setChecked(True)
    dialog.show_digits_checkbox.setChecked(False)
    dialog.scale_slider.setValue(140)
    dialog.red_overlay_seconds_spin.setValue(3)
    _flush_events()

    assert window._runtime_overlay is not None
    assert window._runtime_overlay.active_skill_ids() == [52, 51]
    assert (
        window._runtime_overlay._items_layout.direction()
        == QtWidgets.QBoxLayout.Direction.TopToBottom
    )
    snapshots = window._runtime_overlay.snapshot_active_trackers()
    assert [snapshot.skill_id for snapshot in snapshots] == [52, 51]
    assert all(snapshot.digits_visible is False for snapshot in snapshots)
    assert snapshots[1].warning_active is True
    after_icon_size = window._runtime_overlay._widgets_by_skill_id[
        51
    ]._icon_label.size()
    assert after_icon_size.width() > before_icon_size.width()

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


def test_start_tracker_on_app_run_autostarts_runtime_on_window_open():
    settings = Settings(
        start_tracker_on_app_run=True,
        last_selected_profile_id=0,
        profiles=[Profile(id=0, name="Default")],
        skill_items=[SkillItem(id=71, profile_id=0, skill_key="F1", time_length=4.0)],
    )
    window, _store, router = _build_window(settings)

    assert router.is_running is True
    assert window.is_playing is True
    assert window._runtime_overlay is not None
    assert window.play_button.text() == "Stop"
    assert window.preview_button.isEnabled() is False
    assert window.status_label.text() == "Running"

    window.close()


def test_stop_detaches_runtime_and_ignores_late_router_triggers():
    settings = Settings(
        show_digits_in_tracker=True,
        last_selected_profile_id=0,
        profiles=[Profile(id=0, name="Default")],
        skill_items=[SkillItem(id=41, profile_id=0, skill_key="F1", time_length=4.0)],
    )
    window, _store, router = _build_window(settings)

    window._toggle_playback()
    _flush_events()
    assert window._runtime_overlay is not None

    window._toggle_playback()
    _flush_events()
    assert window._runtime_overlay is None
    assert window._tracker_runtime.countdown_service is None

    router.emit_trigger(window.selected_skill_items())
    _flush_events()

    assert window._runtime_overlay is None
    assert window._tracker_runtime.countdown_service is None

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


def test_close_hides_window_to_tray_and_tray_action_reopens_it():
    settings = Settings(
        last_selected_profile_id=0,
        profiles=[Profile(id=0, name="Default")],
        skill_items=[SkillItem(id=81, profile_id=0, skill_key="F1", time_length=4.0)],
    )
    window, _store, _router = _build_window(settings, enable_tray=True)

    assert isinstance(window._tray_icon, _FakeTrayIcon)
    assert window._tray_toggle_action is not None
    assert window._tray_toggle_action.text() == "Hide"

    window._toggle_preview()
    _flush_events()
    assert window.is_preview_visible is True

    window.close()
    _flush_events()

    assert window.isVisible() is False
    assert window.is_preview_visible is False
    assert window._tray_toggle_action.text() == "Open"

    window._tray_toggle_action.trigger()
    _flush_events()

    assert window.isVisible() is True
    assert window._tray_toggle_action.text() == "Hide"

    window.exit_to_desktop()
    _flush_events()


def test_tray_exit_performs_clean_shutdown_and_saves_runtime_position():
    settings = Settings(
        last_selected_profile_id=0,
        profiles=[Profile(id=0, name="Default")],
        skill_items=[SkillItem(id=82, profile_id=0, skill_key="F1", time_length=4.0)],
    )
    window, store, router = _build_window(settings, enable_tray=True)

    window._toggle_playback()
    _flush_events()
    assert window._runtime_overlay is not None

    window._runtime_overlay.move(123, 456)
    _flush_events()
    tray_icon = window._tray_icon
    assert isinstance(tray_icon, _FakeTrayIcon)
    assert window._tray_exit_action is not None

    window.close()
    _flush_events()
    assert window.isVisible() is False
    assert router.is_running is True

    window._tray_exit_action.trigger()
    _flush_events()

    assert router.is_running is False
    assert router.stop_count == 1
    assert tray_icon.deleted is True
    saved = store.saved_settings
    assert saved.tracker_x == 123
    assert saved.tracker_y == 456


def test_tray_can_be_disabled_by_environment(monkeypatch):
    _get_qapp()
    monkeypatch.setenv("D2RSO_DISABLE_TRAY", "1")
    monkeypatch.setattr(
        QtWidgets.QSystemTrayIcon,
        "isSystemTrayAvailable",
        staticmethod(lambda: True),
    )

    settings = Settings(
        last_selected_profile_id=0,
        profiles=[Profile(id=0, name="Default")],
    )
    store = _MemorySettingsStore(settings)

    window = MainWindow(
        settings_store=store,
        settings=settings,
        icon_registry=KeyIconRegistry(assets_dir="does-not-exist"),
        input_router_factory=lambda **kwargs: _FakeInputRouter(**kwargs),
        enable_tray=None,
        tray_icon_factory=_FakeTrayIcon,
    )
    window.show()
    _flush_events()

    assert window._tray_icon is None

    window.close()


def test_save_failures_surface_in_status_label():
    _get_qapp()
    settings = Settings(
        last_selected_profile_id=0,
        profiles=[Profile(id=0, name="Default")],
    )
    window = MainWindow(
        settings_store=_FailingSettingsStore(settings),
        settings=settings,
        icon_registry=KeyIconRegistry(assets_dir="does-not-exist"),
        input_router_factory=lambda **kwargs: _FakeInputRouter(**kwargs),
    )
    window.show()
    _flush_events()

    assert window.status_label.text() == "Idle"
    window.add_profile("Offline")
    _flush_events()

    assert "Save failed: disk full" in window.status_label.text()

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
