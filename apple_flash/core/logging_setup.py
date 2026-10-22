"""Настройка ротируемого логирования Apple Flash Studio."""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path


def setup_logging(logs_dir: Path, *, verbose: bool = False) -> Path:
    logs_dir.mkdir(parents=True, exist_ok=True)
    log_file = logs_dir / "apple_flash.log"
    root_logger = logging.getLogger("apple_flash")
    root_logger.setLevel(logging.DEBUG if verbose else logging.INFO)

    if not any(isinstance(h, RotatingFileHandler) for h in root_logger.handlers):
        formatter = logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=5 * 1024 * 1024,
            backupCount=3,
            encoding="utf-8",
        )
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)

    return log_file
