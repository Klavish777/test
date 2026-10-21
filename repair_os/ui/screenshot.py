"""Служебная отрисовка страниц в PNG (для документации и проверки вёрстки)."""

from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import QTimer

log = logging.getLogger(__name__)

PAGES = [
    ("home", "01_home"),
    ("catalog", "02_catalog"),
    ("boardview", "03_boardview"),
    ("firmware", "04_firmware"),
    ("library", "05_library"),
    ("settings", "06_settings"),
]


def capture_pages(app, window, directory: Path) -> int:
    directory.mkdir(parents=True, exist_ok=True)
    queue = list(PAGES)

    def capture_next() -> None:
        if not queue:
            app.quit()
            return
        key, name = queue.pop(0)
        window.resize(1440, 900)
        window.navigate(key)
        app.processEvents()
        pixmap = window.grab()
        target = directory / f"{name}.png"
        if pixmap.save(str(target), "PNG"):
            log.info("Снимок сохранён: %s", target)
        else:
            log.error("Не удалось сохранить снимок %s", target)
        QTimer.singleShot(120, capture_next)

    QTimer.singleShot(300, capture_next)
    result = app.exec()
    return result
