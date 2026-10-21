"""Тесты репозиториев: устройства, бренды, прошивки, библиотека."""

from __future__ import annotations

import pytest

from repair_os.core.errors import ConflictError, NotFoundError, ValidationError
from repair_os.data.repositories.brands import BrandRepository
from repair_os.data.repositories.devices import DeviceRepository
from repair_os.data.repositories.firmware import FirmwareRepository
from repair_os.data.repositories.library import LibraryRepository
from repair_os.data.repositories.settings import SettingsRepository


@pytest.fixture()
def repos(db):
    return {
        "brands": BrandRepository(db),
        "devices": DeviceRepository(db),
        "firmware": FirmwareRepository(db),
        "library": LibraryRepository(db),
        "settings": SettingsRepository(db),
    }


def _device_payload(brand_id: int, **overrides):
    payload = {
        "brand_id": brand_id,
        "name": "Galaxy Test",
        "model_code": "SM-T0001",
        "codename": "testcodename",
        "hardware_revision": "rev1",
        "soc": "Test SoC",
        "ram": "6 GB",
        "storage": "128 GB",
        "os_versions": "Android 12",
        "release_year": 2021,
    }
    payload.update(overrides)
    return payload


def test_brand_crud_and_conflict(repos):
    brand = repos["brands"].create({"name": "TestBrand"})
    assert brand.slug == "testbrand"
    with pytest.raises(ConflictError):
        repos["brands"].create({"name": "TestBrand"})
    updated = repos["brands"].update(brand.id, {"country": "MD"})
    assert updated.country == "MD"
    repos["brands"].delete(brand.id)
    with pytest.raises(NotFoundError):
        repos["brands"].get(brand.id)


def test_brand_delete_blocked_when_devices_exist(repos):
    brand = repos["brands"].create({"name": "WithDevices"})
    repos["devices"].create(_device_payload(brand.id))
    with pytest.raises(ConflictError):
        repos["brands"].delete(brand.id)


def test_device_validation(repos):
    brand = repos["brands"].create({"name": "B"})
    with pytest.raises(ValidationError):
        repos["devices"].create(_device_payload(brand.id, name=""))
    with pytest.raises(ValidationError):
        repos["devices"].create(_device_payload(brand.id, model_code=""))
    with pytest.raises(ValidationError):
        repos["devices"].create(_device_payload(brand.id, model_code="<>??"))
    with pytest.raises(ValidationError):
        repos["devices"].create(_device_payload(brand.id, release_year="abcd"))


def test_device_duplicate_detection(repos):
    brand = repos["brands"].create({"name": "B"})
    repos["devices"].create(_device_payload(brand.id))
    with pytest.raises(ConflictError):
        repos["devices"].create(_device_payload(brand.id, name="Other name"))


def test_device_search_and_filters(repos):
    samsung = repos["brands"].create({"name": "Samsung"})
    apple = repos["brands"].create({"name": "Apple"})
    repos["devices"].create(_device_payload(samsung.id, name="Galaxy A52", model_code="SM-A525F", codename="a52q"))
    repos["devices"].create(_device_payload(apple.id, name="iPhone 12", model_code="A2402", codename=None))

    by_code = repos["devices"].list(search="SM-A525F")
    assert len(by_code) == 1 and by_code[0].model_code == "SM-A525F"

    by_codename = repos["devices"].list(search="a52q")
    assert len(by_codename) == 1

    by_brand = repos["devices"].list(brand_id=apple.id)
    assert len(by_brand) == 1 and by_brand[0].model_code == "A2402"

    assert repos["devices"].find_by_model_code("a2402").name == "iPhone 12"
    assert repos["devices"].count() == 2


def test_device_update_changes_audit(repos, db):
    brand = repos["brands"].create({"name": "B"})
    device = repos["devices"].create(_device_payload(brand.id))
    repos["devices"].update(device.id, {"soc": "New SoC"})
    history = db.query("SELECT * FROM audit_log WHERE entity='device' AND entity_id=?", (device.id,))
    actions = [row["action"] for row in history]
    assert "create" in actions and "update" in actions


def test_variants_and_favorites(repos):
    brand = repos["brands"].create({"name": "B"})
    device = repos["devices"].create(_device_payload(brand.id))
    variant = repos["devices"].add_variant(
        {
            "device_id": device.id,
            "name": "EU",
            "model_code": "SM-T0001",
            "region": "EUX",
            "csc": "EUX",
        }
    )
    assert repos["devices"].variants(device.id)[0].region == "EUX"
    repos["devices"].update_variant(variant.id, {"bootloader": "BL1"})
    assert repos["devices"].variants(device.id)[0].bootloader == "BL1"

    assert repos["devices"].toggle_favorite(device.id) is True
    assert len(repos["devices"].favorites()) == 1
    assert repos["devices"].toggle_favorite(device.id) is False
    assert repos["devices"].favorites() == []

    repos["devices"].record_open(device.id)
    repos["devices"].record_open(device.id)
    recent = repos["devices"].recent()
    assert recent[0][0].id == device.id and recent[0][2] == 2
    repos["devices"].clear_recent()
    assert repos["devices"].recent() == []


def test_firmware_requires_model_and_source(repos):
    with pytest.raises(ValidationError):
        repos["firmware"].create({"file_name": "x.zip", "download_url": "https://example.org/x"})
    with pytest.raises(ValidationError):
        repos["firmware"].create({"file_name": "x.zip", "model_code": "SM-1"})


def test_firmware_validation_and_filters(repos):
    brand = repos["brands"].create({"name": "Samsung"})
    device = repos["devices"].create(_device_payload(brand.id))
    source = repos["firmware"].create_source({"name": "Official", "kind": "official", "trusted": True})
    record = repos["firmware"].create(
        {
            "device_id": device.id,
            "source_id": source.id,
            "file_name": "SM-T0001_Android12.zip",
            "model_code": "SM-T0001",
            "os_version": "Android 12",
            "build_number": "T0001XXU1",
            "region": "SER",
            "csc": "SER",
            "release_date": "2023-01-10",
            "file_size": 1024,
            "download_url": "https://example.org/fw",
            "checksum_reference": "a" * 64,
        }
    )
    assert record.verification_status == "unverified"
    assert repos["firmware"].list(search="T0001XXU1")[0].id == record.id
    assert repos["firmware"].list(region="SER")
    assert repos["firmware"].list(status="verified") == []

    repos["firmware"].set_verification(record.id, "verified")
    assert repos["firmware"].list(status="verified")[0].id == record.id
    history = repos["firmware"].history(record.id)
    assert any(item["action"] == "update" for item in history)

    with pytest.raises(ValidationError):
        repos["firmware"].create(
            {
                "model_code": "SM-T0001",
                "file_name": "bad.zip",
                "download_url": "https://example.org/bad",
                "checksum_reference": "zzz",
            }
        )


def test_firmware_source_rules(repos):
    source = repos["firmware"].create_source({"name": "Community", "kind": "community"})
    with pytest.raises(ConflictError):
        repos["firmware"].create_source({"name": "Community"})

    brand = repos["brands"].create({"name": "B"})
    device = repos["devices"].create(_device_payload(brand.id))
    repos["firmware"].create(
        {
            "device_id": device.id,
            "source_id": source.id,
            "file_name": "f.zip",
            "model_code": "SM-T0001",
            "download_url": "https://example.org/f",
        }
    )
    with pytest.raises(ConflictError):
        repos["firmware"].delete_source(source.id)


def test_library_documents_and_notes(repos):
    brand = repos["brands"].create({"name": "B"})
    device = repos["devices"].create(_device_payload(brand.id))
    document = repos["library"].create_document(
        {
            "title": "Схема питания",
            "category": "power",
            "doc_type": "schematic",
            "device_id": device.id,
            "verification_status": "verified",
        }
    )
    assert document.verified_at, "дата проверки ставится автоматически"
    assert repos["library"].list_documents(category="power")[0].id == document.id
    assert repos["library"].list_documents(search="питания")

    note = repos["library"].create_note(
        {"title": "Заметка", "device_id": device.id, "body": "текст", "category": "power"}
    )
    repos["library"].update_note(note.id, {"body": "новый текст"})
    assert repos["library"].notes(device_id=device.id)[0].body == "новый текст"
    repos["library"].delete_note(note.id)
    assert repos["library"].notes() == []

    with pytest.raises(ValidationError):
        repos["library"].create_document({"title": "x", "category": "неизвестно"})
    with pytest.raises(ValidationError):
        repos["library"].create_document({"title": "x", "source_url": "file:///etc/passwd"})


def test_settings_defaults_and_persistence(repos, db):
    settings = repos["settings"]
    assert settings.get("language") == "ru"
    settings.set("language", "en")
    assert settings.get("language") == "en"
    assert SettingsRepository(db).get("language") == "en"
    settings.set("backup_keep_count", 3)
    assert settings.get_int("backup_keep_count") == 3
    settings.reset()
    assert settings.get("language") == "ru"
