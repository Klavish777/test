"""Интернационализация: каталоги переводов JSON.

Добавление языка:
  1. скопируйте ``repair_os/resources/i18n/ru.json`` в ``xx.json``;
  2. переведите значения (ключи менять нельзя);
  3. добавьте язык в ``LANGUAGE_LABELS`` ниже.

Смена языка применяется после перезапуска приложения (интерфейс собирается
из каталога при старте).
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from repair_os.core.paths import app_resource_dir

log = logging.getLogger(__name__)

DEFAULT_LANGUAGE = "ru"
LANGUAGE_LABELS: dict[str, str] = {
    "ru": "Русский",
    "en": "English",
}

_current_language = DEFAULT_LANGUAGE
_catalogs: dict[str, dict[str, str]] = {}
_listeners: list[Any] = []


def i18n_dir() -> Path:
    return app_resource_dir() / "resources" / "i18n"


def available_languages() -> dict[str, str]:
    """Коды и подписи доступных языков (только реально загружаемые каталоги)."""
    _ensure_loaded()
    return {code: LANGUAGE_LABELS.get(code, code.upper()) for code in sorted(_catalogs)}


def _load_catalog(code: str) -> dict[str, str]:
    path = i18n_dir() / f"{code}.json"
    try:
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
        if not isinstance(data, dict):
            raise ValueError("каталог перевода должен быть объектом JSON")
        return {str(key): str(value) for key, value in data.items()}
    except FileNotFoundError:
        log.warning("Каталог перевода не найден: %s", path)
        return {}
    except (OSError, ValueError) as exc:
        log.error("Не удалось загрузить перевод %s: %s", code, exc)
        return {}


def _ensure_loaded() -> None:
    if _catalogs:
        return
    for code in LANGUAGE_LABELS:
        _catalogs[code] = _load_catalog(code)
    if DEFAULT_LANGUAGE not in _catalogs:
        _catalogs[DEFAULT_LANGUAGE] = {}


def set_language(code: str) -> None:
    global _current_language
    _ensure_loaded()
    if code not in _catalogs:
        log.warning("Неизвестный язык %r, используется %s", code, DEFAULT_LANGUAGE)
        code = DEFAULT_LANGUAGE
    _current_language = code
    for listener in list(_listeners):
        try:
            listener(code)
        except Exception:  # pragma: no cover - слушатели не должны ломать приложение
            log.exception("Ошибка слушателя смены языка")


def current_language() -> str:
    return _current_language


def add_language_listener(callback: Any) -> None:
    _listeners.append(callback)


def tr(key: str, **params: Any) -> str:
    """Перевод по ключу с подстановкой ``{name}``-параметров.

    Если ключа нет, возвращается ``params['default']`` (если задан) или сам ключ.
    """
    _ensure_loaded()
    fallback = params.pop("default", key)
    catalog = _catalogs.get(_current_language, {})
    text = catalog.get(key)
    if text is None:
        text = _catalogs.get(DEFAULT_LANGUAGE, {}).get(key, fallback)
    if params:
        try:
            return text.format(**params)
        except (KeyError, IndexError, ValueError):
            log.warning("Некорректные параметры перевода для ключа %s", key)
    return text


def catalog_keys(code: str = DEFAULT_LANGUAGE) -> set[str]:
    _ensure_loaded()
    return set(_catalogs.get(code, {}))
