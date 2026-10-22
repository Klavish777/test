"""Автоматическое сохранение снимков всех страниц Apple Flash Studio в PNG."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QTimer

SCREENSHOT_PLAN = (
    ("dashboard", "macbook_dfu", "apple_01_dashboard"),
    ("flash", "macbook_dfu", "apple_02_flash_wizard"),
    ("library", None, "apple_03_ipsw_library"),
    ("dfu", None, "apple_04_dfu_assistant"),
    ("drivers", None, "apple_05_windows_drivers"),
)


def capture_studio_screenshots(app, window, out_dir: Path) -> int:
    out_dir.mkdir(parents=True, exist_ok=True)
    queue = list(SCREENSHOT_PLAN)

    def _step() -> None:
        if not queue:
            window.select_virtual_preset(None)
            app.quit()
            return
        route, virt_preset, filename = queue.pop(0)
        window.resize(1380, 860)
        window.select_virtual_preset(virt_preset)
        window.navigate(route)
        if route == "dfu":
            window.dfu_page.select_procedure("mac_apple_silicon")
        app.processEvents()
        pix = window.grab()
        pix.save(str(out_dir / f"{filename}.png"), "PNG")
        QTimer.singleShot(100, _step)

    QTimer.singleShot(220, _step)
    return int(app.exec())
