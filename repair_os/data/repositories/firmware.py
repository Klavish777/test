"""Репозиторий прошивок и источников."""

from __future__ import annotations

import sqlite3
from typing import Any

from repair_os.core.errors import ConflictError, NotFoundError, ValidationError
from repair_os.core.security import normalize_checksum, validate_url
from repair_os.data.models import (
    VERIFICATION_LABELS,
    Firmware,
    FirmwareSource,
    clean_date,
    clean_enum,
    clean_int,
    clean_multiline,
    clean_text,
    require_text,
)
from repair_os.data.repositories.base import Repository

_SELECT = """
SELECT f.*, IFNULL(d.name, '') AS device_name, IFNULL(b.name, '') AS brand_name,
       IFNULL(s.name, '') AS source_name
FROM firmware f
LEFT JOIN devices d ON d.id = f.device_id
LEFT JOIN brands b ON b.id = d.brand_id
LEFT JOIN firmware_sources s ON s.id = f.source_id
"""


def validate_firmware(data: dict[str, Any]) -> dict[str, Any]:
    file_name = require_text(data.get("file_name"), "Имя файла", max_len=255)
    download_url = clean_text(data.get("download_url"), max_len=500)
    if download_url:
        download_url = validate_url(download_url)
    checksum_reference = clean_text(data.get("checksum_reference"), max_len=80)
    if checksum_reference:
        checksum_reference = normalize_checksum(checksum_reference)
    checksum_sha256 = clean_text(data.get("checksum_sha256"), max_len=80)
    if checksum_sha256:
        checksum_sha256 = normalize_checksum(checksum_sha256)
    model_code = clean_text(data.get("model_code"), max_len=64)
    device_id = clean_int(data.get("device_id"), "Устройство", minimum=0) or None
    if not model_code and not device_id:
        raise ValidationError(
            "Укажите точный код модели или привяжите прошивку к устройству",
            fields={"model_code": "required"},
        )
    if not download_url and not clean_text(data.get("local_path"), max_len=500):
        raise ValidationError(
            "Нужна ссылка на источник загрузки или локальный файл",
            fields={"download_url": "required"},
        )
    return {
        "device_id": device_id,
        "variant_id": clean_int(data.get("variant_id"), "Вариант", minimum=0) or None,
        "source_id": clean_int(data.get("source_id"), "Источник", minimum=0) or None,
        "title": clean_text(data.get("title"), max_len=160),
        "file_name": file_name,
        "model_code": model_code,
        "os_version": clean_text(data.get("os_version"), max_len=60),
        "build_number": clean_text(data.get("build_number"), max_len=80),
        "region": clean_text(data.get("region"), max_len=40),
        "csc": clean_text(data.get("csc"), max_len=20),
        "release_date": clean_date(data.get("release_date"), "Дата выпуска"),
        "file_size": clean_int(data.get("file_size"), "Размер файла", minimum=0),
        "checksum_sha256": checksum_sha256,
        "checksum_reference": checksum_reference,
        "download_url": download_url,
        "local_path": clean_text(data.get("local_path"), max_len=500),
        "install_instructions": clean_multiline(data.get("install_instructions")),
        "compatibility_notes": clean_multiline(data.get("compatibility_notes")),
        "min_bootloader": clean_text(data.get("min_bootloader"), max_len=40),
        "verification_status": clean_enum(
            data.get("verification_status") or "unverified",
            VERIFICATION_LABELS,
            "Статус проверки",
            "unverified",
        ),
    }


class FirmwareRepository(Repository):
    def list(
        self,
        *,
        search: str | None = None,
        brand_id: int | None = None,
        device_id: int | None = None,
        os_version: str | None = None,
        region: str | None = None,
        status: str | None = None,
        source_id: int | None = None,
        sort: str = "build",
        limit: int = 500,
        offset: int = 0,
    ) -> list[Firmware]:
        where: list[str] = []
        params: list[Any] = []
        if search:
            needle = f"%{search.strip()}%"
            where.append(
                "(f.file_name LIKE ? OR IFNULL(f.model_code,'') LIKE ? OR "
                "IFNULL(f.build_number,'') LIKE ? OR IFNULL(f.title,'') LIKE ?)"
            )
            params.extend([needle] * 4)
        if brand_id:
            where.append("d.brand_id = ?")
            params.append(brand_id)
        if device_id:
            where.append("f.device_id = ?")
            params.append(device_id)
        if os_version:
            where.append("f.os_version LIKE ?")
            params.append(f"%{os_version}%")
        if region:
            where.append("(f.region LIKE ? OR f.csc LIKE ?)")
            params.extend([f"%{region}%", f"%{region}%"])
        if status:
            where.append("f.verification_status = ?")
            params.append(status)
        if source_id:
            where.append("f.source_id = ?")
            params.append(source_id)
        order_sql = {
            "build": "IFNULL(f.build_number,'') COLLATE NOCASE DESC",
            "date": "IFNULL(f.release_date,'') DESC",
            "size": "IFNULL(f.file_size,0) DESC",
            "name": "f.file_name COLLATE NOCASE",
            "added": "f.created_at DESC",
        }.get(sort, "f.created_at DESC")
        sql = _SELECT
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += f" ORDER BY {order_sql} LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        return [Firmware.from_row(row) for row in self.db.query(sql, params)]

    def count(self, **filters: Any) -> int:
        return len(self.list(limit=100000, **filters))

    def get(self, firmware_id: int) -> Firmware:
        row = self.db.query_one(f"{_SELECT} WHERE f.id = ?", (firmware_id,))
        if not row:
            raise NotFoundError(f"Прошивка #{firmware_id} не найдена")
        return Firmware.from_row(row)

    def create(self, data: dict[str, Any], *, is_demo: int = 0) -> Firmware:
        payload = validate_firmware(data)
        with self.db.transaction() as conn:
            cursor = conn.execute(
                """INSERT INTO firmware
                   (device_id, variant_id, source_id, title, file_name, model_code, os_version,
                    build_number, region, csc, release_date, file_size, checksum_sha256,
                    checksum_reference, download_url, local_path, install_instructions,
                    compatibility_notes, min_bootloader, verification_status, is_demo)
                   VALUES (:device_id, :variant_id, :source_id, :title, :file_name, :model_code,
                           :os_version, :build_number, :region, :csc, :release_date, :file_size,
                           :checksum_sha256, :checksum_reference, :download_url, :local_path,
                           :install_instructions, :compatibility_notes, :min_bootloader,
                           :verification_status, :is_demo)""",
                {**payload, "is_demo": is_demo},
            )
            firmware_id = int(cursor.lastrowid)
        self.log_change("firmware", "create", firmware_id, payload["file_name"], payload)
        return self.get(firmware_id)

    def update(self, firmware_id: int, data: dict[str, Any]) -> Firmware:
        existing = self.get(firmware_id)
        payload = validate_firmware({**existing.to_dict(), **data})
        changes = {key: value for key, value in data.items() if existing.to_dict().get(key) != value}
        with self.db.transaction() as conn:
            conn.execute(
                """UPDATE firmware SET device_id=:device_id, variant_id=:variant_id,
                   source_id=:source_id, title=:title, file_name=:file_name, model_code=:model_code,
                   os_version=:os_version, build_number=:build_number, region=:region, csc=:csc,
                   release_date=:release_date, file_size=:file_size, checksum_sha256=:checksum_sha256,
                   checksum_reference=:checksum_reference, download_url=:download_url,
                   local_path=:local_path, install_instructions=:install_instructions,
                   compatibility_notes=:compatibility_notes, min_bootloader=:min_bootloader,
                   verification_status=:verification_status, updated_at=datetime('now')
                   WHERE id=:id""",
                {**payload, "id": firmware_id},
            )
        self.log_change("firmware", "update", firmware_id, payload["file_name"], changes)
        return self.get(firmware_id)

    def set_verification(self, firmware_id: int, status: str) -> Firmware:
        if status not in VERIFICATION_LABELS:
            raise ValidationError("Недопустимый статус проверки")
        return self.update(firmware_id, {"verification_status": status})

    def delete(self, firmware_id: int) -> None:
        existing = self.get(firmware_id)
        with self.db.transaction() as conn:
            conn.execute("DELETE FROM firmware WHERE id = ?", (firmware_id,))
        self.log_change("firmware", "delete", firmware_id, existing.file_name)

    def history(self, firmware_id: int) -> list[dict[str, Any]]:
        return self.audit_history("firmware", firmware_id)

    # ------------------------------------------------------------------ источники
    def sources(self) -> list[FirmwareSource]:
        rows = self.db.query(
            "SELECT * FROM firmware_sources ORDER BY trusted DESC, name COLLATE NOCASE"
        )
        return [FirmwareSource.from_row(row) for row in rows]

    def get_source(self, source_id: int) -> FirmwareSource:
        row = self.db.query_one("SELECT * FROM firmware_sources WHERE id = ?", (source_id,))
        if not row:
            raise NotFoundError(f"Источник #{source_id} не найден")
        return FirmwareSource.from_row(row)

    def create_source(self, data: dict[str, Any], *, is_demo: int = 0) -> FirmwareSource:
        name = require_text(data.get("name"), "Название источника", max_len=120)
        url = clean_text(data.get("url"), max_len=500)
        if url:
            url = validate_url(url)
        kind = clean_enum(data.get("kind") or "community", {"official": "", "community": "", "local": "", "vendor_tool": ""}, "Тип источника", "community")
        try:
            with self.db.transaction() as conn:
                cursor = conn.execute(
                    "INSERT INTO firmware_sources (name, url, kind, trusted, notes, is_demo) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (
                        name,
                        url,
                        kind,
                        int(bool(data.get("trusted"))),
                        clean_multiline(data.get("notes")),
                        is_demo,
                    ),
                )
                source_id = int(cursor.lastrowid)
        except sqlite3.IntegrityError as exc:
            raise ConflictError(f"Источник «{name}» уже существует") from exc
        self.log_change("firmware_source", "create", source_id, name)
        return self.get_source(source_id)

    def update_source(self, source_id: int, data: dict[str, Any]) -> FirmwareSource:
        existing = self.get_source(source_id)
        name = clean_text(data.get("name"), max_len=120) or existing.name
        url = clean_text(data.get("url"), max_len=500)
        if url:
            url = validate_url(url)
        with self.db.transaction() as conn:
            conn.execute(
                "UPDATE firmware_sources SET name=?, url=?, kind=?, trusted=?, notes=?, "
                "last_checked=datetime('now') WHERE id=?",
                (
                    name,
                    url,
                    data.get("kind") or existing.kind,
                    int(bool(data.get("trusted", existing.trusted))),
                    clean_multiline(data.get("notes", existing.notes)),
                    source_id,
                ),
            )
        self.log_change("firmware_source", "update", source_id, name, data)
        return self.get_source(source_id)

    def delete_source(self, source_id: int) -> None:
        used = int(self.db.scalar("SELECT COUNT(*) FROM firmware WHERE source_id = ?", (source_id,)) or 0)
        if used:
            raise ConflictError(f"Источник используется в {used} записях прошивок")
        with self.db.transaction() as conn:
            conn.execute("DELETE FROM firmware_sources WHERE id = ?", (source_id,))
        self.log_change("firmware_source", "delete", source_id, "")

    # ------------------------------------------------------------------ агрегаты
    def stats_by_device(self, device_id: int) -> dict[str, int]:
        row = self.db.query_one(
            "SELECT COUNT(*) AS total, SUM(CASE WHEN verification_status='verified' THEN 1 ELSE 0 END) AS verified "
            "FROM firmware WHERE device_id = ?",
            (device_id,),
        ) or {}
        return {"total": int(row.get("total") or 0), "verified": int(row.get("verified") or 0)}

    def recent(self, limit: int = 8) -> list[Firmware]:
        rows = self.db.query(f"{_SELECT} ORDER BY f.created_at DESC, f.id DESC LIMIT ?", (limit,))
        return [Firmware.from_row(row) for row in rows]
