"""Криптографические контрольные суммы, безопасное чтение архивов и санитизация путей."""

from __future__ import annotations

import hashlib
import re
import sys
import zipfile
from collections.abc import Callable
from pathlib import Path

from apple_flash.core.errors import IpswError, ValidationError

CHUNK_SIZE = 4 * 1024 * 1024  # 4 МиБ для быстрой потоковой проверки больших IPSW (8–16 ГБ)
MAX_PLIST_BYTES = 32 * 1024 * 1024  # Защита от zip-бомб при чтении BuildManifest.plist
SAFE_NAME_RE = re.compile(r"[^A-Za-z0-9._\-+,() ]+")
HEX_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
HEX_SHA1_RE = re.compile(r"^[0-9a-f]{40}$")


def sanitize_filename(name: str) -> str:
    cleaned = SAFE_NAME_RE.sub("_", (name or "").strip()).strip(" .")
    if not cleaned or cleaned in {".", ".."}:
        return "firmware.ipsw"
    return cleaned[:180]


def normalize_hash(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip().lower().replace(" ", "")
    if not cleaned:
        return None
    if not (HEX_SHA256_RE.match(cleaned) or HEX_SHA1_RE.match(cleaned)):
        raise ValidationError(
            "Контрольная сумма должна быть корректной строкой SHA-256 (64 hex-символа) "
            "или SHA-1 (40 hex-символов)."
        )
    return cleaned


def compute_hashes(
    path: Path | str,
    *,
    progress_cb: Callable[[int, int], None] | None = None,
    cancel_check: Callable[[], bool] | None = None,
) -> tuple[str, str]:
    """Потоково вычисляет (sha256, sha1) за один проход чтения файла с диска."""
    target = Path(path)
    if not target.is_file():
        raise IpswError(f"Файл не найден: {target}")
    total = target.stat().st_size
    sha256 = hashlib.sha256()
    sha1 = hashlib.sha1()
    processed = 0

    with target.open("rb") as fh:
        while True:
            if cancel_check and cancel_check():
                raise IpswError("Расчёт контрольной суммы отменён пользователем.")
            chunk = fh.read(CHUNK_SIZE)
            if not chunk:
                break
            sha256.update(chunk)
            sha1.update(chunk)
            processed += len(chunk)
            if progress_cb:
                progress_cb(processed, total)

    return sha256.hexdigest(), sha1.hexdigest()


def read_zip_member_safe(zf: zipfile.ZipFile, member_name: str, *, max_bytes: int = MAX_PLIST_BYTES) -> bytes:
    """Безопасно читает метаданные из ZIP/IPSW в память с защитой от zip-бомб и path traversal."""
    normalized = member_name.replace("\\", "/").lstrip("/")
    if ".." in normalized.split("/"):
        raise IpswError(f"Небезопасный путь внутри архива: {member_name}")
    try:
        info = zf.getinfo(member_name)
    except KeyError as exc:
        raise IpswError(f"В архиве IPSW отсутствует обязательный файл: {member_name}") from exc

    if info.file_size > max_bytes:
        raise IpswError(
            f"Файл метаданных {member_name} превышает допустимый лимит ({info.file_size} байт)."
        )

    chunks: list[bytes] = []
    read_total = 0
    with zf.open(info, "r") as stream:
        while True:
            piece = stream.read(65536)
            if not piece:
                break
            read_total += len(piece)
            if read_total > max_bytes:
                raise IpswError(
                    f"Реальный размер {member_name} при распаковке превысил лимит безопасности."
                )
            chunks.append(piece)
    return b"".join(chunks)


def windows_no_window_kwargs() -> dict[str, int]:
    """Подавляет всплытие консольных окон cmd.exe на Windows при вызове CLI-утилит."""
    if sys.platform == "win32":
        flag = getattr(__import__("subprocess"), "CREATE_NO_WINDOW", 0x08000000)
        return {"creationflags": flag}
    return {}


def resolve_pmb3_command(tools_dir: Path | None = None) -> list[str] | None:
    """Возвращает базовую команду запуска pymobiledevice3 (безопасно для PyInstaller EXE)."""
    import importlib.util
    import shutil

    exe_name = "pymobiledevice3.exe" if sys.platform == "win32" else "pymobiledevice3"
    if tools_dir:
        cand = tools_dir / exe_name
        if cand.is_file():
            return [str(cand)]
    which_pmb = shutil.which("pymobiledevice3")
    if which_pmb:
        return [which_pmb]
    if not getattr(sys, "frozen", False) and importlib.util.find_spec("pymobiledevice3") is not None:
        return [sys.executable, "-m", "pymobiledevice3"]
    return None


def human_bytes(size: int | None) -> str:
    if size is None or size < 0:
        return "—"
    value = float(size)
    for unit in ("Б", "КБ", "МБ", "ГБ", "ТБ"):
        if value < 1024.0 or unit == "ТБ":
            return f"{value:.2f} {unit}" if unit != "Б" else f"{int(value)} Б"
        value /= 1024.0
    return f"{value:.2f} ТБ"
