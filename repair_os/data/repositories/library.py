"""Репозиторий технической библиотеки, компонентных справок и заметок мастера."""

from __future__ import annotations

from typing import Any

from repair_os.core.errors import NotFoundError
from repair_os.core.security import validate_url
from repair_os.data.models import (
    CATEGORIES,
    DOC_TYPES,
    VERIFICATION_LABELS,
    ComponentReference,
    RepairNote,
    TechnicalDocument,
    clean_date,
    clean_enum,
    clean_multiline,
    clean_text,
    require_text,
)
from repair_os.data.repositories.base import Repository

_DOC_SELECT = """
SELECT td.*, IFNULL(d.name, '') AS device_name, IFNULL(b.name, '') AS brand_name
FROM technical_documents td
LEFT JOIN devices d ON d.id = td.device_id
LEFT JOIN brands b ON b.id = d.brand_id
"""


class LibraryRepository(Repository):
    # ------------------------------------------------------------------ документы
    def list_documents(
        self,
        *,
        search: str | None = None,
        device_id: int | None = None,
        brand_id: int | None = None,
        category: str | None = None,
        doc_type: str | None = None,
        status: str | None = None,
        limit: int = 500,
        offset: int = 0,
    ) -> list[TechnicalDocument]:
        where: list[str] = []
        params: list[Any] = []
        if search:
            needle = f"%{search.strip()}%"
            where.append(
                "(td.title LIKE ? OR IFNULL(td.description,'') LIKE ? OR IFNULL(td.tags,'') LIKE ? "
                "OR IFNULL(d.name,'') LIKE ? OR IFNULL(td.file_path,'') LIKE ?)"
            )
            params.extend([needle] * 5)
        if device_id:
            where.append("td.device_id = ?")
            params.append(device_id)
        if brand_id:
            where.append("(d.brand_id = ? OR td.brand_id = ?)")
            params.extend([brand_id, brand_id])
        if category:
            where.append("td.category = ?")
            params.append(category)
        if doc_type:
            where.append("td.doc_type = ?")
            params.append(doc_type)
        if status:
            where.append("td.verification_status = ?")
            params.append(status)
        sql = _DOC_SELECT
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += " ORDER BY td.updated_at DESC, td.id DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        return [TechnicalDocument.from_row(row) for row in self.db.query(sql, params)]

    def get_document(self, document_id: int) -> TechnicalDocument:
        row = self.db.query_one(f"{_DOC_SELECT} WHERE td.id = ?", (document_id,))
        if not row:
            raise NotFoundError(f"Документ #{document_id} не найден")
        return TechnicalDocument.from_row(row)

    def create_document(self, data: dict[str, Any], *, is_demo: int = 0) -> TechnicalDocument:
        payload = self._validate_document(data)
        with self.db.transaction() as conn:
            cursor = conn.execute(
                """INSERT INTO technical_documents
                   (title, category, doc_type, device_id, brand_id, file_path, source_url,
                    description, tags, verification_status, verified_at, license_note, is_demo)
                   VALUES (:title, :category, :doc_type, :device_id, :brand_id, :file_path,
                           :source_url, :description, :tags, :verification_status, :verified_at,
                           :license_note, :is_demo)""",
                {**payload, "is_demo": is_demo},
            )
            document_id = int(cursor.lastrowid)
        self.log_change("document", "create", document_id, payload["title"], payload)
        return self.get_document(document_id)

    def update_document(self, document_id: int, data: dict[str, Any]) -> TechnicalDocument:
        existing = self.get_document(document_id)
        payload = self._validate_document({**existing.to_dict(), **data})
        with self.db.transaction() as conn:
            conn.execute(
                """UPDATE technical_documents SET title=:title, category=:category,
                   doc_type=:doc_type, device_id=:device_id, brand_id=:brand_id,
                   file_path=:file_path, source_url=:source_url, description=:description,
                   tags=:tags, verification_status=:verification_status, verified_at=:verified_at,
                   license_note=:license_note, updated_at=datetime('now')
                   WHERE id=:id""",
                {**payload, "id": document_id},
            )
        self.log_change("document", "update", document_id, payload["title"], data)
        return self.get_document(document_id)

    def delete_document(self, document_id: int) -> None:
        existing = self.get_document(document_id)
        with self.db.transaction() as conn:
            conn.execute("DELETE FROM technical_documents WHERE id = ?", (document_id,))
        self.log_change("document", "delete", document_id, existing.title)

    def _validate_document(self, data: dict[str, Any]) -> dict[str, Any]:
        source_url = clean_text(data.get("source_url"), max_len=500)
        if source_url:
            source_url = validate_url(source_url)
        status = clean_enum(
            data.get("verification_status") or "unverified",
            VERIFICATION_LABELS,
            "Статус проверки",
            "unverified",
        )
        verified_at = clean_date(data.get("verified_at"), "Дата проверки")
        if status == "verified" and not verified_at:
            from datetime import date

            verified_at = date.today().strftime("%Y-%m-%d")
        return {
            "title": require_text(data.get("title"), "Название материала", max_len=200),
            "category": clean_enum(data.get("category") or "general", CATEGORIES, "Категория", "general"),
            "doc_type": clean_enum(data.get("doc_type") or "pdf", DOC_TYPES, "Тип материала", "pdf"),
            "device_id": int(data["device_id"]) if data.get("device_id") else None,
            "brand_id": int(data["brand_id"]) if data.get("brand_id") else None,
            "file_path": clean_text(data.get("file_path"), max_len=500),
            "source_url": source_url,
            "description": clean_multiline(data.get("description")),
            "tags": clean_text(data.get("tags"), max_len=300),
            "verification_status": status,
            "verified_at": verified_at,
            "license_note": clean_text(data.get("license_note"), max_len=300),
        }

    def category_counts(self) -> dict[str, int]:
        rows = self.db.query(
            "SELECT category, COUNT(*) AS cnt FROM technical_documents GROUP BY category"
        )
        return {row["category"]: int(row["cnt"]) for row in rows}

    def recent(self, limit: int = 8) -> list[TechnicalDocument]:
        rows = self.db.query(f"{_DOC_SELECT} ORDER BY td.updated_at DESC LIMIT ?", (limit,))
        return [TechnicalDocument.from_row(row) for row in rows]

    # ------------------------------------------------------------------ справки по компонентам
    def component_references(
        self, *, search: str | None = None, device_id: int | None = None, limit: int = 200
    ) -> list[ComponentReference]:
        where: list[str] = []
        params: list[Any] = []
        if search:
            needle = f"%{search.strip()}%"
            where.append(
                "(designator LIKE ? OR IFNULL(marking,'') LIKE ? OR IFNULL(description,'') LIKE ?)"
            )
            params.extend([needle] * 3)
        if device_id:
            where.append("device_id = ?")
            params.append(device_id)
        sql = "SELECT * FROM component_references"
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += " ORDER BY designator LIMIT ?"
        params.append(limit)
        return [ComponentReference.from_row(row) for row in self.db.query(sql, params)]

    def add_component_reference(self, data: dict[str, Any], *, is_demo: int = 0) -> ComponentReference:
        source_url = clean_text(data.get("source_url"), max_len=500)
        if source_url:
            source_url = validate_url(source_url)
        with self.db.transaction() as conn:
            cursor = conn.execute(
                """INSERT INTO component_references
                   (device_id, document_id, designator, component_type, marking, description,
                    source_url, is_demo)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    int(data["device_id"]) if data.get("device_id") else None,
                    int(data["document_id"]) if data.get("document_id") else None,
                    clean_text(data.get("designator"), max_len=16),
                    clean_text(data.get("component_type"), max_len=40),
                    clean_text(data.get("marking"), max_len=80),
                    clean_multiline(data.get("description")),
                    source_url,
                    is_demo,
                ),
            )
            ref_id = int(cursor.lastrowid)
        row = self.db.query_one("SELECT * FROM component_references WHERE id = ?", (ref_id,))
        return ComponentReference.from_row(row or {})

    # ------------------------------------------------------------------ заметки
    def notes(
        self, *, device_id: int | None = None, search: str | None = None, limit: int = 300
    ) -> list[RepairNote]:
        where: list[str] = []
        params: list[Any] = []
        if device_id:
            where.append("device_id = ?")
            params.append(device_id)
        if search:
            needle = f"%{search.strip()}%"
            where.append("(title LIKE ? OR IFNULL(body,'') LIKE ?)")
            params.extend([needle, needle])
        sql = "SELECT * FROM repair_notes"
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += " ORDER BY updated_at DESC LIMIT ?"
        params.append(limit)
        return [RepairNote.from_row(row) for row in self.db.query(sql, params)]

    def create_note(self, data: dict[str, Any]) -> RepairNote:
        title = require_text(data.get("title"), "Заголовок заметки", max_len=160)
        category = clean_enum(data.get("category") or "general", CATEGORIES, "Категория", "general")
        with self.db.transaction() as conn:
            cursor = conn.execute(
                "INSERT INTO repair_notes (device_id, board_component_id, title, body, category) "
                "VALUES (?, ?, ?, ?, ?)",
                (
                    int(data["device_id"]) if data.get("device_id") else None,
                    int(data["board_component_id"]) if data.get("board_component_id") else None,
                    title,
                    clean_multiline(data.get("body")),
                    category,
                ),
            )
            note_id = int(cursor.lastrowid)
        row = self.db.query_one("SELECT * FROM repair_notes WHERE id = ?", (note_id,))
        return RepairNote.from_row(row or {})

    def update_note(self, note_id: int, data: dict[str, Any]) -> RepairNote:
        row = self.db.query_one("SELECT * FROM repair_notes WHERE id = ?", (note_id,))
        if not row:
            raise NotFoundError(f"Заметка #{note_id} не найдена")
        existing = RepairNote.from_row(row)
        title = clean_text(data.get("title"), max_len=160) or existing.title
        with self.db.transaction() as conn:
            conn.execute(
                "UPDATE repair_notes SET title=?, body=?, category=?, updated_at=datetime('now') "
                "WHERE id=?",
                (
                    title,
                    clean_multiline(data.get("body", existing.body)),
                    clean_enum(
                        data.get("category") or existing.category, CATEGORIES, "Категория", "general"
                    ),
                    note_id,
                ),
            )
        row = self.db.query_one("SELECT * FROM repair_notes WHERE id = ?", (note_id,))
        return RepairNote.from_row(row or {})

    def delete_note(self, note_id: int) -> None:
        with self.db.transaction() as conn:
            conn.execute("DELETE FROM repair_notes WHERE id = ?", (note_id,))
        self.log_change("note", "delete", note_id, "")
