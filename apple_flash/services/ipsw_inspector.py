"""Инспектор локальных файлов .ipsw без распаковки архива на диск.

Читает BuildManifest.plist и Restore.plist напрямую из центрального каталога ZIP,
проверяет наличие образов компонентов внутри архива и определяет поддерживаемые
устройства iPhone, iPad и MacBook (Apple Silicon / T2).
"""

from __future__ import annotations

import plistlib
import zipfile
from pathlib import Path
from typing import Any

from apple_flash.core.errors import IpswError
from apple_flash.core.security import read_zip_member_safe
from apple_flash.data.apple_catalog import infer_ipsw_family
from apple_flash.data.models import IpswManifestInfo


def _parse_int(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, int):
        return value
    text = str(value).strip()
    if not text:
        return None
    try:
        return int(text, 16) if text.lower().startswith("0x") else int(text)
    except ValueError:
        return None


class IpswInspector:
    """Быстрый и безопасный анализатор пакетов прошивок Apple (.ipsw)."""

    def inspect(self, path: Path | str) -> IpswManifestInfo:
        target = Path(path).expanduser().resolve()
        if not target.exists() or not target.is_file():
            raise IpswError(f"Файл прошивки не найден: {target}")
        if target.suffix.lower() != ".ipsw":
            raise IpswError(
                f"Ожидался файл с расширением .ipsw, получен: {target.suffix or 'без расширения'}"
            )
        size = target.stat().st_size
        if size == 0:
            raise IpswError("Файл .ipsw пуст (0 байт) — возможно, копирование не завершилось.")

        try:
            with zipfile.ZipFile(target, "r") as zf:
                names = set(zf.namelist())
                if "BuildManifest.plist" not in names:
                    raise IpswError(
                        "В архиве отсутствует BuildManifest.plist — это не корректный образ прошивки Apple IPSW."
                    )
                raw_manifest = read_zip_member_safe(zf, "BuildManifest.plist")
                try:
                    manifest = plistlib.loads(raw_manifest)
                except Exception as exc:
                    raise IpswError(f"Не удалось разобрать BuildManifest.plist: {exc}") from exc

                restore_plist: dict[str, Any] = {}
                if "Restore.plist" in names:
                    try:
                        restore_plist = plistlib.loads(read_zip_member_safe(zf, "Restore.plist"))
                    except Exception:
                        restore_plist = {}
        except zipfile.BadZipFile as exc:
            raise IpswError(f"Файл повреждён или не является ZIP/IPSW-архивом: {exc}") from exc

        if not isinstance(manifest, dict):
            raise IpswError("Некорректная корневая структура BuildManifest.plist.")

        product_version = str(
            manifest.get("ProductVersion") or restore_plist.get("ProductVersion") or ""
        ).strip()
        build_version = str(
            manifest.get("ProductBuildVersion") or restore_plist.get("ProductBuildVersion") or ""
        ).strip()
        if not product_version and not build_version:
            raise IpswError("В BuildManifest.plist отсутствуют ProductVersion и ProductBuildVersion.")

        supported_types = [
            str(item).strip()
            for item in (manifest.get("SupportedProductTypes") or restore_plist.get("SupportedProductTypes") or [])
            if str(item).strip()
        ]
        if not supported_types and restore_plist.get("ProductType"):
            supported_types = [str(restore_plist["ProductType"]).strip()]

        cpids_set: set[int] = set()
        boards_set: set[str] = set()
        variants_set: set[str] = set()
        referenced_paths: set[str] = set()
        has_baseband = False
        has_sep = False

        identities = manifest.get("BuildIdentities") or []
        if isinstance(identities, list):
            for identity in identities:
                if not isinstance(identity, dict):
                    continue
                cpid = _parse_int(identity.get("ApChipID"))
                if cpid is not None:
                    cpids_set.add(cpid)
                info = identity.get("Info") or {}
                if isinstance(info, dict):
                    dev_class = str(info.get("DeviceClass") or "").strip()
                    if dev_class:
                        boards_set.add(dev_class)
                    variant = str(info.get("Variant") or "").strip()
                    if variant:
                        variants_set.add(variant)
                comp_map = identity.get("Manifest") or {}
                if isinstance(comp_map, dict):
                    if "BasebandFirmware" in comp_map:
                        has_baseband = True
                    if "SEP" in comp_map or "RestoreSEP" in comp_map:
                        has_sep = True
                    for comp_val in comp_map.values():
                        if isinstance(comp_val, dict):
                            comp_info = comp_val.get("Info")
                            if isinstance(comp_info, dict):
                                rel_path = str(comp_info.get("Path") or "").strip()
                                if rel_path:
                                    referenced_paths.add(rel_path.replace("\\", "/"))

        for dev_entry in restore_plist.get("DeviceMap") or []:
            if isinstance(dev_entry, dict):
                cpid = _parse_int(dev_entry.get("CPID"))
                if cpid is not None:
                    cpids_set.add(cpid)
                bcfg = str(dev_entry.get("BoardConfig") or "").strip()
                if bcfg:
                    boards_set.add(bcfg)

        has_erase = True
        has_upgrade = True
        if variants_set:
            lower_variants = [v.lower() for v in variants_set]
            has_erase = any("erase" in v or "customer" in v for v in lower_variants)
            has_upgrade = any(
                "upgrade" in v or "update" in v or "macos customer" in v or "recovery" in v
                for v in lower_variants
            )

        missing_components = sorted(p for p in referenced_paths if p not in names)
        is_demo = bool(manifest.get("AppleFlashDemoMockup")) or ("DEMO_MOCKUP.txt" in names)
        warnings: list[str] = []
        if is_demo:
            warnings.append(
                "Это демонстрационный макет IPSW (ДЕМО) для тестирования интерфейса и Dry-Run. "
                "Он не содержит реальных образов ОС Apple."
            )
        if missing_components:
            warnings.append(
                f"В архиве отсутствуют {len(missing_components)} файлов из манифеста "
                f"(например: {missing_components[0]}). Прошивка таким архивом заблокирована."
            )

        family = infer_ipsw_family(supported_types)

        return IpswManifestInfo(
            path=target,
            file_name=target.name,
            file_size=size,
            product_version=product_version or "—",
            build_version=build_version or "—",
            family=family,
            supported_product_types=supported_types,
            supported_cpids=sorted(cpids_set),
            board_configs=sorted(boards_set),
            restore_variants=sorted(variants_set),
            has_erase_variant=has_erase,
            has_upgrade_variant=has_upgrade,
            has_baseband=has_baseband,
            has_sep=has_sep,
            zip_entries_count=len(names),
            missing_components=missing_components,
            is_demo_mockup=is_demo,
            warnings=warnings,
        )


def create_demo_ipsw_bundle(target_dir: Path) -> list[Path]:
    """Создаёт 3 компактных демонстрационных .ipsw макета (iPhone, iPad, MacBook) с валидным BuildManifest.plist.

    Все макеты явно помечены флагом AppleFlashDemoMockup и файлом DEMO_MOCKUP.txt:
    они подходят для проверки инспектора, расчёта SHA-256 и безопасной симуляции Dry-Run,
    но жёстко заблокированы для реальной прошивки.
    """
    target_dir.mkdir(parents=True, exist_ok=True)
    specs = [
        (
            "DEMO_iPhone16,1_18.1_22B83_Restore.ipsw",
            {
                "ProductVersion": "18.1",
                "ProductBuildVersion": "22B83",
                "SupportedProductTypes": ["iPhone16,1", "iPhone16,2"],
                "AppleFlashDemoMockup": True,
                "BuildIdentities": [
                    {
                        "ApChipID": "0x8130",
                        "Info": {
                            "DeviceClass": "d83ap",
                            "Variant": "Customer Erase Install (IPSW)",
                        },
                        "Manifest": {
                            "iBSS": {"Info": {"Path": "Firmware/dfu/iBSS.d83.RELEASE.im4p"}},
                            "SEP": {"Info": {"Path": "Firmware/all_flash/sep-firmware.d83.RELEASE.im4p"}},
                            "BasebandFirmware": {"Info": {"Path": "Firmware/Mav22-2.20.00.Release.bbfw"}},
                            "OS": {"Info": {"Path": "090-00001-001.dmg"}},
                        },
                    },
                    {
                        "ApChipID": "0x8130",
                        "Info": {
                            "DeviceClass": "d83ap",
                            "Variant": "Customer Upgrade Install (IPSW)",
                        },
                        "Manifest": {
                            "iBSS": {"Info": {"Path": "Firmware/dfu/iBSS.d83.RELEASE.im4p"}},
                            "SEP": {"Info": {"Path": "Firmware/all_flash/sep-firmware.d83.RELEASE.im4p"}},
                            "OS": {"Info": {"Path": "090-00001-001.dmg"}},
                        },
                    },
                ],
            },
        ),
        (
            "DEMO_iPad16,3_18.1_22B83_Restore.ipsw",
            {
                "ProductVersion": "18.1",
                "ProductBuildVersion": "22B83",
                "SupportedProductTypes": ["iPad16,3", "iPad16,4", "iPad16,5", "iPad16,6"],
                "AppleFlashDemoMockup": True,
                "BuildIdentities": [
                    {
                        "ApChipID": "0x8132",
                        "Info": {
                            "DeviceClass": "j717ap",
                            "Variant": "Customer Erase Install (IPSW)",
                        },
                        "Manifest": {
                            "iBSS": {"Info": {"Path": "Firmware/dfu/iBSS.j717.RELEASE.im4p"}},
                            "SEP": {"Info": {"Path": "Firmware/all_flash/sep-firmware.j717.RELEASE.im4p"}},
                            "OS": {"Info": {"Path": "090-00002-001.dmg"}},
                        },
                    },
                    {
                        "ApChipID": "0x8132",
                        "Info": {
                            "DeviceClass": "j717ap",
                            "Variant": "Customer Upgrade Install (IPSW)",
                        },
                        "Manifest": {
                            "iBSS": {"Info": {"Path": "Firmware/dfu/iBSS.j717.RELEASE.im4p"}},
                            "OS": {"Info": {"Path": "090-00002-001.dmg"}},
                        },
                    },
                ],
            },
        ),
        (
            "DEMO_UniversalMac_15.1_24B83_Restore.ipsw",
            {
                "ProductVersion": "15.1",
                "ProductBuildVersion": "24B83",
                "SupportedProductTypes": [
                    "MacBookAir10,1",
                    "MacBookPro17,1",
                    "MacBookPro18,1",
                    "MacBookPro18,3",
                    "Mac14,2",
                    "Mac14,9",
                    "Mac15,3",
                    "Mac15,6",
                    "Mac15,12",
                    "Mac16,1",
                ],
                "AppleFlashDemoMockup": True,
                "BuildIdentities": [
                    {
                        "ApChipID": "0x8122",
                        "Info": {
                            "DeviceClass": "j504ap",
                            "Variant": "macOS Customer",
                        },
                        "Manifest": {
                            "iBSS": {"Info": {"Path": "Firmware/dfu/iBSS.j504.RELEASE.im4p"}},
                            "SEP": {"Info": {"Path": "Firmware/all_flash/sep-firmware.j504.RELEASE.im4p"}},
                            "OS": {"Info": {"Path": "090-00003-001.dmg"}},
                        },
                    },
                    {
                        "ApChipID": "0x8103",
                        "Info": {
                            "DeviceClass": "j313ap",
                            "Variant": "Recovery Customer Install",
                        },
                        "Manifest": {
                            "iBSS": {"Info": {"Path": "Firmware/dfu/iBSS.j504.RELEASE.im4p"}},
                            "OS": {"Info": {"Path": "090-00003-001.dmg"}},
                        },
                    },
                ],
            },
        ),
    ]

    created: list[Path] = []
    for file_name, manifest_dict in specs:
        out_path = target_dir / file_name
        referenced: set[str] = set()
        for ident in manifest_dict["BuildIdentities"]:
            for item in ident["Manifest"].values():
                referenced.add(item["Info"]["Path"])

        restore_dict = {
            "ProductVersion": manifest_dict["ProductVersion"],
            "ProductBuildVersion": manifest_dict["ProductBuildVersion"],
            "SupportedProductTypes": manifest_dict["SupportedProductTypes"],
        }
        with zipfile.ZipFile(out_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("BuildManifest.plist", plistlib.dumps(manifest_dict))
            zf.writestr("Restore.plist", plistlib.dumps(restore_dict))
            zf.writestr(
                "DEMO_MOCKUP.txt",
                "ДЕМО-МАКЕТ IPSW Apple Flash Studio. Не является настоящей прошивкой Apple.\n",
            )
            for rel in sorted(referenced):
                zf.writestr(rel, b"DEMO_PLACEHOLDER_FIRMWARE_PAYLOAD")
        created.append(out_path)

    return created
