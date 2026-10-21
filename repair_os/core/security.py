"""Проверки безопасности: контрольные суммы, валидация путей, архивов и URL."""

from __future__ import annotations

import hashlib
import os
import re
import zipfile
from pathlib import Path, PurePosixPath
from urllib.parse import urlparse

from repair_os.core.errors import ImportErrorOS, IntegrityError, SecurityError, ValidationError

SAFE_NAME_RE = re.compile(r"[^0-9A-Za-zА-Яа-яЁё._ ()\-\[\]]+")
HEX64_RE = re.compile(r"^[0-9a-f]{64}$")
MAX_ARCHIVE_ENTRIES = 5000
MAX_ARCHIVE_UNCOMPRESSED = 2 * 1024 * 1024 * 1024  # 2 ГиБ
MAX_ARCHIVE_RATIO = 200  # защита от zip-бомб


def sha256_file(path: os.PathLike[str] | str, *, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        while True:
            chunk = handle.read(chunk_size)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def normalize_checksum(value: str | None) -> str | None:
    """Приводит контрольную сумму к нижнему регистру и проверяет формат SHA-256."""
    if value is None:
        return None
    cleaned = value.strip().lower().replace(" ", "")
    if not cleaned:
        return None
    if cleaned.startswith("sha256:"):
        cleaned = cleaned.split(":", 1)[1]
    if not HEX64_RE.match(cleaned):
        raise ValidationError(
            "Контрольная сумма должна быть SHA-256 (64 шестнадцатеричных символа)"
        )
    return cleaned


def verify_checksum(path: os.PathLike[str] | str, expected: str) -> bool:
    expected_norm = normalize_checksum(expected)
    if expected_norm is None:
        raise ValidationError("Эталонная контрольная сумма не указана")
    actual = sha256_file(path)
    if actual != expected_norm:
        raise IntegrityError(
            f"Контрольная сумма не совпадает.\nОжидалось: {expected_norm}\nПолучено: {actual}"
        )
    return True


def sanitize_filename(name: str, *, fallback: str = "file") -> str:
    """Убирает опасные символы и элементы пути из имени файла."""
    raw = str(name).replace("\\", "/").replace("\x00", "")
    candidate = os.path.basename(raw).strip()
    candidate = SAFE_NAME_RE.sub("_", candidate)
    candidate = candidate.strip(". ")
    if not candidate:
        candidate = fallback
    return candidate[:180]


def is_within(child: os.PathLike[str] | str, parent: os.PathLike[str] | str) -> bool:
    try:
        child_resolved = Path(child).resolve()
        parent_resolved = Path(parent).resolve()
    except OSError:
        return False
    return child_resolved == parent_resolved or parent_resolved in child_resolved.parents


def ensure_within(child: os.PathLike[str] | str, parent: os.PathLike[str] | str) -> Path:
    path = Path(child)
    if not is_within(path, parent):
        raise SecurityError(f"Путь вне разрешённого каталога: {path}")
    return path


def validate_url(url: str) -> str:
    """Разрешает только http/https и непустой хост."""
    url = (url or "").strip()
    if not url:
        raise ValidationError("Ссылка не указана")
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise ValidationError("Ссылка должна начинаться с http:// или https://")
    if not parsed.netloc:
        raise ValidationError("Ссылка не содержит домена")
    return url


def validate_import_file(path: os.PathLike[str] | str, allowed_suffixes: set[str]) -> Path:
    candidate = Path(path)
    if not candidate.exists() or not candidate.is_file():
        raise ImportErrorOS(f"Файл не найден: {candidate}")
    suffix = candidate.suffix.lower()
    if suffix not in allowed_suffixes:
        raise ImportErrorOS(
            f"Формат {suffix or 'без расширения'} не поддерживается "
            f"(ожидается: {', '.join(sorted(allowed_suffixes))})"
        )
    if candidate.stat().st_size == 0:
        raise ImportErrorOS("Файл пустой")
    return candidate


def sniff_is_zip(path: os.PathLike[str] | str) -> bool:
    try:
        return zipfile.is_zipfile(path)
    except OSError:
        return False


def safe_extract_zip(
    archive: os.PathLike[str] | str, destination: os.PathLike[str] | str
) -> list[Path]:
    """Безопасная распаковка ZIP: без path traversal, симлинков и zip-бомб."""
    archive_path = Path(archive)
    dest = Path(destination)
    dest.mkdir(parents=True, exist_ok=True)
    extracted: list[Path] = []

    if not sniff_is_zip(archive_path):
        raise ImportErrorOS("Файл не является корректным ZIP-архивом")

    with zipfile.ZipFile(archive_path) as zf:
        infos = zf.infolist()
        if len(infos) > MAX_ARCHIVE_ENTRIES:
            raise SecurityError(f"Архив содержит слишком много файлов ({len(infos)})")
        total_uncompressed = sum(info.file_size for info in infos)
        total_compressed = max(1, sum(info.compress_size for info in infos))
        if total_uncompressed > MAX_ARCHIVE_UNCOMPRESSED:
            raise SecurityError("Распакованный размер архива слишком велик")
        if total_uncompressed / total_compressed > MAX_ARCHIVE_RATIO:
            raise SecurityError("Подозрительный коэффициент сжатия (возможна zip-бомба)")

        for info in infos:
            member = PurePosixPath(info.filename.replace("\\", "/"))
            if member.is_absolute() or ".." in member.parts:
                raise SecurityError(f"Небезопасный путь в архиве: {info.filename}")
            if info.is_dir():
                continue
            # Внешние атрибуты содержат бит симлинка в старших 16 битах.
            mode = info.external_attr >> 16
            if mode and (mode & 0o170000) == 0o120000:
                raise SecurityError(f"Символические ссылки в архиве запрещены: {info.filename}")
            target = dest.joinpath(*member.parts)
            if not is_within(target, dest):
                raise SecurityError(f"Небезопасный путь в архиве: {info.filename}")
            target.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(info) as src, open(target, "wb") as out:
                while True:
                    chunk = src.read(1024 * 1024)
                    if not chunk:
                        break
                    out.write(chunk)
            extracted.append(target)
    return extracted


def redact_secret(value: str | None, *, visible: int = 4) -> str:
    if not value:
        return ""
    if len(value) <= visible:
        return "*" * len(value)
    return value[:visible] + "…" + "*" * max(4, len(value) - visible - 1)
