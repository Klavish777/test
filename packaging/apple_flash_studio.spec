# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller-спецификация для сборки Apple Flash Studio (Windows 10/11 x64).

Сборка:
    pyinstaller packaging/apple_flash_studio.spec --noconfirm --clean

Результат:
    dist/AppleFlashStudio/AppleFlashStudio.exe
"""

from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules

PROJECT_ROOT = Path(SPECPATH).resolve().parent  # noqa: F821

icon_file = PROJECT_ROOT / "apple_flash" / "resources" / "apple_flash.ico"
icon_arg = str(icon_file) if icon_file.is_file() else None

datas = [
    (str(PROJECT_ROOT / "apple_flash" / "resources"), "apple_flash/resources"),
]
doc_path = PROJECT_ROOT / "docs" / "APPLE_FLASH_STUDIO.md"
if doc_path.is_file():
    datas.append((str(doc_path), "docs"))

hiddenimports = collect_submodules("apple_flash")

a = Analysis(  # noqa: F821
    [str(PROJECT_ROOT / "apple_flash_main.py")],
    pathex=[str(PROJECT_ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=[
        "tkinter",
        "matplotlib",
        "numpy",
        "pandas",
        "PySide6.Qt3DAnimation",
        "PySide6.Qt3DCore",
        "PySide6.Qt3DExtras",
        "PySide6.Qt3DInput",
        "PySide6.Qt3DLogic",
        "PySide6.Qt3DRender",
        "PySide6.QtCharts",
        "PySide6.QtDataVisualization",
        "PySide6.QtMultimedia",
        "PySide6.QtWebEngineCore",
        "PySide6.QtWebEngineWidgets",
        "PySide6.QtQuick",
        "PySide6.QtQml",
    ],
    noarchive=False,
)

pyz = PYZ(a.pure)  # noqa: F821

exe = EXE(  # noqa: F821
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="AppleFlashStudio",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    icon=icon_arg,
)

coll = COLLECT(  # noqa: F821
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="AppleFlashStudio",
)
