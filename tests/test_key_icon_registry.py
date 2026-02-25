from pathlib import Path

from d2rso.key_icon_registry import KeyEntry, KeyIconRegistry

_PNG_1X1 = bytes.fromhex(
    "89504E470D0A1A0A0000000D49484452000000010000000108060000001F15C489"
    "0000000A49444154789C6360000000020001E221BC330000000049454E44AE426082"
)


def test_key_dropdown_entries_cover_keyboard_mouse_gamepad():
    catalog = KeyIconRegistry(assets_dir=Path("does-not-exist"))

    assert catalog.available_keys[0] == KeyEntry(name="A", code="A")
    assert catalog.get_key("F8") == KeyEntry(name="F8", code="F8")
    assert catalog.get_key("mouse2") == KeyEntry(name="MOUSE2", code="MOUSE2")
    assert catalog.get_key("buttons7") == KeyEntry(
        name="GamePad Button 7",
        code="Buttons7",
    )
    assert catalog.available_keys[-1] == KeyEntry(name=None, code=None)


def test_icon_registry_loads_assets_and_supports_lookup_by_name_and_path(tmp_path):
    assets_dir = tmp_path / "assets" / "skills"
    assets_dir.mkdir(parents=True)

    orb = assets_dir / "orb.png"
    orb.write_bytes(_PNG_1X1)
    shield = assets_dir / "Shield.PNG"
    shield.write_bytes(_PNG_1X1)
    (assets_dir / "corrupt.png").write_bytes(b"not-a-real-image")
    (assets_dir / "ignore.txt").write_text("not an image", encoding="utf-8")

    catalog = KeyIconRegistry(assets_dir=assets_dir)
    loaded = catalog.list_icons()

    assert len(loaded) == 2
    assert {item.path.name for item in loaded} == {"orb.png", "Shield.PNG"}

    by_name = catalog.get_icon("orb.png")
    assert by_name is not None
    assert by_name.path == orb.resolve()
    assert by_name.data == _PNG_1X1

    by_path = catalog.get_icon(str(shield.resolve()))
    assert by_path is not None
    assert by_path.path == shield.resolve()
    assert catalog.get_icon_bytes("shield.png") == _PNG_1X1
    assert catalog.get_icon_path("shield.png") == shield.resolve()


def test_missing_icon_paths_fail_gracefully(tmp_path):
    catalog = KeyIconRegistry(assets_dir=tmp_path / "assets" / "skills")

    assert catalog.list_icons() == ()
    assert catalog.get_icon("missing.png") is None
    assert catalog.get_icon_path("missing.png") is None
    assert catalog.get_icon_bytes("missing.png") is None
