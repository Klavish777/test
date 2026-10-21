"""Хранилище секретов (токены внешних сервисов).

Правила:
  * пароли/токены **никогда** не сохраняются в открытом виде;
  * при наличии пакета ``cryptography`` значения шифруются Fernet-ключом,
    который лежит в каталоге данных с правами только для владельца;
  * без ``cryptography`` секреты живут только в памяти текущей сессии.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path

log = logging.getLogger(__name__)

try:  # необязательная зависимость
    from cryptography.fernet import Fernet, InvalidToken

    _CRYPTO_AVAILABLE = True
except Exception:  # pragma: no cover - окружение без cryptography
    Fernet = None  # type: ignore[assignment]
    InvalidToken = Exception  # type: ignore[assignment,misc]
    _CRYPTO_AVAILABLE = False


class SecretStore:
    def __init__(self, data_dir: Path, *, filename: str = "secrets.bin") -> None:
        self._path = Path(data_dir) / filename
        self._key_path = Path(data_dir) / "secrets.key"
        self._memory: dict[str, str] = {}
        self._fernet = None
        if _CRYPTO_AVAILABLE:
            self._fernet = Fernet(self._load_or_create_key())

    @property
    def persistent(self) -> bool:
        return self._fernet is not None

    def _load_or_create_key(self) -> bytes:
        if self._key_path.exists():
            return self._key_path.read_bytes().strip()
        key = Fernet.generate_key()
        self._key_path.parent.mkdir(parents=True, exist_ok=True)
        self._key_path.write_bytes(key)
        try:
            os.chmod(self._key_path, 0o600)
        except OSError:  # Windows
            pass
        return key

    def _read_all(self) -> dict[str, str]:
        if not self._fernet or not self._path.exists():
            return {}
        try:
            raw = self._path.read_bytes()
            if not raw:
                return {}
            decrypted = self._fernet.decrypt(raw)
            data = json.loads(decrypted.decode("utf-8"))
            return {str(k): str(v) for k, v in data.items()}
        except (InvalidToken, ValueError, OSError):
            log.error("Не удалось прочитать хранилище секретов")
            return {}

    def set_secret(self, key: str, value: str) -> None:
        key = key.strip()
        if not key:
            raise ValueError("Пустой ключ секрета")
        if not self._fernet:
            self._memory[key] = value
            log.warning("cryptography недоступна: секрет %s хранится только в памяти", key)
            return
        data = self._read_all()
        data[key] = value
        payload = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self._path.write_bytes(self._fernet.encrypt(payload))
        try:
            os.chmod(self._path, 0o600)
        except OSError:
            pass

    def get_secret(self, key: str) -> str | None:
        if not self._fernet:
            return self._memory.get(key)
        return self._read_all().get(key)

    def delete_secret(self, key: str) -> None:
        self._memory.pop(key, None)
        if not self._fernet:
            return
        data = self._read_all()
        if data.pop(key, None) is not None:
            payload = json.dumps(data, ensure_ascii=False).encode("utf-8")
            self._path.write_bytes(self._fernet.encrypt(payload))

    def keys(self) -> list[str]:
        return sorted(set(self._read_all()) | set(self._memory))
