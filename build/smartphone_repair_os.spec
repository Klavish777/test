# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller-спецификация для сборки Smartphone Repair OS (Windows/Linux).

Сборка:
    pyinstaller build/smartphone_repair_os.spec --noconfirm --clean

Результат: dist/SmartphoneRepairOS/SmartphoneRepairOS.exe (+ каталог с зависимостями).
"""

from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules

# ВАЖНО: SPECPATH в PyInstaller — это каталог со spec-файлом, а не сам файл.
# Раньше корень проекта вычислялся на уровень выше (/home/user вместо /home/user/test),
# из-за чего сборка падала с "script '.../main.py' not found".
_SPEC_DIR = Path(SPECPATH).resolve()  # noqa: F821 - переменная PyInstaller
if _SPEC_DIR.is_file():
    _SPEC_DIR = _SPEC_DIR.parent
PROJECT_ROOT = _SPEC_DIR.parent if (_SPEC_DIR.parent / "main.py").is_file() else _SPEC_DIR
ROOT = PROJECT_ROOT

datas = [
    (str(PROJECT_ROOT / "repair_os" / "data" / "migrations"), "repair_os/data/migrations"),
    (str(PROJECT_ROOT / "repair_os" / "resources"), "repair_os/resources"),
    (str(PROJECT_ROOT / "repair_os" / "seed" / "assets"), "repair_os/seed/assets"),
    (str(PROJECT_ROOT / "docs"), "docs"),
    (str(PROJECT_ROOT / "README.md"), "."),
]

hiddenimports = collect_submodules("repair_os")

a = Analysis(  # noqa: F821
    [str(PROJECT_ROOT / "main.py")],
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
    name="SmartphoneRepairOS",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    icon=None,
)

coll = COLLECT(  # noqa: F821
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="SmartphoneRepairOS",
)
