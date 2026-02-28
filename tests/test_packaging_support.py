import d2rso.key_icon_registry as key_icon_registry_module
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
