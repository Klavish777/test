"""Заготовка модели лицензирования для будущей монетизации.

На этапе MVP **все функции доступны бесплатно**: провайдер лицензии возвращает
полный набор прав и не блокирует работу приложения. Архитектура позволяет
подключить проверку подписки позже, не меняя код интерфейса.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Protocol

log = logging.getLogger(__name__)


class Feature(str, Enum):
    BOARDVIEW_3D = "boardview_3d"
    BOARDVIEW_PHOTO = "boardview_photo"
    FIRMWARE_LIBRARY = "firmware_library"
    TECHNICAL_LIBRARY = "technical_library"
    LOCAL_IMPORT = "local_import"
    BACKUP = "backup"
    PREMIUM_CONTENT = "premium_content"
    CLOUD_SYNC = "cloud_sync"


class Edition(str, Enum):
    FREE = "free"
    PRO = "pro"


@dataclass(frozen=True)
class Entitlements:
    edition: Edition
    features: frozenset[Feature]
    account_required: bool = False
    provider_name: str = "local"
    metadata: dict[str, str] = field(default_factory=dict)

    def allows(self, feature: Feature) -> bool:
        return feature in self.features

    def describe(self) -> str:
        return f"{self.edition.value} / {self.provider_name} / {len(self.features)} функций"


class EntitlementProvider(Protocol):
    """Интерфейс будущих провайдеров (аккаунт, подписка, сервер лицензий)."""

    name: str

    def entitlements(self) -> Entitlements: ...


class LocalEntitlementProvider:
    """MVP: локальный провайдер — все возможности включены.

    Никакой оплаты, регистрации или сетевых запросов не требуется.
    """

    name = "local"

    def entitlements(self) -> Entitlements:
        return Entitlements(
            edition=Edition.PRO,
            features=frozenset(Feature),
            account_required=False,
            provider_name=self.name,
            metadata={"note": "Полный локальный доступ в MVP, оплата не требуется"},
        )


_ACTIVE_PROVIDER: EntitlementProvider = LocalEntitlementProvider()


def set_provider(provider: EntitlementProvider) -> None:
    """Точка расширения для будущей подписки/аккаунта."""
    global _ACTIVE_PROVIDER
    log.info("Провайдер лицензии переключён на %s", provider.name)
    _ACTIVE_PROVIDER = provider


def current_entitlements() -> Entitlements:
    try:
        return _ACTIVE_PROVIDER.entitlements()
    except Exception:  # pragma: no cover - лицензия не должна ломать приложение
        log.exception("Ошибка провайдера лицензии, используется локальный режим")
        return LocalEntitlementProvider().entitlements()


def feature_available(feature: Feature) -> bool:
    """Проверка прав. В MVP всегда True, но интерфейс уже готов к ограничениям."""
    return current_entitlements().allows(feature)
