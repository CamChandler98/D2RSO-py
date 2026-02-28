"""Dedicated dialog for runtime and overlay presentation settings."""

from __future__ import annotations

from PySide6 import QtCore, QtWidgets

from .models import Settings

_MIN_SCALE_PERCENT = 50
_MAX_SCALE_PERCENT = 200


class OptionsDialog(QtWidgets.QDialog):
    """Modeless settings dialog that persists changes through the main window."""

    settings_changed = QtCore.Signal()

    def __init__(
        self,
        *,
        settings: Settings,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._settings = settings
        self._loading_ui = False

        self._init_window()
        self._init_layout()
        self._load_settings()

    def _init_window(self) -> None:
        self.setWindowTitle("Options")
        self.setModal(False)
        self.resize(420, 320)

    def _init_layout(self) -> None:
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(10)

        form = QtWidgets.QFormLayout()
        form.setLabelAlignment(
            QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter
        )
        form.setFormAlignment(QtCore.Qt.AlignmentFlag.AlignTop)
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(10)

        self.insert_left_checkbox = QtWidgets.QCheckBox(
            "Insert new trackers on left", self
        )
        self.insert_left_checkbox.toggled.connect(self._on_insert_left_toggled)
        form.addRow("Insert Left", self.insert_left_checkbox)

        self.vertical_checkbox = QtWidgets.QCheckBox("Stack trackers vertically", self)
        self.vertical_checkbox.toggled.connect(self._on_vertical_toggled)
        form.addRow("Layout", self.vertical_checkbox)

        self.show_digits_checkbox = QtWidgets.QCheckBox("Show countdown digits", self)
        self.show_digits_checkbox.toggled.connect(self._on_show_digits_toggled)
        form.addRow("Show Digits", self.show_digits_checkbox)

        self.start_on_launch_checkbox = QtWidgets.QCheckBox(
            "Start tracker when the app opens",
            self,
        )
        self.start_on_launch_checkbox.toggled.connect(self._on_start_on_launch_toggled)
        form.addRow("Start On Launch", self.start_on_launch_checkbox)

        self.minimize_to_tray_checkbox = QtWidgets.QCheckBox(
            "Hide the app in the system tray when minimized",
            self,
        )
        self.minimize_to_tray_checkbox.toggled.connect(
            self._on_minimize_to_tray_toggled
        )
        form.addRow("Minimize To Tray", self.minimize_to_tray_checkbox)

        scale_row = QtWidgets.QHBoxLayout()
        scale_row.setContentsMargins(0, 0, 0, 0)
        scale_row.setSpacing(8)

        self.scale_slider = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal, self)
        self.scale_slider.setRange(_MIN_SCALE_PERCENT, _MAX_SCALE_PERCENT)
        self.scale_slider.setSingleStep(5)
        self.scale_slider.setPageStep(10)
        self.scale_slider.setTickPosition(QtWidgets.QSlider.TickPosition.TicksBelow)
        self.scale_slider.setTickInterval(25)
        self.scale_slider.valueChanged.connect(self._on_scale_changed)
        scale_row.addWidget(self.scale_slider, 1)

        self.scale_value_label = QtWidgets.QLabel("100%", self)
        self.scale_value_label.setMinimumWidth(48)
        self.scale_value_label.setAlignment(
            QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignVCenter
        )
        scale_row.addWidget(self.scale_value_label)

        scale_wrapper = QtWidgets.QWidget(self)
        scale_wrapper.setLayout(scale_row)
        form.addRow("Scale", scale_wrapper)

        self.red_overlay_seconds_spin = QtWidgets.QSpinBox(self)
        self.red_overlay_seconds_spin.setRange(0, 600)
        self.red_overlay_seconds_spin.setSingleStep(1)
        self.red_overlay_seconds_spin.setToolTip(
            "Apply the red warning overlay when remaining seconds are at or below this value."
        )
        self.red_overlay_seconds_spin.valueChanged.connect(
            self._on_red_overlay_seconds_changed
        )
        form.addRow("Red Threshold", self.red_overlay_seconds_spin)

        root.addLayout(form)
        root.addStretch(1)

        buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Close,
            parent=self,
        )
        buttons.rejected.connect(self.close)
        buttons.accepted.connect(self.close)
        root.addWidget(buttons)

    def _load_settings(self) -> None:
        self._loading_ui = True
        try:
            self.insert_left_checkbox.setChecked(
                bool(self._settings.is_tracker_insert_to_left)
            )
            self.vertical_checkbox.setChecked(bool(self._settings.is_tracker_vertical))
            self.show_digits_checkbox.setChecked(
                bool(self._settings.show_digits_in_tracker)
            )
            self.start_on_launch_checkbox.setChecked(
                bool(self._settings.start_tracker_on_app_run)
            )
            self.minimize_to_tray_checkbox.setChecked(
                bool(self._settings.minimize_to_tray)
            )
            scale_percent = int(round(float(self._settings.form_scale_x) * 100))
            self.scale_slider.setValue(
                max(_MIN_SCALE_PERCENT, min(_MAX_SCALE_PERCENT, scale_percent))
            )
            self.scale_value_label.setText(f"{self.scale_slider.value()}%")
            self.red_overlay_seconds_spin.setValue(
                int(self._settings.red_overlay_seconds_effective)
            )
        finally:
            self._loading_ui = False

    def _emit_settings_changed(self) -> None:
        if not self._loading_ui:
            self.settings_changed.emit()

    def _on_insert_left_toggled(self, checked: bool) -> None:
        self._settings.is_tracker_insert_to_left = bool(checked)
        self._emit_settings_changed()

    def _on_vertical_toggled(self, checked: bool) -> None:
        self._settings.is_tracker_vertical = bool(checked)
        self._emit_settings_changed()

    def _on_show_digits_toggled(self, checked: bool) -> None:
        self._settings.show_digits_in_tracker = bool(checked)
        self._emit_settings_changed()

    def _on_start_on_launch_toggled(self, checked: bool) -> None:
        self._settings.start_tracker_on_app_run = bool(checked)
        self._emit_settings_changed()

    def _on_minimize_to_tray_toggled(self, checked: bool) -> None:
        self._settings.minimize_to_tray = bool(checked)
        self._emit_settings_changed()

    def _on_scale_changed(self, value: int) -> None:
        normalized = max(_MIN_SCALE_PERCENT, min(_MAX_SCALE_PERCENT, int(value)))
        scale = round(normalized / 100.0, 2)
        self._settings.form_scale_x = scale
        self._settings.form_scale_y = scale
        self.scale_value_label.setText(f"{normalized}%")
        self._emit_settings_changed()

    def _on_red_overlay_seconds_changed(self, value: int) -> None:
        self._settings.red_overlay_seconds = max(0, int(value))
        self._emit_settings_changed()


__all__ = ["OptionsDialog"]
