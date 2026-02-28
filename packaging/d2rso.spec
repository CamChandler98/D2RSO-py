# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules


spec_dir = Path(SPEC).resolve().parent
project_root = spec_dir.parent
src_root = project_root / "src"
assets_root = project_root / "assets" / "skills"

datas = []
if assets_root.exists():
    datas.append((str(assets_root), "assets/skills"))

hiddenimports = sorted(
    set(collect_submodules("pygame") + collect_submodules("pynput"))
)


a = Analysis(
    [str(src_root / "d2rso" / "__main__.py")],
    pathex=[str(src_root)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="d2rso",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="d2rso",
)
