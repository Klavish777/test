"""Загрузка SQL-миграций схемы.

Миграции читаются из каталога ``repair_os/data/migrations`` в порядке номеров.
Файлы должны называться ``<номер>_<имя>.sql``. Добавление новой миграции —
единственный поддерживаемый способ изменить схему.
"""

from __future__ import annotations

import hashlib
import logging
import re
from pathlib import Path

from repair_os.core.paths import app_resource_dir

log = logging.getLogger(__name__)

_MIGRATION_RE = re.compile(r"^(\d{3})_([A-Za-z0-9_\-]+)\.sql$")


def migrations_dir() -> Path:
    return app_resource_dir() / "data" / "migrations"


def load_migrations(directory: Path | None = None) -> list[tuple[int, str, str]]:
    base = Path(directory) if directory else migrations_dir()
    if not base.exists():
        log.error("Каталог миграций не найден: %s", base)
        return []
    found: list[tuple[int, str, str]] = []
    for path in sorted(base.glob("*.sql")):
        match = _MIGRATION_RE.match(path.name)
        if not match:
            log.warning("Пропущен файл миграции с некорректным именем: %s", path.name)
            continue
        version = int(match.group(1))
        name = match.group(2)
        sql = path.read_text(encoding="utf-8")
        found.append((version, name, sql))
    versions = [item[0] for item in found]
    if len(set(versions)) != len(versions):
        raise RuntimeError("Дублирующиеся версии миграций в каталоге")
    found.sort(key=lambda item: item[0])
    return found


def checksums(migrations: list[tuple[int, str, str]]) -> dict[int, str]:
    return {
        version: hashlib.sha256(sql.encode("utf-8")).hexdigest()
        for version, _name, sql in migrations
    }


MIGRATIONS: list[tuple[int, str, str]] = load_migrations()
MIGRATION_CHECKSUMS: dict[int, str] = checksums(MIGRATIONS)
