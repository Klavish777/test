"""Рабочие каталоги данных Apple Flash Studio (Windows LOCALAPPDATA / кроссплатформенно)."""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path

from apple_flash.version import APP_ID


def default_data_root() -> Path:
    """Возвращает стандартный локальный каталог данных пользователя."""
    override = os.environ.get("APPLE_FLASH_DATA_DIR")
    if override:
        return Path(override).expanduser().resolve()
    if sys.platform == "win32":
        local_app_data = os.environ.get("LOCALAPPDATA")
        if local_app_data:
            return Path(local_app_data) / APP_ID
        return Path.home() / "AppData" / "Local" / APP_ID
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / APP_ID
    xdg = os.environ.get("XDG_DATA_HOME")
    if xdg:
        return Path(xdg) / APP_ID
    return Path.home() / ".local" / "share" / APP_ID


@dataclass(frozen=True)
class StudioPaths:
    root: Path
    db_file: Path
    logs_dir: Path
    ipsw_dir: Path
    shsh_dir: Path
    tools_dir: Path
    reports_dir: Path

    @classmethod
    def create(cls, root: Path | str | None = None) -> StudioPaths:
        base = Path(root).expanduser().resolve() if root else default_data_root()
        logs_dir = base / "logs"
        ipsw_dir = base / "ipsw"
        shsh_dir = base / "shsh"
        tools_dir = base / "tools"
        reports_dir = base / "reports"
        for directory in (base, logs_dir, ipsw_dir, shsh_dir, tools_dir, reports_dir):
            directory.mkdir(parents=True, exist_ok=True)
        return cls(
            root=base,
            db_file=base / "apple_flash.db",
            logs_dir=logs_dir,
            ipsw_dir=ipsw_dir,
            shsh_dir=shsh_dir,
            tools_dir=tools_dir,
            reports_dir=reports_dir,
        )
