"""Тесты инспектора .ipsw, безопасности архивов и контрольных сумм SHA-256 / SHA-1."""

from __future__ import annotations

import plistlib
import zipfile
from pathlib import Path

import pytest

from apple_flash.core.errors import IpswError, ValidationError
from apple_flash.core.security import compute_hashes, normalize_hash, read_zip_member_safe
from apple_flash.services.ipsw_inspector import IpswInspector, create_demo_ipsw_bundle


def _make_ipsw(
    path: Path,
    manifest: dict,
    *,
    binary_plist: bool = False,
    include_components: bool = True,
) -> Path:
    fmt = plistlib.FMT_BINARY if binary_plist else plistlib.FMT_XML
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("BuildManifest.plist", plistlib.dumps(manifest, fmt=fmt))
        if include_components:
            for ident in manifest.get("BuildIdentities", []):
                for item in ident.get("Manifest", {}).values():
                    rel = item["Info"]["Path"]
                    zf.writestr(rel, b"REAL_TEST_COMPONENT_BYTES")
    return path


def test_compute_hashes_and_normalize(tmp_path: Path) -> None:
    sample = tmp_path / "payload.bin"
    sample.write_bytes(b"AppleFlashStudioTestPayload2026")
    sha256, sha1 = compute_hashes(sample)
    assert len(sha256) == 64
    assert len(sha1) == 40
    assert normalize_hash(sha256.upper()) == sha256
    assert normalize_hash(sha1.upper()) == sha1

    with pytest.raises(ValidationError):
        normalize_hash("not-a-valid-hash")


def test_inspect_binary_plist_ipsw_for_iphone_and_macbook(tmp_path: Path) -> None:
    inspector = IpswInspector()
    mac_ipsw = _make_ipsw(
        tmp_path / "UniversalMac_15.1_24B83_Restore.ipsw",
        {
            "ProductVersion": "15.1",
            "ProductBuildVersion": "24B83",
            "SupportedProductTypes": ["Mac15,3", "Mac16,1"],
            "BuildIdentities": [
                {
                    "ApChipID": "0x8122",
                    "Info": {"DeviceClass": "j504ap", "Variant": "macOS Customer"},
                    "Manifest": {
                        "iBSS": {"Info": {"Path": "Firmware/dfu/iBSS.j504.im4p"}},
                        "SEP": {"Info": {"Path": "Firmware/all_flash/sep.im4p"}},
                    },
                }
            ],
        },
        binary_plist=True,
    )
    info = inspector.inspect(mac_ipsw)
    assert info.family == "macbook"
    assert info.product_version == "15.1"
    assert info.build_version == "24B83"
    assert "Mac15,3" in info.supported_product_types
    assert 0x8122 in info.supported_cpids
    assert info.has_sep is True
    assert info.has_baseband is False
    assert info.missing_components == []
    assert info.is_demo_mockup is False


def test_inspect_detects_missing_components_and_bad_archives(tmp_path: Path) -> None:
    inspector = IpswInspector()
    incomplete = _make_ipsw(
        tmp_path / "Incomplete_Restore.ipsw",
        {
            "ProductVersion": "18.1",
            "ProductBuildVersion": "22B83",
            "SupportedProductTypes": ["iPhone16,1"],
            "BuildIdentities": [
                {
                    "ApChipID": "0x8130",
                    "Info": {"DeviceClass": "d83ap", "Variant": "Customer Erase Install (IPSW)"},
                    "Manifest": {"iBSS": {"Info": {"Path": "Firmware/dfu/missing_ibss.im4p"}}},
                }
            ],
        },
        include_components=False,
    )
    info = inspector.inspect(incomplete)
    assert info.missing_components == ["Firmware/dfu/missing_ibss.im4p"]
    assert info.warnings

    bad_ext = tmp_path / "wrong.zip"
    bad_ext.write_bytes(b"123")
    with pytest.raises(IpswError):
        inspector.inspect(bad_ext)

    corrupt = tmp_path / "corrupt.ipsw"
    corrupt.write_bytes(b"not a zip archive")
    with pytest.raises(IpswError):
        inspector.inspect(corrupt)


def test_zip_path_traversal_blocked(tmp_path: Path) -> None:
    zpath = tmp_path / "test.zip"
    with zipfile.ZipFile(zpath, "w") as zf:
        zf.writestr("safe.txt", b"ok")
        with pytest.raises(IpswError):
            read_zip_member_safe(zf, "../outside.txt")


def test_demo_bundle_creates_three_platforms(tmp_path: Path) -> None:
    inspector = IpswInspector()
    files = create_demo_ipsw_bundle(tmp_path / "demos")
    assert len(files) == 3
    families = {inspector.inspect(p).family for p in files}
    assert families == {"iphone", "ipad", "macbook"}
    assert all(inspector.inspect(p).is_demo_mockup for p in files)
