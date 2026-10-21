"""Репозиторий устройств: поиск, CRUD, варианты, избранное, история."""

from __future__ import annotations

import sqlite3
from typing import Any

from repair_os.core.errors import ConflictError, NotFoundError
from repair_os.data.models import Device, DeviceVariant, SearchHit
from repair_os.data.repositories.base import Repository

_SELECT = """
SELECT d.*, b.name AS brand_name, b.slug AS brand_slug,
       (SELECT COUNT(*) FROM firmware f WHERE f.device_id = d.id) AS firmware_count,
       (SELECT COUNT(*) FROM technical_documents td WHERE td.device_id = d.id) AS document_count,
       (SELECT COUNT(*) FROM board_models bm WHERE bm.device_id = d.id AND bm.has_3d = 1) AS has_3d,
       (SELECT COUNT(*) FROM favorites fav WHERE fav.device_id = d.id) AS is_favorite
FROM devices d
JOIN brands b ON b.id = d.brand_id
"""


class DeviceRepository(Repository):
    # ------------------------------------------------------------------ чтение
    def list(
        self,
        *,
        search: str | None = None,
        brand_id: int | None = None,
        favorites_only: bool = False,
        has_3d: bool = False,
        limit: int = 500,
        offset: int = 0,
        order: str = "name",
    ) -> list[Device]:
        where: list[str] = []
        params: list[Any] = []
        if search:
            where.append(
                "(d.name LIKE ? OR d.model_code LIKE ? OR IFNULL(d.codename,'') LIKE ? "
                "OR IFNULL(d.soc,'') LIKE ? OR b.name LIKE ? OR d.model_code = ?)"
            )
            needle = f"%{search.strip()}%"
            params.extend([needle, needle, needle, needle, needle, search.strip().upper()])
        if brand_id:
            where.append("d.brand_id = ?")
            params.append(brand_id)
        if favorites_only:
            where.append("is_favorite > 0")
        if has_3d:
            where.append("has_3d > 0")
        order_sql = {
            "name": "b.name COLLATE NOCASE, d.name COLLATE NOCASE",
            "code": "d.model_code COLLATE NOCASE",
            "year": "IFNULL(d.release_year, 0) DESC, d.name COLLATE NOCASE",
            "recent": "d.updated_at DESC",
        }.get(order, "b.name COLLATE NOCASE, d.name COLLATE NOCASE")
        sql = _SELECT
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += f" ORDER BY {order_sql} LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        return [Device.from_row(row) for row in self.db.query(sql, params)]

    def count(self, brand_id: int | None = None) -> int:
        if brand_id:
            return int(
                self.db.scalar("SELECT COUNT(*) FROM devices WHERE brand_id = ?", (brand_id,)) or 0
            )
        return int(self.db.scalar("SELECT COUNT(*) FROM devices") or 0)

    def get(self, device_id: int) -> Device:
        row = self.db.query_one(f"{_SELECT} WHERE d.id = ?", (device_id,))
        if not row:
            raise NotFoundError(f"Устройство #{device_id} не найден")
        return Device.from_row(row)

    def find_by_model_code(self, model_code: str) -> Device | None:
        row = self.db.query_one(
            f"{_SELECT} WHERE d.model_code = ? COLLATE NOCASE LIMIT 1", (model_code.strip(),)
        )
        return Device.from_row(row) if row else None

    def by_brand(self, brand_id: int, *, limit: int = 300) -> list[Device]:
        return self.list(brand_id=brand_id, limit=limit)

    # ------------------------------------------------------------------ изменение
    def create(self, data: dict[str, Any], *, is_demo: int = 0) -> Device:
        payload = Device.validate(data)
        try:
            with self.db.transaction() as conn:
                cursor = conn.execute(
                    """INSERT INTO devices
                       (brand_id, name, model_code, codename, hardware_revision, soc, soc_platform,
                        ram, storage, os_versions, release_year, notes, source, verified, is_demo)
                       VALUES (:brand_id, :name, :model_code, :codename, :hardware_revision, :soc,
                               :soc_platform, :ram, :storage, :os_versions, :release_year, :notes,
                               :source, :verified, :is_demo)""",
                    {**payload, "is_demo": is_demo},
                )
                device_id = int(cursor.lastrowid)
        except sqlite3.IntegrityError as exc:
            raise ConflictError(
                "Устройство с таким брендом, кодом модели, кодовым именем и ревизией уже существует"
            ) from exc
        self.log_change("device", "create", device_id, payload["name"], payload)
        return self.get(device_id)

    def update(self, device_id: int, data: dict[str, Any]) -> Device:
        existing = self.get(device_id)
        merged = {**existing.to_dict(), **data}
        payload = Device.validate(merged)
        try:
            with self.db.transaction() as conn:
                conn.execute(
                    """UPDATE devices SET brand_id=:brand_id, name=:name, model_code=:model_code,
                       codename=:codename, hardware_revision=:hardware_revision, soc=:soc,
                       soc_platform=:soc_platform, ram=:ram, storage=:storage, os_versions=:os_versions,
                       release_year=:release_year, notes=:notes, source=:source, verified=:verified,
                       updated_at=datetime('now')
                       WHERE id=:id""",
                    {**payload, "id": device_id},
                )
        except sqlite3.IntegrityError as exc:
            raise ConflictError("Такое устройство уже существует (дубликат кода модели)") from exc
        self.log_change("device", "update", device_id, payload["name"], data)
        return self.get(device_id)

    def set_verified(self, device_id: int, verified: bool) -> Device:
        return self.update(device_id, {"verified": 1 if verified else 0})

    def delete(self, device_id: int) -> None:
        device = self.get(device_id)
        with self.db.transaction() as conn:
            # Дочерние записи удаляются каскадно; файлы остаются на диске.
            conn.execute("DELETE FROM devices WHERE id = ?", (device_id,))
        self.log_change("device", "delete", device_id, device.name)

    # ------------------------------------------------------------------ варианты
    def variants(self, device_id: int) -> list[DeviceVariant]:
        rows = self.db.query(
            "SELECT * FROM device_variants WHERE device_id = ? "
            "ORDER BY name COLLATE NOCASE, model_code COLLATE NOCASE",
            (device_id,),
        )
        return [DeviceVariant.from_row(row) for row in rows]

    def add_variant(self, data: dict[str, Any], *, is_demo: int = 0) -> DeviceVariant:
        payload = DeviceVariant.validate(data)
        with self.db.transaction() as conn:
            cursor = conn.execute(
                """INSERT INTO device_variants
                   (device_id, name, model_code, region, csc, ram, storage, bootloader, notes, is_demo)
                   VALUES (:device_id, :name, :model_code, :region, :csc, :ram, :storage,
                           :bootloader, :notes, :is_demo)""",
                {**payload, "is_demo": is_demo},
            )
            variant_id = int(cursor.lastrowid)
        self.log_change("device_variant", "create", variant_id, payload["name"], payload)
        row = self.db.query_one("SELECT * FROM device_variants WHERE id = ?", (variant_id,))
        return DeviceVariant.from_row(row or {})

    def update_variant(self, variant_id: int, data: dict[str, Any]) -> DeviceVariant:
        row = self.db.query_one("SELECT * FROM device_variants WHERE id = ?", (variant_id,))
        if not row:
            raise NotFoundError(f"Вариант #{variant_id} не найден")
        payload = DeviceVariant.validate({**DeviceVariant.from_row(row).to_dict(), **data})
        with self.db.transaction() as conn:
            conn.execute(
                """UPDATE device_variants SET name=:name, model_code=:model_code, region=:region,
                   csc=:csc, ram=:ram, storage=:storage, bootloader=:bootloader, notes=:notes
                   WHERE id=:id""",
                {**payload, "id": variant_id},
            )
        self.log_change("device_variant", "update", variant_id, payload["name"], data)
        row = self.db.query_one("SELECT * FROM device_variants WHERE id = ?", (variant_id,))
        return DeviceVariant.from_row(row or {})

    def delete_variant(self, variant_id: int) -> None:
        with self.db.transaction() as conn:
            conn.execute("DELETE FROM device_variants WHERE id = ?", (variant_id,))
        self.log_change("device_variant", "delete", variant_id, "")

    # ------------------------------------------------------------------ избранное
    def toggle_favorite(self, device_id: int) -> bool:
        self.get(device_id)
        existing = self.db.query_one("SELECT id FROM favorites WHERE device_id = ?", (device_id,))
        with self.db.transaction() as conn:
            if existing:
                conn.execute("DELETE FROM favorites WHERE device_id = ?", (device_id,))
                state = False
            else:
                conn.execute("INSERT INTO favorites (device_id) VALUES (?)", (device_id,))
                state = True
        self.log_change("favorite", "toggle", device_id, str(state))
        return state

    def favorites(self, limit: int = 20) -> list[Device]:
        rows = self.db.query(
            f"{_SELECT} JOIN favorites fav ON fav.device_id = d.id "
            "ORDER BY fav.created_at DESC LIMIT ?",
            (limit,),
        )
        return [Device.from_row(row) for row in rows]

    # ------------------------------------------------------------------ недавние
    def record_open(self, device_id: int) -> None:
        with self.db.transaction() as conn:
            conn.execute(
                """INSERT INTO recent_devices (device_id, opened_at, open_count)
                   VALUES (?, datetime('now'), 1)
                   ON CONFLICT(device_id) DO UPDATE SET
                       opened_at = datetime('now'),
                       open_count = recent_devices.open_count + 1""",
                (device_id,),
            )

    def recent(self, limit: int = 12) -> list[tuple[Device, str, int]]:
        rows = self.db.query(
            "SELECT d.*, b.name AS brand_name, b.slug AS brand_slug,"
            "       r.opened_at AS opened_at, r.open_count AS open_count,"
            "       (SELECT COUNT(*) FROM firmware f WHERE f.device_id = d.id) AS firmware_count,"
            "       (SELECT COUNT(*) FROM technical_documents td WHERE td.device_id = d.id)"
            "           AS document_count,"
            "       (SELECT COUNT(*) FROM board_models bm WHERE bm.device_id = d.id"
            "           AND bm.has_3d = 1) AS has_3d,"
            "       (SELECT COUNT(*) FROM favorites fav WHERE fav.device_id = d.id) AS is_favorite"
            " FROM devices d"
            " JOIN brands b ON b.id = d.brand_id"
            " JOIN recent_devices r ON r.device_id = d.id"
            " ORDER BY r.opened_at DESC LIMIT ?",
            (limit,),
        )
        return [(Device.from_row(row), row["opened_at"], int(row["open_count"])) for row in rows]

    def clear_recent(self) -> None:
        self.db.execute("DELETE FROM recent_devices")

    # ------------------------------------------------------------------ поиск
    def search(self, query: str, *, limit: int = 40) -> list[SearchHit]:
        query = (query or "").strip()
        if not query:
            return []
        needle = f"%{query}%"
        hits: list[SearchHit] = []
        rows = self.db.query(
            f"""{_SELECT}
            WHERE d.name LIKE ? OR d.model_code LIKE ? OR IFNULL(d.codename,'') LIKE ?
                  OR b.name LIKE ? OR IFNULL(d.soc,'') LIKE ?
            ORDER BY CASE WHEN d.model_code = ? COLLATE NOCASE THEN 0 ELSE 1 END,
                     b.name COLLATE NOCASE, d.name COLLATE NOCASE
            LIMIT ?""",
            (needle, needle, needle, needle, needle, query, limit),
        )
        for row in rows:
            device = Device.from_row(row)
            hits.append(
                SearchHit(
                    kind="device",
                    title=f"{device.brand_name} {device.name}",
                    subtitle=f"Код модели: {device.display_code}",
                    device_id=device.id,
                    brand_id=device.brand_id,
                    brand_slug=device.brand_slug,
                    extra={"is_demo": device.is_demo, "verified": device.verified},
                )
            )
        return hits
