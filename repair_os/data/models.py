"""Доменные модели и валидация входных данных."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from typing import Any

from repair_os.core.errors import ValidationError

CATEGORIES = {
    "power": "Питание",
    "charging": "Зарядка",
    "usb": "USB",
    "rf": "RF / связь",
    "audio": "Аудио",
    "display": "Дисплей",
    "camera": "Камеры",
    "sensors": "Датчики",
    "memory": "Память",
    "cpu": "Процессор",
    "general": "Общие материалы",
    "software": "Программное обеспечение",
}

VERIFICATION_LABELS = {
    "unverified": "Не проверено",
    "community": "Проверено сообществом",
    "verified": "Проверено вручную",
    "rejected": "Недостоверно",
}

DOC_TYPES = {
    "pdf": "PDF-документ",
    "schematic": "Схема",
    "boardview": "BoardView",
    "photo": "Фото платы",
    "instruction": "Инструкция",
    "note": "Заметка",
    "link": "Ссылка",
    "other": "Другое",
}

SOURCE_KINDS = {
    "official": "Официальный",
    "community": "Сообщество",
    "local": "Локальный файл",
    "vendor_tool": "Инструмент производителя",
}

SIDES = {"top": "Верхняя сторона", "bottom": "Нижняя сторона"}

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_MODEL_CODE_RE = re.compile(r"^[0-9A-Za-zА-Яа-я][0-9A-Za-zА-Яа-я _./+\-()]{0,63}$")
_DESIGNATOR_RE = re.compile(r"^[A-Za-z]{1,4}[0-9]{1,6}[A-Za-z0-9]{0,4}$")


# --------------------------------------------------------------------------- утилиты
def clean_text(value: Any, *, max_len: int = 500) -> str | None:
    if value is None:
        return None
    text = " ".join(str(value).replace("\x00", "").split())
    if not text:
        return None
    if len(text) > max_len:
        raise ValidationError(f"Слишком длинное значение (максимум {max_len} символов)")
    return text


def clean_multiline(value: Any, *, max_len: int = 20000) -> str | None:
    if value is None:
        return None
    text = str(value).replace("\x00", "").replace("\r\n", "\n").strip()
    if not text:
        return None
    if len(text) > max_len:
        raise ValidationError(f"Слишком длинный текст (максимум {max_len} символов)")
    return text


def require_text(value: Any, field_name: str, *, max_len: int = 200) -> str:
    text = clean_text(value, max_len=max_len)
    if not text:
        raise ValidationError(f"Обязательное поле: {field_name}", fields={field_name: "required"})
    return text


def clean_model_code(value: Any) -> str:
    text = require_text(value, "Код модели", max_len=64)
    if not _MODEL_CODE_RE.match(text):
        raise ValidationError(
            "Код модели содержит недопустимые символы",
            fields={"model_code": "invalid"},
        )
    return text


def clean_date(value: Any, field_name: str = "Дата") -> str | None:
    if value in (None, "", "—"):
        return None
    if isinstance(value, (date, datetime)):
        return value.strftime("%Y-%m-%d")
    text = str(value).strip()
    if _DATE_RE.match(text):
        try:
            datetime.strptime(text, "%Y-%m-%d")
            return text
        except ValueError as exc:
            raise ValidationError(f"Некорректная дата: {text}") from exc
    for fmt in ("%d.%m.%Y", "%Y/%m/%d", "%d-%m-%Y"):
        try:
            return datetime.strptime(text, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    raise ValidationError(f"{field_name}: ожидается формат ГГГГ-ММ-ДД, получено «{text}»")


def clean_int(value: Any, field_name: str, *, minimum: int = 0, maximum: int | None = None) -> int | None:
    if value in (None, ""):
        return None
    try:
        number = int(str(value).replace(" ", "").replace(",", ""))
    except (TypeError, ValueError) as exc:
        raise ValidationError(f"{field_name}: ожидается целое число") from exc
    if number < minimum:
        raise ValidationError(f"{field_name}: значение не может быть меньше {minimum}")
    if maximum is not None and number > maximum:
        raise ValidationError(f"{field_name}: значение не может быть больше {maximum}")
    return number


def clean_float(value: Any, field_name: str) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ValidationError(f"{field_name}: ожидается число") from exc


def clean_enum(value: Any, allowed: dict[str, str], field_name: str, default: str | None = None) -> str:
    text = (str(value).strip() if value is not None else "") or (default or "")
    if text not in allowed:
        raise ValidationError(f"{field_name}: недопустимое значение «{text}»")
    return text


def clean_designator(value: Any) -> str:
    text = require_text(value, "Позиционное обозначение", max_len=16).upper()
    if not _DESIGNATOR_RE.match(text):
        raise ValidationError(
            "Позиционное обозначение должно иметь вид U1201, C4502, R3201",
            fields={"designator": "invalid"},
        )
    return text


def clean_bool(value: Any) -> int:
    if isinstance(value, bool):
        return int(value)
    if value is None:
        return 0
    if isinstance(value, (int, float)):
        return int(bool(value))
    return int(str(value).strip().lower() in {"1", "true", "yes", "on", "да"})


_TRANSLIT = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "e", "ж": "zh",
    "з": "z", "и": "i", "й": "y", "к": "k", "л": "l", "м": "m", "н": "n", "о": "o",
    "п": "p", "р": "r", "с": "s", "т": "t", "у": "u", "ф": "f", "х": "kh", "ц": "ts",
    "ч": "ch", "ш": "sh", "щ": "sch", "ъ": "", "ы": "y", "ь": "", "э": "e", "ю": "yu",
    "я": "ya",
}


def slugify(value: str) -> str:
    """Приводит название к slug: латиница + транслитерация кириллицы."""
    text = str(value or "").strip().lower()
    transliterated = "".join(_TRANSLIT.get(char, char) for char in text)
    slug = re.sub(r"[^a-z0-9]+", "-", transliterated).strip("-")
    if not slug:
        slug = "brand-" + str(abs(hash(value)) % 100000)
    return slug[:60]


class _Base:
    def to_dict(self) -> dict[str, Any]:
        return asdict(self)  # type: ignore[arg-type]


# --------------------------------------------------------------------------- бренды
@dataclass(slots=True)
class Brand(_Base):
    id: int | None
    slug: str
    name: str
    country: str | None = None
    website: str | None = None
    sort_order: int = 100
    is_demo: int = 0
    device_count: int = 0

    @classmethod
    def from_row(cls, row: dict[str, Any]) -> "Brand":
        return cls(
            id=row.get("id"),
            slug=row["slug"],
            name=row["name"],
            country=row.get("country"),
            website=row.get("website"),
            sort_order=int(row.get("sort_order") or 100),
            is_demo=int(row.get("is_demo") or 0),
            device_count=int(row.get("device_count") or 0),
        )

    @classmethod
    def validate(cls, data: dict[str, Any]) -> dict[str, Any]:
        name = require_text(data.get("name"), "Название бренда", max_len=80)
        slug = clean_text(data.get("slug"), max_len=60)
        if not slug:
            slug = slugify(name)
        slug = re.sub(r"[^a-z0-9\-]+", "-", slug.lower()).strip("-")
        if not slug:
            raise ValidationError("Не удалось определить slug бренда", fields={"slug": "required"})
        return {
            "name": name,
            "slug": slug,
            "country": clean_text(data.get("country"), max_len=60),
            "website": clean_text(data.get("website"), max_len=200),
            "sort_order": clean_int(data.get("sort_order"), "Порядок", minimum=0, maximum=9999) or 100,
        }


# --------------------------------------------------------------------------- устройства
@dataclass(slots=True)
class Device(_Base):
    id: int | None
    brand_id: int
    name: str
    model_code: str
    codename: str | None = None
    hardware_revision: str | None = None
    soc: str | None = None
    soc_platform: str | None = None
    ram: str | None = None
    storage: str | None = None
    os_versions: str | None = None
    release_year: int | None = None
    notes: str | None = None
    source: str | None = None
    verified: int = 0
    is_demo: int = 0
    brand_name: str = ""
    brand_slug: str = ""
    firmware_count: int = 0
    document_count: int = 0
    has_3d: int = 0
    is_favorite: int = 0

    @classmethod
    def from_row(cls, row: dict[str, Any]) -> "Device":
        return cls(
            id=row.get("id"),
            brand_id=int(row["brand_id"]),
            name=row["name"],
            model_code=row["model_code"],
            codename=row.get("codename"),
            hardware_revision=row.get("hardware_revision"),
            soc=row.get("soc"),
            soc_platform=row.get("soc_platform"),
            ram=row.get("ram"),
            storage=row.get("storage"),
            os_versions=row.get("os_versions"),
            release_year=row.get("release_year"),
            notes=row.get("notes"),
            source=row.get("source"),
            verified=int(row.get("verified") or 0),
            is_demo=int(row.get("is_demo") or 0),
            brand_name=row.get("brand_name") or "",
            brand_slug=row.get("brand_slug") or "",
            firmware_count=int(row.get("firmware_count") or 0),
            document_count=int(row.get("document_count") or 0),
            has_3d=int(row.get("has_3d") or 0),
            is_favorite=int(row.get("is_favorite") or 0),
        )

    @property
    def display_code(self) -> str:
        if self.codename:
            return f"{self.model_code} · {self.codename}"
        return self.model_code

    @classmethod
    def validate(cls, data: dict[str, Any]) -> dict[str, Any]:
        brand_id = clean_int(data.get("brand_id"), "Бренд", minimum=1)
        if not brand_id:
            raise ValidationError("Выберите бренд", fields={"brand_id": "required"})
        os_versions = data.get("os_versions")
        if isinstance(os_versions, (list, tuple)):
            os_versions = ", ".join(str(item) for item in os_versions)
        return {
            "brand_id": brand_id,
            "name": require_text(data.get("name"), "Название устройства", max_len=120),
            "model_code": clean_model_code(data.get("model_code")),
            "codename": clean_text(data.get("codename"), max_len=64),
            "hardware_revision": clean_text(data.get("hardware_revision"), max_len=64),
            "soc": clean_text(data.get("soc"), max_len=80),
            "soc_platform": clean_text(data.get("soc_platform"), max_len=80),
            "ram": clean_text(data.get("ram"), max_len=40),
            "storage": clean_text(data.get("storage"), max_len=40),
            "os_versions": clean_text(os_versions, max_len=200),
            "release_year": clean_int(data.get("release_year"), "Год выпуска", minimum=1990, maximum=2100),
            "notes": clean_multiline(data.get("notes")),
            "source": clean_text(data.get("source"), max_len=200),
            "verified": clean_bool(data.get("verified")),
        }


@dataclass(slots=True)
class DeviceVariant(_Base):
    id: int | None
    device_id: int
    name: str
    model_code: str
    region: str | None = None
    csc: str | None = None
    ram: str | None = None
    storage: str | None = None
    bootloader: str | None = None
    notes: str | None = None
    is_demo: int = 0

    @classmethod
    def from_row(cls, row: dict[str, Any]) -> "DeviceVariant":
        return cls(
            id=row.get("id"),
            device_id=int(row["device_id"]),
            name=row["name"],
            model_code=row["model_code"],
            region=row.get("region"),
            csc=row.get("csc"),
            ram=row.get("ram"),
            storage=row.get("storage"),
            bootloader=row.get("bootloader"),
            notes=row.get("notes"),
            is_demo=int(row.get("is_demo") or 0),
        )

    @classmethod
    def validate(cls, data: dict[str, Any]) -> dict[str, Any]:
        device_id = clean_int(data.get("device_id"), "Устройство", minimum=1)
        if not device_id:
            raise ValidationError("Не выбрано устройство", fields={"device_id": "required"})
        return {
            "device_id": device_id,
            "name": require_text(data.get("name"), "Название варианта", max_len=120),
            "model_code": clean_model_code(data.get("model_code")),
            "region": clean_text(data.get("region"), max_len=40),
            "csc": clean_text(data.get("csc"), max_len=20),
            "ram": clean_text(data.get("ram"), max_len=40),
            "storage": clean_text(data.get("storage"), max_len=40),
            "bootloader": clean_text(data.get("bootloader"), max_len=40),
            "notes": clean_multiline(data.get("notes")),
        }


# --------------------------------------------------------------------------- прошивки
@dataclass(slots=True)
class FirmwareSource(_Base):
    id: int | None
    name: str
    url: str | None = None
    kind: str = "community"
    trusted: int = 0
    notes: str | None = None
    last_checked: str | None = None
    is_demo: int = 0

    @classmethod
    def from_row(cls, row: dict[str, Any]) -> "FirmwareSource":
        return cls(
            id=row.get("id"),
            name=row["name"],
            url=row.get("url"),
            kind=row.get("kind") or "community",
            trusted=int(row.get("trusted") or 0),
            notes=row.get("notes"),
            last_checked=row.get("last_checked"),
            is_demo=int(row.get("is_demo") or 0),
        )


@dataclass(slots=True)
class Firmware(_Base):
    id: int | None
    file_name: str
    device_id: int | None = None
    variant_id: int | None = None
    source_id: int | None = None
    title: str | None = None
    model_code: str | None = None
    os_version: str | None = None
    build_number: str | None = None
    region: str | None = None
    csc: str | None = None
    release_date: str | None = None
    file_size: int | None = None
    checksum_sha256: str | None = None
    checksum_reference: str | None = None
    download_url: str | None = None
    local_path: str | None = None
    install_instructions: str | None = None
    compatibility_notes: str | None = None
    min_bootloader: str | None = None
    verification_status: str = "unverified"
    is_demo: int = 0
    created_at: str | None = None
    updated_at: str | None = None
    device_name: str = ""
    brand_name: str = ""
    source_name: str = ""

    @classmethod
    def from_row(cls, row: dict[str, Any]) -> "Firmware":
        return cls(
            id=row.get("id"),
            file_name=row["file_name"],
            device_id=row.get("device_id"),
            variant_id=row.get("variant_id"),
            source_id=row.get("source_id"),
            title=row.get("title"),
            model_code=row.get("model_code"),
            os_version=row.get("os_version"),
            build_number=row.get("build_number"),
            region=row.get("region"),
            csc=row.get("csc"),
            release_date=row.get("release_date"),
            file_size=row.get("file_size"),
            checksum_sha256=row.get("checksum_sha256"),
            checksum_reference=row.get("checksum_reference"),
            download_url=row.get("download_url"),
            local_path=row.get("local_path"),
            install_instructions=row.get("install_instructions"),
            compatibility_notes=row.get("compatibility_notes"),
            min_bootloader=row.get("min_bootloader"),
            verification_status=row.get("verification_status") or "unverified",
            is_demo=int(row.get("is_demo") or 0),
            created_at=row.get("created_at"),
            updated_at=row.get("updated_at"),
            device_name=row.get("device_name") or "",
            brand_name=row.get("brand_name") or "",
            source_name=row.get("source_name") or "",
        )

    @property
    def size_human(self) -> str:
        return human_size(self.file_size)


def human_size(size: int | None) -> str:
    if size is None:
        return "—"
    value = float(size)
    for unit in ("Б", "КБ", "МБ", "ГБ", "ТБ"):
        if value < 1024 or unit == "ТБ":
            return f"{value:.0f} {unit}" if unit == "Б" else f"{value:.2f} {unit}"
        value /= 1024
    return f"{value:.2f} ТБ"


# --------------------------------------------------------------------------- платы
@dataclass(slots=True)
class BoardModel(_Base):
    id: int | None
    name: str
    device_id: int | None = None
    board_code: str | None = None
    revision: str | None = None
    package_path: str | None = None
    format: str | None = None
    has_3d: int = 0
    photo_top: str | None = None
    photo_bottom: str | None = None
    source: str | None = None
    license_note: str | None = None
    notes: str | None = None
    is_demo: int = 0
    width_mm: float | None = None
    length_mm: float | None = None
    thickness_mm: float | None = None
    package_checksum: str | None = None
    imported_at: str | None = None
    device_name: str = ""
    component_count: int = 0

    @classmethod
    def from_row(cls, row: dict[str, Any]) -> "BoardModel":
        return cls(
            id=row.get("id"),
            name=row["name"],
            device_id=row.get("device_id"),
            board_code=row.get("board_code"),
            revision=row.get("revision"),
            package_path=row.get("package_path"),
            format=row.get("format"),
            has_3d=int(row.get("has_3d") or 0),
            photo_top=row.get("photo_top"),
            photo_bottom=row.get("photo_bottom"),
            source=row.get("source"),
            license_note=row.get("license_note"),
            notes=row.get("notes"),
            is_demo=int(row.get("is_demo") or 0),
            width_mm=row.get("width_mm"),
            length_mm=row.get("length_mm"),
            thickness_mm=row.get("thickness_mm"),
            package_checksum=row.get("package_checksum"),
            imported_at=row.get("imported_at"),
            device_name=row.get("device_name") or "",
            component_count=int(row.get("component_count") or 0),
        )


@dataclass(slots=True)
class BoardComponent(_Base):
    id: int | None
    board_model_id: int
    designator: str
    side: str = "top"
    layer: str | None = None
    component_type: str | None = None
    part_marking: str | None = None
    purpose: str | None = None
    package_type: str | None = None
    pos_x: float | None = None
    pos_y: float | None = None
    pos_z: float | None = None
    size_x: float | None = None
    size_y: float | None = None
    size_z: float | None = None
    rotation: float = 0.0
    marker_u: float | None = None
    marker_v: float | None = None
    notes: str | None = None
    metadata_json: str | None = None
    is_demo: int = 0

    @classmethod
    def from_row(cls, row: dict[str, Any]) -> "BoardComponent":
        return cls(
            id=row.get("id"),
            board_model_id=int(row["board_model_id"]),
            designator=row["designator"],
            side=row.get("side") or "top",
            layer=row.get("layer"),
            component_type=row.get("component_type"),
            part_marking=row.get("part_marking"),
            purpose=row.get("purpose"),
            package_type=row.get("package_type"),
            pos_x=row.get("pos_x"),
            pos_y=row.get("pos_y"),
            pos_z=row.get("pos_z"),
            size_x=row.get("size_x"),
            size_y=row.get("size_y"),
            size_z=row.get("size_z"),
            rotation=float(row.get("rotation") or 0.0),
            marker_u=row.get("marker_u"),
            marker_v=row.get("marker_v"),
            notes=row.get("notes"),
            metadata_json=row.get("metadata_json"),
            is_demo=int(row.get("is_demo") or 0),
        )

    @classmethod
    def validate(cls, data: dict[str, Any]) -> dict[str, Any]:
        board_model_id = clean_int(data.get("board_model_id"), "Плата", minimum=1)
        if not board_model_id:
            raise ValidationError("Не выбрана плата", fields={"board_model_id": "required"})
        return {
            "board_model_id": board_model_id,
            "designator": clean_designator(data.get("designator")),
            "side": clean_enum(data.get("side"), SIDES, "Сторона", "top"),
            "layer": clean_text(data.get("layer"), max_len=40),
            "component_type": clean_text(data.get("component_type"), max_len=40),
            "part_marking": clean_text(data.get("part_marking"), max_len=80),
            "purpose": clean_text(data.get("purpose"), max_len=200),
            "package_type": clean_text(data.get("package_type"), max_len=40),
            "pos_x": clean_float(data.get("pos_x"), "X"),
            "pos_y": clean_float(data.get("pos_y"), "Y"),
            "pos_z": clean_float(data.get("pos_z"), "Z"),
            "size_x": clean_float(data.get("size_x"), "Ширина"),
            "size_y": clean_float(data.get("size_y"), "Длина"),
            "size_z": clean_float(data.get("size_z"), "Высота"),
            "rotation": clean_float(data.get("rotation"), "Поворот") or 0.0,
            "marker_u": clean_float(data.get("marker_u"), "U"),
            "marker_v": clean_float(data.get("marker_v"), "V"),
            "notes": clean_multiline(data.get("notes")),
        }


@dataclass(slots=True)
class BoardAnnotation(_Base):
    id: int | None
    board_model_id: int
    label: str
    component_id: int | None = None
    body: str | None = None
    color: str = "#3d8bfd"
    created_at: str | None = None

    @classmethod
    def from_row(cls, row: dict[str, Any]) -> "BoardAnnotation":
        return cls(
            id=row.get("id"),
            board_model_id=int(row["board_model_id"]),
            label=row["label"],
            component_id=row.get("component_id"),
            body=row.get("body"),
            color=row.get("color") or "#3d8bfd",
            created_at=row.get("created_at"),
        )


# --------------------------------------------------------------------------- библиотека
@dataclass(slots=True)
class TechnicalDocument(_Base):
    id: int | None
    title: str
    category: str = "general"
    doc_type: str = "pdf"
    device_id: int | None = None
    brand_id: int | None = None
    file_path: str | None = None
    source_url: str | None = None
    description: str | None = None
    tags: str | None = None
    verification_status: str = "unverified"
    verified_at: str | None = None
    license_note: str | None = None
    is_demo: int = 0
    created_at: str | None = None
    updated_at: str | None = None
    device_name: str = ""
    brand_name: str = ""

    @classmethod
    def from_row(cls, row: dict[str, Any]) -> "TechnicalDocument":
        return cls(
            id=row.get("id"),
            title=row["title"],
            category=row.get("category") or "general",
            doc_type=row.get("doc_type") or "pdf",
            device_id=row.get("device_id"),
            brand_id=row.get("brand_id"),
            file_path=row.get("file_path"),
            source_url=row.get("source_url"),
            description=row.get("description"),
            tags=row.get("tags"),
            verification_status=row.get("verification_status") or "unverified",
            verified_at=row.get("verified_at"),
            license_note=row.get("license_note"),
            is_demo=int(row.get("is_demo") or 0),
            created_at=row.get("created_at"),
            updated_at=row.get("updated_at"),
            device_name=row.get("device_name") or "",
            brand_name=row.get("brand_name") or "",
        )


@dataclass(slots=True)
class ComponentReference(_Base):
    id: int | None
    designator: str | None = None
    device_id: int | None = None
    document_id: int | None = None
    component_type: str | None = None
    marking: str | None = None
    description: str | None = None
    source_url: str | None = None
    is_demo: int = 0

    @classmethod
    def from_row(cls, row: dict[str, Any]) -> "ComponentReference":
        return cls(
            id=row.get("id"),
            designator=row.get("designator"),
            device_id=row.get("device_id"),
            document_id=row.get("document_id"),
            component_type=row.get("component_type"),
            marking=row.get("marking"),
            description=row.get("description"),
            source_url=row.get("source_url"),
            is_demo=int(row.get("is_demo") or 0),
        )


@dataclass(slots=True)
class RepairNote(_Base):
    id: int | None
    title: str
    device_id: int | None = None
    board_component_id: int | None = None
    body: str | None = None
    category: str = "general"
    created_at: str | None = None
    updated_at: str | None = None

    @classmethod
    def from_row(cls, row: dict[str, Any]) -> "RepairNote":
        return cls(
            id=row.get("id"),
            title=row["title"],
            device_id=row.get("device_id"),
            board_component_id=row.get("board_component_id"),
            body=row.get("body"),
            category=row.get("category") or "general",
            created_at=row.get("created_at"),
            updated_at=row.get("updated_at"),
        )


@dataclass(slots=True)
class SearchHit(_Base):
    kind: str
    title: str
    subtitle: str
    device_id: int | None = None
    brand_id: int | None = None
    brand_slug: str = ""
    extra: dict[str, Any] = field(default_factory=dict)
