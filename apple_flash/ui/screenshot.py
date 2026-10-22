"""Автоматическая генерация актуальных PNG-снимков интерфейса Apple Flash Studio v2.0 для документации."""

from __future__ import annotations

import plistlib
import tempfile
import zipfile
from pathlib import Path

from PySide6.QtCore import QTimer

from apple_flash.data.models import ConnectedDevice


def _make_sample_ipsw(path: Path, product_type: str, os_ver: str, build_ver: str, cpid: str) -> Path:
    manifest = {
        "ProductVersion": os_ver,
        "ProductBuildVersion": build_ver,
        "SupportedProductTypes": [product_type],
        "BuildIdentities": [
            {
                "ApChipID": cpid,
                "Info": {"DeviceClass": "d83ap", "Variant": "Customer Erase Install (IPSW)"},
                "Manifest": {"iBSS": {"Info": {"Path": "Firmware/dfu/iBSS.im4p"}}},
            },
            {
                "ApChipID": cpid,
                "Info": {"DeviceClass": "d83ap", "Variant": "Customer Upgrade Install (IPSW)"},
                "Manifest": {"iBSS": {"Info": {"Path": "Firmware/dfu/iBSS.im4p"}}},
            },
        ],
    }
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("BuildManifest.plist", plistlib.dumps(manifest))
        zf.writestr("Firmware/dfu/iBSS.im4p", b"IBSS")
    return path


def capture_studio_screenshots(app, window, out_dir: Path) -> int:
    out_dir.mkdir(parents=True, exist_ok=True)
    tmp_dir = Path(tempfile.mkdtemp(prefix="afs_shots_"))
    iphone_ipsw = _make_sample_ipsw(
        tmp_dir / "iPhone16,1_18.2_22C152_Restore.ipsw", "iPhone16,1", "18.2", "22C152", "0x8130"
    )
    mac_ipsw = _make_sample_ipsw(
        tmp_dir / "UniversalMac_15.2_24C101_Restore.ipsw", "Mac15,3", "15.2", "24C101", "0x8122"
    )

    sample_iphone = ConnectedDevice(
        uid="00008130-001A2B3C4D5E6F01",
        mode="normal",
        product_type="iPhone16,1",
        marketing_name="iPhone 15 Pro",
        family="iphone",
        ecid="0x1A2B3C4D5E6F01",
        udid="00008130-001A2B3C4D5E6F01",
        cpid=0x8130,
        board_config="D83AP",
        os_version="18.1",
        build_version="22B83",
        serial_number="F2L9X8K2Q1",
        device_name="iPhone",
        usb_driver="USBAAPL64 (Apple Mobile Device USB)",
    )
    sample_mac = ConnectedDevice(
        uid="0x8122FFEEDDCC03",
        mode="dfu",
        product_type="Mac15,3",
        marketing_name="MacBook Pro 14\" (M3, 2023)",
        family="macbook",
        ecid="0x8122FFEEDDCC03",
        cpid=0x8122,
        bdid=0x22,
        board_config="J504AP",
        usb_driver="WinUSB (готов к прошивке DFU)",
    )

    steps = [
        ("flash", [sample_iphone], iphone_ipsw, "apple_01_dashboard"),
        ("flash", [sample_mac], mac_ipsw, "apple_02_flash_wizard"),
        ("flash", [], None, "apple_03_ipsw_library"),
        ("dfu", [], None, "apple_04_dfu_assistant"),
        ("drivers", [], None, "apple_05_windows_drivers"),
    ]

    def _run_next() -> None:
        if not steps:
            window.set_mock_devices_for_preview([])
            app.quit()
            return
        route, devs, ipsw_file, fname = steps.pop(0)
        window.resize(1280, 820)
        window.set_mock_devices_for_preview(devs)
        window.navigate(route)
        if ipsw_file is not None:
            window.flash_page.load_ipsw_path(ipsw_file)
        else:
            window.flash_page._selected_ipsw_path = None
            window.flash_page._selected_manifest = None
            window.flash_page._render_ipsw_summary()
            window.flash_page._refresh_compatibility()
        if route == "dfu":
            window.dfu_page.select_procedure("iphone_faceid")
        app.processEvents()
        pix = window.grab()
        pix.save(str(out_dir / f"{fname}.png"), "PNG")
        QTimer.singleShot(90, _run_next)

    QTimer.singleShot(180, _run_next)
    return int(app.exec())
