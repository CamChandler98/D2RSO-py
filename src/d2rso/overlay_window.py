"""Transparent, topmost cooldown overlay window."""

from __future__ import annotations

import ctypes
import sys
from dataclasses import dataclass
from math import ceil
from pathlib import Path
from typing import Iterable

from PySide6 import QtCore, QtGui, QtWidgets

from .countdown_service import CountdownEvent, CountdownEventType, CountdownService
from .key_icon_registry import KeyIconRegistry, get_key_icon_registry
from .models import Settings, SkillItem

_BASE_ICON_SIZE_PX = 50
_MIN_ICON_SIZE_PX = 8
_DEFAULT_POLL_INTERVAL_MS = 100
_GWL_EXSTYLE = -20
_WS_EX_LAYERED = 0x00080000
_WS_EX_TRANSPARENT = 0x00000020
_SWP_NOSIZE = 0x0001
_SWP_NOMOVE = 0x0002
_SWP_NOZORDER = 0x0004
_SWP_NOACTIVATE = 0x0010
_SWP_FRAMECHANGED = 0x0020


def format_remaining_seconds(remaining_seconds: float) -> str:
    """Return display-friendly countdown text."""
    value = max(0.0, float(remaining_seconds))
    return str(int(ceil(value)))


@dataclass(frozen=True, slots=True)
class OverlayTrackerSnapshot:
    """Read-only overlay item snapshot for testing/inspection."""

    skill_id: int
    remaining_seconds: float
    digits_text: str
    digits_visible: bool
    warning_active: bool


class _CountdownEventBridge(QtCore.QObject):
    event_received = QtCore.Signal(object)


def _is_windows_platform() -> bool:
    return sys.platform == "win32"


def _resolve_user32() -> object | None:
    try:
        return ctypes.windll.user32
    except Exception:
        return None


def _apply_win32_click_through(window_handle: int, *, enabled: bool) -> bool:
    """Apply native Win32 click-through style for the overlay window."""
    if not _is_windows_platform():
        return False
    if window_handle <= 0:
        return False

    user32 = _resolve_user32()
    if user32 is None:
        return False

    get_window_long = getattr(user32, "GetWindowLongPtrW", None) or getattr(
        user32, "GetWindowLongW", None
    )
    set_window_long = getattr(user32, "SetWindowLongPtrW", None) or getattr(
        user32, "SetWindowLongW", None
    )
    if not callable(get_window_long) or not callable(set_window_long):
        return False

    try:
        current_style = int(get_window_long(int(window_handle), _GWL_EXSTYLE))
    except Exception:
        return False

    target_style = current_style | _WS_EX_LAYERED
    if enabled:
        target_style |= _WS_EX_TRANSPARENT
    else:
        target_style &= ~_WS_EX_TRANSPARENT

    if target_style != current_style:
        try:
            set_window_long(int(window_handle), _GWL_EXSTYLE, int(target_style))
        except Exception:
            return False

    set_window_pos = getattr(user32, "SetWindowPos", None)
    if callable(set_window_pos):
        flags = (
            _SWP_NOMOVE
            | _SWP_NOSIZE
            | _SWP_NOZORDER
            | _SWP_NOACTIVATE
            | _SWP_FRAMECHANGED
        )
        try:
            set_window_pos(int(window_handle), 0, 0, 0, 0, 0, flags)
        except Exception:
            return False

    return True


class _OverlayTrackerItemWidget(QtWidgets.QFrame):
    """Widget that renders one active cooldown icon + optional digits."""

    def __init__(
        self,
        *,
        skill_id: int,
        icon_size: QtCore.QSize,
        show_digits: bool,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.skill_id = int(skill_id)
        self._icon_size = icon_size
        self._remaining_seconds = 0.0
        self._is_warning: bool | None = None

        self.setObjectName("overlay_item_frame")
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_TranslucentBackground, True)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(2)

        self._icon_label = QtWidgets.QLabel(self)
        self._icon_label.setObjectName("overlay_icon_label")
        self._icon_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self._icon_label.setFixedSize(icon_size)

        self._digits_label = QtWidgets.QLabel(self)
        self._digits_label.setObjectName("overlay_digits_label")
        self._digits_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)

        layout.addWidget(self._icon_label, 0, QtCore.Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._digits_label, 0, QtCore.Qt.AlignmentFlag.AlignCenter)

        self.set_digits_visible(show_digits)
        self.set_remaining_seconds(0.0)
        self._set_icon_pixmap(None)
        self.set_warning_state(False)

    @property
    def remaining_seconds(self) -> float:
        return self._remaining_seconds

    @property
    def digits_text(self) -> str:
        return self._digits_label.text()

    @property
    def digits_visible(self) -> bool:
        return not self._digits_label.isHidden()

    @property
    def is_warning(self) -> bool:
        return bool(self._is_warning)

    def set_digits_visible(self, visible: bool) -> None:
        self._digits_label.setVisible(bool(visible))

    def set_remaining_seconds(self, remaining_seconds: float) -> None:
        self._remaining_seconds = max(0.0, float(remaining_seconds))
        self._digits_label.setText(format_remaining_seconds(self._remaining_seconds))

    def set_warning_state(self, is_warning: bool) -> None:
        normalized = bool(is_warning)
        if self._is_warning is normalized:
            return
        self._is_warning = normalized
        self._set_warning_property(self, normalized)
        self._set_warning_property(self._digits_label, normalized)

    def set_icon_path(self, icon_path: Path | None) -> None:
        if icon_path is not None and icon_path.exists():
            pixmap = QtGui.QPixmap(str(icon_path))
            if not pixmap.isNull():
                self._set_icon_pixmap(pixmap)
                return
        self._set_icon_pixmap(None)

    def _set_icon_pixmap(self, pixmap: QtGui.QPixmap | None) -> None:
        source = pixmap if pixmap is not None else self._build_placeholder_pixmap()
        scaled = source.scaled(
            self._icon_size,
            QtCore.Qt.AspectRatioMode.KeepAspectRatio,
            QtCore.Qt.TransformationMode.SmoothTransformation,
        )
        self._icon_label.setPixmap(scaled)

    @staticmethod
    def _set_warning_property(widget: QtWidgets.QWidget, is_warning: bool) -> None:
        widget.setProperty("warning", bool(is_warning))
        style = widget.style()
        if style is not None:
            style.unpolish(widget)
            style.polish(widget)
        widget.update()

    def _build_placeholder_pixmap(self) -> QtGui.QPixmap:
        pixmap = QtGui.QPixmap(self._icon_size)
        pixmap.fill(QtCore.Qt.GlobalColor.transparent)

        painter = QtGui.QPainter(pixmap)
        try:
            painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing, True)
            rect = pixmap.rect().adjusted(2, 2, -2, -2)
            painter.setBrush(QtGui.QColor(24, 24, 24, 220))
            painter.setPen(QtGui.QPen(QtGui.QColor(240, 240, 240, 170), 1))
            painter.drawRoundedRect(rect, 8, 8)

            painter.setPen(QtGui.QColor(255, 255, 255))
            font = QtGui.QFont()
            font.setPointSize(9)
            font.setBold(True)
            painter.setFont(font)
            painter.drawText(
                rect,
                QtCore.Qt.AlignmentFlag.AlignCenter,
                str(self.skill_id),
            )
        finally:
            painter.end()

        return pixmap


class CooldownOverlayWindow(QtWidgets.QWidget):
    """Frameless topmost overlay that reflects active CountdownService state."""

    position_changed = QtCore.Signal(int, int)

    def __init__(
        self,
        *,
        settings: Settings,
        icon_registry: KeyIconRegistry | None = None,
        poll_interval_ms: int = _DEFAULT_POLL_INTERVAL_MS,
        preview_mode: bool = False,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._settings = settings
        self._icon_registry = icon_registry or get_key_icon_registry()
        self._preview_mode = bool(preview_mode)
        self._drag_anchor_global: QtCore.QPoint | None = None
        self._drag_anchor_window: QtCore.QPoint | None = None
        self._skill_items_in_order: list[SkillItem] = []
        self._skill_items_by_id: dict[int, SkillItem] = {}
        self._widgets_by_skill_id: dict[int, _OverlayTrackerItemWidget] = {}
        self._countdown_service: CountdownService | None = None

        self._event_bridge = _CountdownEventBridge(self)
        self._event_bridge.event_received.connect(
            self._handle_countdown_event,
            QtCore.Qt.ConnectionType.QueuedConnection,
        )

        self._poll_timer = QtCore.QTimer(self)
        self._poll_timer.setInterval(max(16, int(poll_interval_ms)))
        self._poll_timer.setTimerType(QtCore.Qt.TimerType.PreciseTimer)
        self._poll_timer.timeout.connect(self._poll_countdowns)

        self._icon_size = QtCore.QSize(
            max(
                _MIN_ICON_SIZE_PX,
                int(_BASE_ICON_SIZE_PX * float(self._settings.form_scale_x)),
            ),
            max(
                _MIN_ICON_SIZE_PX,
                int(_BASE_ICON_SIZE_PX * float(self._settings.form_scale_y)),
            ),
        )

        self._init_window()
        self._init_layout()
        self._apply_mode_presentation()

    def showEvent(self, event: QtGui.QShowEvent) -> None:
        super().showEvent(event)
        self._apply_mode_presentation()

    def moveEvent(self, event: QtGui.QMoveEvent) -> None:
        self._sync_settings_position()
        super().moveEvent(event)

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        self.unbind_countdown_service()
        super().closeEvent(event)

    @property
    def is_preview_mode(self) -> bool:
        return self._preview_mode

    def set_preview_mode(self, preview_mode: bool) -> None:
        """Switch between runtime and draggable preview behavior."""
        self._preview_mode = bool(preview_mode)
        if self._preview_mode:
            self.unbind_countdown_service()
            self._render_preview_items()
        else:
            self._hide_preview_hint()
            self._clear_tracker_widgets()
        self._apply_mode_presentation()

    def set_skill_items(self, skill_items: Iterable[SkillItem]) -> None:
        """Replace skill metadata used to resolve icon paths by ``skill_id``."""
        self._skill_items_in_order = [
            item for item in skill_items if isinstance(item, SkillItem)
        ]
        self._skill_items_by_id = {item.id: item for item in self._skill_items_in_order}
        for skill_id, widget in self._widgets_by_skill_id.items():
            widget.set_icon_path(self._resolve_icon_path(skill_id))
        if self._preview_mode:
            self._render_preview_items()

    def bind_countdown_service(self, countdown_service: CountdownService) -> None:
        """Subscribe to countdown events and begin UI polling for updates."""
        if self._preview_mode:
            return
        if countdown_service is self._countdown_service:
            return

        self.unbind_countdown_service()

        self._countdown_service = countdown_service
        self._countdown_service.subscribe(self._queue_countdown_event)
        self._poll_timer.start()

        for state in self._countdown_service.list_active():
            self._handle_countdown_event(
                CountdownEvent(
                    type=CountdownEventType.UPDATED,
                    skill_id=state.skill_id,
                    duration_seconds=state.duration_seconds,
                    remaining_seconds=state.remaining_seconds,
                    completed=False,
                )
            )

    def unbind_countdown_service(self) -> None:
        """Detach from the active countdown service."""
        if self._countdown_service is not None:
            self._countdown_service.unsubscribe(self._queue_countdown_event)
            self._countdown_service = None
        self._poll_timer.stop()

    def active_skill_ids(self) -> list[int]:
        """Return active skill IDs in rendered order."""
        ordered: list[int] = []
        for index in range(self._items_layout.count()):
            widget = self._items_layout.itemAt(index).widget()
            if isinstance(widget, _OverlayTrackerItemWidget):
                ordered.append(widget.skill_id)
        return ordered

    def snapshot_active_trackers(self) -> list[OverlayTrackerSnapshot]:
        """Return snapshots ordered exactly as rendered."""
        snapshots: list[OverlayTrackerSnapshot] = []
        for skill_id in self.active_skill_ids():
            widget = self._widgets_by_skill_id.get(skill_id)
            if widget is None:
                continue
            snapshots.append(
                OverlayTrackerSnapshot(
                    skill_id=skill_id,
                    remaining_seconds=widget.remaining_seconds,
                    digits_text=widget.digits_text,
                    digits_visible=widget.digits_visible,
                    warning_active=widget.is_warning,
                )
            )
        return snapshots

    def _init_window(self) -> None:
        flags = (
            QtCore.Qt.WindowType.Tool
            | QtCore.Qt.WindowType.FramelessWindowHint
            | QtCore.Qt.WindowType.WindowStaysOnTopHint
        )
        self.setWindowFlags(flags)
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setAutoFillBackground(False)
        self.setWindowTitle("D2RSO Overlay")
        self.move(self._resolve_initial_position())

    def _resolve_initial_position(self) -> QtCore.QPoint:
        requested = QtCore.QPoint(
            int(self._settings.tracker_x),
            int(self._settings.tracker_y),
        )
        screens = QtGui.QGuiApplication.screens()
        if not screens:
            return requested
        if any(screen.availableGeometry().contains(requested) for screen in screens):
            return requested

        primary = QtGui.QGuiApplication.primaryScreen() or screens[0]
        safe_geometry = primary.availableGeometry()
        safe_position = QtCore.QPoint(
            int(safe_geometry.left() + 16),
            int(safe_geometry.top() + 16),
        )
        self._settings.tracker_x = int(safe_position.x())
        self._settings.tracker_y = int(safe_position.y())
        return safe_position

    def _init_layout(self) -> None:
        self.setStyleSheet("""
            QWidget#overlay_items_container {
                background: transparent;
            }
            QFrame#overlay_item_frame {
                background: rgba(0, 0, 0, 42);
                border-radius: 8px;
                border: 1px solid transparent;
            }
            QFrame#overlay_item_frame[warning="true"] {
                background: rgba(170, 18, 18, 118);
                border: 1px solid rgba(255, 118, 118, 200);
            }
            QLabel#overlay_digits_label {
                color: white;
                font-size: 18px;
                font-weight: 700;
                min-width: 28px;
                padding: 1px 6px;
                border-radius: 5px;
                background: rgba(0, 0, 0, 130);
            }
            QLabel#overlay_digits_label[warning="true"] {
                background: rgba(165, 20, 20, 196);
            }
            QLabel#overlay_preview_hint_label {
                color: white;
                font-size: 12px;
                font-weight: 600;
                padding: 4px 8px;
                border-radius: 6px;
                background: rgba(30, 30, 30, 180);
            }
            """)

        root_layout = QtWidgets.QVBoxLayout(self)
        root_layout.setContentsMargins(3, 3, 3, 3)
        root_layout.setSpacing(4)

        container = QtWidgets.QWidget(self)
        container.setObjectName("overlay_items_container")

        self._items_layout = QtWidgets.QBoxLayout(self._resolve_direction())
        self._items_layout.setContentsMargins(0, 0, 0, 0)
        self._items_layout.setSpacing(6)
        container.setLayout(self._items_layout)
        root_layout.addWidget(container)

        self._preview_hint_label = QtWidgets.QLabel(
            "Preview mode: drag overlay to reposition", self
        )
        self._preview_hint_label.setObjectName("overlay_preview_hint_label")
        self._preview_hint_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self._preview_hint_label.hide()
        root_layout.addWidget(self._preview_hint_label)

    def _resolve_direction(self) -> QtWidgets.QBoxLayout.Direction:
        if self._settings.is_tracker_vertical:
            return QtWidgets.QBoxLayout.Direction.TopToBottom
        return QtWidgets.QBoxLayout.Direction.LeftToRight

    def _queue_countdown_event(self, event: CountdownEvent) -> None:
        self._event_bridge.event_received.emit(event)

    def _poll_countdowns(self) -> None:
        if self._preview_mode or self._countdown_service is None:
            return
        self._countdown_service.emit_updates()

    @QtCore.Slot(object)
    def _handle_countdown_event(self, event: object) -> None:
        if self._preview_mode:
            return
        if not isinstance(event, CountdownEvent):
            return

        if event.type is CountdownEventType.REMOVED:
            self._remove_tracker_widget(event.skill_id)
            return

        if event.type is CountdownEventType.UPDATED:
            self._upsert_tracker_widget(
                skill_id=event.skill_id,
                remaining_seconds=event.remaining_seconds,
            )

    def _upsert_tracker_widget(
        self,
        *,
        skill_id: int,
        remaining_seconds: float,
    ) -> None:
        widget = self._widgets_by_skill_id.get(skill_id)
        if widget is None:
            widget = _OverlayTrackerItemWidget(
                skill_id=skill_id,
                icon_size=self._icon_size,
                show_digits=self._settings.show_digits_in_tracker,
                parent=self,
            )
            widget.set_icon_path(self._resolve_icon_path(skill_id))
            if self._settings.is_tracker_insert_to_left:
                self._items_layout.insertWidget(0, widget)
            else:
                self._items_layout.addWidget(widget)
            self._widgets_by_skill_id[skill_id] = widget

        widget.set_digits_visible(self._settings.show_digits_in_tracker)
        widget.set_remaining_seconds(remaining_seconds)
        threshold_seconds = self._settings.red_overlay_seconds_effective
        widget.set_warning_state(
            threshold_seconds > 0 and widget.remaining_seconds <= threshold_seconds
        )
        self.adjustSize()

    def _clear_tracker_widgets(self) -> None:
        for skill_id in list(self._widgets_by_skill_id):
            self._remove_tracker_widget(skill_id)

    def _remove_tracker_widget(self, skill_id: int) -> None:
        widget = self._widgets_by_skill_id.pop(skill_id, None)
        if widget is None:
            return
        self._items_layout.removeWidget(widget)
        widget.deleteLater()
        self.adjustSize()

    def _render_preview_items(self) -> None:
        self._clear_tracker_widgets()
        preview_items = [item for item in self._skill_items_in_order if item.is_enabled]
        if not preview_items:
            self._show_preview_hint()
            self.adjustSize()
            return

        for item in preview_items:
            self._upsert_tracker_widget(
                skill_id=item.id,
                remaining_seconds=max(0.0, float(item.time_length)),
            )
        self._show_preview_hint()
        self.adjustSize()

    def _resolve_icon_path(self, skill_id: int) -> Path | None:
        item = self._skill_items_by_id.get(skill_id)
        if item is None:
            return None
        return self._icon_registry.get_icon_path(item.icon_file_name)

    def _apply_mode_presentation(self) -> None:
        self.setAttribute(
            QtCore.Qt.WidgetAttribute.WA_TransparentForMouseEvents,
            not self._preview_mode,
        )
        try:
            window_handle = int(self.winId())
        except Exception:
            window_handle = 0
        _apply_win32_click_through(
            window_handle,
            enabled=not self._preview_mode,
        )
        self._preview_hint_label.setVisible(self._preview_mode)
        self.adjustSize()

    def _sync_settings_position(self) -> None:
        position = self.pos()
        x = int(position.x())
        y = int(position.y())
        self._settings.tracker_x = x
        self._settings.tracker_y = y
        self.position_changed.emit(x, y)

    def _show_preview_hint(self) -> None:
        if self._preview_mode:
            self._preview_hint_label.show()

    def _hide_preview_hint(self) -> None:
        self._preview_hint_label.hide()

    def mousePressEvent(self, event: QtGui.QMouseEvent) -> None:
        if (
            self._preview_mode
            and event.button() == QtCore.Qt.MouseButton.LeftButton
            and event.globalPosition() is not None
        ):
            self._drag_anchor_global = event.globalPosition().toPoint()
            self._drag_anchor_window = self.frameGeometry().topLeft()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QtGui.QMouseEvent) -> None:
        if (
            self._preview_mode
            and self._drag_anchor_global is not None
            and self._drag_anchor_window is not None
            and event.buttons() & QtCore.Qt.MouseButton.LeftButton
            and event.globalPosition() is not None
        ):
            delta = event.globalPosition().toPoint() - self._drag_anchor_global
            self.move(self._drag_anchor_window + delta)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QtGui.QMouseEvent) -> None:
        if self._preview_mode and event.button() == QtCore.Qt.MouseButton.LeftButton:
            self._drag_anchor_global = None
            self._drag_anchor_window = None
            event.accept()
            return
        super().mouseReleaseEvent(event)


__all__ = [
    "CooldownOverlayWindow",
    "OverlayTrackerSnapshot",
    "format_remaining_seconds",
]
