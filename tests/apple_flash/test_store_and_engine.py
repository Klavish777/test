"""Тесты SQLite-хранилища StudioStore и движка перепрошивки FlashEngine (Dry-Run и боевой CLI)."""

from __future__ import annotations

import plistlib
import stat
import sys
import zipfile
from pathlib import Path

import pytest

from apple_flash.core.errors import FlashExecutionError
from apple_flash.data.models import ConnectedDevice, FlashJobConfig
from apple_flash.services.context import StudioContext


def _create_production_like_ipsw(path: Path) -> Path:
    manifest = {
        "ProductVersion": "18.1",
        "ProductBuildVersion": "22B83",
        "SupportedProductTypes": ["iPhone16,1"],
        "BuildIdentities": [
            {
                "ApChipID": "0x8130",
                "Info": {"DeviceClass": "d83ap", "Variant": "Customer Erase Install (IPSW)"},
                "Manifest": {"iBSS": {"Info": {"Path": "Firmware/dfu/iBSS.im4p"}}},
            },
            {
                "ApChipID": "0x8130",
                "Info": {"DeviceClass": "d83ap", "Variant": "Customer Upgrade Install (IPSW)"},
                "Manifest": {"iBSS": {"Info": {"Path": "Firmware/dfu/iBSS.im4p"}}},
            },
        ],
    }
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("BuildManifest.plist", plistlib.dumps(manifest))
        zf.writestr("Firmware/dfu/iBSS.im4p", b"TEST_IBSS_PAYLOAD")
    return path


def test_store_lifecycle_and_hash_verification(tmp_path: Path) -> None:
    ctx = StudioContext.create(tmp_path / "data", seed_demo=True)
    try:
        assert ctx.store.integrity_ok() is True
        items = ctx.store.list_ipsw()
        assert len(items) == 3
        assert all(i.verified_state == "verified" for i in items)

        # Проверка фиксации несовпадения эталонного хэша
        first = items[0]
        assert first.id is not None
        bad = ctx.store.update_ipsw_hashes(
            first.id,
            sha256=first.sha256 or ("a" * 64),
            sha1=first.sha1 or ("b" * 40),
            expected_hash="0" * 64,
        )
        assert bad.verified_state == "mismatch"

        removed = ctx.remove_demo_mockups()
        assert removed == 3
        assert ctx.store.list_ipsw() == []
    finally:
        ctx.close()


def test_flash_engine_commands_and_safety_guards(tmp_path: Path) -> None:
    ctx = StudioContext.create(tmp_path / "data", seed_demo=True)
    try:
        demos = ctx.store.list_ipsw(family="macbook")
        assert len(demos) == 1
        mac_ipsw = Path(demos[0].local_path)
        virt_mac = ctx.detector.set_virtual_device("macbook_dfu")
        assert virt_mac is not None

        # 1. Dry-Run проходит штатно и пишет запись в журнал
        job_dry = FlashJobConfig(
            action="revive_mac",
            device=virt_mac,
            ipsw_path=mac_ipsw,
            backend="idevicerestore",
            dry_run=True,
        )
        backend, cmd = ctx.flash_engine.build_command(job_dry)
        assert backend == "idevicerestore"
        assert "-e" not in cmd

        stages: list[int] = []
        session = ctx.flash_engine.execute(
            job_dry,
            progress_cb=lambda pct, _s: stages.append(pct),
            dry_run_step_delay=0.0,
        )
        assert session.status == "success"
        assert session.dry_run is True
        assert stages[-1] == 100
        assert len(ctx.store.list_sessions()) == 1

        # 2. Защита: виртуальный макет НЕЛЬЗЯ прошить в боевом режиме (dry_run=False)
        job_unsafe = FlashJobConfig(
            action="erase",
            device=virt_mac,
            ipsw_path=mac_ipsw,
            backend="pymobiledevice3",
            dry_run=False,
        )
        with pytest.raises(FlashExecutionError):
            ctx.flash_engine.execute(job_unsafe, dry_run_step_delay=0.0)
    finally:
        ctx.close()


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX shell wrapper test")
def test_flash_engine_real_subprocess_stage_streaming(tmp_path: Path) -> None:
    ctx = StudioContext.create(tmp_path / "data", seed_demo=False)
    try:
        # Создаём имитатор утилиты idevicerestore в tools_dir для проверки потокового парсера
        fake_idr = ctx.paths.tools_dir / "idevicerestore"
        fake_idr.write_text(
            f"#!{sys.executable}\n"
            "import sys\n"
            "print('Extracting BuildManifest from IPSW', flush=True)\n"
            "print('Sending iBSS...', flush=True)\n"
            "print('Sending filesystem now...', flush=True)\n"
            "print('Done: restoring succeeded!', flush=True)\n"
            "sys.exit(0)\n",
            encoding="utf-8",
        )
        fake_idr.chmod(fake_idr.stat().st_mode | stat.S_IEXEC)

        real_ipsw = _create_production_like_ipsw(tmp_path / "iPhone16,1_18.1_22B83_Restore.ipsw")
        real_dev = ConnectedDevice(
            uid="00008130-REALDEVICE",
            mode="recovery",
            product_type="iPhone16,1",
            marketing_name="iPhone 15 Pro",
            family="iphone",
            ecid="0x11223344",
            cpid=0x8130,
            is_virtual=False,
        )
        progress_seen: list[int] = []
        session = ctx.flash_engine.execute(
            FlashJobConfig(
                action="erase",
                device=real_dev,
                ipsw_path=real_ipsw,
                backend="idevicerestore",
                dry_run=False,
            ),
            progress_cb=lambda pct, _st: progress_seen.append(pct),
        )
        assert session.status == "success"
        assert session.exit_code == 0
        assert "-e" in session.command_line
        assert 26 in progress_seen
        assert 100 in progress_seen
    finally:
        ctx.close()
