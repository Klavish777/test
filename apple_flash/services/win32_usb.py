"""Мгновенное нативное обнаружение USB-устройств Apple на Windows через Win32 SetupAPI (ctypes) и реестр AMDS."""

from __future__ import annotations

import ctypes
import logging
import re
import socket
import sys
from dataclasses import dataclass
from typing import Any

log = logging.getLogger("apple_flash.win32_usb")

APPLE_VID = 0x05AC

# Диапазоны USB Product ID мобильных устройств и контроллеров прошивки Apple
DFU_PIDS = {0x1227}
WTF_PIDS = {0x1222}
RECOVERY_PIDS = {0x1280, 0x1281, 0x1282, 0x1283}
RESTORE_PIDS = {0x1901, 0x1902, 0x1903, 0x1904, 0x1905}

_PID_RE = re.compile(r"VID_05AC&PID_([0-9A-F]{4})", re.IGNORECASE)
_KV_TAG_RE = re.compile(r"([A-Z]{4}):([0-9A-F]+)", re.IGNORECASE)
_HEX24_RE = re.compile(r"^[0-9A-F]{24}$", re.IGNORECASE)
_HEX40_RE = re.compile(r"^[0-9A-F]{40}$", re.IGNORECASE)


def classify_apple_pid(pid: int) -> str | None:
    """Определяет режим устройства Apple по его USB PID (возвращает None для клавиатур/мышей/аксессуаров)."""
    if pid in DFU_PIDS:
        return "dfu"
    if pid in WTF_PIDS:
        return "wtf"
    if pid in RECOVERY_PIDS:
        return "recovery"
    if pid in RESTORE_PIDS:
        return "restore"
    if 0x1290 <= pid <= 0x12BF:
        return "normal"
    return None


def parse_usb_serial_segment(serial_seg: str) -> dict[str, Any]:
    """Разбирает хвост USB Instance ID Apple (24-hex UDID, 40-hex UDID или строку CPID/BDID/ECID)."""
    cleaned = serial_seg.strip()
    out: dict[str, Any] = {
        "udid": None,
        "ecid": None,
        "cpid": None,
        "bdid": None,
        "serial_number": None,
    }
    if not cleaned or "&" in cleaned:
        # Автосгенерированный Windows ID интерфейса (например 6&2A3B4C5D&0&1)
        return out

    tags = {k.upper(): v for k, v in _KV_TAG_RE.findall(cleaned)}
    if tags:
        if "CPID" in tags:
            try:
                out["cpid"] = int(tags["CPID"], 16)
            except ValueError:
                pass
        if "BDID" in tags:
            try:
                out["bdid"] = int(tags["BDID"], 16)
            except ValueError:
                pass
        if "ECID" in tags:
            try:
                out["ecid"] = f"0x{int(tags['ECID'], 16):X}"
            except ValueError:
                out["ecid"] = tags["ECID"]
        if "SRNM" in tags:
            out["serial_number"] = tags["SRNM"]
        return out

    if _HEX24_RE.match(cleaned):
        # Современный формат Apple USB Serial (A12+/M1+): 8 hex чип + 16 hex ECID
        chip_hex = cleaned[:8].upper()
        ecid_hex = cleaned[8:].upper()
        out["udid"] = f"{chip_hex}-{ecid_hex}"
        try:
            cpid_val = int(chip_hex, 16)
            if cpid_val > 0:
                out["cpid"] = cpid_val
        except ValueError:
            pass
        try:
            ecid_val = int(ecid_hex, 16)
            if ecid_val > 0:
                out["ecid"] = f"0x{ecid_val:X}"
        except ValueError:
            pass
        return out

    if _HEX40_RE.match(cleaned):
        out["udid"] = cleaned.lower()
        return out

    if len(cleaned) >= 8:
        out["udid"] = cleaned
    return out


@dataclass
class AppleUsbWin32Entry:
    instance_id: str
    pid: int
    mode: str
    is_interface: bool
    service: str
    description: str
    udid: str | None = None
    ecid: str | None = None
    cpid: int | None = None
    bdid: int | None = None
    serial_number: str | None = None


def parse_instance_entry(
    instance_id: str,
    service: str = "",
    description: str = "",
) -> AppleUsbWin32Entry | None:
    """Преобразует строку USB Instance ID Windows в структурированную запись (только целевые PID Apple)."""
    m = _PID_RE.search(instance_id)
    if not m:
        return None
    pid = int(m.group(1), 16)
    mode = classify_apple_pid(pid)
    if mode is None:
        return None

    upper_id = instance_id.upper()
    is_iface = "&MI_" in upper_id
    parts = instance_id.split("\\")
    serial_seg = parts[2] if len(parts) >= 3 else ""
    parsed = parse_usb_serial_segment(serial_seg)

    return AppleUsbWin32Entry(
        instance_id=instance_id,
        pid=pid,
        mode=mode,
        is_interface=is_iface,
        service=service.strip(),
        description=description.strip() or f"Apple USB (05AC:{pid:04X})",
        udid=parsed["udid"],
        ecid=parsed["ecid"],
        cpid=parsed["cpid"],
        bdid=parsed["bdid"],
        serial_number=parsed["serial_number"],
    )


def enumerate_apple_usb_win32() -> list[AppleUsbWin32Entry]:
    """Опрашивает ядро Windows через SetupDiGetClassDevsW (< 2 мс, без PowerShell и без мигания консолей)."""
    if sys.platform != "win32":
        return []

    from ctypes import wintypes

    DIGCF_PRESENT = 0x00000002
    DIGCF_ALLCLASSES = 0x00000004
    SPDRP_DEVICEDESC = 0x00000000
    SPDRP_SERVICE = 0x00000004
    SPDRP_FRIENDLYNAME = 0x0000000C

    class GUID(ctypes.Structure):
        _fields_ = [
            ("Data1", wintypes.DWORD),
            ("Data2", wintypes.WORD),
            ("Data3", wintypes.WORD),
            ("Data4", ctypes.c_ubyte * 8),
        ]

    pack_align = 1 if ctypes.sizeof(ctypes.c_void_p) == 4 else 8

    class SP_DEVINFO_DATA(ctypes.Structure):
        _pack_ = pack_align
        _fields_ = [
            ("cbSize", wintypes.DWORD),
            ("ClassGuid", GUID),
            ("DevInst", wintypes.DWORD),
            ("Reserved", ctypes.c_void_p),
        ]

    setupapi = ctypes.windll.setupapi  # type: ignore[attr-defined]

    SetupDiGetClassDevsW = setupapi.SetupDiGetClassDevsW
    SetupDiGetClassDevsW.argtypes = [
        ctypes.POINTER(GUID),
        wintypes.LPCWSTR,
        wintypes.HWND,
        wintypes.DWORD,
    ]
    SetupDiGetClassDevsW.restype = ctypes.c_void_p

    SetupDiEnumDeviceInfo = setupapi.SetupDiEnumDeviceInfo
    SetupDiEnumDeviceInfo.argtypes = [
        ctypes.c_void_p,
        wintypes.DWORD,
        ctypes.POINTER(SP_DEVINFO_DATA),
    ]
    SetupDiEnumDeviceInfo.restype = wintypes.BOOL

    SetupDiGetDeviceInstanceIdW = setupapi.SetupDiGetDeviceInstanceIdW
    SetupDiGetDeviceInstanceIdW.argtypes = [
        ctypes.c_void_p,
        ctypes.POINTER(SP_DEVINFO_DATA),
        wintypes.LPWSTR,
        wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD),
    ]
    SetupDiGetDeviceInstanceIdW.restype = wintypes.BOOL

    SetupDiGetDeviceRegistryPropertyW = setupapi.SetupDiGetDeviceRegistryPropertyW
    SetupDiGetDeviceRegistryPropertyW.argtypes = [
        ctypes.c_void_p,
        ctypes.POINTER(SP_DEVINFO_DATA),
        wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD),
        ctypes.POINTER(ctypes.c_ubyte),
        wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD),
    ]
    SetupDiGetDeviceRegistryPropertyW.restype = wintypes.BOOL

    SetupDiDestroyDeviceInfoList = setupapi.SetupDiDestroyDeviceInfoList
    SetupDiDestroyDeviceInfoList.argtypes = [ctypes.c_void_p]
    SetupDiDestroyDeviceInfoList.restype = wintypes.BOOL

    invalid_handle = ctypes.c_void_p(-1).value
    h_dev_info = SetupDiGetClassDevsW(
        None,
        "USB",
        None,
        DIGCF_PRESENT | DIGCF_ALLCLASSES,
    )
    if not h_dev_info or h_dev_info == invalid_handle:
        return []

    def _read_reg_str(dev_data: SP_DEVINFO_DATA, prop_id: int) -> str:
        reg_type = wintypes.DWORD(0)
        req_bytes = wintypes.DWORD(0)
        buf = (ctypes.c_ubyte * 1024)()
        ok = SetupDiGetDeviceRegistryPropertyW(
            h_dev_info,
            ctypes.byref(dev_data),
            prop_id,
            ctypes.byref(reg_type),
            buf,
            ctypes.sizeof(buf),
            ctypes.byref(req_bytes),
        )
        if not ok or req_bytes.value == 0:
            return ""
        raw = bytes(buf[: req_bytes.value])
        return raw.decode("utf-16-le", errors="ignore").rstrip("\x00").strip()

    raw_entries: list[AppleUsbWin32Entry] = []
    try:
        idx = 0
        id_buf = ctypes.create_unicode_buffer(512)
        req_chars = wintypes.DWORD(0)
        while True:
            dev_info = SP_DEVINFO_DATA()
            dev_info.cbSize = ctypes.sizeof(SP_DEVINFO_DATA)
            if not SetupDiEnumDeviceInfo(h_dev_info, idx, ctypes.byref(dev_info)):
                break
            idx += 1

            if not SetupDiGetDeviceInstanceIdW(
                h_dev_info,
                ctypes.byref(dev_info),
                id_buf,
                len(id_buf),
                ctypes.byref(req_chars),
            ):
                continue

            inst_id = id_buf.value
            if "VID_05AC" not in inst_id.upper():
                continue

            service = _read_reg_str(dev_info, SPDRP_SERVICE)
            friendly = _read_reg_str(dev_info, SPDRP_FRIENDLYNAME)
            desc = friendly or _read_reg_str(dev_info, SPDRP_DEVICEDESC)
            entry = parse_instance_entry(inst_id, service=service, description=desc)
            if entry is not None:
                raw_entries.append(entry)
    finally:
        SetupDiDestroyDeviceInfoList(h_dev_info)

    return consolidate_win32_entries(raw_entries)


def consolidate_win32_entries(entries: list[AppleUsbWin32Entry]) -> list[AppleUsbWin32Entry]:
    """Объединяет составные интерфейсы usbccgp (&MI_00, &MI_01) с корневым устройством Apple USB."""
    roots = [e for e in entries if not e.is_interface]
    ifaces = [e for e in entries if e.is_interface]

    if not roots and ifaces:
        # На редких конфигурациях драйвер висит только на дочернем интерфейсе
        by_pid: dict[int, AppleUsbWin32Entry] = {}
        for iface in ifaces:
            if iface.pid not in by_pid:
                by_pid[iface.pid] = iface
        return list(by_pid.values())

    for root in roots:
        if root.service.lower() in {"", "usbccgp"}:
            # Ищем реальный функциональный драйвер (USBAAPL64 / WinUSB / libusbK) среди интерфейсов того же PID
            child_services = [
                c.service
                for c in ifaces
                if c.pid == root.pid and c.service and c.service.lower() not in {"usbccgp", "wudfrd"}
            ]
            if child_services:
                # Приоритет USBAAPL64 / WinUSB / libusbK над прочими (например PTP/MTP)
                preferred = next(
                    (
                        s
                        for s in child_services
                        if any(k in s.lower() for k in ("usbaapl", "winusb", "libusb"))
                    ),
                    child_services[0],
                )
                root.service = preferred
    return roots


def check_usbmux_tcp_port(host: str = "127.0.0.1", port: int = 27015, timeout: float = 0.25) -> bool:
    """Проверяет, слушает ли служба Apple Mobile Device Service (usbmuxd) TCP-порт 27015 на Windows."""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def probe_amds_windows() -> tuple[bool, bool, str]:
    """Возвращает (установлена_ли_служба, слушает_ли_порт_27015, описание_источника)."""
    port_open = check_usbmux_tcp_port()
    if sys.platform != "win32":
        return False, port_open, "Не Windows"

    image_path = ""
    try:
        import winreg

        for svc_name in ("Apple Mobile Device Service", "AppleMobileDeviceService"):
            try:
                with winreg.OpenKey(  # type: ignore[attr-defined]
                    winreg.HKEY_LOCAL_MACHINE,  # type: ignore[attr-defined]
                    rf"SYSTEM\CurrentControlSet\Services\{svc_name}",
                ) as key:
                    val, _ = winreg.QueryValueEx(key, "ImagePath")  # type: ignore[attr-defined]
                    image_path = str(val or "")
                    if image_path:
                        break
            except OSError:
                continue
    except Exception:
        pass

    if not image_path and not port_open:
        return (
            False,
            False,
            "Служба Apple Mobile Device Service не установлена (нужна программа «Устройства Apple» из Microsoft Store или iTunes).",
        )

    source = (
        "Устройства Apple (Microsoft Store)"
        if "windowsapps" in image_path.lower()
        else "Apple Mobile Device Service (iTunes / Apple USB)"
    )
    if port_open:
        return True, True, f"{source} — служба запущена (порт 27015 активен)"
    return True, False, f"{source} установлена, но сейчас остановлена (порт 27015 закрыт)"
