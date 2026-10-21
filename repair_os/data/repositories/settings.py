"""Репозиторий настроек приложения (ключ-значение)."""

from __future__ import annotations

import json
import logging
from typing import Any

from repair_os.data.database import Database

log = logging.getLogger(__name__)

DEFAULTS: dict[str, Any] = {
    "language": "ru",
    "theme": "dark",
    "last_brand": "",
    "window_geometry": "",
    "show_demo_badge": True,
    "confirm_dangerous_actions": True,
    "library_root": "",
    "firmware_root": "",
    "boards_root": "",
    "backup_keep_count": 10,
    "onboarding_done": False,
    "board_render_quality": "medium",
    "entitlement_provider": "local",
}


class SettingsRepository:
    def __init__(self, db: Database) -> None:
        self.db = db

    def get(self, key: str, default: Any = None) -> Any:
        row = self.db.query_one("SELECT value FROM app_settings WHERE key = ?", (key,))
        if row is None or row["value"] is None:
            return DEFAULTS.get(key, default)
        raw = row["value"]
        try:
            return json.loads(raw)
        except (TypeError, ValueError):
            return raw

    def get_int(self, key: str, default: int = 0) -> int:
        try:
            return int(self.get(key, default))
        except (TypeError, ValueError):
            return default

    def set(self, key: str, value: Any) -> None:
        payload = json.dumps(value, ensure_ascii=False)
        self.db.execute(
            "INSERT INTO app_settings (key, value, updated_at) VALUES (?, ?, datetime('now')) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = datetime('now')",
            (key, payload),
        )

    def set_many(self, values: dict[str, Any]) -> None:
        with self.db.transaction() as conn:
            for key, value in values.items():
                conn.execute(
                    "INSERT INTO app_settings (key, value, updated_at) VALUES (?, ?, datetime('now')) "
                    "ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = datetime('now')",
                    (key, json.dumps(value, ensure_ascii=False)),
                )

    def all(self) -> dict[str, Any]:
        result = dict(DEFAULTS)
        for row in self.db.query("SELECT key, value FROM app_settings"):
            try:
                result[row["key"]] = json.loads(row["value"]) if row["value"] is not None else None
            except (TypeError, ValueError):
                result[row["key"]] = row["value"]
        return result

    def reset(self) -> None:
        self.db.execute("DELETE FROM app_settings")
