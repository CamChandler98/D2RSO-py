import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6 import QtCore, QtGui, QtWidgets

import d2rso.overlay_window as overlay_window_module
from d2rso.countdown_service import CountdownService
from d2rso.key_icon_registry import KeyIconRegistry
from d2rso.models import Settings, SkillItem
from d2rso.overlay_window import CooldownOverlayWindow, format_remaining_seconds

_PNG_1X1 = bytes.fromhex(
    "89504E470D0A1A0A0000000D4948445200000001000000010804000000B51C0C02"
    "0000000B4944415478DA63FCFF1F0003030200EF9C13470000000049454E44AE426082"
)


class FakeClock:
    def __init__(self, start: float = 0.0) -> None:
        self.now = start

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


def _get_qapp() -> QtWidgets.QApplication:
    app = QtWidgets.QApplication.instance()
    if app is None:
        app = QtWidgets.QApplication(["pytest", "-platform", "offscreen"])
    return app


def _flush_qt_events() -> None:
    app = _get_qapp()
    for _ in range(4):
        app.processEvents(
            QtCore.QEventLoop.ProcessEventsFlag.AllEvents,
            50,
        )


def test_format_remaining_seconds_rounds_up_to_match_countdown_style():
    assert format_remaining_seconds(5.0) == "5"
    assert format_remaining_seconds(4.01) == "5"
    assert format_remaining_seconds(0.1) == "1"
    assert format_remaining_seconds(0.0) == "0"


def test_overlay_window_uses_frameless_topmost_translucent_flags():
    _get_qapp()
    overlay = CooldownOverlayWindow(
        settings=Settings(),
        icon_registry=KeyIconRegistry(assets_dir="does-not-exist"),
    )
    flags = overlay.windowFlags()

    assert bool(flags & QtCore.Qt.WindowType.FramelessWindowHint)
    assert bool(flags & QtCore.Qt.WindowType.WindowStaysOnTopHint)
    assert bool(flags & QtCore.Qt.WindowType.Tool)
    assert overlay.testAttribute(QtCore.Qt.WidgetAttribute.WA_TranslucentBackground)
    assert overlay.testAttribute(QtCore.Qt.WidgetAttribute.WA_ShowWithoutActivating)
    assert overlay.testAttribute(QtCore.Qt.WidgetAttribute.WA_TransparentForMouseEvents)

    overlay.close()


def test_overlay_preview_mode_accepts_mouse_events_for_dragging():
    _get_qapp()
    overlay = CooldownOverlayWindow(
        settings=Settings(),
        icon_registry=KeyIconRegistry(assets_dir="does-not-exist"),
        preview_mode=True,
    )

    assert (
        overlay.testAttribute(QtCore.Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        is False
    )

    overlay.close()


def test_apply_win32_click_through_toggles_extended_style_flags(monkeypatch):
    class _FakeUser32:
        def __init__(self) -> None:
            self.style = 0
            self.set_style_calls: list[tuple[int, int, int]] = []
            self.set_pos_calls: list[tuple[int, int, int, int, int, int, int]] = []

        def GetWindowLongPtrW(self, hwnd: int, index: int) -> int:
            assert index == overlay_window_module._GWL_EXSTYLE
            return self.style

        def SetWindowLongPtrW(self, hwnd: int, index: int, style: int) -> int:
            self.set_style_calls.append((hwnd, index, style))
            self.style = int(style)
            return self.style

        def SetWindowPos(
            self,
            hwnd: int,
            hwnd_insert_after: int,
            x: int,
            y: int,
            cx: int,
            cy: int,
            flags: int,
        ) -> int:
            self.set_pos_calls.append((hwnd, hwnd_insert_after, x, y, cx, cy, flags))
            return 1

    fake_user32 = _FakeUser32()
    monkeypatch.setattr(overlay_window_module, "_is_windows_platform", lambda: True)
    monkeypatch.setattr(overlay_window_module, "_resolve_user32", lambda: fake_user32)

    assert overlay_window_module._apply_win32_click_through(101, enabled=True) is True
    assert fake_user32.style & overlay_window_module._WS_EX_LAYERED
    assert fake_user32.style & overlay_window_module._WS_EX_TRANSPARENT
    assert len(fake_user32.set_style_calls) == 1
    assert len(fake_user32.set_pos_calls) == 1

    assert overlay_window_module._apply_win32_click_through(101, enabled=False) is True
    assert fake_user32.style & overlay_window_module._WS_EX_LAYERED
    assert (fake_user32.style & overlay_window_module._WS_EX_TRANSPARENT) == 0
    assert len(fake_user32.set_style_calls) == 2
    assert len(fake_user32.set_pos_calls) == 2


def test_overlay_move_updates_settings_position():
    _get_qapp()
    settings = Settings(tracker_x=3, tracker_y=4)
    overlay = CooldownOverlayWindow(
        settings=settings,
        icon_registry=KeyIconRegistry(assets_dir="does-not-exist"),
        preview_mode=True,
    )
    overlay.show()
    _flush_qt_events()

    overlay.move(120, 240)
    _flush_qt_events()

    assert settings.tracker_x == 120
    assert settings.tracker_y == 240
    overlay.close()


def test_overlay_repositions_offscreen_saved_coordinates_to_primary_screen():
    _get_qapp()
    settings = Settings(tracker_x=-99999, tracker_y=-99999)
    overlay = CooldownOverlayWindow(
        settings=settings,
        icon_registry=KeyIconRegistry(assets_dir="does-not-exist"),
        preview_mode=True,
    )

    primary = QtGui.QGuiApplication.primaryScreen()
    assert primary is not None
    geometry = primary.availableGeometry()
    assert geometry.contains(overlay.pos())
    assert (settings.tracker_x, settings.tracker_y) == (
        int(overlay.pos().x()),
        int(overlay.pos().y()),
    )

    overlay.close()


def test_overlay_binds_countdown_updates_and_removes_completed_timers(tmp_path):
    _get_qapp()
    assets_dir = tmp_path / "assets" / "skills"
    assets_dir.mkdir(parents=True)
    (assets_dir / "orb.png").write_bytes(_PNG_1X1)

    registry = KeyIconRegistry(assets_dir=assets_dir)
    settings = Settings(show_digits_in_tracker=True)
    clock = FakeClock()
    service = CountdownService(time_provider=clock)
    skill = SkillItem(id=7, icon_file_name="orb.png", time_length=5.0, skill_key="F1")
    overlay = CooldownOverlayWindow(
        settings=settings,
        icon_registry=registry,
        poll_interval_ms=1000,
    )
    overlay.set_skill_items([skill])
    overlay.bind_countdown_service(service)

    service.refresh(skill_id=7, duration_seconds=5.0)
    _flush_qt_events()
    snapshots = overlay.snapshot_active_trackers()
    assert [snapshot.skill_id for snapshot in snapshots] == [7]
    assert snapshots[0].digits_text == "5"
    assert snapshots[0].digits_visible is True
    assert snapshots[0].warning_active is False

    clock.advance(2.0)
    service.emit_updates()
    _flush_qt_events()
    snapshots = overlay.snapshot_active_trackers()
    assert snapshots[0].digits_text == "3"
    assert snapshots[0].warning_active is False

    clock.advance(3.0)
    service.emit_updates()
    _flush_qt_events()
    assert overlay.snapshot_active_trackers() == []

    overlay.close()


def test_overlay_respects_left_insert_order_and_hidden_digits_setting(tmp_path):
    _get_qapp()
    assets_dir = tmp_path / "assets" / "skills"
    assets_dir.mkdir(parents=True)
    (assets_dir / "orb.png").write_bytes(_PNG_1X1)

    registry = KeyIconRegistry(assets_dir=assets_dir)
    settings = Settings(
        is_tracker_insert_to_left=True,
        show_digits_in_tracker=False,
    )
    service = CountdownService(time_provider=FakeClock())
    overlay = CooldownOverlayWindow(
        settings=settings,
        icon_registry=registry,
        poll_interval_ms=1000,
    )
    overlay.set_skill_items(
        [
            SkillItem(id=1, icon_file_name="orb.png", time_length=5.0, skill_key="F1"),
            SkillItem(id=2, icon_file_name="orb.png", time_length=5.0, skill_key="F2"),
        ]
    )
    overlay.bind_countdown_service(service)

    service.refresh(skill_id=1, duration_seconds=5.0)
    service.refresh(skill_id=2, duration_seconds=5.0)
    _flush_qt_events()
    snapshots = overlay.snapshot_active_trackers()
    assert [snapshot.skill_id for snapshot in snapshots] == [2, 1]
    assert snapshots[0].digits_visible is False
    assert snapshots[0].warning_active is False
    assert snapshots[1].digits_visible is False
    assert snapshots[1].warning_active is False

    overlay.close()


def test_overlay_refresh_from_settings_rebuilds_preview_layout_scale_and_warning(
    tmp_path,
):
    _get_qapp()
    assets_dir = tmp_path / "assets" / "skills"
    assets_dir.mkdir(parents=True)
    (assets_dir / "orb.png").write_bytes(_PNG_1X1)

    registry = KeyIconRegistry(assets_dir=assets_dir)
    settings = Settings(
        is_tracker_insert_to_left=False,
        is_tracker_vertical=False,
        show_digits_in_tracker=False,
        red_overlay_seconds=0,
        form_scale_x=1.0,
        form_scale_y=1.0,
    )
    overlay = CooldownOverlayWindow(
        settings=settings,
        icon_registry=registry,
        preview_mode=True,
    )
    overlay.set_skill_items(
        [
            SkillItem(id=1, icon_file_name="orb.png", time_length=4.0, skill_key="F1"),
            SkillItem(id=2, icon_file_name="orb.png", time_length=2.0, skill_key="F2"),
        ]
    )

    before_icon_size = overlay._widgets_by_skill_id[1]._icon_label.size()
    assert overlay.active_skill_ids() == [1, 2]

    settings.is_tracker_insert_to_left = True
    settings.is_tracker_vertical = True
    settings.show_digits_in_tracker = True
    settings.red_overlay_seconds = 3
    settings.form_scale_x = 1.5
    settings.form_scale_y = 1.5
    overlay.refresh_from_settings()
    _flush_qt_events()

    assert overlay.active_skill_ids() == [2, 1]
    assert (
        overlay._items_layout.direction() == QtWidgets.QBoxLayout.Direction.TopToBottom
    )
    snapshots = overlay.snapshot_active_trackers()
    assert [snapshot.skill_id for snapshot in snapshots] == [2, 1]
    assert all(snapshot.digits_visible is True for snapshot in snapshots)
    assert snapshots[0].warning_active is True
    after_icon_size = overlay._widgets_by_skill_id[1]._icon_label.size()
    assert after_icon_size.width() > before_icon_size.width()

    overlay.close()


def test_overlay_warning_activates_at_or_below_threshold(tmp_path):
    _get_qapp()
    assets_dir = tmp_path / "assets" / "skills"
    assets_dir.mkdir(parents=True)
    (assets_dir / "orb.png").write_bytes(_PNG_1X1)

    registry = KeyIconRegistry(assets_dir=assets_dir)
    settings = Settings(show_digits_in_tracker=True, red_overlay_seconds=2)
    clock = FakeClock()
    service = CountdownService(time_provider=clock)
    overlay = CooldownOverlayWindow(
        settings=settings,
        icon_registry=registry,
        poll_interval_ms=1000,
    )
    overlay.set_skill_items(
        [SkillItem(id=11, icon_file_name="orb.png", time_length=5.0, skill_key="F1")]
    )
    overlay.bind_countdown_service(service)

    service.refresh(skill_id=11, duration_seconds=5.0)
    _flush_qt_events()
    snapshots = overlay.snapshot_active_trackers()
    assert snapshots[0].warning_active is False

    clock.advance(3.0)
    service.emit_updates()
    _flush_qt_events()
    snapshots = overlay.snapshot_active_trackers()
    assert snapshots[0].digits_text == "2"
    assert snapshots[0].warning_active is True

    overlay.close()


def test_overlay_warning_is_disabled_when_threshold_is_zero(tmp_path):
    _get_qapp()
    assets_dir = tmp_path / "assets" / "skills"
    assets_dir.mkdir(parents=True)
    (assets_dir / "orb.png").write_bytes(_PNG_1X1)

    registry = KeyIconRegistry(assets_dir=assets_dir)
    settings = Settings(show_digits_in_tracker=True, red_overlay_seconds=0)
    clock = FakeClock()
    service = CountdownService(time_provider=clock)
    overlay = CooldownOverlayWindow(
        settings=settings,
        icon_registry=registry,
        poll_interval_ms=1000,
    )
    overlay.set_skill_items(
        [SkillItem(id=12, icon_file_name="orb.png", time_length=5.0, skill_key="F1")]
    )
    overlay.bind_countdown_service(service)

    service.refresh(skill_id=12, duration_seconds=5.0)
    clock.advance(4.0)
    service.emit_updates()
    _flush_qt_events()
    snapshots = overlay.snapshot_active_trackers()
    assert snapshots[0].digits_text == "1"
    assert snapshots[0].warning_active is False

    overlay.close()


def test_overlay_warning_threshold_updates_without_restart(tmp_path):
    _get_qapp()
    assets_dir = tmp_path / "assets" / "skills"
    assets_dir.mkdir(parents=True)
    (assets_dir / "orb.png").write_bytes(_PNG_1X1)

    registry = KeyIconRegistry(assets_dir=assets_dir)
    settings = Settings(show_digits_in_tracker=True, red_overlay_seconds=1)
    clock = FakeClock()
    service = CountdownService(time_provider=clock)
    overlay = CooldownOverlayWindow(
        settings=settings,
        icon_registry=registry,
        poll_interval_ms=1000,
    )
    overlay.set_skill_items(
        [SkillItem(id=13, icon_file_name="orb.png", time_length=5.0, skill_key="F1")]
    )
    overlay.bind_countdown_service(service)

    service.refresh(skill_id=13, duration_seconds=5.0)
    clock.advance(3.0)
    service.emit_updates()
    _flush_qt_events()
    snapshots = overlay.snapshot_active_trackers()
    assert snapshots[0].digits_text == "2"
    assert snapshots[0].warning_active is False

    settings.red_overlay_seconds = 2
    service.emit_updates()
    _flush_qt_events()
    snapshots = overlay.snapshot_active_trackers()
    assert snapshots[0].warning_active is True

    settings.red_overlay_seconds = 0
    clock.advance(1.2)
    service.emit_updates()
    _flush_qt_events()
    snapshots = overlay.snapshot_active_trackers()
    assert snapshots[0].digits_text == "1"
    assert snapshots[0].warning_active is False

    overlay.close()


def test_overlay_refresh_from_settings_rebuilds_runtime_layout_without_restart(
    tmp_path,
):
    _get_qapp()
    assets_dir = tmp_path / "assets" / "skills"
    assets_dir.mkdir(parents=True)
    (assets_dir / "orb.png").write_bytes(_PNG_1X1)

    registry = KeyIconRegistry(assets_dir=assets_dir)
    settings = Settings(
        is_tracker_insert_to_left=False,
        is_tracker_vertical=False,
        show_digits_in_tracker=True,
        red_overlay_seconds=0,
        form_scale_x=1.0,
        form_scale_y=1.0,
    )
    service = CountdownService(time_provider=FakeClock())
    overlay = CooldownOverlayWindow(
        settings=settings,
        icon_registry=registry,
        poll_interval_ms=1000,
    )
    overlay.set_skill_items(
        [
            SkillItem(id=21, icon_file_name="orb.png", time_length=2.0, skill_key="F1"),
            SkillItem(id=22, icon_file_name="orb.png", time_length=4.0, skill_key="F2"),
        ]
    )
    overlay.bind_countdown_service(service)

    service.refresh(skill_id=21, duration_seconds=2.0)
    service.refresh(skill_id=22, duration_seconds=4.0)
    _flush_qt_events()
    before_icon_size = overlay._widgets_by_skill_id[21]._icon_label.size()
    assert overlay.active_skill_ids() == [21, 22]

    settings.is_tracker_insert_to_left = True
    settings.is_tracker_vertical = True
    settings.show_digits_in_tracker = False
    settings.red_overlay_seconds = 3
    settings.form_scale_x = 1.4
    settings.form_scale_y = 1.4
    overlay.refresh_from_settings()
    _flush_qt_events()

    assert overlay.active_skill_ids() == [22, 21]
    assert (
        overlay._items_layout.direction() == QtWidgets.QBoxLayout.Direction.TopToBottom
    )
    snapshots = overlay.snapshot_active_trackers()
    assert [snapshot.skill_id for snapshot in snapshots] == [22, 21]
    assert all(snapshot.digits_visible is False for snapshot in snapshots)
    assert snapshots[1].warning_active is True
    after_icon_size = overlay._widgets_by_skill_id[21]._icon_label.size()
    assert after_icon_size.width() > before_icon_size.width()

    overlay.close()
