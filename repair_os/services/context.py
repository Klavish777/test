"""Контекст приложения: единая точка доступа к базе и сервисам.

Интерфейс не работает с SQLite напрямую — только через этот контекст, поэтому
логику легко тестировать без GUI и заменять реализации.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from repair_os.core.logging_setup import setup_logging
from repair_os.core.paths import AppPaths, build_paths
from repair_os.data.database import Database, open_database
from repair_os.data.repositories.boards import BoardRepository
from repair_os.data.repositories.brands import BrandRepository
from repair_os.data.repositories.devices import DeviceRepository
from repair_os.data.repositories.firmware import FirmwareRepository
from repair_os.data.repositories.library import LibraryRepository
from repair_os.data.repositories.settings import SettingsRepository
from repair_os.seed.demo_data import DemoSeeder, count_demo
from repair_os.services.backup import BackupService
from repair_os.services.board_packages import BoardPackageService
from repair_os.services.firmware_tools import FirmwareTools
from repair_os.services.import_export import ImportService
from repair_os.services.search import SearchService

log = logging.getLogger(__name__)


@dataclass
class AppContext:
    paths: AppPaths
    db: Database
    settings: SettingsRepository
    brands: BrandRepository
    devices: DeviceRepository
    firmware: FirmwareRepository
    boards: BoardRepository
    library: LibraryRepository
    search: SearchService
    backup: BackupService
    imports: ImportService
    packages: BoardPackageService
    firmware_tools: FirmwareTools
    seeder: DemoSeeder

    # ------------------------------------------------------------------ создание
    @classmethod
    def create(
        cls,
        data_root: str | Path | None = None,
        *,
        seed_demo: bool = True,
        log_level: int = logging.INFO,
    ) -> "AppContext":
        paths = build_paths(data_root).ensure()
        setup_logging(paths.logs_dir, level=log_level)
        db = open_database(paths.database)
        log.info("Каталог данных: %s (схема v%s)", paths.root, db.schema_version())

        settings = SettingsRepository(db)
        library_root = _resolve_dir(settings.get("library_root"), paths.library_dir)
        firmware_root = _resolve_dir(settings.get("firmware_root"), paths.firmware_dir)
        boards_root = _resolve_dir(settings.get("boards_root"), paths.boards_dir)
        for directory in (library_root, firmware_root, boards_root):
            directory.mkdir(parents=True, exist_ok=True)

        context = cls(
            paths=paths,
            db=db,
            settings=settings,
            brands=BrandRepository(db),
            devices=DeviceRepository(db),
            firmware=FirmwareRepository(db),
            boards=BoardRepository(db),
            library=LibraryRepository(db),
            search=SearchService(db),
            backup=BackupService(db, paths.backups_dir, attachments_dir=library_root),
            imports=ImportService(db),
            packages=BoardPackageService(db, boards_root),
            firmware_tools=FirmwareTools(db, firmware_root),
            seeder=DemoSeeder(db, paths),
        )
        if seed_demo and not context.seeder.is_seeded():
            log.info("Первичная загрузка демонстрационных данных")
            context.seeder.seed()
        return context

    # ------------------------------------------------------------------ удобное
    def demo_counts(self) -> dict[str, int]:
        return count_demo(self.db)

    def library_root(self) -> Path:
        return _resolve_dir(self.settings.get("library_root"), self.paths.library_dir)

    def close(self) -> None:
        self.db.close()

    def describe(self) -> dict[str, str]:
        return {
            "data_dir": str(self.paths.root),
            "database": str(self.paths.database),
            "schema": str(self.db.schema_version()),
            "devices": str(self.devices.count()),
            "brands": str(self.brands.count()),
        }


def _resolve_dir(value: object, fallback: Path) -> Path:
    if isinstance(value, str) and value.strip():
        candidate = Path(value).expanduser()
        try:
            candidate.mkdir(parents=True, exist_ok=True)
            return candidate
        except OSError:
            log.warning("Каталог из настроек недоступен: %s", value)
    return fallback
