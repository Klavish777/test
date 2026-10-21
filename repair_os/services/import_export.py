"""Импорт и экспорт данных: устройства, прошивки, материалы библиотеки.

Поддерживаются CSV (UTF-8 с BOM или Windows-1251, разделитель ``;`` или ``,``)
и JSON (массив объектов или объект с ключом ``items``/``data``).

Каждый импорт выполняется в два шага: проверка (``dry_run=True``) и запись.
Отчёт содержит созданные, обновлённые, пропущенные записи и список ошибок.
"""

from __future__ import annotations

import csv
import io
import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from repair_os.core.errors import ImportErrorOS, RepairOSError, UnsupportedFormatError
from repair_os.core.security import validate_import_file
from repair_os.data.database import Database
from repair_os.data.repositories.brands import BrandRepository
from repair_os.data.repositories.devices import DeviceRepository
from repair_os.data.repositories.firmware import FirmwareRepository
from repair_os.data.repositories.library import LibraryRepository

log = logging.getLogger(__name__)

MAX_IMPORT_ROWS = 20000


@dataclass
class ImportIssue:
    row: int
    message: str
    severity: str = "error"


@dataclass
class ImportReport:
    kind: str
    total: int = 0
    created: int = 0
    updated: int = 0
    skipped: int = 0
    dry_run: bool = False
    issues: list[ImportIssue] = field(default_factory=list)

    @property
    def errors(self) -> list[ImportIssue]:
        return [issue for issue in self.issues if issue.severity == "error"]

    @property
    def warnings(self) -> list[ImportIssue]:
        return [issue for issue in self.issues if issue.severity == "warning"]

    @property
    def ok(self) -> bool:
        return not self.errors

    def summary(self) -> str:
        mode = "проверка" if self.dry_run else "импорт"
        parts = [
            f"{mode}: всего строк {self.total}",
            f"создано {self.created}",
            f"обновлено {self.updated}",
            f"пропущено {self.skipped}",
            f"ошибок {len(self.errors)}",
        ]
        return ", ".join(parts)


# --------------------------------------------------------------------------- чтение файлов
DEVICE_ALIASES = {
    "brand": ("brand", "бренд", "производитель", "brand_name", "vendor"),
    "name": ("name", "название", "модель", "device", "device_name", "устройство"),
    "model_code": ("model_code", "код", "код модели", "model", "modelcode", "sm", "номер модели"),
    "codename": ("codename", "кодовое имя", "code_name", "device_codename"),
    "hardware_revision": ("hardware_revision", "ревизия", "hw_rev", "revision", "аппаратная ревизия"),
    "soc": ("soc", "процессор", "cpu", "chipset"),
    "soc_platform": ("soc_platform", "платформа", "platform"),
    "ram": ("ram", "озу", "memory"),
    "storage": ("storage", "память", "rom", "накопитель"),
    "os_versions": ("os_versions", "ос", "os", "версии ос", "android"),
    "release_year": ("release_year", "год", "year", "год выпуска"),
    "notes": ("notes", "примечание", "комментарий", "note"),
    "source": ("source", "источник"),
    "verified": ("verified", "проверено", "verified_flag"),
}

FIRMWARE_ALIASES = {
    "file_name": ("file_name", "файл", "имя файла", "filename", "название файла"),
    "title": ("title", "название", "заголовок"),
    "device_id": ("device_id",),
    "model_code": ("model_code", "код модели", "модель", "model", "modelcode"),
    "brand": ("brand", "бренд", "производитель"),
    "os_version": ("os_version", "версия ос", "android", "os", "ios"),
    "build_number": ("build_number", "сборка", "build", "номер сборки"),
    "region": ("region", "регион"),
    "csc": ("csc",),
    "release_date": ("release_date", "дата", "дата выпуска", "date"),
    "file_size": ("file_size", "размер", "размер файла", "size"),
    "checksum_sha256": ("checksum_sha256", "sha256", "контрольная сумма", "checksum"),
    "checksum_reference": ("checksum_reference", "эталонная сумма", "reference_checksum"),
    "download_url": ("download_url", "ссылка", "url", "download"),
    "local_path": ("local_path", "локальный файл", "путь"),
    "install_instructions": ("install_instructions", "инструкция", "установка"),
    "compatibility_notes": ("compatibility_notes", "совместимость", "ограничения"),
    "min_bootloader": ("min_bootloader", "загрузчик", "bootloader"),
    "source": ("source", "источник"),
    "verification_status": ("verification_status", "статус проверки", "проверка"),
}

DOCUMENT_ALIASES = {
    "title": ("title", "название", "заголовок"),
    "category": ("category", "категория"),
    "doc_type": ("doc_type", "тип", "формат"),
    "model_code": ("model_code", "код модели", "модель"),
    "device_id": ("device_id",),
    "file_path": ("file_path", "файл", "путь"),
    "source_url": ("source_url", "ссылка", "url"),
    "description": ("description", "описание"),
    "tags": ("tags", "теги", "метки"),
    "verification_status": ("verification_status", "статус проверки"),
    "license_note": ("license_note", "лицензия", "права"),
}

_ALIASES_BY_KIND = {
    "devices": DEVICE_ALIASES,
    "firmware": FIRMWARE_ALIASES,
    "documents": DOCUMENT_ALIASES,
}


def _decode_bytes(raw: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-8", "cp1251"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise ImportErrorOS("Не удалось определить кодировку файла (ожидается UTF-8 или Windows-1251)")


def read_rows(path: Path | str, *, kind: str) -> list[dict[str, Any]]:
    """Читает CSV/JSON и приводит заголовки к внутренним именам полей."""
    allowed = {".csv", ".json"}
    source = validate_import_file(path, allowed)
    try:
        text = _decode_bytes(source.read_bytes())
    except OSError as exc:
        raise ImportErrorOS(f"Не удалось прочитать файл: {exc}") from exc

    if source.suffix.lower() == ".json":
        try:
            payload = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ImportErrorOS(f"Некорректный JSON: {exc.msg} (строка {exc.lineno})") from exc
        if isinstance(payload, dict):
            for key in ("items", "data", "records", "devices", "firmware", "documents"):
                if isinstance(payload.get(key), list):
                    payload = payload[key]
                    break
        if not isinstance(payload, list):
            raise ImportErrorOS("JSON должен содержать массив записей")
        rows: list[dict[str, Any]] = []
        for index, item in enumerate(payload, start=1):
            if not isinstance(item, dict):
                raise ImportErrorOS(f"Элемент №{index} не является объектом")
            rows.append({str(k).strip(): v for k, v in item.items()})
    else:
        sample = text[:4096]
        delimiter = ";" if sample.count(";") > sample.count(",") else ","
        reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)
        if not reader.fieldnames:
            raise ImportErrorOS("В CSV не найдена строка заголовков")
        rows = []
        for raw in reader:
            rows.append(
                {
                    str(key).strip(): value
                    for key, value in raw.items()
                    if key is not None and (value or "").strip() != ""
                }
            )
    if len(rows) > MAX_IMPORT_ROWS:
        raise ImportErrorOS(f"Слишком много строк: {len(rows)} (максимум {MAX_IMPORT_ROWS})")
    return [_normalize_keys(row, kind) for row in rows]


def _normalize_keys(row: dict[str, Any], kind: str) -> dict[str, Any]:
    aliases = _ALIASES_BY_KIND.get(kind, {})
    reverse: dict[str, str] = {}
    for field_name, variants in aliases.items():
        for variant in variants:
            reverse[variant.strip().lower()] = field_name
    result: dict[str, Any] = {}
    for key, value in row.items():
        canonical = reverse.get(str(key).strip().lower(), str(key).strip())
        if canonical not in result or result[canonical] in (None, ""):
            result[canonical] = value
    return result


def _is_truthy(value: Any) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "on", "да", "verified", "проверено"}


# --------------------------------------------------------------------------- импорт
class ImportService:
    def __init__(self, db: Database) -> None:
        self.db = db
        self.brands = BrandRepository(db)
        self.devices = DeviceRepository(db)
        self.firmware = FirmwareRepository(db)
        self.library = LibraryRepository(db)

    # ------------------------------------------------------------------ устройства
    def import_devices(
        self, path: Path | str, *, dry_run: bool = True, create_brands: bool = True
    ) -> ImportReport:
        report = ImportReport(kind="devices", dry_run=dry_run)
        try:
            rows = read_rows(path, kind="devices")
        except RepairOSError as exc:
            report.issues.append(ImportIssue(0, str(exc)))
            return report
        report.total = len(rows)
        brand_cache = {brand.name.lower(): brand for brand in self.brands.list()}
        brand_cache.update({brand.slug.lower(): brand for brand in self.brands.list()})

        for index, row in enumerate(rows, start=1):
            try:
                brand_name = str(row.get("brand") or "").strip()
                if not brand_name:
                    raise ImportErrorOS("Не указан бренд")
                brand = brand_cache.get(brand_name.lower())
                if brand is None and not create_brands:
                    raise ImportErrorOS(f"Бренд «{brand_name}» отсутствует в базе")

                payload = {
                    "brand_id": brand.id if brand else None,
                    "name": row.get("name"),
                    "model_code": row.get("model_code"),
                    "codename": row.get("codename"),
                    "hardware_revision": row.get("hardware_revision"),
                    "soc": row.get("soc"),
                    "soc_platform": row.get("soc_platform"),
                    "ram": row.get("ram"),
                    "storage": row.get("storage"),
                    "os_versions": row.get("os_versions"),
                    "release_year": row.get("release_year"),
                    "notes": row.get("notes"),
                    "source": row.get("source"),
                    "verified": _is_truthy(row.get("verified")),
                }
                # Проверка выполняется и в режиме dry_run, чтобы отчёт был достоверным.
                from repair_os.data.models import Device as DeviceModel

                if brand is None:
                    validated = DeviceModel.validate({**payload, "brand_id": 1})
                    validated.pop("brand_id", None)
                else:
                    validated = DeviceModel.validate(payload)

                existing = self._find_existing_device(
                    brand.id if brand else None, row, payload
                )
                if existing:
                    if not dry_run:
                        self.devices.update(int(existing["id"]), payload)
                    report.updated += 1
                else:
                    if not dry_run:
                        if brand is None:
                            brand = self.brands.create(
                                {"name": brand_name, "sort_order": 500}
                            )
                            brand_cache[brand_name.lower()] = brand
                            payload["brand_id"] = brand.id
                            report.issues.append(
                                ImportIssue(
                                    index, f"Создан новый бренд «{brand_name}»", "warning"
                                )
                            )
                        self.devices.create(payload, is_demo=0)
                    report.created += 1
            except RepairOSError as exc:
                report.skipped += 1
                report.issues.append(ImportIssue(index, str(exc)))
        return report

    def _find_existing_device(
        self, brand_id: int | None, row: dict[str, Any], payload: dict[str, Any]
    ) -> dict[str, Any] | None:
        """Ищет существующее устройство.

        Сопоставление идёт по бренду и точному коду модели. Если в строке импорта
        указаны кодовое имя или ревизия, они тоже должны совпадать — так один и тот
        же код модели с разными ревизиями не превращается в дубликат.
        """
        if not brand_id and payload.get("brand_id"):
            brand_id = int(payload["brand_id"])
        if not brand_id:
            return None
        candidates = self.db.query(
            "SELECT * FROM devices WHERE brand_id = ? AND lower(model_code) = lower(?)",
            (brand_id, str(row.get("model_code") or "")),
        )
        codename = str(row.get("codename") or "").strip().lower()
        revision = str(row.get("hardware_revision") or "").strip().lower()
        for candidate in candidates:
            if codename and (candidate.get("codename") or "").strip().lower() != codename:
                continue
            if revision and (candidate.get("hardware_revision") or "").strip().lower() != revision:
                continue
            return candidate
        return None

    # ------------------------------------------------------------------ прошивки
    def import_firmware(self, path: Path | str, *, dry_run: bool = True) -> ImportReport:
        report = ImportReport(kind="firmware", dry_run=dry_run)
        try:
            rows = read_rows(path, kind="firmware")
        except RepairOSError as exc:
            report.issues.append(ImportIssue(0, str(exc)))
            return report
        report.total = len(rows)
        sources = {source.name.lower(): source for source in self.firmware.sources()}

        for index, row in enumerate(rows, start=1):
            try:
                model_code = str(row.get("model_code") or "").strip()
                device = self.devices.find_by_model_code(model_code) if model_code else None
                if device is None and not row.get("device_id"):
                    raise ImportErrorOS(
                        "Модель не найдена в каталоге: сначала импортируйте устройство "
                        "или укажите device_id (совместимость по названию не проверяется)"
                    )
                source_id = None
                source_name = str(row.get("source") or "").strip()
                if source_name:
                    source = sources.get(source_name.lower())
                    if source is None and not dry_run:
                        source = self.firmware.create_source(
                            {"name": source_name, "kind": "community"}
                        )
                        sources[source_name.lower()] = source
                    source_id = source.id if source else None

                payload = {
                    "device_id": device.id if device else row.get("device_id"),
                    "source_id": source_id,
                    "title": row.get("title"),
                    "file_name": row.get("file_name"),
                    "model_code": model_code or (device.model_code if device else None),
                    "os_version": row.get("os_version"),
                    "build_number": row.get("build_number"),
                    "region": row.get("region"),
                    "csc": row.get("csc"),
                    "release_date": row.get("release_date"),
                    "file_size": row.get("file_size"),
                    "checksum_sha256": row.get("checksum_sha256"),
                    "checksum_reference": row.get("checksum_reference"),
                    "download_url": row.get("download_url"),
                    "local_path": row.get("local_path"),
                    "install_instructions": row.get("install_instructions"),
                    "compatibility_notes": row.get("compatibility_notes"),
                    "min_bootloader": row.get("min_bootloader"),
                    "verification_status": str(row.get("verification_status") or "unverified")
                    .strip()
                    .lower(),
                }
                dup = self.db.query_one(
                    "SELECT id FROM firmware WHERE lower(file_name) = lower(?) "
                    "AND IFNULL(model_code,'') = IFNULL(?, '')",
                    (str(payload["file_name"] or ""), payload["model_code"]),
                )
                if dup:
                    if not dry_run:
                        self.firmware.update(int(dup["id"]), payload)
                    report.updated += 1
                else:
                    if not dry_run:
                        self.firmware.create(payload)
                    report.created += 1
            except RepairOSError as exc:
                report.skipped += 1
                report.issues.append(ImportIssue(index, str(exc)))
        return report

    # ------------------------------------------------------------------ материалы
    def import_documents(self, path: Path | str, *, dry_run: bool = True) -> ImportReport:
        report = ImportReport(kind="documents", dry_run=dry_run)
        try:
            rows = read_rows(path, kind="documents")
        except RepairOSError as exc:
            report.issues.append(ImportIssue(0, str(exc)))
            return report
        report.total = len(rows)
        for index, row in enumerate(rows, start=1):
            try:
                device_id = row.get("device_id")
                if not device_id and row.get("model_code"):
                    device = self.devices.find_by_model_code(str(row["model_code"]))
                    device_id = device.id if device else None
                payload = {
                    "title": row.get("title"),
                    "category": str(row.get("category") or "general").strip().lower(),
                    "doc_type": str(row.get("doc_type") or "other").strip().lower(),
                    "device_id": device_id,
                    "file_path": row.get("file_path"),
                    "source_url": row.get("source_url"),
                    "description": row.get("description"),
                    "tags": row.get("tags"),
                    "verification_status": str(
                        row.get("verification_status") or "unverified"
                    ).strip().lower(),
                    "license_note": row.get("license_note"),
                }
                if not dry_run:
                    self.library.create_document(payload)
                report.created += 1
            except RepairOSError as exc:
                report.skipped += 1
                report.issues.append(ImportIssue(index, str(exc)))
        return report

    # ------------------------------------------------------------------ безопасность
    @staticmethod
    def inspect_archive(path: Path | str) -> dict[str, Any]:
        """Проверка ZIP-архива перед использованием (без распаковки)."""
        import zipfile

        from repair_os.core.security import sniff_is_zip

        target = Path(path)
        if not sniff_is_zip(target):
            raise UnsupportedFormatError("Файл не является ZIP-архивом")
        with zipfile.ZipFile(target) as zf:
            infos = zf.infolist()
        return {
            "entries": len(infos),
            "uncompressed": sum(info.file_size for info in infos),
            "compressed": sum(info.compress_size for info in infos),
            "suspicious_paths": [
                info.filename
                for info in infos
                if ".." in info.filename.replace("\\", "/").split("/")
                or info.filename.startswith(("/", "\\"))
            ],
        }


# --------------------------------------------------------------------------- экспорт
def export_rows(path: Path | str, rows: list[dict[str, Any]], *, fieldnames: list[str], delimiter: str = ";") -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, delimiter=delimiter, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key) for key in fieldnames})
    return target


TEMPLATES: dict[str, tuple[str, list[dict[str, Any]]]] = {
    "devices": (
        "devices_template.csv",
        [
            {
                "Бренд": "Samsung",
                "Название": "Galaxy A52",
                "Код модели": "SM-A525F",
                "Кодовое имя": "a52q",
                "Ревизия": "rev1",
                "Процессор": "Exynos 9611",
                "ОЗУ": "6 GB",
                "Память": "128 GB",
                "Версии ОС": "Android 11, 12, 13",
                "Год": "2021",
                "Проверено": "0",
                "Источник": "https://example.org/device-db",
                "Примечание": "Пример строки — замените данными из проверенного источника",
            }
        ],
    ),
    "firmware": (
        "firmware_template.csv",
        [
            {
                "Файл": "SM-A525F_1_20230101120000.zip",
                "Код модели": "SM-A525F",
                "Версия ОС": "Android 13",
                "Сборка": "A525FXXU4DWB1",
                "Регион": "SER",
                "CSC": "SER",
                "Дата": "2023-02-14",
                "Размер файла": "3500000000",
                "Ссылка": "https://example.org/firmware",
                "SHA256": "",
                "Источник": "Пример источника",
                "Статус проверки": "unverified",
                "Совместимость": "Укажите ограничения по загрузчику и ревизии",
                "Инструкция": "Опишите порядок установки",
            }
        ],
    ),
    "documents": (
        "documents_template.csv",
        [
            {
                "Название": "Схема питания (пример)",
                "Категория": "power",
                "Тип": "schematic",
                "Код модели": "SM-A525F",
                "Файл": "",
                "Ссылка": "https://example.org/schematic",
                "Описание": "Пример записи, не является реальной документацией",
                "Теги": "power,pmic",
                "Статус проверки": "unverified",
            }
        ],
    ),
}


def write_template(kind: str, destination: Path | str) -> Path:
    if kind not in TEMPLATES:
        raise RepairOSError(f"Неизвестный тип шаблона: {kind}")
    filename, rows = TEMPLATES[kind]
    target = Path(destination)
    if target.is_dir() or not target.suffix:
        target = target / filename
    return export_rows(target, rows, fieldnames=list(rows[0].keys()))


def install_sample_files(directory: Path) -> list[Path]:
    directory.mkdir(parents=True, exist_ok=True)
    written = []
    for kind in TEMPLATES:
        written.append(write_template(kind, directory))
    return written
