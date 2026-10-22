"""Тесты совместимости моделей Apple, встроенного рантайма USB/libusb и трёхуровневого детектора Win32 SetupAPI."""

from __future__ import annotations

from pathlib import Path

from apple_flash.core.usb_runtime import check_runtime_health
from apple_flash.data.apple_catalog import lookup_hardware_by_cpid_bdid, resolve_product_name
from apple_flash.data.models import ConnectedDevice
from apple_flash.services.compatibility import evaluate_compatibility
from apple_flash.services.device_detector import DeviceDetector
from apple_flash.services.ipsw_inspector import IpswInspector, create_demo_ipsw_bundle
from apple_flash.services.win32_usb import (
    consolidate_win32_entries,
    parse_instance_entry,
    parse_usb_serial_segment,
)


def test_runtime_health_bundles_pmb3_and_libusb() -> None:
    health = check_runtime_health()
    assert health["pymobiledevice3"][0] is True
    assert "34" in health["pymobiledevice3"][1]  # 340+ моделей Apple в базе IRECV_DEVICES
    assert health["libusb"][0] is True
    assert health["certifi"][0] is True


def test_irecv_340_model_lookup_by_cpid_bdid_and_product() -> None:
    pt, hm, name = lookup_hardware_by_cpid_bdid(0x8122, 0x22)
    assert pt == "Mac15,3"
    assert hm and hm.lower() == "j504ap"
    assert name and "MacBook Pro" in name

    # Даже модели вне ручного списка разрешаются через встроенную базу IRECV_DEVICES
    assert "iPhone" in resolve_product_name("iPhone8,1")
    assert "iPad" in resolve_product_name("iPad11,3")


def test_compatibility_blocks_wrong_model_and_wrong_family(tmp_path: Path) -> None:
    inspector = IpswInspector()
    demos = {inspector.inspect(p).family: inspector.inspect(p) for p in create_demo_ipsw_bundle(tmp_path)}

    iphone_15_pro = ConnectedDevice(
        uid="UDID-1",
        mode="normal",
        product_type="iPhone16,1",
        marketing_name="iPhone 15 Pro",
        family="iphone",
        cpid=0x8130,
    )
    iphone_14_pro = ConnectedDevice(
        uid="UDID-2",
        mode="normal",
        product_type="iPhone15,2",
        marketing_name="iPhone 14 Pro",
        family="iphone",
        cpid=0x8120,
    )

    ok_verdict = evaluate_compatibility(iphone_15_pro, demos["iphone"], "update")
    assert ok_verdict.can_proceed is True

    bad_model = evaluate_compatibility(iphone_14_pro, demos["iphone"], "update")
    assert bad_model.level == "incompatible"
    assert bad_model.can_proceed is False

    cross_family = evaluate_compatibility(iphone_15_pro, demos["macbook"], "erase")
    assert cross_family.level == "incompatible"

    wrong_action = evaluate_compatibility(iphone_15_pro, demos["iphone"], "revive_mac")
    assert wrong_action.level == "incompatible"


def test_compatibility_dfu_cpid_matching(tmp_path: Path) -> None:
    inspector = IpswInspector()
    mac_manifest = next(
        inspector.inspect(p)
        for p in create_demo_ipsw_bundle(tmp_path)
        if "UniversalMac" in p.name
    )

    raw_dfu_m3 = ConnectedDevice(
        uid="ECID:0x112233",
        mode="dfu",
        product_type=None,
        family="macbook",
        cpid=0x8122,
    )
    verdict_ok = evaluate_compatibility(raw_dfu_m3, mac_manifest, "revive_mac")
    assert verdict_ok.can_proceed is True

    raw_dfu_a11 = ConnectedDevice(
        uid="ECID:0x999999",
        mode="dfu",
        product_type=None,
        family="iphone",
        cpid=0x8015,
    )
    verdict_bad = evaluate_compatibility(raw_dfu_a11, mac_manifest, "erase")
    assert verdict_bad.level == "incompatible"


def test_win32_usb_instance_parser_and_composite_consolidation() -> None:
    # 1. Современный 24-hex USB серийник iPhone (A16 Bionic 0x8120 + 16-hex ECID)
    parsed_24 = parse_usb_serial_segment("00008120001A2B3C4D5E6F01")
    assert parsed_24["udid"] == "00008120-001A2B3C4D5E6F01"
    assert parsed_24["cpid"] == 0x8120
    assert parsed_24["ecid"] == "0x1A2B3C4D5E6F01"

    # 2. Составное устройство usbccgp + интерфейс USBAAPL64 объединяются в одно устройство
    root_e = parse_instance_entry(
        r"USB\VID_05AC&PID_12A8\00008120001A2B3C4D5E6F01",
        service="usbccgp",
        description="Apple Mobile Device USB Composite Device",
    )
    iface_e = parse_instance_entry(
        r"USB\VID_05AC&PID_12A8&MI_00\6&2A3B4C5D&0&0000",
        service="USBAAPL64",
        description="Apple Mobile Device USB Driver",
    )
    assert root_e is not None and iface_e is not None
    merged = consolidate_win32_entries([root_e, iface_e])
    assert len(merged) == 1
    assert merged[0].service == "USBAAPL64"
    assert merged[0].mode == "normal"

    # 3. Клавиатура Apple (PID 0x024F) игнорируется и не принимается за телефон
    assert parse_instance_entry(r"USB\VID_05AC&PID_024F\123456", service="HidUsb") is None

    # 4. DFU-устройство с заблокированным драйвером USBAAPL64 распознаёт точную модель Mac15,3 и выдаёт подсказку
    dfu_entry = parse_instance_entry(
        r"USB\VID_05AC&PID_1227\CPID:8122_CPRV:10_CPFM:03_BDID:22_ECID:0099887766554433",
        service="USBAAPL64",
        description="Apple Mobile Device (DFU Mode)",
    )
    assert dfu_entry is not None
    detector = DeviceDetector()
    unmatched = detector._scan_win32_unmatched([dfu_entry], set(), set())
    assert len(unmatched) == 1
    dev = unmatched[0]
    assert dev.mode == "dfu"
    assert dev.product_type == "Mac15,3"
    assert dev.family == "macbook"
    assert dev.ecid == "0x99887766554433"
    assert dev.driver_warning and "WinUSB" in dev.driver_warning
