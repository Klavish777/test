"""Доменные исключения Apple Flash Studio."""

from __future__ import annotations


class AppleFlashError(Exception):
    """Базовая ошибка приложения."""


class ValidationError(AppleFlashError):
    """Некорректные входные данные."""


class IpswError(AppleFlashError):
    """Повреждённый, неподдерживаемый или неполный файл .ipsw."""


class IntegrityError(IpswError):
    """Несовпадение контрольной суммы SHA-256 / SHA-1."""


class CompatibilityError(AppleFlashError):
    """Прошивка несовместима с целевым устройством Apple."""


class DeviceConnectionError(AppleFlashError):
    """Ошибка обнаружения или связи с устройством по USB."""


class FlashExecutionError(AppleFlashError):
    """Ошибка во время выполнения перепрошивки или команды восстановления."""
