"""Подключение к SQLite, миграции схемы и обслуживание базы."""

from __future__ import annotations

import hashlib
import logging
import sqlite3
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from repair_os.core.errors import BackupError, RepairOSError
from repair_os.core.paths import app_resource_dir
from repair_os.data.migrations import MIGRATIONS, MIGRATION_CHECKSUMS

log = logging.getLogger(__name__)

MIGRATION_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    version     INTEGER PRIMARY KEY,
    name        TEXT NOT NULL,
    checksum    TEXT NOT NULL,
    applied_at  TEXT NOT NULL DEFAULT (datetime('now'))
);
"""


class Database:
    """Тонкая обёртка над sqlite3 с thread-local соединениями."""

    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._local = threading.local()
        self._lock = threading.Lock()

    # ------------------------------------------------------------------ соединения
    def connection(self) -> sqlite3.Connection:
        conn = getattr(self._local, "conn", None)
        if conn is not None:
            return conn
        conn = sqlite3.connect(self.path, timeout=15, isolation_level=None)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA synchronous = NORMAL")
        conn.execute("PRAGMA temp_store = MEMORY")
        self._local.conn = conn
        return conn

    def close(self) -> None:
        conn = getattr(self._local, "conn", None)
        if conn is not None:
            conn.close()
            self._local.conn = None

    # ------------------------------------------------------------------ запросы
    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        conn = self.connection()
        conn.execute("BEGIN IMMEDIATE")
        try:
            yield conn
        except BaseException:
            conn.execute("ROLLBACK")
            raise
        else:
            conn.execute("COMMIT")

    def execute(self, sql: str, params: tuple[Any, ...] | dict[str, Any] = ()) -> sqlite3.Cursor:
        return self.connection().execute(sql, params)

    def executemany(self, sql: str, seq: list[tuple[Any, ...]]) -> sqlite3.Cursor:
        with self.transaction() as conn:
            return conn.executemany(sql, seq)

    def query(self, sql: str, params: tuple[Any, ...] | dict[str, Any] = ()) -> list[dict[str, Any]]:
        cursor = self.connection().execute(sql, params)
        rows = cursor.fetchall()
        cursor.close()
        return [dict(row) for row in rows]

    def query_one(
        self, sql: str, params: tuple[Any, ...] | dict[str, Any] = ()
    ) -> dict[str, Any] | None:
        cursor = self.connection().execute(sql, params)
        row = cursor.fetchone()
        cursor.close()
        return dict(row) if row else None

    def scalar(self, sql: str, params: tuple[Any, ...] | dict[str, Any] = ()) -> Any:
        cursor = self.connection().execute(sql, params)
        row = cursor.fetchone()
        cursor.close()
        if row is None:
            return None
        return row[0]

    def table_count(self, table: str) -> int:
        if not table.replace("_", "").isalnum():
            raise ValueError(f"Некорректное имя таблицы: {table}")
        return int(self.scalar(f"SELECT COUNT(*) FROM {table}") or 0)

    # ------------------------------------------------------------------ миграции
    def migrate(self) -> int:
        """Применяет неприменённые миграции, проверяя контрольные суммы."""
        with self._lock:
            conn = self.connection()
            conn.execute(MIGRATION_TABLE_SQL)
            applied = {
                row["version"]: row["checksum"]
                for row in conn.execute("SELECT version, checksum FROM schema_migrations")
            }
            for version, name, sql in MIGRATIONS:
                expected = MIGRATION_CHECKSUMS.get(version)
                if version in applied:
                    if expected and applied[version] != expected:
                        log.warning(
                            "Контрольная сумма миграции %s изменилась — вероятно, файл правили вручную",
                            version,
                        )
                    continue
                log.info("Применение миграции %s (%s)", version, name)
                digest = expected or _checksum(sql)
                safe_name = name.replace("'", "")
                script = (
                    "BEGIN IMMEDIATE;\n"
                    f"{sql}\n;\n"
                    "INSERT INTO schema_migrations (version, name, checksum) "
                    f"VALUES ({int(version)}, '{safe_name}', '{digest}');\n"
                    "COMMIT;"
                )
                try:
                    conn.executescript(script)
                except sqlite3.Error as exc:
                    try:
                        conn.execute("ROLLBACK")
                    except sqlite3.Error:
                        pass
                    raise RepairOSError(f"Ошибка миграции {version}: {exc}") from exc
            return int(self.scalar("SELECT COALESCE(MAX(version), 0) FROM schema_migrations") or 0)

    def schema_version(self) -> int:
        try:
            return int(self.scalar("SELECT COALESCE(MAX(version), 0) FROM schema_migrations") or 0)
        except sqlite3.Error:
            return 0

    # ------------------------------------------------------------------ обслуживание
    def integrity_check(self) -> bool:
        result = self.scalar("PRAGMA integrity_check")
        return str(result).lower() == "ok"

    def vacuum(self) -> None:
        self.connection().execute("VACUUM")

    def backup_database(self, destination: Path | str) -> Path:
        """Создаёт консистентную копию базы средствами SQLite backup API."""
        dest = Path(destination)
        dest.parent.mkdir(parents=True, exist_ok=True)
        target = sqlite3.connect(dest)
        try:
            self.connection().backup(target)
        finally:
            target.close()
        if not dest.exists() or dest.stat().st_size == 0:
            raise BackupError("Резервная копия базы данных не создана")
        return dest

    def restore_database(self, source: Path | str, *, safety_copy: Path | None = None) -> None:
        """Восстанавливает базу из резервной копии с проверкой целостности."""
        src = Path(source)
        if not src.exists():
            raise BackupError(f"Файл резервной копии не найден: {src}")
        try:
            probe = sqlite3.connect(f"file:{src}?mode=ro", uri=True)
        except sqlite3.DatabaseError as exc:
            raise BackupError(f"Файл не является базой данных: {exc}") from exc
        try:
            check = probe.execute("PRAGMA integrity_check").fetchone()
            if not check or str(check[0]).lower() != "ok":
                raise BackupError("Резервная копия повреждена (integrity_check не пройден)")
            has_migrations = probe.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='schema_migrations'"
            ).fetchone()
            if not has_migrations:
                raise BackupError("Файл не является базой Smartphone Repair OS")
            version = probe.execute("SELECT COALESCE(MAX(version), 0) FROM schema_migrations").fetchone()
            if version and int(version[0]) > MIGRATIONS[-1][0]:
                raise BackupError(
                    "База создана более новой версией приложения — восстановление невозможно"
                )
        except sqlite3.DatabaseError as exc:
            raise BackupError(f"Файл не является базой данных: {exc}") from exc
        finally:
            probe.close()

        if safety_copy is not None:
            self.backup_database(safety_copy)

        self.close()
        src_conn = sqlite3.connect(f"file:{src}?mode=ro", uri=True)
        dst_conn = sqlite3.connect(self.path)
        try:
            src_conn.backup(dst_conn)
        finally:
            src_conn.close()
            dst_conn.close()
        self.migrate()


def _checksum(sql: str) -> str:
    return hashlib.sha256(sql.encode("utf-8")).hexdigest()


def default_migrations_dir() -> Path:
    return app_resource_dir() / "data" / "migrations"


def open_database(path: Path | str, *, run_migrations: bool = True) -> Database:
    db = Database(path)
    if run_migrations:
        db.migrate()
    return db
