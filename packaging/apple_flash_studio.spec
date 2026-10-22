# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller-спецификация для сборки Apple Flash Studio v2.0 (Windows 10/11 x64).

Включает встроенный движок pymobiledevice3, библиотеку libusb-1.0.dll (libusb_package),
парсер IPSW/IMG4, компрессоры lzfse/lzss и корневые сертификаты SSL для Apple TSS.

Сборка:
    pyinstaller packaging/apple_flash_studio.spec --noconfirm --clean

Результат:
    dist/AppleFlashStudio/AppleFlashStudio.exe
"""

import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_all, collect_data_files, collect_submodules, copy_metadata

PROJECT_ROOT = Path(SPECPATH).resolve().parent  # noqa: F821

icon_file = PROJECT_ROOT / "apple_flash" / "resources" / "apple_flash.ico"
icon_arg = str(icon_file) if icon_file.is_file() else None

datas = [
    (str(PROJECT_ROOT / "apple_flash" / "resources"), "apple_flash/resources"),
]
binaries = []

doc_path = PROJECT_ROOT / "docs" / "APPLE_FLASH_STUDIO.md"
if doc_path.is_file():
    datas.append((str(doc_path), "docs"))

# Встраиваем libusb-1.0.dll / .so и сертификаты CA для подписи Apple TSS (gs.apple.com)
for pkg_all in ("libusb_package", "certifi"):
    d, b, _h = collect_all(pkg_all)
    datas.extend(d)
    binaries.extend(b)

datas.extend(collect_data_files("pymobiledevice3", include_py_files=False))

for meta_pkg in ("pymobiledevice3", "libusb_package", "ipsw_parser", "pyimg4", "certifi"):
    try:
        datas.extend(copy_metadata(meta_pkg))
    except Exception:
        pass

hiddenimports = (
    collect_submodules("apple_flash")
    + collect_submodules("pymobiledevice3.restore")
    + collect_submodules("pymobiledevice3.osu")
    + collect_submodules("ipsw_parser")
    + collect_submodules("pyimg4")
    + collect_submodules("usb")
    + [
        "pymobiledevice3",
        "pymobiledevice3.usbmux",
        "pymobiledevice3.lockdown",
        "pymobiledevice3.lockdown_service_provider",
        "pymobiledevice3.service_connection",
        "pymobiledevice3.irecv",
        "pymobiledevice3.irecv_devices",
        "pymobiledevice3.progress",
        "pymobiledevice3.exceptions",
        "pymobiledevice3.services.diagnostics",
        "libusb_package",
        "certifi",
        "asn1",
        "lzfse",
        "lzss",
        "bytestruct",
        "remotezip2",
    ]
)

if sys.platform == "win32":
    hiddenimports.extend(["win32security", "win32api", "pywintypes"])

a = Analysis(  # noqa: F821
    [str(PROJECT_ROOT / "apple_flash_main.py")],
    pathex=[str(PROJECT_ROOT)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=[
        "tkinter",
        "matplotlib",
        "numpy",
        "pandas",
        "scipy",
        "IPython",
        "jedi",
        "parso",
        "fastapi",
        "uvicorn",
        "starlette",
        "av",
        "PIL",
        "typer",
        "pytest",
        "pymobiledevice3.cli",
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
