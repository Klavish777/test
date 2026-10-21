"""Сквозной поиск по устройствам, прошивкам, документам, платам и компонентам."""

from __future__ import annotations

import logging
from typing import Any

from repair_os.data.database import Database
from repair_os.data.models import SearchHit

log = logging.getLogger(__name__)

MAX_PER_GROUP = 12


class SearchService:
    def __init__(self, db: Database) -> None:
        self.db = db

    def search(
        self,
        query: str,
        *,
        include: tuple[str, ...] = ("devices", "firmware", "documents", "boards", "components"),
        limit_per_group: int = MAX_PER_GROUP,
    ) -> list[SearchHit]:
        query = (query or "").strip()
        if not query:
            return []
        needle = f"%{query}%"
        exact = query.upper()
        hits: list[SearchHit] = []
        if "devices" in include:
            hits.extend(self._devices(needle, exact, limit_per_group))
        if "firmware" in include:
            hits.extend(self._firmware(needle, limit_per_group))
        if "documents" in include:
            hits.extend(self._documents(needle, limit_per_group))
        if "boards" in include:
            hits.extend(self._boards(needle, limit_per_group))
        if "components" in include:
            hits.extend(self._components(needle, limit_per_group))
        return hits

    # ------------------------------------------------------------------ группы
    def _devices(self, needle: str, exact: str, limit: int) -> list[SearchHit]:
        rows = self.db.query(
            """SELECT d.id, d.name, d.model_code, d.codename, d.verified, d.is_demo,
                      b.name AS brand_name, b.id AS brand_id, b.slug AS brand_slug
               FROM devices d JOIN brands b ON b.id = d.brand_id
               WHERE d.name LIKE ? OR d.model_code LIKE ? OR IFNULL(d.codename,'') LIKE ?
                     OR b.name LIKE ? OR IFNULL(d.soc,'') LIKE ? OR UPPER(d.model_code) = ?
               ORDER BY CASE WHEN UPPER(d.model_code) = ? THEN 0 ELSE 1 END,
                        b.name COLLATE NOCASE, d.name COLLATE NOCASE
               LIMIT ?""",
            (needle, needle, needle, needle, needle, exact, exact, limit),
        )
        return [
            SearchHit(
                kind="device",
                title=f"{row['brand_name']} {row['name']}",
                subtitle=f"Код модели: {row['model_code']}"
                + (f" · {row['codename']}" if row["codename"] else ""),
                device_id=int(row["id"]),
                brand_id=int(row["brand_id"]),
                brand_slug=row["brand_slug"],
                extra={"is_demo": row["is_demo"], "verified": row["verified"]},
            )
            for row in rows
        ]

    def _firmware(self, needle: str, limit: int) -> list[SearchHit]:
        rows = self.db.query(
            """SELECT f.id, f.file_name, f.model_code, f.build_number, f.os_version,
                      f.verification_status, f.is_demo, f.device_id
               FROM firmware f
               WHERE f.file_name LIKE ? OR IFNULL(f.model_code,'') LIKE ?
                     OR IFNULL(f.build_number,'') LIKE ?
               ORDER BY f.file_name COLLATE NOCASE LIMIT ?""",
            (needle, needle, needle, limit),
        )
        result = []
        for row in rows:
            subtitle_parts = [f"Модель: {row['model_code'] or '—'}"]
            if row["build_number"]:
                subtitle_parts.append(f"сборка {row['build_number']}")
            if row["os_version"]:
                subtitle_parts.append(str(row["os_version"]))
            result.append(
                SearchHit(
                    kind="firmware",
                    title=row["file_name"],
                    subtitle=" · ".join(subtitle_parts),
                    device_id=row["device_id"],
                    extra={
                        "firmware_id": row["id"],
                        "status": row["verification_status"],
                        "is_demo": row["is_demo"],
                    },
                )
            )
        return result

    def _documents(self, needle: str, limit: int) -> list[SearchHit]:
        rows = self.db.query(
            """SELECT td.id, td.title, td.category, td.doc_type, td.verification_status,
                      td.device_id, IFNULL(d.name,'') AS device_name
               FROM technical_documents td
               LEFT JOIN devices d ON d.id = td.device_id
               WHERE td.title LIKE ? OR IFNULL(td.description,'') LIKE ?
                     OR IFNULL(td.tags,'') LIKE ? OR IFNULL(d.name,'') LIKE ?
               ORDER BY td.title COLLATE NOCASE LIMIT ?""",
            (needle, needle, needle, needle, limit),
        )
        return [
            SearchHit(
                kind="document",
                title=row["title"],
                subtitle=f"{row['doc_type']} · {row['category']}"
                + (f" · {row['device_name']}" if row["device_name"] else ""),
                device_id=row["device_id"],
                extra={
                    "document_id": row["id"],
                    "status": row["verification_status"],
                },
            )
            for row in rows
        ]

    def _boards(self, needle: str, limit: int) -> list[SearchHit]:
        rows = self.db.query(
            """SELECT bm.id, bm.name, bm.board_code, bm.has_3d, bm.device_id,
                      IFNULL(d.name,'') AS device_name
               FROM board_models bm LEFT JOIN devices d ON d.id = bm.device_id
               WHERE bm.name LIKE ? OR IFNULL(bm.board_code,'') LIKE ? OR IFNULL(d.name,'') LIKE ?
               ORDER BY bm.has_3d DESC LIMIT ?""",
            (needle, needle, needle, limit),
        )
        return [
            SearchHit(
                kind="board",
                title=row["name"],
                subtitle=("3D-модель · " if row["has_3d"] else "Фото/метки · ")
                + (row["board_code"] or "без кода")
                + (f" · {row['device_name']}" if row["device_name"] else ""),
                device_id=row["device_id"],
                extra={"board_model_id": row["id"], "has_3d": row["has_3d"]},
            )
            for row in rows
        ]

    def _components(self, needle: str, limit: int) -> list[SearchHit]:
        rows = self.db.query(
            """SELECT bc.id, bc.designator, bc.component_type, bc.part_marking, bc.purpose,
                      bc.board_model_id, bm.name AS board_name, bm.device_id
               FROM board_components bc JOIN board_models bm ON bm.id = bc.board_model_id
               WHERE bc.designator LIKE ? OR IFNULL(bc.part_marking,'') LIKE ?
                     OR IFNULL(bc.purpose,'') LIKE ?
               ORDER BY bc.designator LIMIT ?""",
            (needle, needle, needle, limit),
        )
        return [
            SearchHit(
                kind="component",
                title=row["designator"],
                subtitle=" · ".join(
                    part
                    for part in (
                        row["part_marking"],
                        row["purpose"],
                        row["board_name"],
                    )
                    if part
                ),
                device_id=row["device_id"],
                extra={"component_id": row["id"], "board_model_id": row["board_model_id"]},
            )
            for row in rows
        ]

    # ------------------------------------------------------------------ подсказки
    def suggest(self, query: str, limit: int = 8) -> list[dict[str, Any]]:
        """Быстрые подсказки для строки поиска (без тяжёлых запросов)."""
        query = (query or "").strip()
        if len(query) < 2:
            return []
        needle = f"{query}%"
        rows = self.db.query(
            """SELECT d.id, d.name, d.model_code, b.name AS brand_name
               FROM devices d JOIN brands b ON b.id = d.brand_id
               WHERE d.name LIKE ? OR d.model_code LIKE ? OR b.name LIKE ?
               ORDER BY d.model_code COLLATE NOCASE LIMIT ?""",
            (needle, needle, needle, limit),
        )
        return [dict(row) for row in rows]
