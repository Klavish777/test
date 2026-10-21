"""Импорт/экспорт пакетов плат BoardView (собственный открытый формат JSON).

Формат ``smartphone-repair-os-board`` версии 1::

    {
      "format": "smartphone-repair-os-board",
      "version": 1,
      "board": {
        "name": "Плата …", "board_code": "…", "revision": "…",
        "dimensions": {"width": 62.0, "length": 128.0, "thickness": 1.0},
        "source": "…", "license_note": "…", "notes": "…",
        "photo_top": "top.jpg", "photo_bottom": "bottom.jpg"
      },
      "components": [
        {"designator": "U1201", "side": "top", "layer": "power",
         "type": "IC", "marking": "PM8150", "purpose": "PMIC",
         "position": {"x": 10.0, "y": 20.0, "z": 0.6},
         "size": {"x": 3.0, "y": 3.0, "z": 1.0}, "rotation": 0,
         "marker": {"u": 0.42, "v": 0.55}, "notes": "…"}
      ],
      "annotations": [{"label": "Нет питания", "body": "…", "component": "U1201"}]
    }

Координаты — в миллиметрах, начало в левом нижнем углу платы, ось Y направлена
вверх, Z — толщина. ``marker.u``/``marker.v`` — относительные координаты метки на
фотографии (0..1).

Приложение **не придумывает** геометрию: если у компонента нет ``position`` и
``size``, он не рисуется объёмным телом, а показывается только маркером в списке
и на фото. Импорт фиксируется в журнале изменений.
"""

from __future__ import annotations

import json
import logging
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from repair_os.core.errors import ImportErrorOS, ValidationError
from repair_os.core.security import (
    ensure_within,
    safe_extract_zip,
    sanitize_filename,
    sha256_file,
)
from repair_os.data.database import Database
from repair_os.data.models import BoardComponent, BoardModel
from repair_os.data.repositories.boards import BoardRepository
from repair_os.data.repositories.devices import DeviceRepository

log = logging.getLogger(__name__)

PACKAGE_FORMAT = "smartphone-repair-os-board"
PACKAGE_VERSION = 1
SUPPORTED_EXTENSIONS = {".json"}
MAX_COMPONENTS = 20000
MAX_FILE_SIZE = 512 * 1024 * 1024


@dataclass
class PackageSummary:
    name: str
    board_code: str | None
    components: int
    annotations: int
    has_dimensions: bool
    sides: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    assets: list[str] = field(default_factory=list)


def _as_float(value: Any, field_name: str) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ValidationError(f"{field_name}: ожидается число") from exc


def read_package(path: Path | str) -> dict[str, Any]:
    source = Path(path)
    if not source.exists() or not source.is_file():
        raise ImportErrorOS(f"Файл не найден: {source}")
    if source.suffix.lower() not in SUPPORTED_EXTENSIONS:
        raise ImportErrorOS(
            "Поддерживается только JSON-пакет BoardView "
            "(BRD/BDV/PCB-форматы требуют конвертации — см. docs/BOARDVIEW_FORMAT.md)"
        )
    if source.stat().st_size > MAX_FILE_SIZE:
        raise ImportErrorOS("Файл пакета слишком большой")
    try:
        payload = json.loads(source.read_text(encoding="utf-8-sig"))
    except UnicodeDecodeError as exc:
        raise ImportErrorOS("Пакет должен быть в кодировке UTF-8") from exc
    except json.JSONDecodeError as exc:
        raise ImportErrorOS(f"Некорректный JSON: {exc.msg} (строка {exc.lineno})") from exc
    if not isinstance(payload, dict):
        raise ImportErrorOS("Корневой элемент пакета должен быть объектом")
    if payload.get("format") != PACKAGE_FORMAT:
        raise ImportErrorOS(
            f"Неизвестный формат пакета: {payload.get('format')!r}. "
            f"Ожидается {PACKAGE_FORMAT!r}"
        )
    version = payload.get("version")
    if version != PACKAGE_VERSION:
        raise ImportErrorOS(
            f"Неподдерживаемая версия пакета {version!r} (поддерживается {PACKAGE_VERSION})"
        )
    if not isinstance(payload.get("components"), list):
        raise ImportErrorOS("В пакете отсутствует массив components")
    if len(payload["components"]) > MAX_COMPONENTS:
        raise ImportErrorOS(f"Слишком много компонентов (максимум {MAX_COMPONENTS})")
    if not isinstance(payload.get("board"), dict):
        raise ImportErrorOS("В пакете отсутствует объект board")
    return payload


def summarize(payload: dict[str, Any]) -> PackageSummary:
    board = payload.get("board", {})
    components = payload.get("components", [])
    dims = board.get("dimensions") or {}
    warnings: list[str] = []
    sides = sorted({str(item.get("side") or "top").lower() for item in components if isinstance(item, dict)})
    if not dims:
        warnings.append("Не заданы размеры платы — 3D-сцена будет использовать условный масштаб")
    for index, item in enumerate(components, start=1):
        if not isinstance(item, dict):
            warnings.append(f"Компонент №{index} пропущен: ожидался объект")
            continue
        if not item.get("designator"):
            warnings.append(f"Компонент №{index} без позиционного обозначения")
        if not item.get("position") or not item.get("size"):
            warnings.append(
                f"{item.get('designator', '#' + str(index))}: нет геометрии — будет показан только маркер"
            )
    assets = [
        str(value)
        for key, value in board.items()
        if key in {"photo_top", "photo_bottom"} and value
    ]
    return PackageSummary(
        name=str(board.get("name") or "Без названия"),
        board_code=board.get("board_code"),
        components=len(components),
        annotations=len(payload.get("annotations") or []),
        has_dimensions=bool(dims),
        sides=sides,
        warnings=warnings[:50],
        assets=assets,
    )


class BoardPackageService:
    def __init__(self, db: Database, boards_dir: Path) -> None:
        self.db = db
        self.boards_dir = Path(boards_dir)
        self.boards = BoardRepository(db)
        self.devices = DeviceRepository(db)
        self.boards_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------ импорт
    def import_package(
        self,
        path: Path | str,
        *,
        device_id: int | None = None,
        is_demo: bool = False,
        replace_board_id: int | None = None,
    ) -> BoardModel:
        payload = read_package(path)
        summary = summarize(payload)
        board = payload["board"]
        source = Path(path)

        stored_package = self._store_package_file(source)
        photo_top, photo_bottom = self._store_photos(source, board)

        if replace_board_id:
            model = self.boards.get_model(replace_board_id)
            board_id = model.id or replace_board_id
            self.boards.update_model(
                board_id,
                {
                    "name": board.get("name"),
                    "board_code": board.get("board_code"),
                    "revision": board.get("revision"),
                    "package_path": str(stored_package),
                    "format": PACKAGE_FORMAT,
                    "has_3d": 1,
                    "photo_top": photo_top,
                    "photo_bottom": photo_bottom,
                    "source": board.get("source"),
                    "license_note": board.get("license_note"),
                    "notes": board.get("notes"),
                },
            )
            self.db.execute(
                "UPDATE board_models SET width_mm=?, length_mm=?, thickness_mm=?, "
                "package_checksum=?, imported_at=datetime('now') WHERE id=?",
                (
                    _as_float((board.get("dimensions") or {}).get("width"), "Ширина"),
                    _as_float((board.get("dimensions") or {}).get("length"), "Длина"),
                    _as_float((board.get("dimensions") or {}).get("thickness"), "Толщина"),
                    sha256_file(stored_package),
                    board_id,
                ),
            )
            self.db.execute("DELETE FROM board_components WHERE board_model_id = ?", (board_id,))
        else:
            model = self.boards.create_model(
                {
                    "device_id": device_id,
                    "name": board.get("name") or summary.name,
                    "board_code": board.get("board_code"),
                    "revision": board.get("revision"),
                    "package_path": str(stored_package),
                    "format": PACKAGE_FORMAT,
                    "has_3d": 1,
                    "photo_top": photo_top,
                    "photo_bottom": photo_bottom,
                    "source": board.get("source"),
                    "license_note": board.get("license_note"),
                    "notes": board.get("notes"),
                },
                is_demo=int(is_demo),
            )
            board_id = int(model.id or 0)
            self.db.execute(
                "UPDATE board_models SET width_mm=?, length_mm=?, thickness_mm=?, "
                "package_checksum=?, imported_at=datetime('now') WHERE id=?",
                (
                    _as_float((board.get("dimensions") or {}).get("width"), "Ширина"),
                    _as_float((board.get("dimensions") or {}).get("length"), "Длина"),
                    _as_float((board.get("dimensions") or {}).get("thickness"), "Толщина"),
                    sha256_file(stored_package),
                    board_id,
                ),
            )

        designator_to_id: dict[str, int] = {}
        created = 0
        for item in payload["components"]:
            if not isinstance(item, dict):
                continue
            designator = str(item.get("designator") or "").strip().upper()
            if not designator:
                continue
            position = item.get("position") or {}
            size = item.get("size") or {}
            marker = item.get("marker") or {}
            component = self.boards.upsert_component(
                {
                    "board_model_id": board_id,
                    "designator": designator,
                    "side": str(item.get("side") or "top").lower(),
                    "layer": item.get("layer"),
                    "component_type": item.get("type"),
                    "part_marking": item.get("marking"),
                    "purpose": item.get("purpose"),
                    "package_type": item.get("package"),
                    "pos_x": position.get("x"),
                    "pos_y": position.get("y"),
                    "pos_z": position.get("z"),
                    "size_x": size.get("x"),
                    "size_y": size.get("y"),
                    "size_z": size.get("z"),
                    "rotation": item.get("rotation"),
                    "marker_u": marker.get("u"),
                    "marker_v": marker.get("v"),
                    "notes": item.get("notes"),
                },
                is_demo=int(is_demo),
            )
            if component.id:
                designator_to_id[designator] = int(component.id)
            created += 1

        for item in payload.get("annotations") or []:
            if not isinstance(item, dict):
                continue
            self.boards.add_annotation(
                board_id,
                str(item.get("label") or "Метка"),
                body=item.get("body"),
                component_id=designator_to_id.get(str(item.get("component") or "").upper()),
                color=str(item.get("color") or "#3d8bfd"),
            )

        log.info("Пакет платы %s импортирован: %s компонентов", model.name, created)
        return self.boards.get_model(board_id)

    def _store_package_file(self, source: Path) -> Path:
        target_dir = self.boards_dir / "packages"
        target_dir.mkdir(parents=True, exist_ok=True)
        target = target_dir / sanitize_filename(source.name)
        counter = 1
        while target.exists() and sha256_file(target) != sha256_file(source):
            target = target_dir / f"{target.stem}-{counter}{target.suffix}"
            counter += 1
        if not target.exists():
            shutil.copy2(source, target)
        return target

    def _store_photos(self, source: Path, board: dict[str, Any]) -> tuple[str | None, str | None]:
        base = source.parent
        result: list[str | None] = []
        for key in ("photo_top", "photo_bottom"):
            value = board.get(key)
            if not value:
                result.append(None)
                continue
            candidate = (base / str(value)).resolve()
            try:
                ensure_within(candidate, base)
            except Exception:
                log.warning("Фото платы вне каталога пакета: %s", value)
                result.append(None)
                continue
            if not candidate.exists():
                result.append(None)
                continue
            target_dir = self.boards_dir / "photos"
            target_dir.mkdir(parents=True, exist_ok=True)
            target = target_dir / sanitize_filename(candidate.name)
            if not target.exists():
                shutil.copy2(candidate, target)
            result.append(str(target))
        return result[0], result[1]

    def import_zip(self, path: Path | str, *, device_id: int | None = None, is_demo: bool = False) -> BoardModel:
        """Импорт ZIP-пакета: JSON + фотографии в одном архиве."""
        archive = Path(path)
        extract_dir = self.boards_dir / "incoming" / sanitize_filename(archive.stem)
        if extract_dir.exists():
            shutil.rmtree(extract_dir, ignore_errors=True)
        files = safe_extract_zip(archive, extract_dir)
        packages = [item for item in files if item.suffix.lower() in SUPPORTED_EXTENSIONS]
        if not packages:
            raise ImportErrorOS("В архиве не найден JSON-пакет платы")
        if len(packages) > 1:
            raise ImportErrorOS("В архиве несколько пакетов — импортируйте их по одному")
        return self.import_package(packages[0], device_id=device_id, is_demo=is_demo)

    # ------------------------------------------------------------------ экспорт
    def export_package(self, board_model_id: int, destination: Path | str) -> Path:
        model = self.boards.get_model(board_model_id)
        components = self.boards.components(board_model_id, limit=MAX_COMPONENTS)
        annotations = self.boards.annotations(board_model_id)
        payload: dict[str, Any] = {
            "format": PACKAGE_FORMAT,
            "version": PACKAGE_VERSION,
            "board": {
                "name": model.name,
                "board_code": model.board_code,
                "revision": model.revision,
                "dimensions": {
                    "width": model.width_mm,
                    "length": model.length_mm,
                    "thickness": model.thickness_mm,
                },
                "source": model.source,
                "license_note": model.license_note,
                "notes": model.notes,
                "photo_top": Path(model.photo_top).name if model.photo_top else None,
                "photo_bottom": Path(model.photo_bottom).name if model.photo_bottom else None,
            },
            "components": [],
            "annotations": [],
        }
        by_id = {component.id: component.designator for component in components}
        for component in components:
            payload["components"].append(_component_payload(component))
        for annotation in annotations:
            payload["annotations"].append(
                {
                    "label": annotation.label,
                    "body": annotation.body,
                    "component": by_id.get(annotation.component_id),
                    "color": annotation.color,
                }
            )
        target = Path(destination)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return target

    # ------------------------------------------------------------------ загрузка в 3D
    def load_scene(self, board_model_id: int) -> dict[str, Any]:
        """Возвращает данные для просмотрщика: плата, компоненты, метки."""
        model = self.boards.get_model(board_model_id)
        components = self.boards.components(board_model_id, limit=MAX_COMPONENTS)
        annotations = self.boards.annotations(board_model_id)
        return {
            "board": {**model.to_dict(), "components": len(components)},
            "components": [component.to_dict() for component in components],
            "annotations": [annotation.to_dict() for annotation in annotations],
            "layers": self.boards.layers(board_model_id),
            "types": self.boards.component_types(board_model_id),
        }


def _component_payload(component: BoardComponent) -> dict[str, Any]:
    item: dict[str, Any] = {
        "designator": component.designator,
        "side": component.side,
        "layer": component.layer,
        "type": component.component_type,
        "marking": component.part_marking,
        "purpose": component.purpose,
        "package": component.package_type,
        "rotation": component.rotation,
        "notes": component.notes,
    }
    if component.pos_x is not None or component.pos_y is not None:
        item["position"] = {"x": component.pos_x, "y": component.pos_y, "z": component.pos_z}
    if component.size_x is not None or component.size_y is not None:
        item["size"] = {"x": component.size_x, "y": component.size_y, "z": component.size_z}
    if component.marker_u is not None or component.marker_v is not None:
        item["marker"] = {"u": component.marker_u, "v": component.marker_v}
    return item
