"""Доменные исключения приложения."""

from __future__ import annotations


class RepairOSError(Exception):
    """Базовое исключение приложения (безопасно показывать пользователю)."""


class ValidationError(RepairOSError):
    """Некорректные входные данные."""

    def __init__(self, message: str, *, fields: dict[str, str] | None = None) -> None:
        super().__init__(message)
        self.fields = fields or {}


class NotFoundError(RepairOSError):
    """Запись не найдена."""


class ConflictError(RepairOSError):
    """Нарушение уникальности или конфликт данных."""


class IntegrityError(RepairOSError):
    """Проверка целостности/контрольной суммы не пройдена."""


class ImportErrorOS(RepairOSError):
    """Ошибка импорта файла или пакета данных."""


class UnsupportedFormatError(RepairOSError):
    """Неподдерживаемый формат файла."""


class SecurityError(RepairOSError):
    """Операция отклонена по требованиям безопасности."""


class BackupError(RepairOSError):
    """Ошибка резервного копирования или восстановления."""
