"""Тесты сервисов: поиск, импорт/экспорт, прошивки, резервные копии."""

from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest

from repair_os.core.errors import ImportErrorOS, IntegrityError, ValidationError
from repair_os.services.backup import BackupService
from repair_os.services.firmware_tools import FirmwareTools
from repair_os.services.import_export import ImportService, read_rows, write_template


# --------------------------------------------------------------------------- поиск
def test_global_search_finds_all_kinds(context):
    results = context.search.search("SM-G991B")
    kinds = {hit.kind for hit in results}
    assert "device" in kinds
    assert any(hit.title.startswith("Samsung") for hit in results)
    firmware_hits = context.search.search("DEMO_")
    assert any(hit.kind == "firmware" for hit in firmware_hits)
    assert context.search.search("") == []
    assert context.search.suggest("Gal")


# --------------------------------------------------------------------------- импорт
def test_import_devices_csv_dry_run_and_apply(context, tmp_path):
    csv_path = tmp_path / "devices.csv"
    csv_path.write_text(
        "Бренд;Название;Код модели;Кодовое имя;Ревизия;Процессор;ОЗУ;Память;Версии ОС;Год;Проверено\n"
        "Samsung;Galaxy A99;SM-A999F;a99q;rev1;Exynos 999;8 GB;256 GB;Android 14;2024;1\n"
        "НовыйБренд;Test Phone;TEST-1;testcodename;;;4 GB;64 GB;Android 13;2023;0\n"
        "Samsung;;SM-EMPTY;;;;;;;\n",
        encoding="utf-8",
    )
    dry = context.imports.import_devices(csv_path, dry_run=True)
    assert dry.dry_run
    assert dry.total == 3
    assert dry.created == 2
    assert len(dry.errors) == 1, dry.summary()
    assert context.devices.find_by_model_code("SM-A999F") is None

    applied = context.imports.import_devices(csv_path, dry_run=False)
    assert applied.created == 2
    device = context.devices.find_by_model_code("SM-A999F")
    assert device and device.soc == "Exynos 999" and device.verified == 1
    assert context.brands.find_by_slug("новыйбренд") is not None or any(
        brand.name == "НовыйБренд" for brand in context.brands.list()
    )


def test_import_devices_updates_existing(context, tmp_path):
    csv_path = tmp_path / "update.csv"
    csv_path.write_text(
        "brand,name,model_code,soc\nSamsung,Galaxy S21 5G,SM-G991B,Updated SoC\n",
        encoding="utf-8",
    )
    report = context.imports.import_devices(csv_path, dry_run=False)
    assert report.updated == 1 and report.created == 0
    device = context.devices.find_by_model_code("SM-G991B")
    assert device.soc == "Updated SoC"


def test_import_firmware_requires_known_device(context, tmp_path):
    payload = [
        {
            "file_name": "unknown.zip",
            "model_code": "UNKNOWN-1",
            "download_url": "https://example.org/x",
        }
    ]
    path = tmp_path / "fw.json"
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    report = context.imports.import_firmware(path, dry_run=True)
    assert report.skipped == 1
    assert "не найдена" in report.errors[0].message

    payload[0]["model_code"] = "SM-G991B"
    payload[0]["build_number"] = "G991BXXU9TEST"
    payload[0]["release_date"] = "2023-05-05"
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    report = context.imports.import_firmware(path, dry_run=False)
    assert report.created == 1
    records = context.firmware.list(search="G991BXXU9TEST")
    assert records and records[0].model_code == "SM-G991B"


def test_import_documents(context, tmp_path):
    csv_path = tmp_path / "docs.csv"
    csv_path.write_text(
        "Название;Категория;Тип;Код модели;Ссылка\n"
        "Тестовая схема;power;schematic;SM-A525F;https://example.org/s\n",
        encoding="utf-8",
    )
    report = context.imports.import_documents(csv_path, dry_run=False)
    assert report.created == 1
    document = context.library.list_documents(search="Тестовая")[0]
    assert document.device_id is not None


def test_read_rows_rejects_bad_json(tmp_path):
    path = tmp_path / "bad.json"
    path.write_text("{ not json", encoding="utf-8")
    with pytest.raises(ImportErrorOS):
        read_rows(path, kind="devices")
    path.write_text('{"items": [{"a": 1}]}', encoding="utf-8")
    rows = read_rows(path, kind="devices")
    assert rows == [{"a": 1}]


def test_write_template(tmp_path):
    target = write_template("firmware", tmp_path)
    assert target.exists()
    assert "Код модели" in target.read_text(encoding="utf-8-sig")
    with pytest.raises(Exception):
        write_template("unknown", tmp_path)


# --------------------------------------------------------------------------- прошивки
def _make_firmware(context, tmp_path, **overrides):
    device = context.devices.find_by_model_code("SM-G991B")
    payload = {
        "device_id": device.id,
        "file_name": "test_firmware.zip",
        "model_code": "SM-G991B",
        "download_url": "https://example.org/fw",
        "verification_status": "unverified",
    }
    payload.update(overrides)
    return context.firmware.create(payload)


def test_firmware_tools_inspect_and_reject(context, tmp_path):
    tools = context.firmware_tools
    archive = tmp_path / "fw.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("boot.img", "data")
    check = tools.inspect_file(archive)
    assert check.is_zip and check.zip_ok and check.zip_entries == 1

    broken = tmp_path / "broken.zip"
    broken.write_bytes(b"PK\x03\x04broken")
    with pytest.raises(ImportErrorOS):
        tools.inspect_file(tmp_path / "missing.zip")
    empty = tmp_path / "empty.zip"
    empty.write_bytes(b"")
    with pytest.raises(ImportErrorOS):
        tools.inspect_file(empty)
    with pytest.raises(ImportErrorOS):
        tools.inspect_file(tmp_path / "script.exe") if (tmp_path / "script.exe").write_text("x") else None


def test_attach_file_verifies_checksum(context, tmp_path):
    import hashlib

    payload = b"firmware-bytes"
    source = tmp_path / "SM-G991B_test.zip"
    with zipfile.ZipFile(source, "w") as zf:
        zf.writestr("data.bin", payload)
    digest = hashlib.sha256(source.read_bytes()).hexdigest()

    record = _make_firmware(context, tmp_path, checksum_reference=digest)
    updated = context.firmware_tools.attach_local_file(record.id, source)
    assert updated.file_size > 0
    assert Path(updated.local_path).exists()

    bad = _make_firmware(
        context, tmp_path, file_name="bad.zip", checksum_reference="0" * 64
    )
    with pytest.raises(IntegrityError):
        context.firmware_tools.attach_local_file(bad.id, source)


def test_compatibility_check(context):
    device = context.devices.find_by_model_code("SM-G991B")
    good = _make_firmware(context, None)
    result = context.firmware_tools.check_compatibility(good.id)
    assert result.level in {"ok", "warning"}
    assert result.messages, "проверка должна возвращать хотя бы одно пояснение"

    mismatched = context.firmware.create(
        {
            "device_id": device.id,
            "file_name": "wrong_model.zip",
            "model_code": "SM-A525F",
            "download_url": "https://example.org/x",
        }
    )
    result = context.firmware_tools.check_compatibility(mismatched.id)
    assert result.level == "incompatible"
    assert result.is_blocking


def test_verify_reference_requires_reference(context, tmp_path):
    record = _make_firmware(context, tmp_path)
    with pytest.raises(ValidationError):
        context.firmware_tools.verify_reference(record.id)


# --------------------------------------------------------------------------- резервные копии
def test_backup_create_list_and_restore(context):
    info = context.backup.create_backup(note="unit-test")
    assert info.path.exists()
    assert info.schema_version == context.db.schema_version()
    assert context.backup.list_backups()

    before = context.devices.count()
    context.devices.create(
        {
            "brand_id": context.brands.find_by_slug("samsung").id,
            "name": "Temporary",
            "model_code": "SM-TEMP-1",
        }
    )
    assert context.devices.count() == before + 1

    report = context.backup.restore_backup(info.path)
    assert report.total_rows > 0
    assert context.devices.count() == before
    assert context.db.integrity_check()


def test_backup_rejects_corrupted_archive(context, tmp_path):
    broken = tmp_path / "broken.zip"
    broken.write_bytes(b"not a zip")
    from repair_os.core.errors import BackupError

    with pytest.raises(BackupError):
        context.backup.restore_backup(broken)


def test_backup_prune(context):
    for _ in range(3):
        context.backup.create_backup(include_attachments=False, keep=0)
    backups = context.backup.list_backups()
    assert len(backups) >= 3
    context.backup.prune(1)
    assert len(context.backup.list_backups()) == 1


def test_backup_detects_tampered_db(context, tmp_path):
    from repair_os.core.errors import BackupError

    info = context.backup.create_backup(include_attachments=False)
    tampered = tmp_path / "tampered.zip"
    with zipfile.ZipFile(info.path) as src, zipfile.ZipFile(tampered, "w") as dst:
        for item in src.infolist():
            data = src.read(item.filename)
            if item.filename == "repair_os.sqlite3":
                data = data[:-64] + b"0" * 64
            dst.writestr(item, data)
    with pytest.raises(BackupError):
        context.backup.restore_backup(tampered)


def test_export_json(context, tmp_path):
    target = context.backup.export_json(tmp_path / "export.json")
    payload = json.loads(target.read_text(encoding="utf-8"))
    assert payload["format"] == "smartphone-repair-os-export"
    assert payload["data"]["devices"]


def test_backup_service_standalone(tmp_path):
    from repair_os.data.database import open_database

    db = open_database(tmp_path / "db.sqlite3")
    service = BackupService(db, tmp_path / "backups")
    info = service.create_backup(include_attachments=False)
    assert service.inspect(info.path) is not None
    db.close()
