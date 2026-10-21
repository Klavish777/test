"""Демонстрационные данные.

ВАЖНО: все записи создаются с ``is_demo = 1`` и подписаны в интерфейсе как «ДЕМО».
Это не проверенные сведения о прошивках, не настоящие ссылки на загрузку и не
реальные 3D-модели плат. Данные нужны только для знакомства с интерфейсом и
проверки работы приложения.

Реальные данные добавляются пользователем (вручную или импортом CSV/JSON) и
имеют ``is_demo = 0``.
"""

from __future__ import annotations

import json
import logging
import math
from pathlib import Path
from typing import Any

from repair_os.core.paths import AppPaths
from repair_os.data.database import Database
from repair_os.data.repositories.brands import BrandRepository
from repair_os.data.repositories.devices import DeviceRepository
from repair_os.data.repositories.firmware import FirmwareRepository
from repair_os.data.repositories.library import LibraryRepository
from repair_os.services.board_packages import PACKAGE_FORMAT, PACKAGE_VERSION, BoardPackageService

log = logging.getLogger(__name__)

DEMO_SOURCE = "ДЕМО-данные Smartphone Repair OS (не проверено)"
DEMO_NOTE = "Демонстрационная запись. Не является проверенной технической информацией."

BRANDS: list[dict[str, Any]] = [
    {"name": "Samsung", "slug": "samsung", "country": "Южная Корея", "sort_order": 10},
    {"name": "Apple", "slug": "apple", "country": "США", "sort_order": 20},
    {"name": "Xiaomi", "slug": "xiaomi", "country": "Китай", "sort_order": 30},
    {"name": "Redmi", "slug": "redmi", "country": "Китай", "sort_order": 40},
    {"name": "POCO", "slug": "poco", "country": "Китай", "sort_order": 50},
    {"name": "Huawei", "slug": "huawei", "country": "Китай", "sort_order": 60},
    {"name": "HONOR", "slug": "honor", "country": "Китай", "sort_order": 70},
    {"name": "Google Pixel", "slug": "google-pixel", "country": "США", "sort_order": 80},
    {"name": "OPPO", "slug": "oppo", "country": "Китай", "sort_order": 90},
    {"name": "vivo", "slug": "vivo", "country": "Китай", "sort_order": 100},
    {"name": "OnePlus", "slug": "oneplus", "country": "Китай", "sort_order": 110},
    {"name": "Realme", "slug": "realme", "country": "Китай", "sort_order": 120},
    {"name": "Motorola", "slug": "motorola", "country": "США", "sort_order": 130},
    {"name": "Другие производители", "slug": "other", "country": None, "sort_order": 900},
]

# brand_slug, name, model_code, codename, revision, soc, ram, storage, os_versions, year
DEVICES: list[tuple[str, str, str, str | None, str | None, str | None, str | None, str | None, str, int]] = [
    ("samsung", "Galaxy S21 5G", "SM-G991B", "o1s", "rev1", "Exynos 2100", "8 GB", "128 GB", "Android 11–14", 2021),
    ("samsung", "Galaxy A52", "SM-A525F", "a52q", "rev1", "Snapdragon 720G", "6 GB", "128 GB", "Android 11–13", 2021),
    ("samsung", "Galaxy Note 20 Ultra", "SM-N986B", "c2s", "rev1", "Exynos 990", "12 GB", "256 GB", "Android 10–13", 2020),
    ("apple", "iPhone 11", "A2221", None, None, "Apple A13 Bionic", "4 GB", "64 GB", "iOS 13–17", 2019),
    ("apple", "iPhone 12", "A2402", None, None, "Apple A14 Bionic", "4 GB", "128 GB", "iOS 14–17", 2020),
    ("apple", "iPhone 13", "A2633", None, None, "Apple A15 Bionic", "4 GB", "128 GB", "iOS 15–17", 2021),
    ("xiaomi", "Mi 11", "M2011K2G", "venus", None, "Snapdragon 888", "8 GB", "128 GB", "Android 11–13", 2020),
    ("xiaomi", "Xiaomi 13", "2211133G", "fuxi", None, "Snapdragon 8 Gen 2", "8 GB", "256 GB", "Android 13–15", 2022),
    ("redmi", "Redmi Note 10 Pro", "M2101K6G", "sweet", None, "Snapdragon 732G", "6 GB", "128 GB", "Android 11–13", 2021),
    ("redmi", "Redmi Note 12", "22111317G", None, None, None, "4 GB", "128 GB", "Android 12–14", 2022),
    ("poco", "POCO X3 Pro", "M2102J20SG", "vayu", None, "Snapdragon 860", "6 GB", "128 GB", "Android 11–13", 2021),
    ("poco", "POCO F3", "M2012K11AG", "alioth", None, "Snapdragon 870", "8 GB", "256 GB", "Android 11–13", 2021),
    ("huawei", "P30", "ELE-L29", "ELLE", None, "Kirin 980", "6 GB", "128 GB", "EMUI 9–12", 2019),
    ("huawei", "P40 Pro", "ELS-NX9", "ELS", None, "Kirin 990 5G", "8 GB", "256 GB", "EMUI 10–12", 2020),
    ("honor", "HONOR 50", "NTH-NX9", "NTH", None, "Snapdragon 778G", "8 GB", "128 GB", "Android 11–13", 2021),
    ("honor", "HONOR 90", "REA-NX9", None, None, "Snapdragon 7 Gen 1 Accelerated", "8 GB", "256 GB", "Android 13–14", 2023),
    ("google-pixel", "Pixel 6", "G9S9B16", "oriole", None, "Google Tensor", "8 GB", "128 GB", "Android 12–14", 2021),
    ("google-pixel", "Pixel 7", "GVU6C", "panther", None, "Google Tensor G2", "8 GB", "128 GB", "Android 13–15", 2022),
    ("oppo", "Reno 6", "CPH2251", None, None, "MediaTek Dimensity 900", "8 GB", "128 GB", "Android 11–13", 2021),
    ("oppo", "Find X3", "CPH2173", None, None, "Snapdragon 870", "8 GB", "256 GB", "Android 11–13", 2021),
    ("vivo", "V21 5G", "V2050", None, None, "MediaTek Dimensity 800U", "8 GB", "128 GB", "Android 11–13", 2021),
    ("vivo", "X60 Pro", "V2045", None, None, "Exynos 1080", "12 GB", "256 GB", "Android 11–13", 2020),
    ("oneplus", "9", "LE2113", "lemonade", None, "Snapdragon 888", "8 GB", "128 GB", "Android 11–14", 2021),
    ("oneplus", "Nord 2 5G", "DN2103", "denniz", None, "MediaTek Dimensity 1200-AI", "8 GB", "128 GB", "Android 11–13", 2021),
    ("realme", "8 Pro", "RMX3081", None, None, "Snapdragon 720G", "8 GB", "128 GB", "Android 11–13", 2021),
    ("realme", "GT Neo 2", "RMX3370", None, None, "Snapdragon 870", "8 GB", "128 GB", "Android 11–13", 2021),
    ("motorola", "Edge 20", "XT2143-1", None, None, "Snapdragon 778G", "8 GB", "128 GB", "Android 11–13", 2021),
    ("motorola", "Moto G60", "XT2135-1", None, None, "Snapdragon 732G", "6 GB", "128 GB", "Android 11–12", 2021),
    ("other", "Nothing Phone (1)", "A063", "spacewar", None, "Snapdragon 778G+", "8 GB", "128 GB", "Android 12–14", 2022),
    ("other", "Sony Xperia 1 III", "XQ-BC52", None, None, "Snapdragon 888", "12 GB", "256 GB", "Android 11–13", 2021),
]

DEMO_BOARD_DEVICE = ("other", "DEMO Reference Board", "DEMO-BOARD-01", "demo_ref", "demo")

FIRMWARE_ROWS: list[dict[str, Any]] = [
    {
        "brand": "samsung",
        "model_code": "SM-G991B",
        "file_name": "DEMO_SM-G991B_Android13_O1s_DEMO.zip",
        "os_version": "Android 13",
        "build_number": "G991BXXU0DEMO1",
        "region": "SER",
        "csc": "SER",
        "release_date": "2023-01-15",
        "file_size": 5_400_000_000,
        "download_url": "https://example.org/demo-firmware/samsung-g991b",
        "compatibility_notes": "ДЕМО: совместимость не проверена. Учитывайте CSC, ревизию и версию загрузчика.",
        "install_instructions": "ДЕМО-инструкция: не использовать для реального устройства.",
        "verification_status": "unverified",
    },
    {
        "brand": "samsung",
        "model_code": "SM-A525F",
        "file_name": "DEMO_SM-A525F_Android12_A525F_DEMO.zip",
        "os_version": "Android 12",
        "build_number": "A525FXXU0DEMO2",
        "region": "SER",
        "csc": "SER",
        "release_date": "2022-06-01",
        "file_size": 4_300_000_000,
        "download_url": "https://example.org/demo-firmware/samsung-a525f",
        "compatibility_notes": "ДЕМО: запись для демонстрации фильтров и поиска.",
        "install_instructions": "ДЕМО-инструкция.",
        "verification_status": "unverified",
    },
    {
        "brand": "apple",
        "model_code": "A2633",
        "file_name": "DEMO_iPhone13_17.5.1_DEMO.ipsw",
        "os_version": "iOS 17.5.1",
        "build_number": "21F90-DEMO",
        "region": "Global",
        "release_date": "2024-05-20",
        "file_size": 6_100_000_000,
        "download_url": "https://example.org/demo-firmware/iphone13",
        "compatibility_notes": "ДЕМО: восстановление iOS требует подписи Apple; обход защиты запрещён.",
        "install_instructions": "ДЕМО-инструкция: используйте официальные инструменты Apple.",
        "verification_status": "unverified",
    },
    {
        "brand": "xiaomi",
        "model_code": "M2101K6G",
        "file_name": "DEMO_sweet_global_images_DEMO.tar.gz",
        "os_version": "MIUI 14 (Android 13)",
        "build_number": "TKFMIXMDEMO",
        "region": "Global",
        "release_date": "2023-03-10",
        "file_size": 3_900_000_000,
        "download_url": "https://example.org/demo-firmware/redmi-note-10-pro",
        "compatibility_notes": "ДЕМО: проверяйте антироллбек и регион.",
        "install_instructions": "ДЕМО-инструкция.",
        "verification_status": "unverified",
    },
    {
        "brand": "google-pixel",
        "model_code": "G9S9B16",
        "file_name": "DEMO_oriole_factory_DEMO.zip",
        "os_version": "Android 14",
        "build_number": "AP1A.DEMO.001",
        "region": "Global",
        "release_date": "2023-10-04",
        "file_size": 2_700_000_000,
        "download_url": "https://example.org/demo-firmware/pixel-6",
        "compatibility_notes": "ДЕМО: закрытый загрузчик не позволяет откат на старые сборки.",
        "install_instructions": "ДЕМО-инструкция.",
        "verification_status": "unverified",
    },
]

DOCUMENTS: list[dict[str, Any]] = [
    {
        "title": "ДЕМО · Схема цепей питания (пример)",
        "category": "power",
        "doc_type": "schematic",
        "brand": "samsung",
        "model_code": "SM-G991B",
        "description": "Пример карточки материала. Файл не приложен, данные не проверены.",
        "tags": "power,pmic,demo",
        "verification_status": "unverified",
    },
    {
        "title": "ДЕМО · Диагностика цепи зарядки (методика)",
        "category": "charging",
        "doc_type": "instruction",
        "brand": "apple",
        "model_code": "A2402",
        "description": "Пример инструкции по диагностике. Не является официальной документацией.",
        "tags": "charging,usb,demo",
        "verification_status": "unverified",
    },
    {
        "title": "ДЕМО · Фотографии платы (placeholder)",
        "category": "general",
        "doc_type": "photo",
        "brand": "xiaomi",
        "model_code": "M2101K6G",
        "description": "Карточка для собственных фотографий платы.",
        "tags": "photo,demo",
        "verification_status": "unverified",
    },
    {
        "title": "ДЕМО · RF-узел: порядок проверки",
        "category": "rf",
        "doc_type": "note",
        "brand": "google-pixel",
        "model_code": "G9S9B16",
        "description": "Черновик заметки для демонстрации категорий библиотеки.",
        "tags": "rf,antenna,demo",
        "verification_status": "unverified",
    },
]


def build_demo_board_package() -> dict[str, Any]:
    """Создаёт демонстрационный пакет платы.

    Геометрия **условная**: это синтетическая демонстрационная плата, а не модель
    реального устройства. Позиционные обозначения не привязаны к реальной схеме.
    """
    width, length, thickness = 70.0, 140.0, 1.0
    components: list[dict[str, Any]] = []
    layers_top = ["power", "rf", "audio"]
    layers_bottom = ["power", "usb", "display"]
    prefix_cycle = [("U", "IC", 3.0, 3.0, 0.9), ("C", "Capacitor", 1.0, 0.5, 0.5), ("R", "Resistor", 0.6, 0.3, 0.3)]
    types = ["IC", "Capacitor", "Resistor", "Inductor", "Connector", "TestPoint"]

    index = 0
    for side, layers in (("top", layers_top), ("bottom", layers_bottom)):
        for row in range(6):
            for column in range(4):
                prefix, ctype, sx, sy, sz = prefix_cycle[index % len(prefix_cycle)]
                designator = f"{prefix}{1000 + index * 7 + 1}"
                x = 6.0 + column * 17.0 + (2.0 if row % 2 else 0.0)
                y = 12.0 + row * 21.0
                components.append(
                    {
                        "designator": designator,
                        "side": side,
                        "layer": layers[(row + column) % len(layers)],
                        "type": ctype,
                        "marking": None,
                        "purpose": None,
                        "position": {
                            "x": round(x, 2),
                            "y": round(y, 2),
                            "z": round(thickness + sz / 2, 2) if side == "top" else round(-sz / 2, 2),
                        },
                        "size": {"x": sx, "y": sy, "z": sz},
                        "rotation": 0,
                        "notes": "Условный демонстрационный компонент. Не отражает реальную плату.",
                    }
                )
                index += 1

    # Пара крупных демонстрационных узлов и разъёмов.
    extras = [
        ("U1201", "IC", 6.0, 6.0, 1.1, 18.0, 118.0, "top", "power"),
        ("U1202", "IC", 5.0, 5.0, 1.0, 50.0, 118.0, "top", "power"),
        ("J4501", "Connector", 8.0, 3.0, 1.5, 35.0, 4.0, "bottom", "usb"),
        ("J4502", "Connector", 12.0, 3.0, 1.2, 55.0, 4.0, "bottom", "display"),
        ("TP3201", "TestPoint", 1.2, 1.2, 0.2, 10.0, 70.0, "top", "power"),
    ]
    for designator, ctype, sx, sy, sz, x, y, side, layer in extras:
        components.append(
            {
                "designator": designator,
                "side": side,
                "layer": layer,
                "type": ctype,
                "marking": None,
                "purpose": None,
                "position": {
                    "x": x,
                    "y": y,
                    "z": round(thickness + sz / 2, 2) if side == "top" else round(-sz / 2, 2),
                },
                "size": {"x": sx, "y": sy, "z": sz},
                "rotation": 0,
                "notes": "Условный демонстрационный узел.",
            }
        )

    return {
        "format": PACKAGE_FORMAT,
        "version": PACKAGE_VERSION,
        "board": {
            "name": "ДЕМО · Условная плата (не реальное устройство)",
            "board_code": "DEMO-REF-01",
            "revision": "demo",
            "dimensions": {"width": width, "length": length, "thickness": thickness},
            "source": DEMO_SOURCE,
            "license_note": "Синтетические демонстрационные данные, созданные для этого приложения.",
            "notes": (
                "Демонстрационная плата. Геометрия и обозначения условные и не описывают "
                "реальное изделие. Используйте импорт собственных пакетов BoardView."
            ),
            "photo_top": "demo_top.jpg",
            "photo_bottom": "demo_bottom.jpg",
        },
        "components": components,
        "annotations": [
            {
                "label": "ДЕМО: пример метки",
                "body": "Метка мастера. Создана в демонстрационных данных, можно удалить.",
                "component": "U1201",
                "color": "#3d8bfd",
            }
        ],
    }


class DemoSeeder:
    def __init__(self, db: Database, paths: AppPaths, *, assets_dir: Path | None = None) -> None:
        self.db = db
        self.paths = paths
        self.assets_dir = assets_dir or (Path(__file__).resolve().parent / "assets")
        self.brands = BrandRepository(db)
        self.devices = DeviceRepository(db)
        self.firmware = FirmwareRepository(db)
        self.library = LibraryRepository(db)

    def is_seeded(self) -> bool:
        return bool(self.db.scalar("SELECT COUNT(*) FROM devices WHERE is_demo = 1"))

    def seed(self, *, force: bool = False) -> dict[str, int]:
        if self.is_seeded() and not force:
            log.info("Демонстрационные данные уже загружены")
            return self._counts()

        brand_map: dict[str, int] = {}
        for brand in BRANDS:
            existing = self.brands.find_by_slug(brand["slug"])
            if existing:
                brand_map[brand["slug"]] = int(existing.id or 0)
                continue
            created = self.brands.create({**brand, "is_demo": 1}, is_demo=1)
            brand_map[brand["slug"]] = int(created.id or 0)

        device_map: dict[str, int] = {}
        for (
            brand_slug,
            name,
            model_code,
            codename,
            revision,
            soc,
            ram,
            storage,
            os_versions,
            year,
        ) in DEVICES:
            brand_id = brand_map[brand_slug]
            existing = self.db.query_one(
                "SELECT id FROM devices WHERE brand_id = ? AND model_code = ? COLLATE NOCASE",
                (brand_id, model_code),
            )
            if existing:
                device_map[model_code] = int(existing["id"])
                continue
            device = self.devices.create(
                {
                    "brand_id": brand_id,
                    "name": name,
                    "model_code": model_code,
                    "codename": codename,
                    "hardware_revision": revision,
                    "soc": soc,
                    "soc_platform": "ДЕМО · платформа не указана",
                    "ram": ram,
                    "storage": storage,
                    "os_versions": os_versions,
                    "release_year": year,
                    "notes": DEMO_NOTE,
                    "source": DEMO_SOURCE,
                    "verified": 0,
                },
                is_demo=1,
            )
            device_map[model_code] = int(device.id or 0)
            self.devices.add_variant(
                {
                    "device_id": device.id,
                    "name": f"{name} · демонстрационный вариант",
                    "model_code": model_code,
                    "region": "DEMO",
                    "csc": None,
                    "ram": ram,
                    "storage": storage,
                    "bootloader": "DEMO-BL",
                    "notes": DEMO_NOTE,
                },
                is_demo=1,
            )

        # Демонстрационная плата (условная геометрия).
        demo_brand = brand_map["other"]
        board_device = self.db.query_one(
            "SELECT id FROM devices WHERE brand_id = ? AND model_code = ?",
            (demo_brand, DEMO_BOARD_DEVICE[2]),
        )
        if board_device:
            board_device_id = int(board_device["id"])
        else:
            created_device = self.devices.create(
                {
                    "brand_id": demo_brand,
                    "name": DEMO_BOARD_DEVICE[1],
                    "model_code": DEMO_BOARD_DEVICE[2],
                    "codename": DEMO_BOARD_DEVICE[3],
                    "hardware_revision": DEMO_BOARD_DEVICE[4],
                    "soc": None,
                    "ram": None,
                    "storage": None,
                    "os_versions": None,
                    "release_year": None,
                    "notes": "ДЕМО-плата для проверки 3D BoardView. Геометрия условная.",
                    "source": DEMO_SOURCE,
                    "verified": 0,
                },
                is_demo=1,
            )
            board_device_id = int(created_device.id or 0)

        self._install_demo_board(board_device_id)

        source = self.db.query_one("SELECT id FROM firmware_sources WHERE name = ?", (DEMO_SOURCE,))
        source_id = None
        if source:
            source_id = int(source["id"])
        else:
            created_source = self.firmware.create_source(
                {
                    "name": DEMO_SOURCE,
                    "kind": "community",
                    "trusted": 0,
                    "notes": "Источник существует только для демонстрации. Ссылки ведут на example.org.",
                },
                is_demo=1,
            )
            source_id = created_source.id

        for row in FIRMWARE_ROWS:
            device_id = device_map.get(row["model_code"])
            try:
                self.firmware.create(
                    {
                        "device_id": device_id,
                        "source_id": source_id,
                        "title": f"ДЕМО · {row['file_name']}",
                        "file_name": row["file_name"],
                        "model_code": row["model_code"],
                        "os_version": row["os_version"],
                        "build_number": row["build_number"],
                        "region": row["region"],
                        "csc": row.get("csc"),
                        "release_date": row["release_date"],
                        "file_size": row["file_size"],
                        "download_url": row["download_url"],
                        "install_instructions": row["install_instructions"],
                        "compatibility_notes": row["compatibility_notes"],
                        "verification_status": row["verification_status"],
                    },
                    is_demo=1,
                )
            except Exception as exc:  # pragma: no cover - устойчивость сидирования
                log.warning("Не удалось создать демо-прошивку %s: %s", row["file_name"], exc)

        for row in DOCUMENTS:
            device_id = device_map.get(row["model_code"])
            self.library.create_document(
                {
                    "title": row["title"],
                    "category": row["category"],
                    "doc_type": row["doc_type"],
                    "device_id": device_id,
                    "brand_id": brand_map.get(row["brand"]),
                    "source_url": None,
                    "description": row["description"] + " " + DEMO_NOTE,
                    "tags": row["tags"],
                    "verification_status": row["verification_status"],
                },
                is_demo=1,
            )

        for model_code, title, body in (
            ("SM-G991B", "ДЕМО · Заметка мастера", "Пример заметки. Замените своими наблюдениями."),
            ("A2402", "ДЕМО · Быстрая диагностика", "Пример структуры диагностической заметки."),
        ):
            self.library.create_note(
                {
                    "device_id": device_map.get(model_code),
                    "title": title,
                    "body": body + "\n\n" + DEMO_NOTE,
                    "category": "general",
                }
            )

        for model_code in ("SM-G991B", "A2402", "M2101K6G", "G9S9B16"):
            device_id = device_map.get(model_code)
            if device_id and model_code in {"SM-G991B", "G9S9B16"}:
                self.devices.toggle_favorite(device_id)
            if device_id:
                self.devices.record_open(device_id)

        self.library.add_component_reference(
            {
                "designator": "U1201",
                "device_id": board_device_id,
                "component_type": "IC",
                "marking": None,
                "description": "ДЕМО: условный компонент демонстрационной платы.",
            },
            is_demo=1,
        )

        counts = self._counts()
        log.info("Демонстрационные данные загружены: %s", counts)
        return counts

    def _install_demo_board(self, device_id: int) -> None:
        existing = self.db.query_one(
            "SELECT id FROM board_models WHERE device_id = ? AND board_code = 'DEMO-REF-01'",
            (device_id,),
        )
        if existing:
            return
        package = build_demo_board_package()
        work_dir = self.assets_dir
        work_dir.mkdir(parents=True, exist_ok=True)
        package_path = work_dir / "demo_board.json"
        package_path.write_text(json.dumps(package, ensure_ascii=False, indent=2), encoding="utf-8")

        for name in ("demo_top.jpg", "demo_bottom.jpg"):
            candidate = work_dir / name
            if candidate.exists():
                package["board"][
                    "photo_top" if name == "demo_top.jpg" else "photo_bottom"
                ] = name
        package_path.write_text(json.dumps(package, ensure_ascii=False, indent=2), encoding="utf-8")

        service = BoardPackageService(self.db, self.paths.boards_dir)
        service.import_package(package_path, device_id=device_id, is_demo=True)

    def _counts(self) -> dict[str, int]:
        return {
            "brands": self.db.table_count("brands"),
            "devices": self.db.table_count("devices"),
            "firmware": self.db.table_count("firmware"),
            "documents": self.db.table_count("technical_documents"),
            "board_models": self.db.table_count("board_models"),
            "board_components": self.db.table_count("board_components"),
        }

    def clear_demo(self) -> int:
        """Удаляет только демонстрационные записи, не затрагивая данные пользователя."""
        removed = 0
        with self.db.transaction() as conn:
            demo_device_ids = [
                row["id"] for row in conn.execute("SELECT id FROM devices WHERE is_demo = 1")
            ]
            for device_id in demo_device_ids:
                conn.execute("DELETE FROM devices WHERE id = ?", (device_id,))
                removed += 1
            conn.execute("DELETE FROM technical_documents WHERE is_demo = 1")
            conn.execute("DELETE FROM firmware WHERE is_demo = 1")
            conn.execute("DELETE FROM firmware_sources WHERE is_demo = 1")
            conn.execute(
                "DELETE FROM brands WHERE is_demo = 1 "
                "AND id NOT IN (SELECT DISTINCT brand_id FROM devices)"
            )
        return removed


def count_demo(db: Database) -> dict[str, int]:
    return {
        "devices": int(db.scalar("SELECT COUNT(*) FROM devices WHERE is_demo = 1") or 0),
        "firmware": int(db.scalar("SELECT COUNT(*) FROM firmware WHERE is_demo = 1") or 0),
        "documents": int(
            db.scalar("SELECT COUNT(*) FROM technical_documents WHERE is_demo = 1") or 0
        ),
        "boards": int(db.scalar("SELECT COUNT(*) FROM board_models WHERE is_demo = 1") or 0),
    }
