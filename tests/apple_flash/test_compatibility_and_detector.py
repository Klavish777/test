"""Тесты проверки совместимости моделей Apple и парсеров USB / DFU / Recovery."""

from __future__ import annotations

import json
from pathlib import Path

from apple_flash.data.models import ConnectedDevice
from apple_flash.services.compatibility import evaluate_compatibility
from apple_flash.services.device_detector import (
    parse_irecovery_output,
    parse_windows_pnp_apple_Output,
)
from apple_flash.services.ipsw_inspector import IpswInspector, create_demo_ipsw_bundle


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

    # Совместимый iPhone 15 Pro (с предупреждением из-за DEMO-макета)
    ok_verdict = evaluate_compatibility(iphone_15_pro, demos["iphone"], "update")
    assert ok_verdict.can_proceed is True

    # Чужая модель iPhone 14 Pro -> Жёсткая блокировка!
    bad_model = evaluate_compatibility(iphone_14_pro, demos["iphone"], "update")
    assert bad_model.level == "incompatible"
    assert bad_model.can_proceed is False

    # Попытка прошить образ MacBook на iPhone -> Жёсткая блокировка!
    cross_family = evaluate_compatibility(iphone_15_pro, demos["macbook"], "erase")
    assert cross_family.level == "incompatible"

    # Попытка запустить режим Revive MacBook на iPhone -> Жёсткая блокировка!
    wrong_action = evaluate_compatibility(iphone_15_pro, demos["iphone"], "revive_mac")
    assert wrong_action.level == "incompatible"


def test_compatibility_dfu_cpid_matching(tmp_path: Path) -> None:
    inspector = IpswInspector()
    mac_manifest = next(
        inspector.inspect(p)
        for p in create_demo_ipsw_bundle(tmp_path)
        if "UniversalMac" in p.name
    )

    # MacBook в голом DFU без ProductType, но с верным кристаллом M3 (0x8122)
    raw_dfu_m3 = ConnectedDevice(
        uid="ECID:0x112233",
        mode="dfu",
        product_type=None,
        family="macbook",
        cpid=0x8122,
    )
    verdict_ok = evaluate_compatibility(raw_dfu_m3, mac_manifest, "revive_mac")
    assert verdict_ok.can_proceed is True

    # Устройство в DFU на старом чипе A11 (0x8015) с образом UniversalMac -> блокировка
    raw_dfu_a11 = ConnectedDevice(
        uid="ECID:0x999999",
        mode="dfu",
        product_type=None,
        family="iphone",
        cpid=0x8015,
    )
    verdict_bad = evaluate_compatibility(raw_dfu_a11, mac_manifest, "erase")
    assert verdict_bad.level == "incompatible"


def test_windows_pnp_usb_parser_extracts_dfu_cpid_ecid_and_driver() -> None:
    payload = [
        {
            "Name": "Apple Mobile Device (DFU Mode)",
            "PNPDeviceID": r"USB\VID_05AC&PID_1227\CPID:8122_CPRV:10_CPFM:03_SCEP:01_BDID:02_ECID:0099887766554433_IBFL:3C",
            "Service": "WinUSB",
            "Status": "OK",
        },
        {
            "Name": "Apple Recovery (iBoot) USB Composite Device",
            "PNPDeviceID": r"USB\VID_05AC&PID_1281\CPID:8132_BDID:08_ECID:00AABBCCDDEEFF11",
            "Service": "USBAAPL64",
            "Status": "OK",
        },
    ]
    devices = parse_windows_pnp_apple_Output(json.dumps(payload))
    assert len(devices) == 2

    dfu_dev = devices[0]
    assert dfu_dev.mode == "dfu"
    assert dfu_dev.cpid == 0x8122
    assert dfu_dev.bdid == 0x02
    assert dfu_dev.ecid == "0x0099887766554433"
    assert dfu_dev.usb_driver == "WinUSB"

    rec_dev = devices[1]
    assert rec_dev.mode == "recovery"
    assert rec_dev.cpid == 0x8132
    assert rec_dev.usb_driver == "USBAAPL64"


def test_irecovery_output_parser() -> None:
    sample = """
CPID: 0x8130
CPRV: 0x11
BDID: 0x0c
ECID: 0x001a2b3c4d5e6f01
MODE: DFU
PRODUCT: iPhone16,1
MODEL: d83ap
"""
    dev = parse_irecovery_output(sample)
    assert dev is not None
    assert dev.mode == "dfu"
    assert dev.product_type == "iPhone16,1"
    assert dev.family == "iphone"
    assert dev.cpid == 0x8130
    assert dev.board_config == "d83ap"
