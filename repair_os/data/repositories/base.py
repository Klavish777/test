"""Базовый класс репозитория и журналирование изменений."""

from __future__ import annotations

import json
import logging
from typing import Any

from repair_os.data.database import Database

log = logging.getLogger(__name__)


class Repository:
    def __init__(self, db: Database) -> None:
        self.db = db

    # ------------------------------------------------------------------ аудит
    def log_change(
        self,
        entity: str,
        action: str,
        entity_id: int | None = None,
        summary: str = "",
        changes: Any = None,
    ) -> None:
        payload = None
        if changes is not None:
            try:
                payload = json.dumps(changes, ensure_ascii=False, default=str)
            except (TypeError, ValueError):  # pragma: no cover - защитный код
                payload = None
            if payload and len(payload) > 8000:
                payload = payload[:8000] + "…"
        self.db.execute(
            "INSERT INTO audit_log (entity, entity_id, action, summary, changes_json) "
            "VALUES (?, ?, ?, ?, ?)",
            (entity, entity_id, action, summary[:500], payload),
        )

    def audit_history(self, entity: str, entity_id: int, *, limit: int = 100) -> list[dict[str, Any]]:
        return self.db.query(
            "SELECT * FROM audit_log WHERE entity = ? AND entity_id = ? "
            "ORDER BY created_at DESC, id DESC LIMIT ?",
            (entity, entity_id, limit),
        )


def diff_fields(old: dict[str, Any] | None, new: dict[str, Any]) -> dict[str, Any]:
    if not old:
        return dict(new)
    return {key: value for key, value in new.items() if old.get(key) != value}
