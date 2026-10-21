"""Настройка логирования: файл с ротацией + консоль.

Логи пишутся в ``<data>/logs/repair_os.log`` и не содержат секретов.
"""

from __future__ import annotations

import logging
import logging.handlers
from pathlib import Path

_LOG_FORMAT = "%(asctime)s %(levelname)-8s [%(name)s] %(message)s"
_configured = False


def setup_logging(log_dir: Path, *, level: int = logging.INFO, console: bool = True) -> Path:
    """Инициализирует корневой логгер. Повторные вызовы безопасны."""
    global _configured
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "repair_os.log"

    root = logging.getLogger()
    if _configured:
        return log_file

    root.setLevel(level)
    formatter = logging.Formatter(_LOG_FORMAT)

    file_handler = logging.handlers.RotatingFileHandler(
        log_file, maxBytes=2 * 1024 * 1024, backupCount=5, encoding="utf-8"
    )
    file_handler.setFormatter(formatter)
    root.addHandler(file_handler)

    if console:
        stream = logging.StreamHandler()
        stream.setFormatter(formatter)
        stream.setLevel(logging.WARNING)
        root.addHandler(stream)

    logging.getLogger("repair_os").setLevel(level)
    _configured = True
    logging.getLogger(__name__).info("Логирование запущено: %s", log_file)
    return log_file


def install_exception_hook(logger_name: str = "repair_os.unhandled") -> None:
    """Логирует необработанные исключения, чтобы приложение не падало молча."""
    import sys

    logger = logging.getLogger(logger_name)

    def _hook(exc_type, exc_value, exc_tb):  # pragma: no cover - защитный код
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_tb)
            return
        logger.critical("Необработанное исключение", exc_info=(exc_type, exc_value, exc_tb))

    sys.excepthook = _hook
