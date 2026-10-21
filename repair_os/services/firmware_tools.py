"""Работа с файлами прошивок: контрольные суммы, проверка архивов, совместимость.

Приложение **не загружает файлы из интернета** и не обходит защиту устройств.
Все операции с файлами выполняются только после явного подтверждения пользователя.
"""

from __future__ import annotations

import logging
import shutil
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

from repair_os.core.errors import ImportErrorOS, IntegrityError, RepairOSError, ValidationError
from repair_os.core.security import (
    normalize_checksum,
    sanitize_filename,
    sha256_file,
    sniff_is_zip,
)
from repair_os.data.database import Database
from repair_os.data.models import Firmware
from repair_os.data.repositories.firmware import FirmwareRepository

log = logging.getLogger(__name__)

MAX_FIRMWARE_SIZE = 32 * 1024 * 1024 * 1024  # 32 ГиБ
ALLOWED_SUFFIXES = {
    ".zip",
    ".tar",
    ".md5",
    ".img",
    ".bin",
    ".tar.md5",
    ".7z",
    ".rar",
    ".gz",
    ".tgz",
    ".lz4",
    ".payload",
    ".payload.bin",
    ".dmg",
    ".ipsw",
}


@dataclass
class FileCheck:
    path: Path
    size: int
    sha256: str
    is_zip: bool
    zip_ok: bool | None = None
    zip_entries: int | None = None
    warnings: list[str] = field(default_factory=list)

    @property
    def size_human(self) -> str:
        value = float(self.size)
        for unit in ("Б", "КБ", "МБ", "ГБ", "ТБ"):
            if value < 1024 or unit == "ТБ":
                return f"{value:.2f} {unit}"
            value /= 1024
        return f"{value:.2f} ТБ"


@dataclass
class CompatibilityResult:
    level: str  # ok | warning | incompatible
    messages: list[str] = field(default_factory=list)

    @property
    def is_blocking(self) -> bool:
        return self.level == "incompatible"


class FirmwareTools:
    def __init__(self, db: Database, firmware_root: Path) -> None:
        self.db = db
        self.repo = FirmwareRepository(db)
        self.firmware_root = Path(firmware_root)
        self.firmware_root.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------ проверки
    def inspect_file(self, path: Path | str, *, deep: bool = True) -> FileCheck:
        source = Path(path)
        if not source.exists() or not source.is_file():
            raise ImportErrorOS(f"Файл не найден: {source}")
        size = source.stat().st_size
        if size == 0:
            raise ImportErrorOS("Файл пустой — вероятно, загрузка повреждена")
        if size > MAX_FIRMWARE_SIZE:
            raise ImportErrorOS("Файл слишком большой (максимум 32 ГиБ)")
        suffix = source.suffix.lower()
        if suffix not in ALLOWED_SUFFIXES and not source.name.lower().endswith(".tar.md5"):
            raise ImportErrorOS(
                f"Расширение {suffix or '—'} не поддерживается для прошивок"
            )
        result = FileCheck(
            path=source,
            size=size,
            sha256=sha256_file(source),
            is_zip=sniff_is_zip(source),
        )
        if result.is_zip and deep:
            try:
                with zipfile.ZipFile(source) as zf:
                    bad = zf.testzip()
                    result.zip_entries = len(zf.infolist())
                if bad:
                    result.zip_ok = False
                    result.warnings.append(f"Повреждённый элемент архива: {bad}")
                else:
                    result.zip_ok = True
            except (zipfile.BadZipFile, OSError) as exc:
                result.zip_ok = False
                result.warnings.append(f"Архив не читается: {exc}")
        return result

    def verify_reference(self, firmware_id: int) -> tuple[bool, str]:
        """Сверяет локальный файл с эталонной контрольной суммой записи."""
        firmware = self.repo.get(firmware_id)
        if not firmware.local_path:
            raise ValidationError("У записи нет локального файла")
        path = Path(firmware.local_path)
        if not path.exists():
            raise ValidationError(f"Файл не найден на диске: {path}")
        reference = normalize_checksum(firmware.checksum_reference or firmware.checksum_sha256)
        if not reference:
            raise ValidationError("В записи нет эталонной контрольной суммы SHA-256")
        actual = sha256_file(path)
        self.repo.update(
            firmware_id,
            {"checksum_sha256": actual, "verification_status": firmware.verification_status},
        )
        if actual != reference:
            self.repo.log_change(
                "firmware",
                "checksum_mismatch",
                firmware_id,
                f"{firmware.file_name}: {actual}",
            )
            raise IntegrityError(
                f"Контрольная сумма не совпадает.\nЭталон: {reference}\nФайл:   {actual}"
            )
        self.repo.log_change("firmware", "checksum_ok", firmware_id, firmware.file_name)
        return True, actual

    # ------------------------------------------------------------------ локальные файлы
    def attach_local_file(
        self,
        firmware_id: int,
        source: Path | str,
        *,
        copy_into_library: bool = True,
        verify_reference: bool = True,
    ) -> Firmware:
        """Прикрепляет локальный файл к записи после проверки формата и контрольной суммы.

        Вызывается только после подтверждения пользователя (см. UI).
        """
        check = self.inspect_file(source)
        firmware = self.repo.get(firmware_id)
        reference = normalize_checksum(firmware.checksum_reference)
        if reference and verify_reference:
            if check.sha256 != reference:
                raise IntegrityError(
                    "Контрольная сумма файла не совпадает с эталоном записи.\n"
                    f"Эталон: {reference}\nФайл:   {check.sha256}"
                )

        target = check.path
        if copy_into_library:
            folder = self.firmware_root / sanitize_filename(
                firmware.model_code or firmware.device_name or "unknown"
            )
            folder.mkdir(parents=True, exist_ok=True)
            target = folder / sanitize_filename(check.path.name)
            if target.exists() and sha256_file(target) != check.sha256:
                raise ImportErrorOS(
                    f"В библиотеке уже есть файл с другим содержимым: {target.name}"
                )
            if not target.exists():
                shutil.copy2(check.path, target)
        updated = self.repo.update(
            firmware_id,
            {
                "local_path": str(target),
                "file_size": check.size,
                "checksum_sha256": check.sha256,
            },
        )
        self.repo.log_change(
            "firmware",
            "attach_file",
            firmware_id,
            f"{target.name} (SHA-256 {check.sha256[:16]}…)",
        )
        return updated

    def create_from_file(
        self,
        path: Path | str,
        *,
        device_id: int | None,
        source_id: int | None = None,
        extra: dict | None = None,
        copy_into_library: bool = True,
    ) -> Firmware:
        check = self.inspect_file(path)
        payload = {
            "device_id": device_id,
            "source_id": source_id,
            "file_name": check.path.name,
            "file_size": check.size,
            "checksum_sha256": check.sha256,
            "local_path": str(check.path),
            "os_version": None,
            "build_number": None,
            "verification_status": "unverified",
            "compatibility_notes": (
                "Добавлено из локального файла. Совместимость не проверена автоматически."
            ),
        }
        payload.update(extra or {})
        record = self.repo.create(payload)
        if copy_into_library:
            record = self.attach_local_file(record.id or 0, check.path, verify_reference=False)
        return record

    # ------------------------------------------------------------------ совместимость
    def check_compatibility(self, firmware_id: int) -> CompatibilityResult:
        firmware = self.repo.get(firmware_id)
        messages: list[str] = []
        level = "ok"
        if firmware.device_id:
            device = self.db.query_one(
                "SELECT d.*, b.name AS brand_name FROM devices d JOIN brands b ON b.id = d.brand_id "
                "WHERE d.id = ?",
                (firmware.device_id,),
            )
            if not device:
                return CompatibilityResult("incompatible", ["Устройство записи удалено из каталога"])
            if firmware.model_code and device["model_code"].lower() != firmware.model_code.lower():
                level = "incompatible"
                messages.append(
                    f"Код модели прошивки ({firmware.model_code}) не совпадает с устройством "
                    f"({device['model_code']}). Установка может вывести устройство из строя."
                )
            variants = self.db.query(
                "SELECT * FROM device_variants WHERE device_id = ?", (device["id"],)
            )
            if variants:
                if firmware.region or firmware.csc:
                    matching = [
                        variant
                        for variant in variants
                        if (firmware.csc and (variant["csc"] or "").upper() == firmware.csc.upper())
                        or (
                            firmware.region
                            and (variant["region"] or "").upper() == firmware.region.upper()
                        )
                    ]
                    if not matching:
                        if level != "incompatible":
                            level = "warning"
                        messages.append(
                            "Регион/CSC прошивки не совпадает ни с одним вариантом устройства "
                            f"({', '.join(sorted({v['region'] or '—' for v in variants}))})."
                        )
                    else:
                        bootloaders = {v["bootloader"] for v in matching if v["bootloader"]}
                        if firmware.min_bootloader and bootloaders:
                            if firmware.min_bootloader.upper() not in {
                                str(item).upper() for item in bootloaders
                            }:
                                level = "warning"
                                messages.append(
                                    "Требуемая версия загрузчика не подтверждена для варианта "
                                    f"({', '.join(sorted(str(b) for b in bootloaders))})."
                                )
        else:
            if level != "incompatible":
                level = "warning"
            messages.append("Прошивка не привязана к устройству — совместимость не подтверждена")
        if not firmware.checksum_reference and not firmware.checksum_sha256:
            if level == "ok":
                level = "warning"
            messages.append("Контрольная сумма не указана — целостность файла проверить нельзя")
        if firmware.is_demo:
            messages.append("Демонстрационная запись: данные не являются проверенными")
        if firmware.verification_status in {"unverified", "rejected"}:
            messages.append("Статус проверки: " + firmware.verification_status)
        if not messages:
            messages.append("Явных несоответствий не найдено")
        return CompatibilityResult(level, messages)
