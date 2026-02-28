import d2rso.key_icon_registry as key_icon_registry_module
import d2rso.main as main_module
from d2rso.key_icon_registry import KeyIconRegistry
from d2rso.main import _get_auto_exit_delay_ms


def test_key_icon_registry_uses_assets_override_env_var(monkeypatch, tmp_path):
    assets_dir = tmp_path / "custom-assets"
    monkeypatch.setenv("D2RSO_ASSETS_DIR", str(assets_dir))

    registry = KeyIconRegistry()

    assert registry.assets_dir == assets_dir


def test_key_icon_registry_uses_pyinstaller_bundle_assets(monkeypatch, tmp_path):
    bundle_root = tmp_path / "bundle"
    assets_dir = bundle_root / "assets" / "skills"
    assets_dir.mkdir(parents=True)

    monkeypatch.delenv("D2RSO_ASSETS_DIR", raising=False)
    monkeypatch.setattr(
        key_icon_registry_module.sys,
        "_MEIPASS",
        str(bundle_root),
        raising=False,
    )

    registry = KeyIconRegistry()

    assert registry.assets_dir == assets_dir


def test_auto_exit_delay_reads_positive_milliseconds(monkeypatch):
    monkeypatch.setenv("D2RSO_AUTO_EXIT_MS", "1200")

    assert _get_auto_exit_delay_ms() == 1200


def test_auto_exit_delay_ignores_invalid_values(monkeypatch):
    for raw_value in ("0", "-10", "not-a-number"):
        monkeypatch.setenv("D2RSO_AUTO_EXIT_MS", raw_value)
        assert _get_auto_exit_delay_ms() is None


def test_run_auto_exit_uses_window_shutdown_path(monkeypatch):
    scheduled: list[tuple[int, object]] = []

    class _FakeApp:
        @staticmethod
        def instance():
            return None

        def __init__(self, _argv) -> None:
            self.exec_count = 0

        def exec(self) -> int:
            self.exec_count += 1
            return 0

    class _FakeWindow:
        def __init__(self) -> None:
            self.show_count = 0
            self.exit_count = 0

        def show(self) -> None:
            self.show_count += 1

        def exit_to_desktop(self) -> None:
            self.exit_count += 1

    window = _FakeWindow()

    monkeypatch.setenv("D2RSO_AUTO_EXIT_MS", "1200")
    monkeypatch.setattr(main_module.QtWidgets, "QApplication", _FakeApp)
    monkeypatch.setattr(main_module, "build_window", lambda: window)
    monkeypatch.setattr(
        main_module.QtCore.QTimer,
        "singleShot",
        lambda delay_ms, callback: scheduled.append((delay_ms, callback)),
    )

    main_module.run()

    assert window.show_count == 1
    assert len(scheduled) == 1
    assert scheduled[0][0] == 1200
    assert scheduled[0][1] == window.exit_to_desktop
    assert window.exit_count == 0
