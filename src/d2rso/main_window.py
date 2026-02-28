"""Main configuration UI for profile/skill/run controls."""

from __future__ import annotations

import os
from collections.abc import Callable
from typing import Any

from PySide6 import QtCore, QtGui, QtWidgets

from .countdown_service import CountdownService
from .input_events import normalize_input_code
from .key_icon_registry import KeyIconRegistry, get_key_icon_registry
from .models import (
    DEFAULT_SKILL_DURATION_SECONDS,
    DEFAULT_SKILL_KEY,
    Profile,
    Settings,
    SkillItem,
)
from .options_dialog import OptionsDialog
from .overlay_window import CooldownOverlayWindow
from .settings_store import SettingsStore
from .tracker_runtime import TrackerRuntimeController

_COL_ENABLED = 0
_COL_ICON = 1
_COL_DURATION = 2
_COL_SELECT = 3
_COL_USE = 4
_COL_REMOVE = 5
_DISABLE_TRAY_ENV_VAR = "D2RSO_DISABLE_TRAY"


def _env_var_enabled(name: str) -> bool:
    raw_value = os.environ.get(name)
    if raw_value is None:
        return False
    return raw_value.strip().lower() in {"1", "true", "yes", "on"}


class MainWindow(QtWidgets.QMainWindow):
    """Desktop window for profile CRUD, skill configuration, and run controls."""

    def __init__(
        self,
        *,
        settings_store: SettingsStore | None = None,
        settings: Settings | None = None,
        icon_registry: KeyIconRegistry | None = None,
        input_router_factory: Callable[..., Any] | None = None,
        countdown_service_factory: Callable[[], CountdownService] | None = None,
        enable_tray: bool | None = None,
        tray_icon_factory: Callable[..., Any] | None = None,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._settings_store = settings_store or SettingsStore()
        self._settings = settings or self._settings_store.load()
        self._settings.ensure_defaults()

        self._icon_registry = icon_registry or get_key_icon_registry()
        self._options_dialog: OptionsDialog | None = None
        self._preview_overlay: CooldownOverlayWindow | None = None
        self._runtime_overlay: CooldownOverlayWindow | None = None
        self._tracker_runtime = TrackerRuntimeController(
            input_router_factory=input_router_factory,
            countdown_service_factory=countdown_service_factory or CountdownService,
            parent=self,
        )
        self._tracker_runtime.error_occurred.connect(self._handle_runtime_error)

        self._loading_ui = False
        self._enable_tray = enable_tray
        self._tray_icon_factory = tray_icon_factory or QtWidgets.QSystemTrayIcon
        self._tray_icon: Any | None = None
        self._tray_menu: QtWidgets.QMenu | None = None
        self._tray_toggle_action: QtGui.QAction | None = None
        self._tray_exit_action: QtGui.QAction | None = None
        self._is_exiting = False
        self._shutdown_complete = False

        self._init_window()
        self._init_layout()
        self._init_tray_icon()
        self._refresh_profiles(
            selected_profile_id=self._settings.last_selected_profile_id
        )
        self._update_control_states()
        if self._settings.start_tracker_on_app_run:
            QtCore.QTimer.singleShot(0, self._start_tracking_from_settings)

    @property
    def is_playing(self) -> bool:
        return self._tracker_runtime.is_running

    @property
    def is_preview_visible(self) -> bool:
        return self._preview_overlay is not None

    @property
    def settings(self) -> Settings:
        return self._settings

    def changeEvent(self, event: QtCore.QEvent) -> None:
        super().changeEvent(event)
        if event.type() != QtCore.QEvent.Type.WindowStateChange:
            return
        self._sync_tray_actions()
        if self._should_hide_minimized_window():
            QtCore.QTimer.singleShot(0, self._hide_minimized_window_to_tray)

    def hideEvent(self, event: QtGui.QHideEvent) -> None:
        super().hideEvent(event)
        self._sync_tray_actions()

    def showEvent(self, event: QtGui.QShowEvent) -> None:
        super().showEvent(event)
        self._sync_tray_actions()

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        try:
            if self._should_hide_to_tray_on_close():
                event.ignore()
                self._hide_to_tray()
                return
            self._perform_shutdown()
            super().closeEvent(event)
        except KeyboardInterrupt:
            event.accept()

    def exit_to_desktop(self) -> None:
        self._is_exiting = True
        self.close()

    def add_profile(self, name: str) -> Profile | None:
        normalized_name = name.strip()
        if not normalized_name:
            return None

        new_id = (
            max((profile.id for profile in self._settings.profiles), default=-1) + 1
        )
        created = Profile(id=new_id, name=normalized_name)
        self._settings.profiles.append(created)
        self._settings.last_selected_profile_id = created.id
        self._save_settings()
        self._refresh_profiles(selected_profile_id=created.id)
        return created

    def rename_current_profile(self, name: str) -> bool:
        profile = self._current_profile()
        if profile is None:
            return False

        normalized_name = name.strip()
        if not normalized_name:
            return False

        profile.name = normalized_name
        self._save_settings()
        self._refresh_profiles(selected_profile_id=profile.id)
        return True

    def remove_current_profile(self) -> bool:
        profile = self._current_profile()
        if profile is None:
            return False

        if len(self._settings.profiles) <= 1:
            return False

        replacement_profile_id = self._replacement_profile_id_after_removal(profile.id)
        self._settings.profiles = [
            item for item in self._settings.profiles if item.id != profile.id
        ]
        self._settings.skill_items = [
            item for item in self._settings.skill_items if item.profile_id != profile.id
        ]
        self._settings.ensure_defaults()
        self._settings.last_selected_profile_id = replacement_profile_id
        self._save_settings()
        self._refresh_profiles(
            selected_profile_id=self._settings.last_selected_profile_id
        )
        return True

    def add_skill_to_current_profile(self) -> SkillItem | None:
        profile = self._current_profile()
        if profile is None:
            return None

        new_id = max((item.id for item in self._settings.skill_items), default=0) + 1
        default_icon_name = self._default_icon_name()
        item = SkillItem(
            id=new_id,
            profile_id=profile.id,
            icon_file_name=default_icon_name,
            time_length=DEFAULT_SKILL_DURATION_SECONDS,
            is_enabled=True,
            select_key=None,
            skill_key=DEFAULT_SKILL_KEY,
        )
        self._settings.skill_items.append(item)
        self._save_settings()
        self._populate_skill_table()
        return item

    def remove_skill(self, skill_id: int) -> bool:
        current_count = len(self._settings.skill_items)
        self._settings.skill_items = [
            item for item in self._settings.skill_items if item.id != skill_id
        ]
        if len(self._settings.skill_items) == current_count:
            return False
        self._save_settings()
        self._populate_skill_table()
        return True

    def selected_profile_id(self) -> int | None:
        profile_id = self.profile_combo.currentData()
        if profile_id is None:
            return None
        return int(profile_id)

    def selected_skill_items(self) -> list[SkillItem]:
        profile_id = self.selected_profile_id()
        if profile_id is None:
            return []
        return [
            item for item in self._settings.skill_items if item.profile_id == profile_id
        ]

    def _init_tray_icon(self) -> None:
        if not self._is_tray_enabled():
            return

        tray_icon = self._tray_icon_factory(self._window_icon_for_tray(), self)
        tray_icon.setToolTip(self.windowTitle())

        tray_menu = QtWidgets.QMenu(self)
        toggle_action = tray_menu.addAction("Hide")
        toggle_action.triggered.connect(self._toggle_main_window_visibility)

        exit_action = tray_menu.addAction("Exit")
        exit_action.triggered.connect(self.exit_to_desktop)

        tray_icon.activated.connect(self._on_tray_icon_activated)
        tray_icon.setContextMenu(tray_menu)
        tray_icon.show()

        self._tray_icon = tray_icon
        self._tray_menu = tray_menu
        self._tray_toggle_action = toggle_action
        self._tray_exit_action = exit_action
        self._sync_tray_actions()

    def _is_tray_enabled(self) -> bool:
        if self._enable_tray is not None:
            return bool(self._enable_tray)
        if _env_var_enabled(_DISABLE_TRAY_ENV_VAR):
            return False
        return bool(QtWidgets.QSystemTrayIcon.isSystemTrayAvailable())

    def _window_icon_for_tray(self) -> QtGui.QIcon:
        icon = self.windowIcon()
        if icon.isNull():
            icon = self.style().standardIcon(
                QtWidgets.QStyle.StandardPixmap.SP_ComputerIcon
            )
            self.setWindowIcon(icon)
        return icon

    def _is_window_open_for_interaction(self) -> bool:
        return self.isVisible() and not self.isMinimized()

    def _sync_tray_actions(self) -> None:
        if self._tray_toggle_action is None:
            return
        self._tray_toggle_action.setText(
            "Hide" if self._is_window_open_for_interaction() else "Open"
        )

    def _toggle_main_window_visibility(self) -> None:
        if self._is_window_open_for_interaction():
            self._hide_to_tray()
        else:
            self._show_from_tray()

    def _show_from_tray(self) -> None:
        self.showNormal()
        self.raise_()
        self.activateWindow()
        self._sync_tray_actions()

    def _hide_to_tray(self) -> None:
        if self._options_dialog is not None:
            self._options_dialog.close()
        self._close_preview_overlay()
        self._update_control_states()
        self._save_settings()
        self.hide()
        self._sync_tray_actions()

    def _should_hide_to_tray_on_close(self) -> bool:
        return self._tray_icon is not None and not self._is_exiting

    def _should_hide_minimized_window(self) -> bool:
        return (
            self._tray_icon is not None
            and self._settings.minimize_to_tray
            and not self._is_exiting
            and self.isMinimized()
        )

    def _hide_minimized_window_to_tray(self) -> None:
        if not self._should_hide_minimized_window():
            return
        self.hide()
        self.setWindowState(self.windowState() & ~QtCore.Qt.WindowState.WindowMinimized)
        self._sync_tray_actions()

    @QtCore.Slot(QtWidgets.QSystemTrayIcon.ActivationReason)
    def _on_tray_icon_activated(
        self,
        reason: QtWidgets.QSystemTrayIcon.ActivationReason,
    ) -> None:
        if reason in {
            QtWidgets.QSystemTrayIcon.ActivationReason.Trigger,
            QtWidgets.QSystemTrayIcon.ActivationReason.DoubleClick,
        }:
            self._toggle_main_window_visibility()

    def _perform_shutdown(self) -> None:
        if self._shutdown_complete:
            return
        self._shutdown_complete = True
        if self._options_dialog is not None:
            self._options_dialog.close()
        self._stop_tracking()
        self._close_preview_overlay()
        self._save_settings()
        self._dispose_tray_icon()

    def _dispose_tray_icon(self) -> None:
        if self._tray_icon is None:
            return
        tray_icon = self._tray_icon
        self._tray_icon = None
        self._tray_menu = None
        self._tray_toggle_action = None
        self._tray_exit_action = None
        tray_icon.hide()
        tray_icon.deleteLater()

    def _init_window(self) -> None:
        self.setWindowTitle("D2R Skill Overlay")
        self.resize(980, 620)
        self.setMinimumSize(860, 460)

    def _init_layout(self) -> None:
        central = QtWidgets.QWidget(self)
        self.setCentralWidget(central)

        root = QtWidgets.QVBoxLayout(central)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(10)

        runtime_bar = QtWidgets.QHBoxLayout()
        runtime_bar.setSpacing(8)

        self.preview_button = QtWidgets.QPushButton("Preview", self)
        self.preview_button.clicked.connect(self._toggle_preview)
        runtime_bar.addWidget(self.preview_button)

        self.play_button = QtWidgets.QPushButton("Play", self)
        self.play_button.clicked.connect(self._toggle_playback)
        runtime_bar.addWidget(self.play_button)

        self.options_button = QtWidgets.QPushButton("Options", self)
        self.options_button.clicked.connect(self._open_options_dialog)
        runtime_bar.addWidget(self.options_button)

        runtime_bar.addStretch(1)

        self.status_label = QtWidgets.QLabel("Idle", self)
        self.status_label.setObjectName("runtime_status_label")
        runtime_bar.addWidget(self.status_label)

        root.addLayout(runtime_bar)

        profile_bar = QtWidgets.QHBoxLayout()
        profile_bar.setSpacing(6)
        profile_bar.addWidget(QtWidgets.QLabel("Profile", self))

        self.profile_combo = QtWidgets.QComboBox(self)
        self.profile_combo.currentIndexChanged.connect(
            self._on_profile_selection_changed
        )
        profile_bar.addWidget(self.profile_combo, 1)

        self.add_profile_button = QtWidgets.QPushButton("Add", self)
        self.add_profile_button.clicked.connect(self._on_add_profile_clicked)
        profile_bar.addWidget(self.add_profile_button)

        self.rename_profile_button = QtWidgets.QPushButton("Rename", self)
        self.rename_profile_button.clicked.connect(self._on_rename_profile_clicked)
        profile_bar.addWidget(self.rename_profile_button)

        self.remove_profile_button = QtWidgets.QPushButton("Delete", self)
        self.remove_profile_button.clicked.connect(self._on_remove_profile_clicked)
        profile_bar.addWidget(self.remove_profile_button)

        root.addLayout(profile_bar)

        self.add_skill_button = QtWidgets.QPushButton("Add Skill", self)
        self.add_skill_button.clicked.connect(self._on_add_skill_clicked)
        root.addWidget(self.add_skill_button, 0, QtCore.Qt.AlignmentFlag.AlignLeft)

        self.skill_table = QtWidgets.QTableWidget(0, 6, self)
        self.skill_table.setHorizontalHeaderLabels(
            ["Enabled", "Icon", "Duration (sec)", "Select Key", "Skill Key", ""]
        )
        self.skill_table.verticalHeader().setVisible(False)
        self.skill_table.setAlternatingRowColors(True)
        self.skill_table.setSelectionMode(
            QtWidgets.QAbstractItemView.SelectionMode.NoSelection
        )
        self.skill_table.setEditTriggers(
            QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self.skill_table.setFocusPolicy(QtCore.Qt.FocusPolicy.NoFocus)

        header = self.skill_table.horizontalHeader()
        header.setSectionResizeMode(
            _COL_ENABLED, QtWidgets.QHeaderView.ResizeMode.ResizeToContents
        )
        header.setSectionResizeMode(_COL_ICON, QtWidgets.QHeaderView.ResizeMode.Fixed)
        header.resizeSection(_COL_ICON, 180)
        header.setSectionResizeMode(
            _COL_DURATION, QtWidgets.QHeaderView.ResizeMode.ResizeToContents
        )
        header.setSectionResizeMode(
            _COL_SELECT, QtWidgets.QHeaderView.ResizeMode.Stretch
        )
        header.setSectionResizeMode(_COL_USE, QtWidgets.QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(
            _COL_REMOVE, QtWidgets.QHeaderView.ResizeMode.ResizeToContents
        )

        root.addWidget(self.skill_table, 1)

    def _current_profile(self) -> Profile | None:
        profile_id = self.selected_profile_id()
        if profile_id is None:
            return None
        return next(
            (
                profile
                for profile in self._settings.profiles
                if profile.id == profile_id
            ),
            None,
        )

    def _refresh_profiles(self, *, selected_profile_id: int | None = None) -> None:
        self._loading_ui = True
        try:
            profiles = list(self._settings.profiles)
            target_profile_id = (
                self._settings.last_selected_profile_id
                if selected_profile_id is None
                else int(selected_profile_id)
            )

            with QtCore.QSignalBlocker(self.profile_combo):
                self.profile_combo.clear()
                for profile in profiles:
                    self.profile_combo.addItem(profile.name, profile.id)

                selected_index = self.profile_combo.findData(target_profile_id)
                if selected_index < 0:
                    selected_index = 0 if profiles else -1
                if selected_index >= 0:
                    self.profile_combo.setCurrentIndex(selected_index)

            current_profile_id = self.selected_profile_id()
            if current_profile_id is not None:
                self._settings.last_selected_profile_id = current_profile_id

            self._populate_skill_table()
        finally:
            self._loading_ui = False

    def _populate_skill_table(self) -> None:
        self.skill_table.setRowCount(0)
        profile = self._current_profile()
        if profile is None:
            self._refresh_preview_skills()
            self._update_control_states()
            return

        selected_items = [
            item for item in self._settings.skill_items if item.profile_id == profile.id
        ]
        for item in selected_items:
            self._append_skill_row(item)

        self._refresh_preview_skills()
        self._update_control_states()

    def _append_skill_row(self, item: SkillItem) -> None:
        row_index = self.skill_table.rowCount()
        self.skill_table.insertRow(row_index)

        enabled_checkbox = QtWidgets.QCheckBox(self)
        enabled_checkbox.setChecked(item.is_enabled)
        enabled_checkbox.toggled.connect(
            lambda checked, skill_id=item.id: self._update_skill_value(
                skill_id, "is_enabled", bool(checked)
            )
        )
        self.skill_table.setCellWidget(
            row_index,
            _COL_ENABLED,
            self._wrap_centered(enabled_checkbox),
        )

        icon_combo = self._build_icon_combo(item)
        icon_combo.currentIndexChanged.connect(
            lambda _index, combo=icon_combo, skill_id=item.id: self._update_skill_value(
                skill_id,
                "icon_file_name",
                self._combo_data_or_none(combo) or "",
            )
        )
        self.skill_table.setCellWidget(row_index, _COL_ICON, icon_combo)

        duration_spin = QtWidgets.QDoubleSpinBox(self)
        duration_spin.setDecimals(1)
        duration_spin.setSingleStep(0.1)
        duration_spin.setRange(0.0, 600.0)
        duration_spin.setValue(max(0.0, float(item.time_length)))
        duration_spin.valueChanged.connect(
            lambda value, skill_id=item.id: self._update_skill_value(
                skill_id, "time_length", float(value)
            )
        )
        self.skill_table.setCellWidget(row_index, _COL_DURATION, duration_spin)

        select_combo = self._build_key_combo(item.select_key)
        select_combo.currentIndexChanged.connect(
            lambda _index, combo=select_combo, skill_id=item.id: (
                self._update_skill_value(
                    skill_id,
                    "select_key",
                    self._combo_data_or_none(combo),
                )
            )
        )
        self.skill_table.setCellWidget(row_index, _COL_SELECT, select_combo)

        use_combo = self._build_key_combo(item.skill_key)
        use_combo.currentIndexChanged.connect(
            lambda _index, combo=use_combo, skill_id=item.id: self._update_skill_value(
                skill_id,
                "skill_key",
                self._combo_data_or_none(combo),
            )
        )
        self.skill_table.setCellWidget(row_index, _COL_USE, use_combo)

        remove_button = QtWidgets.QPushButton("Remove", self)
        remove_button.clicked.connect(
            lambda _checked=False, skill_id=item.id: self.remove_skill(skill_id)
        )
        self.skill_table.setCellWidget(row_index, _COL_REMOVE, remove_button)

        self.skill_table.setRowHeight(row_index, 46)

    def _build_icon_combo(self, item: SkillItem) -> QtWidgets.QComboBox:
        combo = QtWidgets.QComboBox(self)
        combo.setIconSize(QtCore.QSize(32, 32))
        combo.addItem("(none)", "")

        for icon in self._icon_registry.list_icons():
            combo.addItem(
                QtGui.QIcon(str(icon.path)),
                icon.path.name,
                icon.path.name,
            )

        selected_icon = self._icon_registry.get_icon(item.icon_file_name)
        selected_name = selected_icon.path.name if selected_icon is not None else ""
        if not selected_name and item.icon_file_name:
            selected_name = item.icon_file_name
            combo.addItem(item.icon_file_name, item.icon_file_name)

        selected_index = self._find_combo_data_index(combo, selected_name)
        combo.setCurrentIndex(selected_index if selected_index >= 0 else 0)
        return combo

    def _build_key_combo(self, current_code: str | None) -> QtWidgets.QComboBox:
        combo = QtWidgets.QComboBox(self)
        for entry in self._icon_registry.list_key_entries(include_empty=True):
            label = entry.name if entry.name is not None else "(none)"
            combo.addItem(label, entry.code)
        selected_code = self._validated_key_code(current_code)
        selected_index = self._find_combo_data_index(combo, selected_code)
        if selected_index < 0:
            selected_index = self._find_combo_data_index(combo, None)
        combo.setCurrentIndex(selected_index if selected_index >= 0 else 0)
        return combo

    @staticmethod
    def _find_combo_data_index(combo: QtWidgets.QComboBox, target: str | None) -> int:
        if target is None:
            return combo.findData(None)
        normalized_target = str(target).strip().casefold()
        for index in range(combo.count()):
            value = combo.itemData(index)
            if value is None and not normalized_target:
                return index
            if isinstance(value, str) and value.strip().casefold() == normalized_target:
                return index
        return -1

    @staticmethod
    def _combo_data_or_none(combo: QtWidgets.QComboBox) -> str | None:
        value = combo.currentData()
        if isinstance(value, str):
            normalized = value.strip()
            return normalized or None
        return None

    def _validated_key_code(self, value: Any) -> str | None:
        if value is None:
            return None
        if not isinstance(value, str):
            return None

        normalized = normalize_input_code(value.strip())
        if normalized is None:
            return None

        entry = self._icon_registry.get_key(normalized)
        if entry is None:
            return None
        return entry.code

    @staticmethod
    def _validated_duration(
        value: Any,
        *,
        fallback: float,
    ) -> float:
        try:
            normalized = float(value)
        except (TypeError, ValueError):
            normalized = fallback
        return round(min(600.0, max(0.0, normalized)), 1)

    @staticmethod
    def _wrap_centered(widget: QtWidgets.QWidget) -> QtWidgets.QWidget:
        wrapper = QtWidgets.QWidget()
        layout = QtWidgets.QHBoxLayout(wrapper)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(widget, 0, QtCore.Qt.AlignmentFlag.AlignCenter)
        return wrapper

    def _default_icon_name(self) -> str:
        icons = self._icon_registry.list_icons()
        if not icons:
            return ""
        return icons[0].path.name

    def _update_skill_value(self, skill_id: int, field: str, value: Any) -> None:
        if self._loading_ui:
            return
        item = next(
            (row for row in self._settings.skill_items if row.id == skill_id), None
        )
        if item is None:
            return

        if field == "is_enabled":
            item.is_enabled = bool(value)
        elif field == "icon_file_name":
            item.icon_file_name = str(value or "")
        elif field == "time_length":
            item.time_length = self._validated_duration(
                value,
                fallback=item.time_length,
            )
        elif field == "select_key":
            item.select_key = (
                self._validated_key_code(value) if value is not None else None
            )
        elif field == "skill_key":
            item.skill_key = (
                self._validated_key_code(value) if value is not None else None
            )
        else:
            return

        self._save_settings()
        self._refresh_preview_skills()

    def _save_settings(self) -> None:
        self._settings.ensure_defaults()
        try:
            self._settings_store.save(self._settings)
        except OSError as exc:
            self._handle_runtime_error(f"Save failed: {exc}")

    def _refresh_preview_skills(self) -> None:
        if self._preview_overlay is not None:
            self._preview_overlay.set_skill_items(self.selected_skill_items())

    def _on_profile_selection_changed(self, _index: int) -> None:
        if self._loading_ui:
            return
        profile_id = self.selected_profile_id()
        if profile_id is None:
            return
        self._settings.last_selected_profile_id = profile_id
        self._save_settings()
        self._populate_skill_table()

    def _on_add_profile_clicked(self) -> None:
        name, accepted = QtWidgets.QInputDialog.getText(
            self,
            "Add Profile",
            "Profile name:",
        )
        if accepted:
            self.add_profile(name)

    def _on_rename_profile_clicked(self) -> None:
        profile = self._current_profile()
        if profile is None:
            return
        name, accepted = QtWidgets.QInputDialog.getText(
            self,
            "Rename Profile",
            "Profile name:",
            QtWidgets.QLineEdit.EchoMode.Normal,
            profile.name,
        )
        if accepted:
            self.rename_current_profile(name)

    def _on_remove_profile_clicked(self) -> None:
        profile = self._current_profile()
        if profile is None:
            return
        result = QtWidgets.QMessageBox.question(
            self,
            "Delete Profile",
            self._profile_delete_message(profile),
            QtWidgets.QMessageBox.StandardButton.Yes
            | QtWidgets.QMessageBox.StandardButton.No,
            QtWidgets.QMessageBox.StandardButton.No,
        )
        if result == QtWidgets.QMessageBox.StandardButton.Yes:
            self.remove_current_profile()

    def _replacement_profile_id_after_removal(self, removed_profile_id: int) -> int:
        remaining_profiles = [
            profile
            for profile in self._settings.profiles
            if profile.id != removed_profile_id
        ]
        if not remaining_profiles:
            return 0

        removed_index = next(
            (
                index
                for index, profile in enumerate(self._settings.profiles)
                if profile.id == removed_profile_id
            ),
            len(remaining_profiles) - 1,
        )
        replacement_index = min(removed_index, len(remaining_profiles) - 1)
        return remaining_profiles[replacement_index].id

    def _profile_delete_message(self, profile: Profile) -> str:
        skill_count = sum(
            1 for item in self._settings.skill_items if item.profile_id == profile.id
        )
        skill_label = "skill row" if skill_count == 1 else "skill rows"
        return (
            f"Delete profile '{profile.name}' and its {skill_count} {skill_label}?\n\n"
            "This cannot be undone."
        )

    def _on_add_skill_clicked(self) -> None:
        self.add_skill_to_current_profile()

    def _open_options_dialog(self) -> None:
        if self._options_dialog is None:
            dialog = OptionsDialog(settings=self._settings, parent=self)
            dialog.settings_changed.connect(self._on_options_settings_changed)
            dialog.finished.connect(self._on_options_dialog_finished)
            self._options_dialog = dialog
        self._options_dialog.show()
        self._options_dialog.activateWindow()

    def _on_options_dialog_finished(self, _result: int) -> None:
        self._options_dialog = None

    def _on_options_settings_changed(self) -> None:
        self._save_settings()
        self._apply_overlay_settings_update()

    def _apply_overlay_settings_update(self) -> None:
        countdown_service = self._tracker_runtime.countdown_service
        if countdown_service is not None:
            countdown_service.emit_updates()
        if self._preview_overlay is not None:
            self._preview_overlay.refresh_from_settings()
        if self._runtime_overlay is not None:
            self._runtime_overlay.refresh_from_settings()

    def _toggle_preview(self) -> None:
        if self.is_playing:
            return
        if self.is_preview_visible:
            self._close_preview_overlay()
        else:
            self._open_preview_overlay()
        self._update_control_states()

    def _open_preview_overlay(self) -> None:
        if self._preview_overlay is not None:
            return

        overlay = CooldownOverlayWindow(
            settings=self._settings,
            icon_registry=self._icon_registry,
            preview_mode=True,
        )
        overlay.set_skill_items(self.selected_skill_items())
        overlay.show()
        self._preview_overlay = overlay

    def _close_preview_overlay(self) -> None:
        if self._preview_overlay is None:
            return
        overlay = self._preview_overlay
        self._preview_overlay = None
        self._store_overlay_position(overlay)
        overlay.close()
        overlay.deleteLater()
        self._save_settings()

    def _toggle_playback(self) -> None:
        if self.is_playing:
            self._stop_tracking()
        else:
            self._start_tracking()
        self._update_control_states()

    def _start_tracking(self) -> None:
        if self.is_playing:
            return

        self._close_preview_overlay()
        selected_items = self.selected_skill_items()
        self._save_settings()

        try:
            countdown_service = self._tracker_runtime.start(selected_items)
            overlay = CooldownOverlayWindow(
                settings=self._settings,
                icon_registry=self._icon_registry,
                preview_mode=False,
            )
            overlay.set_skill_items(selected_items)
            overlay.bind_countdown_service(countdown_service)
            overlay.show()
            self._runtime_overlay = overlay
        except Exception as exc:
            self._handle_runtime_error(f"Start failed: {exc}")
            self._dispose_runtime_overlay()
            try:
                self._tracker_runtime.stop()
            except Exception:
                pass

    def _start_tracking_from_settings(self) -> None:
        if not self._settings.start_tracker_on_app_run or self.is_playing:
            return
        self._start_tracking()
        self._update_control_states()

    def _stop_tracking(self) -> None:
        self._dispose_runtime_overlay()
        try:
            self._tracker_runtime.stop()
        except Exception as exc:
            self._handle_runtime_error(f"Stop failed: {exc}")

    def _dispose_runtime_overlay(self) -> None:
        if self._runtime_overlay is None:
            return
        overlay = self._runtime_overlay
        self._runtime_overlay = None
        self._store_overlay_position(overlay)
        overlay.unbind_countdown_service()
        overlay.close()
        overlay.deleteLater()
        self._save_settings()

    def _store_overlay_position(self, overlay: CooldownOverlayWindow) -> None:
        position = overlay.pos()
        self._settings.tracker_x = int(position.x())
        self._settings.tracker_y = int(position.y())

    @QtCore.Slot(str)
    def _handle_runtime_error(self, message: str) -> None:
        if not message:
            return
        self.status_label.setText(message)

    def _update_control_states(self) -> None:
        is_playing = self.is_playing
        is_preview = self.is_preview_visible

        self.play_button.setText("Stop" if is_playing else "Play")
        self.preview_button.setText("Hide Preview" if is_preview else "Preview")
        self.preview_button.setEnabled(not is_playing)

        configure_enabled = not is_playing
        self.profile_combo.setEnabled(configure_enabled)
        self.add_profile_button.setEnabled(configure_enabled)
        self.rename_profile_button.setEnabled(
            configure_enabled and self.profile_combo.count() > 0
        )
        self.remove_profile_button.setEnabled(
            configure_enabled and self.profile_combo.count() > 1
        )
        self.add_skill_button.setEnabled(
            configure_enabled and self._current_profile() is not None
        )
        self.skill_table.setEnabled(configure_enabled)

        if is_playing:
            self.status_label.setText("Running")
        elif is_preview:
            self.status_label.setText("Previewing")
        elif "failed" not in self.status_label.text().lower():
            self.status_label.setText("Idle")


__all__ = ["MainWindow"]
