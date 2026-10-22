"""Локальное SQLite-хранилище Apple Flash Studio (библиотека IPSW, журнал прошивок, настройки)."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from apple_flash.data.models import FlashSessionRecord, IpswManifestInfo, IpswRecord

SCHEMA_SQL = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS schema_meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS ipsw_library (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_name TEXT NOT NULL,
    local_path TEXT NOT NULL UNIQUE,
    file_size INTEGER NOT NULL DEFAULT 0,
    family TEXT NOT NULL DEFAULT 'unknown',
    product_version TEXT NOT NULL DEFAULT '',
    build_version TEXT NOT NULL DEFAULT '',
    supported_products_json TEXT NOT NULL DEFAULT '[]',
    supported_cpids_json TEXT NOT NULL DEFAULT '[]',
    board_configs_json TEXT NOT NULL DEFAULT '[]',
    has_erase INTEGER NOT NULL DEFAULT 1,
    has_upgrade INTEGER NOT NULL DEFAULT 1,
    sha256 TEXT,
    sha1 TEXT,
    expected_hash TEXT,
    verified_state TEXT NOT NULL DEFAULT 'unchecked',
    is_demo INTEGER NOT NULL DEFAULT 0,
    notes TEXT,
    added_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_ipsw_family ON ipsw_library(family);
CREATE INDEX IF NOT EXISTS idx_ipsw_build ON ipsw_library(build_version);

CREATE TABLE IF NOT EXISTS flash_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    device_title TEXT NOT NULL,
    device_uid TEXT NOT NULL,
    product_type TEXT,
    family TEXT NOT NULL DEFAULT 'unknown',
    action TEXT NOT NULL,
    backend TEXT NOT NULL,
    ipsw_name TEXT,
    ipsw_build TEXT,
    dry_run INTEGER NOT NULL DEFAULT 1,
    status TEXT NOT NULL,
    exit_code INTEGER NOT NULL DEFAULT 0,
    command_line TEXT NOT NULL DEFAULT '',
    log_text TEXT NOT NULL DEFAULT ''
);

CREATE INDEX IF NOT EXISTS idx_sessions_started ON flash_sessions(started_at DESC);
"""


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M:%S")


class StudioStore:
    def __init__(self, db_path: Path | str) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self) -> None:
        with self._conn:
            self._conn.executescript(SCHEMA_SQL)
            self._conn.execute(
                "INSERT OR REPLACE INTO schema_meta(key, value) VALUES ('version', '1')"
            )

    def close(self) -> None:
        self._conn.close()

    def integrity_ok(self) -> bool:
        row = self._conn.execute("PRAGMA integrity_check").fetchone()
        return bool(row and row[0] == "ok")

    # ------------------------------------------------------------------ настройки
    def get_setting(self, key: str, default: str = "") -> str:
        row = self._conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
        return str(row["value"]) if row else default

    def set_setting(self, key: str, value: str) -> None:
        with self._conn:
            self._conn.execute(
                "INSERT INTO settings(key, value, updated_at) VALUES (?, ?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at",
                (key, value, now_iso()),
            )

    # ------------------------------------------------------------------ IPSW библиотека
    def upsert_ipsw_from_manifest(
        self,
        info: IpswManifestInfo,
        *,
        sha256: str | None = None,
        sha1: str | None = None,
        expected_hash: str | None = None,
        notes: str | None = None,
    ) -> IpswRecord:
        local_path = str(info.path.resolve())
        existing = self._conn.execute(
            "SELECT * FROM ipsw_library WHERE local_path = ?", (local_path,)
        ).fetchone()

        eff_sha256 = sha256 or (existing["sha256"] if existing else None)
        eff_sha1 = sha1 or (existing["sha1"] if existing else None)
        eff_expected = expected_hash if expected_hash is not None else (existing["expected_hash"] if existing else None)
        verified_state = self._compute_verified_state(eff_sha256, eff_sha1, eff_expected)
        added_at = existing["added_at"] if existing else now_iso()
        eff_notes = notes if notes is not None else (existing["notes"] if existing else None)

        with self._conn:
            self._conn.execute(
                """
                INSERT INTO ipsw_library(
                    file_name, local_path, file_size, family, product_version, build_version,
                    supported_products_json, supported_cpids_json, board_configs_json,
                    has_erase, has_upgrade, sha256, sha1, expected_hash, verified_state,
                    is_demo, notes, added_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(local_path) DO UPDATE SET
                    file_name = excluded.file_name,
                    file_size = excluded.file_size,
                    family = excluded.family,
                    product_version = excluded.product_version,
                    build_version = excluded.build_version,
                    supported_products_json = excluded.supported_products_json,
                    supported_cpids_json = excluded.supported_cpids_json,
                    board_configs_json = excluded.board_configs_json,
                    has_erase = excluded.has_erase,
                    has_upgrade = excluded.has_upgrade,
                    sha256 = excluded.sha256,
                    sha1 = excluded.sha1,
                    expected_hash = excluded.expected_hash,
                    verified_state = excluded.verified_state,
                    is_demo = excluded.is_demo,
                    notes = excluded.notes
                """,
                (
                    info.file_name,
                    local_path,
                    info.file_size,
                    info.family,
                    info.product_version,
                    info.build_version,
                    json.dumps(info.supported_product_types, ensure_ascii=False),
                    json.dumps(info.supported_cpids),
                    json.dumps(info.board_configs, ensure_ascii=False),
                    int(info.has_erase_variant),
                    int(info.has_upgrade_variant),
                    eff_sha256,
                    eff_sha1,
                    eff_expected,
                    verified_state,
                    int(info.is_demo_mockup),
                    eff_notes,
                    added_at,
                ),
            )
        row = self._conn.execute(
            "SELECT * FROM ipsw_library WHERE local_path = ?", (local_path,)
        ).fetchone()
        return self._row_to_ipsw(row)

    @staticmethod
    def _compute_verified_state(
        sha256: str | None, sha1: str | None, expected: str | None
    ) -> str:
        if expected:
            norm = expected.strip().lower()
            if len(norm) == 64 and sha256:
                return "verified" if sha256.lower() == norm else "mismatch"
            if len(norm) == 40 and sha1:
                return "verified" if sha1.lower() == norm else "mismatch"
        if sha256 or sha1:
            return "hashed"
        return "unchecked"

    def update_ipsw_hashes(
        self,
        ipsw_id: int,
        *,
        sha256: str,
        sha1: str,
        expected_hash: str | None = None,
    ) -> IpswRecord:
        current = self.get_ipsw(ipsw_id)
        eff_expected = expected_hash if expected_hash is not None else current.expected_hash
        state = self._compute_verified_state(sha256, sha1, eff_expected)
        with self._conn:
            self._conn.execute(
                "UPDATE ipsw_library SET sha256 = ?, sha1 = ?, expected_hash = ?, verified_state = ? WHERE id = ?",
                (sha256, sha1, eff_expected, state, ipsw_id),
            )
        return self.get_ipsw(ipsw_id)

    def get_ipsw(self, ipsw_id: int) -> IpswRecord:
        row = self._conn.execute("SELECT * FROM ipsw_library WHERE id = ?", (ipsw_id,)).fetchone()
        if not row:
            raise KeyError(f"IPSW id={ipsw_id} не найден")
        return self._row_to_ipsw(row)

    def list_ipsw(
        self, *, family: str | None = None, search: str | None = None
    ) -> list[IpswRecord]:
        clauses: list[str] = []
        params: list[Any] = []
        if family and family != "all":
            clauses.append("family = ?")
            params.append(family)
        if search and search.strip():
            q = f"%{search.strip()}%"
            clauses.append(
                "(file_name LIKE ? OR product_version LIKE ? OR build_version LIKE ? OR supported_products_json LIKE ?)"
            )
            params.extend([q, q, q, q])
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        rows = self._conn.execute(
            f"SELECT * FROM ipsw_library {where} ORDER BY added_at DESC, id DESC",
            params,
        ).fetchall()
        return [self._row_to_ipsw(r) for r in rows]

    def delete_ipsw(self, ipsw_id: int) -> None:
        with self._conn:
            self._conn.execute("DELETE FROM ipsw_library WHERE id = ?", (ipsw_id,))

    def delete_demo_ipsw(self) -> list[Path]:
        rows = self._conn.execute("SELECT local_path FROM ipsw_library WHERE is_demo = 1").fetchall()
        paths = [Path(r["local_path"]) for r in rows]
        with self._conn:
            self._conn.execute("DELETE FROM ipsw_library WHERE is_demo = 1")
        return paths

    @staticmethod
    def _row_to_ipsw(row: sqlite3.Row) -> IpswRecord:
        return IpswRecord(
            id=int(row["id"]),
            file_name=row["file_name"],
            local_path=row["local_path"],
            file_size=int(row["file_size"]),
            family=row["family"],
            product_version=row["product_version"],
            build_version=row["build_version"],
            supported_products=json.loads(row["supported_products_json"] or "[]"),
            supported_cpids=[int(x) for x in json.loads(row["supported_cpids_json"] or "[]")],
            board_configs=json.loads(row["board_configs_json"] or "[]"),
            has_erase=bool(row["has_erase"]),
            has_upgrade=bool(row["has_upgrade"]),
            sha256=row["sha256"],
            sha1=row["sha1"],
            expected_hash=row["expected_hash"],
            verified_state=row["verified_state"],
            is_demo=bool(row["is_demo"]),
            notes=row["notes"],
            added_at=row["added_at"],
        )

    # ------------------------------------------------------------------ Журнал прошивок
    def record_session(self, session: FlashSessionRecord) -> FlashSessionRecord:
        with self._conn:
            cursor = self._conn.execute(
                """
                INSERT INTO flash_sessions(
                    started_at, finished_at, device_title, device_uid, product_type,
                    family, action, backend, ipsw_name, ipsw_build, dry_run,
                    status, exit_code, command_line, log_text
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    session.started_at,
                    session.finished_at or now_iso(),
                    session.device_title,
                    session.device_uid,
                    session.product_type,
                    session.family,
                    session.action,
                    session.backend,
                    session.ipsw_name,
                    session.ipsw_build,
                    int(session.dry_run),
                    session.status,
                    int(session.exit_code),
                    session.command_line,
                    session.log_text,
                ),
            )
            session_id = int(cursor.lastrowid)
        return self.get_session(session_id)

    def get_session(self, session_id: int) -> FlashSessionRecord:
        row = self._conn.execute(
            "SELECT * FROM flash_sessions WHERE id = ?", (session_id,)
        ).fetchone()
        if not row:
            raise KeyError(f"Сессия id={session_id} не найдена")
        return self._row_to_session(row)

    def list_sessions(self, *, limit: int = 200) -> list[FlashSessionRecord]:
        rows = self._conn.execute(
            "SELECT * FROM flash_sessions ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
        return [self._row_to_session(r) for r in rows]

    def clear_sessions(self) -> None:
        with self._conn:
            self._conn.execute("DELETE FROM flash_sessions")

    @staticmethod
    def _row_to_session(row: sqlite3.Row) -> FlashSessionRecord:
        return FlashSessionRecord(
            id=int(row["id"]),
            started_at=row["started_at"],
            finished_at=row["finished_at"],
            device_title=row["device_title"],
            device_uid=row["device_uid"],
            product_type=row["product_type"],
            family=row["family"],
            action=row["action"],
            backend=row["backend"],
            ipsw_name=row["ipsw_name"],
            ipsw_build=row["ipsw_build"],
            dry_run=bool(row["dry_run"]),
            status=row["status"],
            exit_code=int(row["exit_code"]),
            command_line=row["command_line"],
            log_text=row["log_text"],
        )
