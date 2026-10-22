"""Автоопределение подключённых устройств Apple (iPhone, iPad, MacBook) по USB.

Источники обнаружения (объединяются без дублей):
1. CLI libimobiledevice (`idevice_id`, `ideviceinfo`, `irecovery`) — Normal, Recovery, DFU.
2. Python/CLI `pymobiledevice3` — usbmuxd список устройств.
3. Системная шина USB Windows PnP (`VID_05AC`) — видит физические устройства в DFU (`PID_1227`),
   Recovery (`PID_1281`), Mac DFU (`PID_1901`) и извлекает `CPID`, `BDID`, `ECID` прямо из USB Instance ID,
   даже если внешние утилиты ещё не установлены.
4. Опциональный виртуальный стенд (только с явной меткой `[МАКЕТ]` для Dry-Run).
"""

from __future__ import annotations

import json
import plistlib
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from apple_flash.core.security import resolve_pmb3_command, windows_no_window_kwargs
from apple_flash.data.apple_catalog import (
    SPECS_BY_PRODUCT_TYPE,
    infer_device_family,
    resolve_product_name,
)
from apple_flash.data.models import ConnectedDevice

USB_TAG_RE = re.compile(r"([A-Z]{4}):([0-9A-Fa-f]+)")
VID_PID_RE = re.compile(r"VID_05AC&PID_([0-9A-Fa-f]{4})", re.IGNORECASE)


VIRTUAL_PRESETS: dict[str, ConnectedDevice] = {
    "iphone_normal": ConnectedDevice(
        uid="00008130-001A2B3C4D5E6F01",
        mode="normal",
        product_type="iPhone16,1",
        marketing_name="iPhone 15 Pro",
        family="iphone",
        ecid="0x001A2B3C4D5E6F01",
        udid="00008130-001A2B3C4D5E6F01",
        cpid=0x8130,
        bdid=0x0C,
        board_config="d83ap",
        os_version="18.0.1",
        build_version="22A3370",
        serial_number="DEMO15PROX",
        device_name="iPhone (Тестовый стенд)",
        battery_percent=84,
        usb_driver="usbmuxd (виртуальный)",
        source_backend="virtual",
        is_virtual=True,
    ),
    "ipad_recovery": ConnectedDevice(
        uid="ECID:0x0022446688AACCEE",
        mode="recovery",
        product_type="iPad16,3",
        marketing_name="iPad Pro 11\" (M4, Wi-Fi)",
        family="ipad",
        ecid="0x0022446688AACCEE",
        cpid=0x8132,
        bdid=0x08,
        board_config="j717ap",
        usb_driver="WinUSB (виртуальный)",
        source_backend="virtual",
        is_virtual=True,
    ),
    "macbook_dfu": ConnectedDevice(
        uid="ECID:0x0099887766554433",
        mode="dfu",
        product_type="Mac15,3",
        marketing_name="MacBook Pro 14\" (M3, 2023)",
        family="macbook",
        ecid="0x0099887766554433",
        cpid=0x8122,
        bdid=0x02,
        board_config="j504ap",
        usb_driver="WinUSB (виртуальный DFU)",
        source_backend="virtual",
        is_virtual=True,
    ),
}


def parse_windows_pnp_apple_Output(raw_json: str) -> list[ConnectedDevice]:
    """Разбирает JSON-вывод Win32_PnPEntity для USB-устройств Apple (VID_05AC)."""
    raw_json = (raw_json or "").strip()
    if not raw_json:
        return []
    try:
        parsed = json.loads(raw_json)
    except json.JSONDecodeError:
        return []
    items = parsed if isinstance(parsed, list) else [parsed]
    results: list[ConnectedDevice] = []
    seen_uids: set[str] = set()

    for entry in items:
        if not isinstance(entry, dict):
            continue
        pnp_id = str(entry.get("PNPDeviceID") or "")
        match = VID_PID_RE.search(pnp_id)
        if not match:
            continue
        pid = match.group(1).upper()
        service = str(entry.get("Service") or "").strip() or None

        tags = {k.upper(): v for k, v in USB_TAG_RE.findall(pnp_id)}
        cpid = int(tags["CPID"], 16) if "CPID" in tags else None
        bdid = int(tags["BDID"], 16) if "BDID" in tags else None
        ecid_hex = f"0x{tags['ECID'].upper()}" if "ECID" in tags else None

        if pid == "1227" or pid in {"1901", "1905"}:
            mode = "dfu"
        elif pid == "1281":
            mode = "recovery"
        elif pid == "1222":
            mode = "wtf"
        elif pid.startswith("129") or pid.startswith("12A"):
            mode = "normal"
        else:
            continue

        serial_tail = pnp_id.split("\\")[-1] if "\\" in pnp_id else pnp_id
        uid = f"ECID:{ecid_hex}" if ecid_hex else f"USB:{pid}:{serial_tail[:24]}"
        if uid in seen_uids:
            continue
        seen_uids.add(uid)

        family = infer_device_family(None, cpid)
        if pid in {"1901", "1905"} and family == "unknown":
            family = "macbook"
        name = resolve_product_name(None, cpid)
        if name == "Устройство Apple" and entry.get("Name"):
            name = str(entry["Name"])

        results.append(
            ConnectedDevice(
                uid=uid,
                mode=mode,
                product_type=None,
                marketing_name=name,
                family=family,
                ecid=ecid_hex,
                cpid=cpid,
                bdid=bdid,
                usb_driver=service,
                source_backend="windows_pnp",
            )
        )
    return results


def parse_irecovery_output(text: str) -> ConnectedDevice | None:
    """Разбирает вывод `irecovery -q` для устройств в Recovery / DFU."""
    kv: dict[str, str] = {}
    for line in (text or "").splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            kv[k.strip().upper()] = v.strip()
    if not kv:
        return None
    mode_raw = kv.get("MODE", "").lower()
    mode = "dfu" if "dfu" in mode_raw else ("wtf" if "wtf" in mode_raw else "recovery")
    product_type = kv.get("PRODUCT") or None
    if product_type == "UNKNOWN":
        product_type = None

    def _hex(val: str | None) -> int | None:
        if not val:
            return None
        try:
            return int(val, 16) if val.lower().startswith("0x") else int(val, 16)
        except ValueError:
            return None

    cpid = _hex(kv.get("CPID"))
    bdid = _hex(kv.get("BDID"))
    ecid = kv.get("ECID")
    uid = f"ECID:{ecid}" if ecid else f"IREC:{cpid or 0:04X}"
    family = infer_device_family(product_type, cpid)
    return ConnectedDevice(
        uid=uid,
        mode=mode,
        product_type=product_type,
        marketing_name=resolve_product_name(product_type, cpid),
        family=family,
        ecid=ecid,
        cpid=cpid,
        bdid=bdid,
        board_config=kv.get("MODEL"),
        serial_number=kv.get("SRNM"),
        source_backend="irecovery",
    )


class DeviceDetector:
    """Сканер подключённых устройств Apple."""

    def __init__(self, tools_dir: Path | None = None) -> None:
        self.tools_dir = tools_dir
        self._active_virtual_key: str | None = None

    @property
    def active_virtual_key(self) -> str | None:
        return self._active_virtual_key

    def set_virtual_device(self, preset_key: str | None) -> ConnectedDevice | None:
        if preset_key is None or preset_key not in VIRTUAL_PRESETS:
            self._active_virtual_key = None
            return None
        self._active_virtual_key = preset_key
        return VIRTUAL_PRESETS[preset_key]

    def resolve_binary(self, name: str) -> str | None:
        candidates: list[Path] = []
        exe = f"{name}.exe" if sys.platform == "win32" else name
        if self.tools_dir:
            candidates.append(self.tools_dir / exe)
            candidates.append(self.tools_dir / name)
        found = next((str(p) for p in candidates if p.is_file()), None)
        if found:
            return found
        return shutil.which(name)

    def scan(self) -> list[ConnectedDevice]:
        devices_by_key: dict[str, ConnectedDevice] = {}

        # 1. libimobiledevice Normal Mode (idevice_id + ideviceinfo)
        for dev in self._scan_idevice_normal():
            key = (dev.ecid or dev.udid or dev.uid).lower()
            devices_by_key[key] = dev

        # 2. pymobiledevice3 usbmux list (если установлен и ещё не найдено через ideviceinfo)
        for dev in self._scan_pymobiledevice3():
            key = (dev.ecid or dev.udid or dev.uid).lower()
            if key not in devices_by_key:
                devices_by_key[key] = dev

        # 3. irecovery (Recovery / DFU)
        irec_dev = self._scan_irecovery()
        if irec_dev:
            key = (irec_dev.ecid or irec_dev.uid).lower()
            devices_by_key[key] = irec_dev

        # 4. Нативный Windows PnP (VID_05AC) — дополняет драйвер или находит голый DFU без утилит
        if sys.platform == "win32":
            for pnp_dev in self._scan_windows_pnp():
                key = (pnp_dev.ecid or pnp_dev.uid).lower()
                if key in devices_by_key:
                    if not devices_by_key[key].usb_driver and pnp_dev.usb_driver:
                        devices_by_key[key].usb_driver = pnp_dev.usb_driver
                elif pnp_dev.mode != "normal" or not devices_by_key:
                    devices_by_key[key] = pnp_dev

        # 5. Виртуальный стенд (если включён пользователем)
        if self._active_virtual_key and self._active_virtual_key in VIRTUAL_PRESETS:
            virt = VIRTUAL_PRESETS[self._active_virtual_key]
            devices_by_key[f"virtual:{self._active_virtual_key}"] = virt

        return list(devices_by_key.values())

    def _run_quiet(self, cmd: list[str], timeout: float = 4.0) -> subprocess.CompletedProcess[str] | None:
        try:
            return subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout,
                check=False,
                **windows_no_window_kwargs(),
            )
        except (OSError, subprocess.SubprocessError):
            return None

    def _scan_idevice_normal(self) -> list[ConnectedDevice]:
        idevice_id_bin = self.resolve_binary("idevice_id")
        ideviceinfo_bin = self.resolve_binary("ideviceinfo")
        if not idevice_id_bin or not ideviceinfo_bin:
            return []
        res = self._run_quiet([idevice_id_bin, "-l"])
        if not res or res.returncode != 0:
            return []
        found: list[ConnectedDevice] = []
        for raw_udid in res.stdout.splitlines():
            udid = raw_udid.strip()
            if not udid:
                continue
            info_res = self._run_quiet([ideviceinfo_bin, "-u", udid, "-x"])
            info: dict[str, Any] = {}
            if info_res and info_res.returncode == 0 and info_res.stdout.strip():
                try:
                    info = plistlib.loads(info_res.stdout.encode("utf-8", errors="ignore"))
                except Exception:
                    info = {}
            pt = str(info.get("ProductType") or "").strip() or None
            ecid_raw = info.get("UniqueChipID")
            ecid = f"0x{int(ecid_raw):X}" if isinstance(ecid_raw, int) else None
            spec = SPECS_BY_PRODUCT_TYPE.get(pt or "")
            cpid = spec.cpid if spec else None
            found.append(
                ConnectedDevice(
                    uid=udid,
                    mode="normal",
                    product_type=pt,
                    marketing_name=resolve_product_name(pt, cpid),
                    family=infer_device_family(pt, cpid),
                    ecid=ecid,
                    udid=udid,
                    cpid=cpid,
                    board_config=str(info.get("HardwareModel") or "").strip() or None,
                    os_version=str(info.get("ProductVersion") or "").strip() or None,
                    build_version=str(info.get("BuildVersion") or "").strip() or None,
                    serial_number=str(info.get("SerialNumber") or "").strip() or None,
                    device_name=str(info.get("DeviceName") or "").strip() or None,
                    source_backend="libimobiledevice",
                )
            )
        return found

    def _scan_pymobiledevice3(self) -> list[ConnectedDevice]:
        base = resolve_pmb3_command(self.tools_dir)
        if not base:
            return []
        cmd = [*base, "usbmux", "list", "--no-color"]
        res = self._run_quiet(cmd, timeout=5.0)
        if not res or res.returncode != 0 or not res.stdout.strip():
            return []
        try:
            items = json.loads(res.stdout)
        except json.JSONDecodeError:
            return []
        if not isinstance(items, list):
            return []
        found: list[ConnectedDevice] = []
        for entry in items:
            if not isinstance(entry, dict):
                continue
            if str(entry.get("ConnectionType") or "USB").upper() != "USB":
                continue
            udid = str(entry.get("UniqueDeviceID") or entry.get("Identifier") or "").strip()
            if not udid:
                continue
            pt = str(entry.get("ProductType") or "").strip() or None
            spec = SPECS_BY_PRODUCT_TYPE.get(pt or "")
            cpid = spec.cpid if spec else None
            found.append(
                ConnectedDevice(
                    uid=udid,
                    mode="normal",
                    product_type=pt,
                    marketing_name=resolve_product_name(pt, cpid),
                    family=infer_device_family(pt, cpid),
                    udid=udid,
                    cpid=cpid,
                    os_version=str(entry.get("ProductVersion") or "").strip() or None,
                    build_version=str(entry.get("BuildVersion") or "").strip() or None,
                    device_name=str(entry.get("DeviceName") or "").strip() or None,
                    source_backend="pymobiledevice3",
                )
            )
        return found

    def _scan_irecovery(self) -> ConnectedDevice | None:
        irec = self.resolve_binary("irecovery")
        if not irec:
            return None
        res = self._run_quiet([irec, "-q"])
        if not res or res.returncode != 0:
            return None
        return parse_irecovery_output(res.stdout)

    def _scan_windows_pnp(self) -> list[ConnectedDevice]:
        ps = shutil.which("powershell")
        if not ps:
            return []
        ps_cmd = (
            "Get-CimInstance Win32_PnPEntity | "
            "Where-Object { $_.PNPDeviceID -like '*VID_05AC*' } | "
            "Select-Object Name, PNPDeviceID, Service, Status | ConvertTo-Json -Compress"
        )
        res = self._run_quiet([ps, "-NoProfile", "-NonInteractive", "-Command", ps_cmd], timeout=5.0)
        if not res or res.returncode != 0:
            return []
        return parse_windows_pnp_apple_Output(res.stdout)
