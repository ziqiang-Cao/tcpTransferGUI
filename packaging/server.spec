# -*- mode: python ; coding: utf-8 -*-

import sys
from pathlib import Path


project_root = Path(SPECPATH).parent
entry_script = project_root / "Server" / "server_main.py"

a = Analysis(
    [str(entry_script)],
    pathex=[str(project_root)],
    binaries=[],
    datas=[
        (str(project_root / "assets" / "branding" / "app_icon.png"), "assets/branding"),
    ],
    hiddenimports=[
        "PyQt5.sip",
        "Client",
        "Client.src",
        "Client.src.core",
        "Client.src.ui",
        "Server",
        "Server.src",
        "Server.src.core",
        "Server.src.ui",
        "common",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)
icon_file = project_root / "assets" / "branding" / ("app_icon.ico" if sys.platform == "win32" else "app_icon.png")

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="tcpTransServer",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    icon=str(icon_file),
    codesign_identity=None,
    entitlements_file=None,
)
