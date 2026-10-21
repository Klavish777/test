"""Репозиторий плат, компонентов и пользовательских меток."""

from __future__ import annotations

import sqlite3
from typing import Any

from repair_os.core.errors import ConflictError, NotFoundError
from repair_os.data.models import (
    BoardAnnotation,
    BoardComponent,
    BoardModel,
    clean_bool,
    clean_multiline,
    clean_text,
    require_text,
)
from repair_os.data.repositories.base import Repository

_MODEL_SELECT = """
SELECT bm.*, IFNULL(d.name, '') AS device_name,
       (SELECT COUNT(*) FROM board_components bc WHERE bc.board_model_id = bm.id) AS component_count
FROM board_models bm
LEFT JOIN devices d ON d.id = bm.device_id
"""


class BoardRepository(Repository):
    # ------------------------------------------------------------------ платы
    def list_models(
        self, *, device_id: int | None = None, search: str | None = None, limit: int = 300
    ) -> list[BoardModel]:
        where: list[str] = []
        params: list[Any] = []
        if device_id:
            where.append("bm.device_id = ?")
            params.append(device_id)
        if search:
            needle = f"%{search.strip()}%"
            where.append(
                "(bm.name LIKE ? OR IFNULL(bm.board_code,'') LIKE ? OR IFNULL(d.name,'') LIKE ?)"
            )
            params.extend([needle, needle, needle])
        sql = _MODEL_SELECT
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += " ORDER BY bm.has_3d DESC, bm.name COLLATE NOCASE LIMIT ?"
        params.append(limit)
        return [BoardModel.from_row(row) for row in self.db.query(sql, params)]

    def get_model(self, board_model_id: int) -> BoardModel:
        row = self.db.query_one(f"{_MODEL_SELECT} WHERE bm.id = ?", (board_model_id,))
        if not row:
            raise NotFoundError(f"Плата #{board_model_id} не найдена")
        return BoardModel.from_row(row)

    def model_for_device(self, device_id: int) -> BoardModel | None:
        row = self.db.query_one(
            f"{_MODEL_SELECT} WHERE bm.device_id = ? ORDER BY bm.has_3d DESC, bm.id LIMIT 1",
            (device_id,),
        )
        return BoardModel.from_row(row) if row else None

    def create_model(self, data: dict[str, Any], *, is_demo: int = 0) -> BoardModel:
        payload = {
            "device_id": int(data["device_id"]) if data.get("device_id") else None,
            "name": require_text(data.get("name"), "Название платы", max_len=120),
            "board_code": clean_text(data.get("board_code"), max_len=64),
            "revision": clean_text(data.get("revision"), max_len=32),
            "package_path": clean_text(data.get("package_path"), max_len=500),
            "format": clean_text(data.get("format"), max_len=32),
            "has_3d": clean_bool(data.get("has_3d")),
            "photo_top": clean_text(data.get("photo_top"), max_len=500),
            "photo_bottom": clean_text(data.get("photo_bottom"), max_len=500),
            "source": clean_text(data.get("source"), max_len=200),
            "license_note": clean_text(data.get("license_note"), max_len=300),
            "notes": clean_multiline(data.get("notes")),
            "is_demo": is_demo,
        }
        try:
            with self.db.transaction() as conn:
                cursor = conn.execute(
                    """INSERT INTO board_models
                       (device_id, name, board_code, revision, package_path, format, has_3d,
                        photo_top, photo_bottom, source, license_note, notes, is_demo)
                       VALUES (:device_id, :name, :board_code, :revision, :package_path, :format,
                               :has_3d, :photo_top, :photo_bottom, :source, :license_note, :notes,
                               :is_demo)""",
                    payload,
                )
                board_id = int(cursor.lastrowid)
        except sqlite3.IntegrityError as exc:  # pragma: no cover - схема не имеет уникальных ключей
            raise ConflictError("Не удалось создать плату") from exc
        self.log_change("board_model", "create", board_id, payload["name"], payload)
        return self.get_model(board_id)

    def update_model(self, board_model_id: int, data: dict[str, Any]) -> BoardModel:
        existing = self.get_model(board_model_id)
        merged = {**existing.to_dict(), **data}
        payload = {
            "device_id": int(merged["device_id"]) if merged.get("device_id") else None,
            "name": require_text(merged.get("name"), "Название платы", max_len=120),
            "board_code": clean_text(merged.get("board_code"), max_len=64),
            "revision": clean_text(merged.get("revision"), max_len=32),
            "package_path": clean_text(merged.get("package_path"), max_len=500),
            "format": clean_text(merged.get("format"), max_len=32),
            "has_3d": clean_bool(merged.get("has_3d")),
            "photo_top": clean_text(merged.get("photo_top"), max_len=500),
            "photo_bottom": clean_text(merged.get("photo_bottom"), max_len=500),
            "source": clean_text(merged.get("source"), max_len=200),
            "license_note": clean_text(merged.get("license_note"), max_len=300),
            "notes": clean_multiline(merged.get("notes")),
        }
        with self.db.transaction() as conn:
            conn.execute(
                """UPDATE board_models SET device_id=:device_id, name=:name, board_code=:board_code,
                   revision=:revision, package_path=:package_path, format=:format, has_3d=:has_3d,
                   photo_top=:photo_top, photo_bottom=:photo_bottom, source=:source,
                   license_note=:license_note, notes=:notes, updated_at=datetime('now')
                   WHERE id=:id""",
                {**payload, "id": board_model_id},
            )
        self.log_change("board_model", "update", board_model_id, payload["name"], data)
        return self.get_model(board_model_id)

    def delete_model(self, board_model_id: int) -> None:
        model = self.get_model(board_model_id)
        with self.db.transaction() as conn:
            conn.execute("DELETE FROM board_models WHERE id = ?", (board_model_id,))
        self.log_change("board_model", "delete", board_model_id, model.name)

    # ------------------------------------------------------------------ компоненты
    def components(
        self,
        board_model_id: int,
        *,
        search: str | None = None,
        side: str | None = None,
        layer: str | None = None,
        limit: int = 5000,
    ) -> list[BoardComponent]:
        where = ["board_model_id = ?"]
        params: list[Any] = [board_model_id]
        if search:
            needle = f"%{search.strip()}%"
            where.append(
                "(designator LIKE ? OR IFNULL(part_marking,'') LIKE ? OR "
                "IFNULL(purpose,'') LIKE ? OR IFNULL(component_type,'') LIKE ?)"
            )
            params.extend([needle] * 4)
        if side:
            where.append("side = ?")
            params.append(side)
        if layer:
            where.append("layer = ?")
            params.append(layer)
        params.append(limit)
        rows = self.db.query(
            f"SELECT * FROM board_components WHERE {' AND '.join(where)} "
            "ORDER BY designator LIMIT ?",
            params,
        )
        return [BoardComponent.from_row(row) for row in rows]

    def get_component(self, component_id: int) -> BoardComponent:
        row = self.db.query_one("SELECT * FROM board_components WHERE id = ?", (component_id,))
        if not row:
            raise NotFoundError(f"Компонент #{component_id} не найден")
        return BoardComponent.from_row(row)

    def components_by_designators(
        self, board_model_id: int, designators: list[str]
    ) -> dict[str, BoardComponent]:
        if not designators:
            return {}
        placeholders = ",".join("?" * len(designators))
        rows = self.db.query(
            f"SELECT * FROM board_components WHERE board_model_id = ? "
            f"AND designator IN ({placeholders})",
            [board_model_id, *[d.upper() for d in designators]],
        )
        return {row["designator"]: BoardComponent.from_row(row) for row in rows}

    def upsert_component(self, data: dict[str, Any], *, is_demo: int = 0) -> BoardComponent:
        payload = BoardComponent.validate(data)
        existing = self.db.query_one(
            "SELECT id FROM board_components WHERE board_model_id = ? AND designator = ?",
            (payload["board_model_id"], payload["designator"]),
        )
        if existing:
            return self.update_component(int(existing["id"]), payload)
        with self.db.transaction() as conn:
            cursor = conn.execute(
                """INSERT INTO board_components
                   (board_model_id, designator, side, layer, component_type, part_marking, purpose,
                    package_type, pos_x, pos_y, pos_z, size_x, size_y, size_z, rotation,
                    marker_u, marker_v, notes, is_demo)
                   VALUES (:board_model_id, :designator, :side, :layer, :component_type,
                           :part_marking, :purpose, :package_type, :pos_x, :pos_y, :pos_z,
                           :size_x, :size_y, :size_z, :rotation, :marker_u, :marker_v, :notes,
                           :is_demo)""",
                {**payload, "is_demo": is_demo},
            )
            component_id = int(cursor.lastrowid)
        return self.get_component(component_id)

    def update_component(self, component_id: int, data: dict[str, Any]) -> BoardComponent:
        existing = self.get_component(component_id)
        payload = BoardComponent.validate({**existing.to_dict(), **data})
        with self.db.transaction() as conn:
            conn.execute(
                """UPDATE board_components SET side=:side, layer=:layer,
                   component_type=:component_type, part_marking=:part_marking, purpose=:purpose,
                   package_type=:package_type, pos_x=:pos_x, pos_y=:pos_y, pos_z=:pos_z,
                   size_x=:size_x, size_y=:size_y, size_z=:size_z, rotation=:rotation,
                   marker_u=:marker_u, marker_v=:marker_v, notes=:notes
                   WHERE id=:id""",
                {**payload, "id": component_id},
            )
        return self.get_component(component_id)

    def delete_component(self, component_id: int) -> None:
        component = self.get_component(component_id)
        with self.db.transaction() as conn:
            conn.execute("DELETE FROM board_components WHERE id = ?", (component_id,))
        self.log_change("board_component", "delete", component_id, component.designator)

    def layers(self, board_model_id: int) -> list[str]:
        rows = self.db.query(
            "SELECT DISTINCT layer FROM board_components WHERE board_model_id = ? "
            "AND layer IS NOT NULL AND layer <> '' ORDER BY layer",
            (board_model_id,),
        )
        return [row["layer"] for row in rows]

    def component_types(self, board_model_id: int) -> list[str]:
        rows = self.db.query(
            "SELECT DISTINCT component_type FROM board_components WHERE board_model_id = ? "
            "AND component_type IS NOT NULL AND component_type <> '' ORDER BY component_type",
            (board_model_id,),
        )
        return [row["component_type"] for row in rows]

    # ------------------------------------------------------------------ метки/заметки
    def annotations(self, board_model_id: int) -> list[BoardAnnotation]:
        rows = self.db.query(
            "SELECT * FROM board_annotations WHERE board_model_id = ? ORDER BY created_at DESC",
            (board_model_id,),
        )
        return [BoardAnnotation.from_row(row) for row in rows]

    def add_annotation(
        self,
        board_model_id: int,
        label: str,
        *,
        body: str | None = None,
        component_id: int | None = None,
        color: str = "#3d8bfd",
    ) -> BoardAnnotation:
        label = require_text(label, "Метка", max_len=120)
        text = clean_multiline(body)
        with self.db.transaction() as conn:
            cursor = conn.execute(
                "INSERT INTO board_annotations (board_model_id, component_id, label, body, color) "
                "VALUES (?, ?, ?, ?, ?)",
                (board_model_id, component_id, label, text, color or "#3d8bfd"),
            )
            annotation_id = int(cursor.lastrowid)
        row = self.db.query_one("SELECT * FROM board_annotations WHERE id = ?", (annotation_id,))
        return BoardAnnotation.from_row(row or {})

    def delete_annotation(self, annotation_id: int) -> None:
        with self.db.transaction() as conn:
            conn.execute("DELETE FROM board_annotations WHERE id = ?", (annotation_id,))
