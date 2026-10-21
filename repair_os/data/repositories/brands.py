"""Репозиторий брендов."""

from __future__ import annotations

import sqlite3
from typing import Any

from repair_os.core.errors import ConflictError, NotFoundError
from repair_os.data.models import Brand
from repair_os.data.repositories.base import Repository

_SELECT = """
SELECT b.*,
       (SELECT COUNT(*) FROM devices d WHERE d.brand_id = b.id) AS device_count
FROM brands b
"""


class BrandRepository(Repository):
    def list(self, *, with_counts: bool = True) -> list[Brand]:
        order = "b.sort_order, b.name COLLATE NOCASE"
        if with_counts:
            rows = self.db.query(f"{_SELECT} ORDER BY {order}")
        else:
            rows = self.db.query(f"SELECT b.*, 0 AS device_count FROM brands b ORDER BY {order}")
        return [Brand.from_row(row) for row in rows]

    def get(self, brand_id: int) -> Brand:
        row = self.db.query_one(f"{_SELECT} WHERE b.id = ?", (brand_id,))
        if not row:
            raise NotFoundError(f"Бренд #{brand_id} не найден")
        return Brand.from_row(row)

    def find_by_slug(self, slug: str) -> Brand | None:
        row = self.db.query_one(f"{_SELECT} WHERE b.slug = ?", (slug,))
        return Brand.from_row(row) if row else None

    def create(self, data: dict[str, Any], *, is_demo: int = 0) -> Brand:
        payload = Brand.validate(data)
        try:
            with self.db.transaction() as conn:
                cursor = conn.execute(
                    "INSERT INTO brands (slug, name, country, website, sort_order, is_demo) "
                    "VALUES (:slug, :name, :country, :website, :sort_order, :is_demo)",
                    {**payload, "is_demo": is_demo},
                )
                brand_id = int(cursor.lastrowid)
        except sqlite3.IntegrityError as exc:
            raise ConflictError(f"Бренд «{payload['name']}» уже существует") from exc
        self.log_change("brand", "create", brand_id, payload["name"])
        return self.get(brand_id)

    def update(self, brand_id: int, data: dict[str, Any]) -> Brand:
        existing = self.get(brand_id)
        payload = Brand.validate({**existing.to_dict(), **data})
        try:
            with self.db.transaction() as conn:
                conn.execute(
                    "UPDATE brands SET name=:name, slug=:slug, country=:country, "
                    "website=:website, sort_order=:sort_order, "
                    "updated_at=datetime('now') WHERE id=:id",
                    {**payload, "id": brand_id},
                )
        except sqlite3.IntegrityError as exc:
            raise ConflictError("Бренд с таким slug уже существует") from exc
        self.log_change("brand", "update", brand_id, payload["name"])
        return self.get(brand_id)

    def delete(self, brand_id: int) -> None:
        brand = self.get(brand_id)
        devices = int(self.db.scalar("SELECT COUNT(*) FROM devices WHERE brand_id = ?", (brand_id,)) or 0)
        if devices:
            raise ConflictError(
                f"Нельзя удалить бренд «{brand.name}»: к нему привязано устройств — {devices}"
            )
        with self.db.transaction() as conn:
            conn.execute("DELETE FROM brands WHERE id = ?", (brand_id,))
        self.log_change("brand", "delete", brand_id, brand.name)

    def popular(self, limit: int = 8) -> list[Brand]:
        rows = self.db.query(
            "SELECT * FROM ("
            "  SELECT b.*, (SELECT COUNT(*) FROM devices d WHERE d.brand_id = b.id) AS device_count"
            "  FROM brands b"
            ") WHERE device_count > 0 "
            "ORDER BY device_count DESC, sort_order, name COLLATE NOCASE LIMIT ?",
            (limit,),
        )
        return [Brand.from_row(row) for row in rows]

    def count(self) -> int:
        return int(self.db.scalar("SELECT COUNT(*) FROM brands") or 0)
