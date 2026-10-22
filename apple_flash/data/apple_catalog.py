"""Встроенный офлайн-справочник устройств Apple (iPhone, iPad, MacBook), чипов CPID и режимов DFU."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AppleDeviceSpec:
    product_type: str
    marketing_name: str
    family: str  # iphone | ipad | macbook
    soc: str
    cpid: int
    dfu_group: str
    dfu_port_hint: str | None = None


@dataclass(frozen=True)
class DfuProcedure:
    key: str
    title: str
    family: str
    summary: str
    cable_note: str
    steps: tuple[tuple[str, int], ...]  # (описание шага, длительность сек; 0 = действие без таймера)
    recovery_steps: tuple[str, ...]
    port_diagram: str | None = None


# Справочник кристаллов Apple Silicon / Bionic / T2 по идентификатору CPID (в DFU/Recovery)
CHIP_BY_CPID: dict[int, str] = {
    0x8010: "Apple A10 Fusion",
    0x8011: "Apple A10X Fusion",
    0x8012: "Apple T2 Security Chip",
    0x8015: "Apple A11 Bionic",
    0x8020: "Apple A12 Bionic",
    0x8027: "Apple A12X / A12Z Bionic",
    0x8030: "Apple A13 Bionic",
    0x8101: "Apple A14 Bionic",
    0x8103: "Apple M1",
    0x6000: "Apple M1 Pro",
    0x6001: "Apple M1 Max",
    0x8110: "Apple A15 Bionic",
    0x8112: "Apple M2",
    0x6020: "Apple M2 Pro",
    0x6021: "Apple M2 Max",
    0x8120: "Apple A16 Bionic",
    0x8122: "Apple M3",
    0x6030: "Apple M3 Pro",
    0x6031: "Apple M3 Max",
    0x8130: "Apple A17 Pro",
    0x8132: "Apple M4",
    0x6040: "Apple M4 Pro",
    0x6041: "Apple M4 Max",
    0x8140: "Apple A18 / A18 Pro",
}


APPLE_SPECS: tuple[AppleDeviceSpec, ...] = (
    # ---------------------------- iPhone ----------------------------
    AppleDeviceSpec("iPhone10,3", "iPhone X (Global)", "iphone", "Apple A11 Bionic", 0x8015, "iphone_faceid"),
    AppleDeviceSpec("iPhone10,6", "iPhone X (GSM)", "iphone", "Apple A11 Bionic", 0x8015, "iphone_faceid"),
    AppleDeviceSpec("iPhone11,8", "iPhone XR", "iphone", "Apple A12 Bionic", 0x8020, "iphone_faceid"),
    AppleDeviceSpec("iPhone11,2", "iPhone XS", "iphone", "Apple A12 Bionic", 0x8020, "iphone_faceid"),
    AppleDeviceSpec("iPhone11,6", "iPhone XS Max", "iphone", "Apple A12 Bionic", 0x8020, "iphone_faceid"),
    AppleDeviceSpec("iPhone12,1", "iPhone 11", "iphone", "Apple A13 Bionic", 0x8030, "iphone_faceid"),
    AppleDeviceSpec("iPhone12,3", "iPhone 11 Pro", "iphone", "Apple A13 Bionic", 0x8030, "iphone_faceid"),
    AppleDeviceSpec("iPhone12,5", "iPhone 11 Pro Max", "iphone", "Apple A13 Bionic", 0x8030, "iphone_faceid"),
    AppleDeviceSpec("iPhone12,8", "iPhone SE (2-го поколения)", "iphone", "Apple A13 Bionic", 0x8030, "iphone_se_side"),
    AppleDeviceSpec("iPhone13,1", "iPhone 12 mini", "iphone", "Apple A14 Bionic", 0x8101, "iphone_faceid"),
    AppleDeviceSpec("iPhone13,2", "iPhone 12", "iphone", "Apple A14 Bionic", 0x8101, "iphone_faceid"),
    AppleDeviceSpec("iPhone13,3", "iPhone 12 Pro", "iphone", "Apple A14 Bionic", 0x8101, "iphone_faceid"),
    AppleDeviceSpec("iPhone13,4", "iPhone 12 Pro Max", "iphone", "Apple A14 Bionic", 0x8101, "iphone_faceid"),
    AppleDeviceSpec("iPhone14,4", "iPhone 13 mini", "iphone", "Apple A15 Bionic", 0x8110, "iphone_faceid"),
    AppleDeviceSpec("iPhone14,5", "iPhone 13", "iphone", "Apple A15 Bionic", 0x8110, "iphone_faceid"),
    AppleDeviceSpec("iPhone14,2", "iPhone 13 Pro", "iphone", "Apple A15 Bionic", 0x8110, "iphone_faceid"),
    AppleDeviceSpec("iPhone14,3", "iPhone 13 Pro Max", "iphone", "Apple A15 Bionic", 0x8110, "iphone_faceid"),
    AppleDeviceSpec("iPhone14,6", "iPhone SE (3-го поколения)", "iphone", "Apple A15 Bionic", 0x8110, "iphone_se_side"),
    AppleDeviceSpec("iPhone14,7", "iPhone 14", "iphone", "Apple A15 Bionic", 0x8110, "iphone_faceid"),
    AppleDeviceSpec("iPhone14,8", "iPhone 14 Plus", "iphone", "Apple A15 Bionic", 0x8110, "iphone_faceid"),
    AppleDeviceSpec("iPhone15,2", "iPhone 14 Pro", "iphone", "Apple A16 Bionic", 0x8120, "iphone_faceid"),
    AppleDeviceSpec("iPhone15,3", "iPhone 14 Pro Max", "iphone", "Apple A16 Bionic", 0x8120, "iphone_faceid"),
    AppleDeviceSpec("iPhone15,4", "iPhone 15", "iphone", "Apple A16 Bionic", 0x8120, "iphone_faceid"),
    AppleDeviceSpec("iPhone15,5", "iPhone 15 Plus", "iphone", "Apple A16 Bionic", 0x8120, "iphone_faceid"),
    AppleDeviceSpec("iPhone16,1", "iPhone 15 Pro", "iphone", "Apple A17 Pro", 0x8130, "iphone_faceid"),
    AppleDeviceSpec("iPhone16,2", "iPhone 15 Pro Max", "iphone", "Apple A17 Pro", 0x8130, "iphone_faceid"),
    AppleDeviceSpec("iPhone17,1", "iPhone 16 Pro", "iphone", "Apple A18 Pro", 0x8140, "iphone_faceid"),
    AppleDeviceSpec("iPhone17,2", "iPhone 16 Pro Max", "iphone", "Apple A18 Pro", 0x8140, "iphone_faceid"),
    AppleDeviceSpec("iPhone17,3", "iPhone 16", "iphone", "Apple A18", 0x8140, "iphone_faceid"),
    AppleDeviceSpec("iPhone17,4", "iPhone 16 Plus", "iphone", "Apple A18", 0x8140, "iphone_faceid"),
    AppleDeviceSpec("iPhone17,5", "iPhone 16e", "iphone", "Apple A18", 0x8140, "iphone_faceid"),
    # ---------------------------- iPad ----------------------------
    AppleDeviceSpec("iPad12,1", "iPad (9-го поколения, Wi-Fi)", "ipad", "Apple A13 Bionic", 0x8030, "ipad_home"),
    AppleDeviceSpec("iPad12,2", "iPad (9-го поколения, Cellular)", "ipad", "Apple A13 Bionic", 0x8030, "ipad_home"),
    AppleDeviceSpec("iPad13,18", "iPad (10-го поколения, Wi-Fi)", "ipad", "Apple A14 Bionic", 0x8101, "ipad_top_button"),
    AppleDeviceSpec("iPad13,19", "iPad (10-го поколения, Cellular)", "ipad", "Apple A14 Bionic", 0x8101, "ipad_top_button"),
    AppleDeviceSpec("iPad14,1", "iPad mini (6-го поколения, Wi-Fi)", "ipad", "Apple A15 Bionic", 0x8110, "ipad_top_button"),
    AppleDeviceSpec("iPad14,2", "iPad mini (6-го поколения, Cellular)", "ipad", "Apple A15 Bionic", 0x8110, "ipad_top_button"),
    AppleDeviceSpec("iPad16,1", "iPad mini (A17 Pro, Wi-Fi)", "ipad", "Apple A17 Pro", 0x8130, "ipad_top_button"),
    AppleDeviceSpec("iPad16,2", "iPad mini (A17 Pro, Cellular)", "ipad", "Apple A17 Pro", 0x8130, "ipad_top_button"),
    AppleDeviceSpec("iPad13,16", "iPad Air (5-го поколения M1, Wi-Fi)", "ipad", "Apple M1", 0x8103, "ipad_top_button"),
    AppleDeviceSpec("iPad13,17", "iPad Air (5-го поколения M1, Cellular)", "ipad", "Apple M1", 0x8103, "ipad_top_button"),
    AppleDeviceSpec("iPad14,8", "iPad Air 11\" (M2, Wi-Fi)", "ipad", "Apple M2", 0x8112, "ipad_top_button"),
    AppleDeviceSpec("iPad14,9", "iPad Air 11\" (M2, Cellular)", "ipad", "Apple M2", 0x8112, "ipad_top_button"),
    AppleDeviceSpec("iPad14,10", "iPad Air 13\" (M2, Wi-Fi)", "ipad", "Apple M2", 0x8112, "ipad_top_button"),
    AppleDeviceSpec("iPad14,3", "iPad Pro 11\" (4-го поколения M2, Wi-Fi)", "ipad", "Apple M2", 0x8112, "ipad_top_button"),
    AppleDeviceSpec("iPad14,4", "iPad Pro 11\" (4-го поколения M2, Cellular)", "ipad", "Apple M2", 0x8112, "ipad_top_button"),
    AppleDeviceSpec("iPad14,5", "iPad Pro 12.9\" (6-го поколения M2, Wi-Fi)", "ipad", "Apple M2", 0x8112, "ipad_top_button"),
    AppleDeviceSpec("iPad14,6", "iPad Pro 12.9\" (6-го поколения M2, Cellular)", "ipad", "Apple M2", 0x8112, "ipad_top_button"),
    AppleDeviceSpec("iPad16,3", "iPad Pro 11\" (M4, Wi-Fi)", "ipad", "Apple M4", 0x8132, "ipad_top_button"),
    AppleDeviceSpec("iPad16,4", "iPad Pro 11\" (M4, Cellular)", "ipad", "Apple M4", 0x8132, "ipad_top_button"),
    AppleDeviceSpec("iPad16,5", "iPad Pro 13\" (M4, Wi-Fi)", "ipad", "Apple M4", 0x8132, "ipad_top_button"),
    AppleDeviceSpec("iPad16,6", "iPad Pro 13\" (M4, Cellular)", "ipad", "Apple M4", 0x8132, "ipad_top_button"),
    # ---------------------------- MacBook (Apple Silicon & T2) ----------------------------
    AppleDeviceSpec(
        "MacBookAir10,1",
        "MacBook Air 13\" (M1, 2020)",
        "macbook",
        "Apple M1",
        0x8103,
        "mac_apple_silicon",
        "Левая сторона: задний порт USB-C (ближе к экрану / дальний от трекпада).",
    ),
    AppleDeviceSpec(
        "MacBookPro17,1",
        "MacBook Pro 13\" (M1, 2020)",
        "macbook",
        "Apple M1",
        0x8103,
        "mac_apple_silicon",
        "Левая сторона: задний порт USB-C (ближе к экрану).",
    ),
    AppleDeviceSpec(
        "MacBookPro18,3",
        "MacBook Pro 14\" (M1 Pro, 2021)",
        "macbook",
        "Apple M1 Pro",
        0x6000,
        "mac_apple_silicon",
        "Левая сторона: задний порт USB-C (сразу рядом с разъёмом MagSafe 3).",
    ),
    AppleDeviceSpec(
        "MacBookPro18,1",
        "MacBook Pro 16\" (M1 Pro, 2021)",
        "macbook",
        "Apple M1 Pro",
        0x6000,
        "mac_apple_silicon",
        "Левая сторона: задний порт USB-C (рядом с MagSafe 3).",
    ),
    AppleDeviceSpec(
        "Mac14,2",
        "MacBook Air 13\" (M2, 2022)",
        "macbook",
        "Apple M2",
        0x8112,
        "mac_apple_silicon",
        "Левая сторона: задний порт USB-C (рядом с MagSafe 3).",
    ),
    AppleDeviceSpec(
        "Mac14,15",
        "MacBook Air 15\" (M2, 2023)",
        "macbook",
        "Apple M2",
        0x8112,
        "mac_apple_silicon",
        "Левая сторона: задний порт USB-C (рядом с MagSafe 3).",
    ),
    AppleDeviceSpec(
        "Mac14,7",
        "MacBook Pro 13\" (M2, 2022)",
        "macbook",
        "Apple M2",
        0x8112,
        "mac_apple_silicon",
        "Левая сторона: задний порт USB-C (ближе к экрану).",
    ),
    AppleDeviceSpec(
        "Mac14,9",
        "MacBook Pro 14\" (M2 Pro, 2023)",
        "macbook",
        "Apple M2 Pro",
        0x6020,
        "mac_apple_silicon",
        "Левая сторона: задний порт USB-C (рядом с MagSafe 3).",
    ),
    AppleDeviceSpec(
        "Mac14,10",
        "MacBook Pro 16\" (M2 Pro, 2023)",
        "macbook",
        "Apple M2 Pro",
        0x6020,
        "mac_apple_silicon",
        "Левая сторона: задний порт USB-C (рядом с MagSafe 3).",
    ),
    AppleDeviceSpec(
        "Mac15,12",
        "MacBook Air 13\" (M3, 2024)",
        "macbook",
        "Apple M3",
        0x8122,
        "mac_apple_silicon",
        "Левая сторона: задний порт USB-C (рядом с MagSafe 3).",
    ),
    AppleDeviceSpec(
        "Mac15,13",
        "MacBook Air 15\" (M3, 2024)",
        "macbook",
        "Apple M3",
        0x8122,
        "mac_apple_silicon",
        "Левая сторона: задний порт USB-C (рядом с MagSafe 3).",
    ),
    AppleDeviceSpec(
        "Mac15,3",
        "MacBook Pro 14\" (M3, 2023)",
        "macbook",
        "Apple M3",
        0x8122,
        "mac_apple_silicon",
        "Левая сторона: передний порт USB-C (дальше от MagSafe 3, ближе к трекпаду!).",
    ),
    AppleDeviceSpec(
        "Mac15,6",
        "MacBook Pro 14\" (M3 Pro, 2023)",
        "macbook",
        "Apple M3 Pro",
        0x6030,
        "mac_apple_silicon",
        "Левая сторона: задний порт USB-C (сразу рядом с MagSafe 3).",
    ),
    AppleDeviceSpec(
        "Mac16,1",
        "MacBook Pro 14\" (M4, 2024)",
        "macbook",
        "Apple M4",
        0x8132,
        "mac_apple_silicon",
        "Левая сторона: задний порт USB-C (сразу рядом с MagSafe 3).",
    ),
    AppleDeviceSpec(
        "Mac16,6",
        "MacBook Pro 14\" (M4 Pro, 2024)",
        "macbook",
        "Apple M4 Pro",
        0x6040,
        "mac_apple_silicon",
        "Левая сторона: задний порт USB-C (сразу рядом с MagSafe 3).",
    ),
    AppleDeviceSpec(
        "iBridge2,14",
        "MacBook Pro 16\" (Intel + Apple T2, 2019)",
        "macbook",
        "Apple T2 Security Chip",
        0x8012,
        "mac_t2",
        "Левая сторона: передний порт Thunderbolt 3 (ближе к трекпаду).",
    ),
    AppleDeviceSpec(
        "iBridge2,12",
        "MacBook Air 13\" (Intel + Apple T2, 2018–2020)",
        "macbook",
        "Apple T2 Security Chip",
        0x8012,
        "mac_t2",
        "Левая сторона: передний порт Thunderbolt 3 (ближе к трекпаду).",
    ),
)

SPECS_BY_PRODUCT_TYPE: dict[str, AppleDeviceSpec] = {s.product_type: s for s in APPLE_SPECS}


DFU_PROCEDURES: dict[str, DfuProcedure] = {
    "iphone_faceid": DfuProcedure(
        key="iphone_faceid",
        title="iPhone с Face ID (iPhone X / 11 / 12 / 13 / 14 / 15 / 16)",
        family="iphone",
        summary="Для всех моделей iPhone с Face ID и для iPhone 8 / SE 2 / SE 3.",
        cable_note="Подключите iPhone к ПК Windows кабелем USB-A — Lightning/USB-C (рекомендуется порт USB-A на материнской плате; некоторые кабели USB-C — Lightning не переводят устройство в DFU).",
        steps=(
            ("Подключите включённый или выключенный iPhone кабелем к ПК Windows.", 0),
            ("Быстро нажмите и отпустите кнопку Громкость ВВЕРХ (+).", 1),
            ("Быстро нажмите и отпустите кнопку Громкость ВНИЗ (-).", 1),
            ("Зажмите и удерживайте БОКОВУЮ кнопку питания до погасания экрана.", 10),
            ("Не отпуская Боковую кнопку, зажмите Громкость ВНИЗ (-) ровно на 5 секунд.", 5),
            ("Отпустите Боковую кнопку, но ПРОДОЛЖАЙТЕ удерживать Громкость ВНИЗ (-) ещё 10 секунд.", 10),
            ("Экран должен оставаться полностью ЧЁРНЫМ — ПК обнаружит Apple Mobile Device (DFU Mode).", 0),
        ),
        recovery_steps=(
            "Быстро нажмите и отпустите Громкость ВВЕРХ (+).",
            "Быстро нажмите и отпустите Громкость ВНИЗ (-).",
            "Удерживайте Боковую кнопку питания (~15–20 сек), не отпуская на яблоке, пока не появится экран с кабелем и ноутбуком.",
        ),
    ),
    "iphone_se_side": DfuProcedure(
        key="iphone_se_side",
        title="iPhone SE (2-го / 3-го поколения) и iPhone 8",
        family="iphone",
        summary="Кнопка Домой не используется при входе в DFU — используется связка Боковой кнопки и Громкости вниз.",
        cable_note="Используйте качественный дата-кабель USB-A — Lightning напрямую в порт ПК.",
        steps=(
            ("Подключите iPhone кабелем к ПК Windows.", 0),
            ("Быстро нажмите и отпустите Громкость ВВЕРХ (+).", 1),
            ("Быстро нажмите и отпустите Громкость ВНИЗ (-).", 1),
            ("Удерживайте Боковую кнопку питания до полного погасания экрана.", 10),
            ("Удерживая Боковую кнопку, зажмите Громкость ВНИЗ (-) на 5 секунд.", 5),
            ("Отпустите Боковую кнопку и продолжайте держать Громкость ВНИЗ (-) 10 секунд.", 10),
            ("Если экран чёрный, а в Диспетчере устройств появилось VID_05AC&PID_1227 — вы в DFU.", 0),
        ),
        recovery_steps=(
            "Нажмите и отпустите Громкость ВВЕРХ (+), затем Громкость ВНИЗ (-).",
            "Держите Боковую кнопку до появления иконки кабеля и ноутбука.",
        ),
    ),
    "ipad_top_button": DfuProcedure(
        key="ipad_top_button",
        title="iPad без кнопки «Домой» (iPad Pro Face ID, iPad Air 4/5/M2, iPad 10, iPad mini 6/7)",
        family="ipad",
        summary="Модели iPad с узкими рамками (Face ID или Touch ID в верхней кнопке).",
        cable_note="Подключите iPad кабелем USB-C к порту ПК Windows.",
        steps=(
            ("Подключите iPad кабелем к ПК Windows.", 0),
            ("Быстро нажмите и отпустите кнопку Громкости, БЛИЖАЙШУЮ к верхней кнопке питания.", 1),
            ("Быстро нажмите и отпустите кнопку Громкости, ДАЛЬНЮЮ от верхней кнопки питания.", 1),
            ("Зажмите и удерживайте ВЕРХНЮЮ кнопку питания до погасания экрана.", 10),
            ("Не отпуская Верхнюю кнопку, зажмите кнопку Громкости ВНИЗ на 5 секунд.", 5),
            ("Отпустите Верхнюю кнопку, продолжая удерживать Громкость ВНИЗ ещё 10 секунд.", 10),
            ("Экран останется чёрным — iPad перешёл в режим DFU.", 0),
        ),
        recovery_steps=(
            "Нажмите кнопку громкости ближе к верхней кнопке, затем кнопку громкости дальше от неё.",
            "Удерживайте Верхнюю кнопку, пока на экране iPad не появится значок подключения к компьютеру.",
        ),
    ),
    "ipad_home": DfuProcedure(
        key="ipad_home",
        title="iPad с физической кнопкой «Домой» (iPad 5–9 поколения)",
        family="ipad",
        summary="Классические модели iPad с круглой кнопкой Home на передней панели.",
        cable_note="Подключите iPad кабелем USB — Lightning к ПК Windows.",
        steps=(
            ("Подключите iPad кабелем к ПК Windows.", 0),
            ("Одновременно зажмите и удерживайте кнопку «Домой» (Home) и Верхнюю кнопку питания.", 8),
            ("Как только экран погаснет (через ~8 секунд), отпустите Верхнюю кнопку питания, но ПРОДОЛЖАЙТЕ удерживать кнопку «Домой» ещё 10 секунд.", 10),
            ("Экран останется чёрным — устройство определится в режиме DFU (05ac:1227).", 0),
        ),
        recovery_steps=(
            "Зажмите одновременно кнопку «Домой» и Верхнюю кнопку питания.",
            "Не отпускайте кнопки на логотипе Apple — держите до появления экрана кабеля и компьютера.",
        ),
    ),
    "mac_apple_silicon": DfuProcedure(
        key="mac_apple_silicon",
        title="MacBook на Apple Silicon (M1 / M2 / M3 / M4 — Air и Pro)",
        family="macbook",
        summary="Восстановление прошивки (Revive) и полная перепрошивка (Restore) через UniversalMac .ipsw.",
        cable_note="ВАЖНО: используйте дата-кабель USB-C (USB 2.0 / 3.x), а НЕ кабель Thunderbolt 3/4. Вставляйте кабель строго в сервисный DFU-порт целевого MacBook!",
        steps=(
            ("Отсоедините кабель от MacBook и полностью выключите MacBook (удерживайте Touch ID 10 секунд).", 0),
            ("Подключите дата-кабель USB-C в сервисный DFU-порт MacBook и в USB-порт ПК Windows.", 0),
            ("Нажмите и отпустите кнопку питания (Touch ID), затем СРАЗУ зажмите 4 клавиши: ПРАВЫЙ Shift + ЛЕВЫЙ Option + ЛЕВЫЙ Control + кнопку питания (Touch ID).", 10),
            ("Через 10 секунд отпустите 3 клавиши клавиатуры (Shift, Option, Control), но ПРОДОЛЖАЙТЕ удерживать кнопку питания (Touch ID) ещё до 8 секунд.", 8),
            ("Экран MacBook должен оставаться полностью ЧЁРНЫМ — на ПК Windows появится USB-устройство Apple Mobile Device (DFU Mode) VID_05AC&PID_1227.", 0),
        ),
        recovery_steps=(
            "Выключите MacBook полностью.",
            "Нажмите и УДЕРЖИВАЙТЕ кнопку питания (Touch ID) ~10 секунд до надписи «Загрузка параметров запуска» (Loading startup options).",
        ),
        port_diagram=(
            "Схема сервисного порта DFU на MacBook (Apple Silicon):\n"
            "• MacBook Air M1 / Pro 13\" M1/M2 (2 порта слева): ЗАДНИЙ левый порт USB-C (ближе к экрану).\n"
            "• MacBook Air M2 / M3 и MacBook Pro 14\"/16\" M1 Pro/Max, M2 Pro/Max, M3 Pro/Max, M4: ЗАДНИЙ левый порт USB-C (сразу возле MagSafe 3).\n"
            "• ИСКЛЮЧЕНИЕ — MacBook Pro 14\" на базовом чипе M3 (Mac15,3, 2 порта слева): ПЕРЕДНИЙ левый порт USB-C (ближе к трекпаду)!"
        ),
    ),
    "mac_t2": DfuProcedure(
        key="mac_t2",
        title="MacBook на Intel с чипом безопасности Apple T2 (2018–2020)",
        family="macbook",
        summary="Прошивка сопроцессора T2 (bridgeOS .ipsw — iBridge2,*): устраняет кирпич после сбоя обновления EFI/bridgeOS.",
        cable_note="Используйте дата-кабель USB-C в ПЕРЕДНИЙ левый порт Thunderbolt 3 (ближе к трекпаду).",
        steps=(
            ("Выключите MacBook (удерживайте кнопку питания 5–10 секунд) и подключите кабель в ПЕРЕДНИЙ левый порт USB-C.", 0),
            ("Зажмите кнопку питания и СРАЗУ зажмите ПРАВЫЙ Shift + ЛЕВЫЙ Option + ЛЕВЫЙ Control.", 3),
            ("Удерживайте все 4 кнопки ровно 3 секунды — экран останется чёрным, контроллер T2 перейдёт в DFU.", 0),
        ),
        recovery_steps=(
            "Включите MacBook и сразу удерживайте Command (⌘) + R (локальное восстановление) или Option + Command + R (Internet Recovery macOS).",
        ),
        port_diagram=(
            "Схема порта DFU для MacBook с чипом Apple T2 (2018–2020):\n"
            "• На всех MacBook Air и MacBook Pro с T2 сервисный порт DFU — ПЕРЕДНИЙ левый порт USB-C (ближайший к трекпаду / пользователю)."
        ),
    ),
}


def resolve_product_name(product_type: str | None, cpid: int | None = None) -> str:
    """Возвращает человекочитаемое имя модели по коду ProductType или идентификатору кристалла CPID."""
    if product_type:
        spec = SPECS_BY_PRODUCT_TYPE.get(product_type)
        if spec:
            return spec.marketing_name
        lower = product_type.lower()
        if lower.startswith("iphone"):
            return f"iPhone ({product_type})"
        if lower.startswith("ipad"):
            return f"iPad ({product_type})"
        if lower.startswith(("macbook", "mac")):
            return f"Mac ({product_type})"
        if lower.startswith("ibridge"):
            return f"Mac T2 Security Chip ({product_type})"
    if cpid is not None and cpid in CHIP_BY_CPID:
        return f"Устройство Apple на базе {CHIP_BY_CPID[cpid]}"
    return "Устройство Apple"


def infer_device_family(product_type: str | None, cpid: int | None = None) -> str:
    """Определяет семейство: iphone | ipad | macbook | unknown."""
    if product_type:
        spec = SPECS_BY_PRODUCT_TYPE.get(product_type)
        if spec:
            return spec.family
        lower = product_type.lower()
        if lower.startswith("iphone"):
            return "iphone"
        if lower.startswith("ipad"):
            return "ipad"
        if lower.startswith(("macbook", "mac", "ibridge")):
            return "macbook"
    if cpid is not None:
        chip = CHIP_BY_CPID.get(cpid, "")
        if "T2" in chip or any(tag in chip for tag in ("M1 Pro", "M1 Max", "M2 Pro", "M2 Max", "M3 Pro", "M3 Max", "M4 Pro", "M4 Max")):
            return "macbook"
        if "Bionic" in chip or "Fusion" in chip or "A17" in chip or "A18" in chip:
            return "iphone"
    return "unknown"


def infer_ipsw_family(supported_types: list[str]) -> str:
    """Определяет платформу IPSW по списку SupportedProductTypes из BuildManifest.plist."""
    families = {infer_device_family(pt) for pt in supported_types if pt}
    families.discard("unknown")
    if len(families) == 1:
        return next(iter(families))
    if "macbook" in families:
        return "macbook"
    if "ipad" in families and "iphone" not in families:
        return "ipad"
    if "iphone" in families and "ipad" not in families:
        return "iphone"
    if families:
        return "universal"
    return "unknown"


FAMILY_LABELS: dict[str, str] = {
    "iphone": "iPhone (iOS)",
    "ipad": "iPad (iPadOS)",
    "macbook": "MacBook (macOS / bridgeOS)",
    "universal": "Универсальный образ Apple",
    "unknown": "Не определено",
}
