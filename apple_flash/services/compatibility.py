"""Проверка совместимости устройства Apple (iPhone, iPad, MacBook) и выбранного образа .ipsw."""

from __future__ import annotations

from apple_flash.data.apple_catalog import CHIP_BY_CPID, resolve_product_name
from apple_flash.data.models import (
    CompatibilityVerdict,
    ConnectedDevice,
    IpswManifestInfo,
    IpswRecord,
)


def evaluate_compatibility(
    device: ConnectedDevice | None,
    ipsw: IpswManifestInfo | IpswRecord | None,
    action: str,
) -> CompatibilityVerdict:
    """Сверяет идентификаторы устройства (ProductType / CPID / режим) с манифестом IPSW."""
    if action in {"exit_recovery", "enter_recovery"}:
        if device is None:
            return CompatibilityVerdict(
                "incompatible",
                "Устройство не подключено",
                ["Подключите iPhone или iPad по USB для переключения режима Recovery."],
            )
        if action == "exit_recovery" and device.mode != "recovery":
            return CompatibilityVerdict(
                "warning",
                "Устройство не находится в режиме Recovery",
                [f"Текущий режим устройства: {device.mode_label}. Команда выхода рассчитана на iBoot Recovery."],
            )
        if action == "enter_recovery" and device.mode != "normal":
            return CompatibilityVerdict(
                "warning",
                "Вход в Recovery программно выполняется из Обычного режима",
                ["В режимах DFU/Recovery перевод через lockdown недоступен — используйте кнопочную инструкцию."],
            )
        return CompatibilityVerdict(
            "compatible",
            "Команда управления режимом Recovery готова",
            [f"Целевое устройство: {device.display_title} ({device.uid})."],
        )

    if ipsw is None:
        return CompatibilityVerdict(
            "incompatible",
            "Не выбран файл прошивки .ipsw",
            ["Выберите локальный образ .ipsw на диске или из библиотеки."],
        )

    supported_types = (
        ipsw.supported_product_types
        if isinstance(ipsw, IpswManifestInfo)
        else ipsw.supported_products
    )
    supported_cpids = ipsw.supported_cpids
    has_erase = ipsw.has_erase_variant if isinstance(ipsw, IpswManifestInfo) else ipsw.has_erase
    has_upgrade = (
        ipsw.has_upgrade_variant if isinstance(ipsw, IpswManifestInfo) else ipsw.has_upgrade
    )
    is_demo = ipsw.is_demo_mockup if isinstance(ipsw, IpswManifestInfo) else ipsw.is_demo
    build_ver = ipsw.build_version
    os_ver = ipsw.product_version

    details: list[str] = [
        f"Образ IPSW: версия ОС {os_ver} (сборка {build_ver}), поддерживаемых моделей: {len(supported_types)}."
    ]
    level = "compatible"

    if isinstance(ipsw, IpswManifestInfo) and ipsw.missing_components:
        return CompatibilityVerdict(
            "incompatible",
            "Архив IPSW повреждён или неполный",
            [
                f"Отсутствуют файлы компонентов из BuildManifest.plist ({len(ipsw.missing_components)} шт.).",
                f"Пример отсутствующего компонента: {ipsw.missing_components[0]}",
            ],
        )

    if isinstance(ipsw, IpswRecord) and ipsw.verified_state == "mismatch":
        return CompatibilityVerdict(
            "incompatible",
            "Контрольная сумма файла IPSW НЕ совпадает с эталоном",
            [
                "Файл повреждён или изменён. Использование повреждённого образа может привести к ошибке восстановления.",
                f"Ожидалось: {ipsw.expected_hash}",
                f"Фактически SHA-256: {ipsw.sha256 or '—'}",
            ],
        )

    if device is None:
        return CompatibilityVerdict(
            "warning",
            "Устройство не подключено — проверен только файл прошивки",
            details
            + [
                "Подключите iPhone, iPad или MacBook кабелем USB, чтобы сверить точную модель устройства."
            ],
        )

    if action == "revive_mac" and device.family != "macbook":
        return CompatibilityVerdict(
            "incompatible",
            "Режим «Оживление MacBook (Revive)» предназначен только для компьютеров Mac",
            [
                f"Подключено устройство семейства {device.family_label}. "
                "Для iPhone и iPad выберите «Обновление (Update)» или «Чистая перепрошивка (Clean Restore)»."
            ],
        )

    # 1. Проверка точного кода ProductType (например iPhone16,1, iPad16,3, Mac15,3)
    if device.product_type:
        normalized_supported = {pt.lower(): pt for pt in supported_types}
        if supported_types and device.product_type.lower() not in normalized_supported:
            preview = ", ".join(supported_types[:6])
            if len(supported_types) > 6:
                preview += f" (+{len(supported_types) - 6})"
            return CompatibilityVerdict(
                "incompatible",
                f"Несовместимая модель: прошивка НЕ подходит для {device.product_type}",
                [
                    f"Подключено: {resolve_product_name(device.product_type)} ({device.product_type}).",
                    f"Выбранный IPSW поддерживает только: {preview or '—'}.",
                    "Прошивка чужим образом заблокирована для защиты устройства.",
                ],
            )
        details.append(
            f"Точное совпадение модели подтверждено: {device.product_type} ({resolve_product_name(device.product_type)})."
        )
    # 2. Если устройство в чистом DFU без ProductType — сверяем кристалл CPID
    elif device.cpid is not None and supported_cpids:
        if device.cpid not in supported_cpids:
            chip_str = CHIP_BY_CPID.get(device.cpid, f"0x{device.cpid:04X}")
            ipsw_chips = ", ".join(CHIP_BY_CPID.get(c, f"0x{c:04X}") for c in supported_cpids[:5])
            return CompatibilityVerdict(
                "incompatible",
                f"Несовпадение процессора (CPID): устройство на {chip_str}",
                [
                    f"Устройство в DFU сообщило CPID 0x{device.cpid:04X} ({chip_str}).",
                    f"Выбранный IPSW собран для кристаллов: {ipsw_chips}.",
                ],
            )
        details.append(
            f"Кристалл CPID 0x{device.cpid:04X} присутствует в BuildManifest.plist (точная ревизия платы BDID будет проверена при старте)."
        )
        level = "warning"
    else:
        level = "warning"
        details.append(
            "Точный идентификатор модели пока не прочитан (устройство в низкоуровневом режиме) — убедитесь в модели вручную."
        )

    # 3. Проверка варианта установки (Update vs Erase)
    if action in {"update", "revive_mac"} and not has_upgrade:
        return CompatibilityVerdict(
            "incompatible",
            "Образ IPSW не содержит сценария обновления без стирания",
            ["В BuildManifest.plist найден только вариант полной очистки (Erase)."],
        )
    if action == "erase" and not has_erase:
        return CompatibilityVerdict(
            "incompatible",
            "Образ IPSW не содержит сценария полной перепрошивки (Erase)",
            ["Выберите полный образ Restore.ipsw."],
        )

    # 4. Особенности режима подключения для MacBook и iPhone/iPad
    if device.family == "macbook" and device.mode != "dfu":
        level = "warning"
        details.append(
            "Для перепрошивки или оживления (Revive) MacBook с ПК Windows ноутбук должен находиться строго в режиме DFU (05ac:1227)."
        )
    elif device.family in {"iphone", "ipad"} and device.mode == "dfu" and action == "update":
        level = "warning"
        details.append(
            "Устройство в режиме DFU: если системный раздел повреждён, обновление с сохранением данных может потребовать Clean Restore."
        )

    # 5. Напоминание о подписи Apple TSS и Find My
    details.append(
        "Примечание Apple TSS: при реальной записи устройство запрашивает цифровую подпись SHSH у сервера Apple (gs.apple.com), если не передан локальный билет SHSH2."
    )
    if action == "erase":
        details.append(
            "ВНИМАНИЕ: Чистая перепрошивка (Clean Restore) безвозвратно удалит все данные пользователя. Если включён «Локатор» (Find My), после прошивки потребуется Apple ID владельца."
        )

    if is_demo or device.is_virtual:
        level = "warning"
        details.append(
            "Активен ДЕМО-макет (виртуальное устройство или тестовый .ipsw): разрешён только безопасный режим репетиции Dry-Run."
        )

    headline = (
        "Образ IPSW полностью совместим с устройством"
        if level == "compatible"
        else "Совместимо с предупреждениями — проверьте условия перед запуском"
    )
    return CompatibilityVerdict(level=level, headline=headline, details=details)
