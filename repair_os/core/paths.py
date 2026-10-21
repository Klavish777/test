"""Пути приложения: база, документы, прошивки, резервные копии, логи.

Каталог данных можно переопределить:
  * переменной окружения ``REPAIR_OS_DATA``;
  * аргументом командной строки ``--data-dir`` (см. ``repair_os.app``).

Модуль намеренно не зависит от Qt, чтобы его можно было использовать в тестах
и в консольных утилитах.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path

from repair_os.version import APP_ID

APP_DIR_NAME = "SmartphoneRepairOS"


def _default_data_root() -> Path:
    override = os.environ.get("REPAIR_OS_DATA")
    if override:
        return Path(override).expanduser().resolve()

    if sys.platform.startswith("win"):
        base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
        if base:
            return Path(base) / APP_DIR_NAME
        return Path.home() / "AppData" / "Local" / APP_DIR_NAME
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / APP_DIR_NAME
    base = os.environ.get("XDG_DATA_HOME")
    root = Path(base) if base else Path.home() / ".local" / "share"
    return root / APP_ID


@dataclass(frozen=True)
class AppPaths:
    """Набор каталогов, используемых приложением."""

    root: Path

    @property
    def db_dir(self) -> Path:
        return self.root / "db"

    @property
    def database(self) -> Path:
        return self.db_dir / "repair_os.sqlite3"

    @property
    def firmware_dir(self) -> Path:
        return self.root / "firmware"

    @property
    def library_dir(self) -> Path:
        return self.root / "library"

    @property
    def boards_dir(self) -> Path:
        return self.root / "boards"

    @property
    def backups_dir(self) -> Path:
        return self.root / "backups"

    @property
    def logs_dir(self) -> Path:
        return self.root / "logs"

    @property
    def cache_dir(self) -> Path:
        return self.root / "cache"

    def all_dirs(self) -> tuple[Path, ...]:
        return (
            self.root,
            self.db_dir,
            self.firmware_dir,
            self.library_dir,
            self.boards_dir,
            self.backups_dir,
            self.logs_dir,
            self.cache_dir,
        )

    def ensure(self) -> "AppPaths":
        for directory in self.all_dirs():
            directory.mkdir(parents=True, exist_ok=True)
        return self


def default_paths() -> AppPaths:
    return AppPaths(_default_data_root())


def build_paths(root: str | os.PathLike[str] | None = None) -> AppPaths:
    return AppPaths(Path(root).expanduser().resolve() if root else _default_data_root())


def app_resource_dir() -> Path:
    """Каталог с ресурсами, поставляемыми вместе с приложением.

    Работает и при запуске из исходников, и в сборке PyInstaller (``_MEIPASS``).
    """
    if getattr(sys, "frozen", False):
        meipass = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
        candidate = meipass / "repair_os"
        if candidate.exists():
            return candidate
        return meipass
    return Path(__file__).resolve().parent.parent
