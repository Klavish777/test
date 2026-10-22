"""Тесты графического интерфейса Apple Flash Studio v2.0 (PySide6 offscreen)."""

from __future__ import annotations

import plistlib
import zipfile
from pathlib import Path

from PySide6.QtWidgets import QApplication

from apple_flash.data.models import ConnectedDevice
from apple_flash.services.context import StudioContext
from apple_flash.ui.icon_gen import write_windows_ico
from apple_flash.ui.main_window import AppleFlashMainWindow
from apple_flash.ui.theme import apply_studio_theme


def _make_real_like_ipsw(path: Path, product_type: str, os_ver: str, build_ver: str, cpid: str) -> Path:
    manifest = {
        "ProductVersion": os_ver,
        "ProductBuildVersion": build_ver,
        "SupportedProductTypes": [product_type],
        "BuildIdentities": [
            {
                "ApChipID": cpid,
                "Info": {"DeviceClass": "j504ap", "Variant": "Customer Erase Install (IPSW)"},
                "Manifest": {"iBSS": {"Info": {"Path": "Firmware/dfu/iBSS.im4p"}}},
            },
            {
                "ApChipID": cpid,
                "Info": {"DeviceClass": "j504ap", "Variant": "Customer Upgrade Install (IPSW)"},
                "Manifest": {"iBSS": {"Info": {"Path": "Firmware/dfu/iBSS.im4p"}}},
            },
        ],
    }
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("BuildManifest.plist", plistlib.dumps(manifest))
        zf.writestr("Firmware/dfu/iBSS.im4p", b"REAL_IBSS_HEADER")
    return path


def test_clean_startup_has_no_demo_mockups_and_purges_legacy_v1(tmp_path: Path) -> None:
    data_dir = tmp_path / "user_appdata"
    # Имитируем базу пользователя после v1.0 с засеянными DEMO_*.ipsw
    legacy_ctx = StudioContext.create(data_dir, seed_demo=True)
    assert len(legacy_ctx.store.list_ipsw()) == 3
    legacy_ctx.close()

    # При обычном открытии v2.0 старые DEMO_*.ipsw автоматически вычищаются
    clean_ctx = StudioContext.create(data_dir, seed_demo=False)
    try:
        assert clean_ctx.store.list_ipsw() == []
    finally:
        clean_ctx.close()


def test_apple_flash_v2_window_navigation_and_workflows(tmp_path: Path) -> None:
    app = QApplication.instance() or QApplication([])
    apply_studio_theme(app)

    ico_file = write_windows_ico(tmp_path / "test_icon.ico")
    assert ico_file.read_bytes()[:4] == b"\x00\x00\x01\x00"

    ctx = StudioContext.create(tmp_path / "studio_data")
    window = AppleFlashMainWindow(ctx, enable_auto_poll=False)
    try:
        # Чистый запуск: нет фейковых макетов IPSW
        assert ctx.store.list_ipsw() == []

        for route in ("flash", "dfu", "drivers", "history"):
            window.navigate(route)
            app.processEvents()

        # Подключение MacBook M3 в DFU и проверка автоматического выбора Revive + совместимости IPSW
        mac_dev = ConnectedDevice(
            uid="0x8122FFEEDDCC03",
            mode="dfu",
            product_type="Mac15,3",
            marketing_name="MacBook Pro 14\" (M3, 2023)",
            family="macbook",
            ecid="0x8122FFEEDDCC03",
            cpid=0x8122,
            bdid=0x02,
            usb_driver="WinUSB",
        )
        window.set_mock_devices_for_preview([mac_dev])
        window.navigate("flash")
        mac_ipsw = _make_real_like_ipsw(
            tmp_path / "UniversalMac_15.2_24C101_Restore.ipsw", "Mac15,3", "15.2", "24C101", "0x8122"
        )
        assert window.flash_page.load_ipsw_path(mac_ipsw) is True
        app.processEvents()
        assert window.flash_page.rb_revive.isChecked() is True
        assert window.flash_page.current_action() == "revive_mac"
        assert window.flash_page.compat_pill.text() == "Совместима"

        # Проверка секундомера DFU для всех семейств (включая iPhone 7 / 6s)
        for proc_key in (
            "iphone_faceid",
            "iphone_7",
            "iphone_6s",
            "ipad_top_button",
            "mac_apple_silicon",
            "mac_t2",
        ):
            window.open_dfu_guide(proc_key)
            window.dfu_page._start_trainer()
            window.dfu_page._advance_step()
            window.dfu_page._reset_trainer()
            app.processEvents()
    finally:
        window.close()
        ctx.close()
