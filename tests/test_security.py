"""Тесты проверок безопасности и валидации ввода."""

from __future__ import annotations

import zipfile
from pathlib import Path

import pytest

from repair_os.core.errors import (
    ImportErrorOS,
    IntegrityError,
    SecurityError,
    ValidationError,
)
from repair_os.core.security import (
    ensure_within,
    is_within,
    normalize_checksum,
    redact_secret,
    safe_extract_zip,
    sanitize_filename,
    sha256_file,
    validate_import_file,
    validate_url,
    verify_checksum,
)


def test_sanitize_filename_strips_paths():
    assert sanitize_filename("../../etc/passwd") == "passwd"
    assert sanitize_filename("C:\\Windows\\evil.exe") == "evil.exe"
    assert sanitize_filename("  ...  ") == "file"
    assert "/" not in sanitize_filename("a/b/c.zip")
    assert sanitize_filename("файл прошивки.zip") == "файл прошивки.zip"


def test_checksum_normalization_and_verification(tmp_path):
    target = tmp_path / "file.bin"
    target.write_bytes(b"data")
    digest = sha256_file(target)
    assert len(digest) == 64
    assert normalize_checksum(digest.upper()) == digest
    assert normalize_checksum(f"sha256:{digest}") == digest
    assert verify_checksum(target, digest) is True
    with pytest.raises(IntegrityError):
        verify_checksum(target, "0" * 64)
    with pytest.raises(ValidationError):
        normalize_checksum("not-a-hash")


def test_url_validation():
    assert validate_url("https://example.org/file.zip") == "https://example.org/file.zip"
    with pytest.raises(ValidationError):
        validate_url("javascript:alert(1)")
    with pytest.raises(ValidationError):
        validate_url("ftp://example.org/file")
    with pytest.raises(ValidationError):
        validate_url("")


def test_import_file_validation(tmp_path):
    good = tmp_path / "data.csv"
    good.write_text("a,b\n1,2\n", encoding="utf-8")
    assert validate_import_file(good, {".csv"}).exists()
    with pytest.raises(ImportErrorOS):
        validate_import_file(tmp_path / "missing.csv", {".csv"})
    with pytest.raises(ImportErrorOS):
        validate_import_file(good, {".json"})
    empty = tmp_path / "empty.csv"
    empty.write_text("", encoding="utf-8")
    with pytest.raises(ImportErrorOS):
        validate_import_file(empty, {".csv"})


def test_zip_traversal_blocked(tmp_path):
    archive = tmp_path / "evil.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("../escape.txt", "bad")
    with pytest.raises(SecurityError):
        safe_extract_zip(archive, tmp_path / "out")
    assert not (tmp_path / "escape.txt").exists()


def test_zip_symlink_and_absolute_paths_blocked(tmp_path):
    absolute = tmp_path / "abs.zip"
    with zipfile.ZipFile(absolute, "w") as zf:
        zf.writestr("/etc/passwd", "bad")
    with pytest.raises(SecurityError):
        safe_extract_zip(absolute, tmp_path / "out2")

    symlink = tmp_path / "link.zip"
    with zipfile.ZipFile(symlink, "w") as zf:
        info = zipfile.ZipInfo("link")
        info.external_attr = (0o120777 << 16)
        zf.writestr(info, "/etc/passwd")
    with pytest.raises(SecurityError):
        safe_extract_zip(symlink, tmp_path / "out3")


def test_safe_zip_extraction_ok(tmp_path):
    archive = tmp_path / "ok.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("folder/board.json", "{}")
        zf.writestr("folder/top.jpg", "img")
    files = safe_extract_zip(archive, tmp_path / "out")
    assert {item.name for item in files} == {"board.json", "top.jpg"}
    assert (tmp_path / "out" / "folder" / "board.json").exists()


def test_not_a_zip(tmp_path):
    fake = tmp_path / "fake.zip"
    fake.write_bytes(b"not a zip at all")
    with pytest.raises(ImportErrorOS):
        safe_extract_zip(fake, tmp_path / "out")


def test_path_within():
    base = Path("/tmp/base")
    assert is_within("/tmp/base/sub/file", base)
    assert not is_within("/tmp/base-other/file", base)
    with pytest.raises(SecurityError):
        ensure_within("/tmp/base-other/file", base)


def test_redact_secret():
    assert redact_secret("supersecretvalue").startswith("supe")
    assert "secret" not in redact_secret("supersecretvalue")
    assert redact_secret(None) == ""


def test_secret_store_encrypts(tmp_path):
    from repair_os.core.secrets_store import SecretStore

    store = SecretStore(tmp_path)
    store.set_secret("token", "my-very-secret-token")
    assert store.get_secret("token") == "my-very-secret-token"
    if store.persistent:
        raw = (tmp_path / "secrets.bin").read_bytes()
        assert b"my-very-secret-token" not in raw
    store.delete_secret("token")
    assert store.get_secret("token") is None
