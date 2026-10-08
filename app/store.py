"""Хранилище отчётов устройств (SQLite, без внешних зависимостей)."""
from __future__ import annotations

import os
import sqlite3
import time
from typing import Any

DB_PATH = os.environ.get("FARM_DB", os.path.join(os.path.dirname(__file__), "farm.db"))

SCHEMA = """
CREATE TABLE IF NOT EXISTS devices (
    device_id   TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    public_ip   TEXT NOT NULL,
    conn_type   TEXT,
    org         TEXT,
    country     TEXT,
    is_hosting  INTEGER DEFAULT 0,
    bytes_shared INTEGER DEFAULT 0,
    first_seen  REAL NOT NULL,
    last_seen   REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_devices_ip ON devices(public_ip);
"""


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


def upsert(report: dict[str, Any]) -> None:
    now = time.time()
    with connect() as conn:
        row = conn.execute("SELECT first_seen FROM devices WHERE device_id = ?", (report["device_id"],)).fetchone()
        conn.execute(
            """
            INSERT INTO devices (device_id, name, public_ip, conn_type, org, country,
                                 is_hosting, bytes_shared, first_seen, last_seen)
            VALUES (:device_id, :name, :public_ip, :conn_type, :org, :country,
                    :is_hosting, :bytes_shared, :first_seen, :last_seen)
            ON CONFLICT(device_id) DO UPDATE SET
                name         = excluded.name,
                public_ip    = excluded.public_ip,
                conn_type    = excluded.conn_type,
                org          = excluded.org,
                country      = excluded.country,
                is_hosting   = excluded.is_hosting,
                bytes_shared = excluded.bytes_shared,
                last_seen    = excluded.last_seen
            """,
            {
                "device_id": report["device_id"],
                "name": report.get("name") or report["device_id"],
                "public_ip": report.get("public_ip") or "unknown",
                "conn_type": report.get("conn_type"),
                "org": report.get("org"),
                "country": report.get("country"),
                "is_hosting": int(bool(report.get("is_hosting"))),
                "bytes_shared": int(report.get("bytes_shared") or 0),
                "first_seen": row["first_seen"] if row else now,
                "last_seen": now,
            },
        )


def all_devices() -> list[sqlite3.Row]:
    with connect() as conn:
        return conn.execute("SELECT * FROM devices ORDER BY public_ip, name").fetchall()


def delete(device_id: str) -> None:
    with connect() as conn:
        conn.execute("DELETE FROM devices WHERE device_id = ?", (device_id,))


def reset() -> None:
    with connect() as conn:
        conn.execute("DELETE FROM devices")
