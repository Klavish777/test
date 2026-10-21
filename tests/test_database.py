"""Тесты схемы, миграций и обслуживания базы."""

from __future__ import annotations

import sqlite3

import pytest

from repair_os.core.errors import BackupError, RepairOSError
from repair_os.data.database import Database, open_database
from repair_os.data.migrations import MIGRATIONS, MIGRATION_CHECKSUMS

REQUIRED_TABLES = {
    "brands",
    "devices",
    "device_variants",
    "firmware",
    "firmware_sources",
    "board_models",
    "board_components",
    "technical_documents",
    "component_references",
    "repair_notes",
    "favorites",
    "recent_devices",
    "app_settings",
}


def test_migrations_are_loaded_and_unique():
    assert MIGRATIONS, "должна быть хотя бы одна миграция"
    versions = [version for version, _, _ in MIGRATIONS]
    assert versions == sorted(versions)
    assert len(set(versions)) == len(versions)
    assert set(versions) == set(MIGRATION_CHECKSUMS)


def test_schema_has_required_tables(db):
    tables = {row["name"] for row in db.query("SELECT name FROM sqlite_master WHERE type='table'")}
    assert REQUIRED_TABLES.issubset(tables)
    assert db.schema_version() == MIGRATIONS[-1][0]


def test_migration_is_idempotent(tmp_path):
    path = tmp_path / "idempotent.sqlite3"
    first = open_database(path)
    version = first.schema_version()
    first.close()
    second = open_database(path)
    assert second.schema_version() == version
    applied = second.query("SELECT COUNT(*) AS c FROM schema_migrations")[0]["c"]
    assert applied == len(MIGRATIONS)
    second.close()


def test_foreign_keys_enforced(db):
    with pytest.raises(sqlite3.IntegrityError):
        db.execute(
            "INSERT INTO devices (brand_id, name, model_code) VALUES (99999, 'X', 'X-1')"
        )


def test_unique_device_identity(db):
    db.execute("INSERT INTO brands (slug, name) VALUES ('b', 'B')")
    brand_id = db.scalar("SELECT id FROM brands WHERE slug='b'")
    db.execute(
        "INSERT INTO devices (brand_id, name, model_code) VALUES (?, 'M', 'SM-1')", (brand_id,)
    )
    with pytest.raises(sqlite3.IntegrityError):
        db.execute(
            "INSERT INTO devices (brand_id, name, model_code) VALUES (?, 'M2', 'sm-1')",
            (brand_id,),
        )


def test_check_constraints(db):
    db.execute("INSERT INTO brands (slug, name) VALUES ('b', 'B')")
    brand_id = db.scalar("SELECT id FROM brands WHERE slug='b'")
    db.execute(
        "INSERT INTO board_models (device_id, name) VALUES (NULL, 'P')"
    )
    board_id = db.scalar("SELECT id FROM board_models LIMIT 1")
    with pytest.raises(sqlite3.IntegrityError):
        db.execute(
            "INSERT INTO board_components (board_model_id, designator, side) VALUES (?, 'U1', 'middle')",
            (board_id,),
        )
    _ = brand_id


def test_integrity_and_backup_restore(tmp_path, db):
    db.execute("INSERT INTO brands (slug, name) VALUES ('b', 'B')")
    backup_path = db.backup_database(tmp_path / "copy.sqlite3")
    assert backup_path.exists() and backup_path.stat().st_size > 0

    db.execute("INSERT INTO brands (slug, name) VALUES ('c', 'C')")
    assert db.table_count("brands") == 2

    db.restore_database(backup_path)
    assert db.table_count("brands") == 1
    assert db.integrity_check()


def test_restore_rejects_corrupted_file(tmp_path, db):
    broken = tmp_path / "broken.sqlite3"
    broken.write_bytes(b"this is not a database")
    with pytest.raises(BackupError):
        db.restore_database(broken)


def test_restore_rejects_foreign_database(tmp_path, db):
    other = sqlite3.connect(tmp_path / "other.sqlite3")
    other.execute("CREATE TABLE something (id INTEGER)")
    other.commit()
    other.close()
    with pytest.raises(BackupError):
        db.restore_database(tmp_path / "other.sqlite3")


def test_restore_rejects_newer_schema(tmp_path):
    path = tmp_path / "newer.sqlite3"
    newer = open_database(path)
    newer.execute(
        "INSERT INTO schema_migrations (version, name, checksum) VALUES (999, 'future', 'x')"
    )
    newer.close()

    target = open_database(tmp_path / "target.sqlite3")
    with pytest.raises(BackupError):
        target.restore_database(path)
    target.close()


def test_table_count_validates_name(db):
    with pytest.raises(ValueError):
        db.table_count("brands; DROP TABLE devices")


def test_transaction_rollback(tmp_path):
    database = Database(tmp_path / "tx.sqlite3")
    database.migrate()
    with pytest.raises(RepairOSError):
        with database.transaction() as conn:
            conn.execute("INSERT INTO brands (slug, name) VALUES ('x', 'X')")
            raise RepairOSError("boom")
    assert database.table_count("brands") == 0
    database.close()
