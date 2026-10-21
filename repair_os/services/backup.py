"""Резервное копирование и восстановление пользовательских данных.

Формат копии — ZIP-архив ``smartphone-repair-os-backup-YYYYmmdd-HHMMSS.zip``:
    manifest.json        метаданные, версии, размеры и SHA-256 всех файлов
    repair_os.sqlite3    консистентная копия базы (SQLite backup API)
    attachments/…        дополнительные материалы (по запросу)

При восстановлении архив проверяется: целостность ZIP, manifest, контрольные
суммы, версия схемы. Перед заменой базы создаётся страховочная копия.
"""

from __future__ import annotations

import json
import logging
import shutil
import tempfile
import zipfile
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from repair_os.core.errors import BackupError, SecurityError
from repair_os.core.security import is_within, sha256_file
from repair_os.data.database import Database
from repair_os.version import APP_VERSION

log = logging.getLogger(__name__)

BACKUP_MAGIC = "smartphone-repair-os-backup"
BACKUP_FORMAT_VERSION = 1
MANIFEST_NAME = "manifest.json"
DB_NAME = "repair_os.sqlite3"
MAX_BACKUP_UNCOMPRESSED = 8 * 1024 * 1024 * 1024


@dataclass
class BackupInfo:
    path: Path
    created_at: str
    app_version: str
    schema_version: int
    size: int
    includes_attachments: bool = False

    @property
    def size_human(self) -> str:
        value = float(self.size)
        for unit in ("Б", "КБ", "МБ", "ГБ"):
            if value < 1024 or unit == "ГБ":
                return f"{value:.1f} {unit}"
            value /= 1024
        return f"{value:.1f} ГБ"


@dataclass
class RestoreReport:
    restored_from: Path
    safety_copy: Path | None
    tables: dict[str, int] = field(default_factory=dict)

    @property
    def total_rows(self) -> int:
        return sum(self.tables.values())


class BackupService:
    def __init__(self, db: Database, backups_dir: Path, *, attachments_dir: Path | None = None) -> None:
        self.db = db
        self.backups_dir = Path(backups_dir)
        self.attachments_dir = Path(attachments_dir) if attachments_dir else None
        self.backups_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------ создание
    def create_backup(
        self, *, include_attachments: bool = True, note: str = "", keep: int = 10
    ) -> BackupInfo:
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        target = self.backups_dir / f"smartphone-repair-os-backup-{stamp}.zip"
        counter = 1
        while target.exists():
            target = self.backups_dir / f"smartphone-repair-os-backup-{stamp}-{counter}.zip"
            counter += 1

        with tempfile.TemporaryDirectory(prefix="repos-backup-") as tmp:
            tmp_path = Path(tmp)
            db_copy = tmp_path / DB_NAME
            self.db.backup_database(db_copy)
            files: list[dict[str, Any]] = [
                {
                    "name": DB_NAME,
                    "size": db_copy.stat().st_size,
                    "sha256": sha256_file(db_copy),
                }
            ]
            attachments: list[Path] = []
            if include_attachments and self.attachments_dir and self.attachments_dir.exists():
                for path in sorted(self.attachments_dir.rglob("*")):
                    if path.is_file():
                        attachments.append(path)

            manifest = {
                "magic": BACKUP_MAGIC,
                "format_version": BACKUP_FORMAT_VERSION,
                "app_version": APP_VERSION,
                "schema_version": self.db.schema_version(),
                "created_at": datetime.now().isoformat(timespec="seconds"),
                "note": note,
                "files": files,
                "attachments": [str(p.relative_to(self.attachments_dir)) for p in attachments]
                if attachments
                else [],
            }
            try:
                with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
                    zf.writestr(MANIFEST_NAME, json.dumps(manifest, ensure_ascii=False, indent=2))
                    zf.write(db_copy, DB_NAME)
                    if self.attachments_dir:
                        for path in attachments:
                            arcname = "attachments/" + path.relative_to(self.attachments_dir).as_posix()
                            zf.write(path, arcname)
            except OSError as exc:
                target.unlink(missing_ok=True)
                raise BackupError(f"Не удалось создать резервную копию: {exc}") from exc

        if keep > 0:
            self.prune(keep)
        return BackupInfo(
            path=target,
            created_at=manifest["created_at"],
            app_version=APP_VERSION,
            schema_version=int(manifest["schema_version"]),
            size=target.stat().st_size,
            includes_attachments=bool(attachments),
        )

    def prune(self, keep: int) -> list[Path]:
        backups = sorted(self.backups_dir.glob("smartphone-repair-os-backup-*.zip"), reverse=True)
        removed: list[Path] = []
        for old in backups[keep:]:
            try:
                old.unlink()
                removed.append(old)
            except OSError:  # pragma: no cover
                log.warning("Не удалось удалить старую копию %s", old)
        return removed

    # ------------------------------------------------------------------ список
    def list_backups(self) -> list[BackupInfo]:
        result: list[BackupInfo] = []
        for path in sorted(
            self.backups_dir.glob("smartphone-repair-os-backup-*.zip"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        ):
            info = self.inspect(path)
            if info:
                result.append(info)
        return result

    def inspect(self, path: Path | str) -> BackupInfo | None:
        source = Path(path)
        try:
            with zipfile.ZipFile(source) as zf:
                manifest = json.loads(zf.read(MANIFEST_NAME).decode("utf-8"))
            if manifest.get("magic") != BACKUP_MAGIC:
                return None
            return BackupInfo(
                path=source,
                created_at=manifest.get("created_at", ""),
                app_version=manifest.get("app_version", "?"),
                schema_version=int(manifest.get("schema_version") or 0),
                size=source.stat().st_size,
                includes_attachments=bool(manifest.get("attachments")),
            )
        except (KeyError, ValueError, OSError, zipfile.BadZipFile):
            return None

    # ------------------------------------------------------------------ восстановление
    def restore_backup(
        self,
        path: Path | str,
        *,
        restore_attachments: bool = True,
        current_schema: int | None = None,
    ) -> RestoreReport:
        current_schema = self.db.schema_version() if current_schema is None else current_schema
        source = Path(path)
        if not source.exists():
            raise BackupError(f"Файл не найден: {source}")

        with tempfile.TemporaryDirectory(prefix="repos-restore-") as tmp:
            tmp_path = Path(tmp)
            try:
                with zipfile.ZipFile(source) as zf:
                    total = sum(item.file_size for item in zf.infolist())
                    if total > MAX_BACKUP_UNCOMPRESSED:
                        raise BackupError("Архив слишком большой для восстановления")
                    names = zf.namelist()
                    if MANIFEST_NAME not in names:
                        raise BackupError("В архиве нет manifest.json — это не копия Repair OS")
                    manifest = json.loads(zf.read(MANIFEST_NAME).decode("utf-8"))
                    if manifest.get("magic") != BACKUP_MAGIC:
                        raise BackupError("Неизвестный формат резервной копии")
                    if int(manifest.get("schema_version") or 0) > (current_schema or 0):
                        raise BackupError(
                            "Резервная копия создана более новой версией приложения.\n"
                            "Обновите приложение перед восстановлением."
                        )
                    for entry in manifest.get("files", []):
                        name = entry["name"]
                        if name not in names:
                            raise BackupError(f"В архиве отсутствует файл {name}")
                        target = tmp_path / Path(name).name
                        with zf.open(name) as src, open(target, "wb") as out:
                            shutil.copyfileobj(src, out)
                        if sha256_file(target) != entry["sha256"]:
                            raise BackupError(
                                f"Контрольная сумма {name} не совпадает — архив повреждён"
                            )

                    if restore_attachments and self.attachments_dir:
                        for arcname in manifest.get("attachments", []):
                            rel = Path(arcname)
                            if rel.is_absolute() or ".." in rel.parts:
                                raise SecurityError(f"Небезопасный путь в архиве: {arcname}")
                            dest = self.attachments_dir / rel
                            if not is_within(dest, self.attachments_dir):
                                raise SecurityError(f"Небезопасный путь в архиве: {arcname}")
                            dest.parent.mkdir(parents=True, exist_ok=True)
                            with zf.open("attachments/" + rel.as_posix()) as src, open(dest, "wb") as out:
                                shutil.copyfileobj(src, out)
            except zipfile.BadZipFile as exc:
                raise BackupError("Архив повреждён и не может быть открыт") from exc
            except json.JSONDecodeError as exc:
                raise BackupError("manifest.json повреждён") from exc

            db_file = tmp_path / DB_NAME
            if not db_file.exists():
                raise BackupError("В архиве отсутствует файл базы данных")

            # Страховочная копия текущего состояния — до любых изменений.
            safety: Path | None = None
            try:
                safety = self.create_backup(
                    include_attachments=False, note="before-restore", keep=0
                ).path
            except BackupError:  # pragma: no cover - не блокирует восстановление
                log.warning("Не удалось создать страховочную копию перед восстановлением")

            self.db.restore_database(db_file)

        counts = {
            table: self.db.table_count(table)
            for table in (
                "brands",
                "devices",
                "device_variants",
                "firmware",
                "firmware_sources",
                "board_models",
                "board_components",
                "technical_documents",
                "repair_notes",
            )
        }
        log.info("База восстановлена из %s", source)
        return RestoreReport(restored_from=source, safety_copy=safety, tables=counts)

    # ------------------------------------------------------------------ обмен данными
    def export_json(self, destination: Path | str) -> Path:
        """Экспорт всех пользовательских таблиц в JSON (для резервных копий/миграции)."""
        dest = Path(destination)
        dest.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "format": "smartphone-repair-os-export",
            "version": 1,
            "app_version": APP_VERSION,
            "exported_at": datetime.now().isoformat(timespec="seconds"),
            "data": {},
        }
        for table in (
            "brands",
            "devices",
            "device_variants",
            "firmware_sources",
            "firmware",
            "board_models",
            "board_components",
            "board_annotations",
            "technical_documents",
            "component_references",
            "repair_notes",
            "favorites",
        ):
            payload["data"][table] = self.db.query(f"SELECT * FROM {table}")
        dest.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
        return dest
