"""Smoke-тесты графического интерфейса Apple Flash Studio (PySide6 offscreen)."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QApplication

from apple_flash.services.context import StudioContext
from apple_flash.ui.icon_gen import write_windows_ico
from apple_flash.ui.main_window import AppleFlashMainWindow
from apple_flash.ui.theme import apply_studio_theme


def test_apple_flash_window_navigation_and_workflows(tmp_path: Path) -> None:
    app = QApplication.instance() or QApplication([])
    apply_studio_theme(app)

    ico_file = write_windows_ico(tmp_path / "test_icon.ico")
    raw_ico = ico_file.read_bytes()
    assert raw_ico[:4] == b"\x00\x00\x01\x00"

    ctx = StudioContext.create(tmp_path / "studio_data", seed_demo=True)
    window = AppleFlashMainWindow(ctx)
    try:
        for route in ("dashboard", "flash", "library", "dfu", "drivers", "history", "settings"):
            window.navigate(route)
            app.processEvents()

        # Подключение виртуального MacBook M3 в DFU и переход в мастер прошивки
        window.select_virtual_preset("macbook_dfu")
        app.processEvents()
        assert len(window.connected_devices) == 1
        assert window.connected_devices[0].family == "macbook"

        mac_records = ctx.store.list_ipsw(family="macbook")
        assert len(mac_records) == 1
        window.open_flash_for_device(window.connected_devices[0])
        window.open_flash_for_ipsw(mac_records[0])
        app.processEvents()
        assert window.flash_page.rb_revive.isChecked() is True
        assert "UniversalMac" in window.flash_page.cmd_preview.text()

        # Проверка тренажёра DFU для всех семейств
        for proc_key in ("iphone_faceid", "ipad_top_button", "mac_apple_silicon", "mac_t2"):
            window.open_dfu_guide(proc_key)
            window.dfu_page._start_trainer()
            window.dfu_page._advance_step()
            window.dfu_page._reset_trainer()
            app.processEvents()
    finally:
        window.close()
        ctx.close()
