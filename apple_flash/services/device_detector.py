"""Трёхуровневое обнаружение реальных устройств Apple по USB (usbmuxd + libusb IRecv + нативный Win32 SetupAPI)."""

from __future__ import annotations

import asyncio
import logging
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from apple_flash.core.security import windows_no_window_kwargs
from apple_flash.core.usb_runtime import initialize_runtime
from apple_flash.data.apple_catalog import (
    infer_device_family,
    lookup_hardware_by_cpid_bdid,
    resolve_product_name,
)
from apple_flash.data.models import ConnectedDevice
from apple_flash.services.win32_usb import (
    AppleUsbWin32Entry,
    classify_apple_pid,
    enumerate_apple_usb_win32,
    probe_amds_windows,
)

log = logging.getLogger("apple_flash.detector")

LOCKDOWN_PORT = 62078


def _norm_hex_ecid(val: int | str | None) -> str | None:
    if val is None:
        return None
    if isinstance(val, int):
        return f"0x{val:X}" if val > 0 else None
    text = str(val).strip()
    if not text:
        return None
    try:
        parsed = int(text, 16) if text.lower().startswith("0x") else int(text)
        return f"0x{parsed:X}"
    except ValueError:
        try:
            return f"0x{int(text, 16):X}"
        except ValueError:
            return text


class DeviceDetector:
    """Обнаруживает подключённые iPhone, iPad и MacBook в режимах Normal, Recovery и DFU."""

    def __init__(self, tools_dir: Path | None = None) -> None:
        self.tools_dir = tools_dir
        self._test_virtual_preset: str | None = None
        initialize_runtime()

    def set_virtual_device(self, preset_key: str | None) -> ConnectedDevice | None:
        """Используется только в автотестах для имитации подключённого профиля."""
        self._test_virtual_preset = preset_key
        if not preset_key or preset_key == "none":
            self._test_virtual_preset = None
            return None
        mapping = {
            "iphone_normal": 0,
            "ipad_recovery": 1,
            "macbook_dfu": 2,
        }
        vlist = self.virtual_devices()
        idx = mapping.get(preset_key)
        return vlist[idx] if idx is not None and idx < len(vlist) else None

    def scan_devices(self, *, include_virtual: bool = False) -> list[ConnectedDevice]:
        initialize_runtime()
        devices: list[ConnectedDevice] = []
        seen_ecids: set[str] = set()
        seen_udids: set[str] = set()

        def _register(dev: ConnectedDevice) -> None:
            norm_ecid = _norm_hex_ecid(dev.ecid)
            if norm_ecid:
                dev.ecid = norm_ecid
            norm_udid = dev.udid.lower() if dev.udid else None
            if norm_ecid and norm_ecid in seen_ecids:
                return
            if norm_udid and norm_udid in seen_udids:
                return
            if norm_ecid:
                seen_ecids.add(norm_ecid)
            if norm_udid:
                seen_udids.add(norm_udid)
            devices.append(dev)

        # Предварительно снимаем мгновенный снимок ядра Win32 USB (< 2 мс на Windows),
        # чтобы обогатить устройства именем драйвера Windows и поймать устройства без драйвера.
        win32_entries = enumerate_apple_usb_win32() if sys.platform == "win32" else []

        # Уровень 1: Встроенный pymobiledevice3 (usbmux + pre-session lockdownd без запроса «Доверять»)
        for dev in self._scan_usbmux_native(win32_entries):
            _register(dev)

        # Резерв Уровня 1: внешние утилиты libimobiledevice (если установлены и usbmux ещё не дал устройство)
        if not devices:
            for dev in self._scan_libimobiledevice():
                _register(dev)

        # Уровень 2: Встроенный pymobiledevice3 IRecv через libusb-1.0 (режимы Recovery / DFU / WTF)
        for dev in self._scan_irecv_libusb(win32_entries):
            _register(dev)

        # Уровень 3: Нативный Win32 SetupAPI — находит физически подключённые по USB iPhone/iPad/MacBook,
        # даже если в Windows не установлен Apple Mobile Device Service или драйвер USBAAPL64 блокирует DFU.
        for dev in self._scan_win32_unmatched(win32_entries, seen_ecids, seen_udids):
            _register(dev)

        if include_virtual:
            devices.extend(self.virtual_devices())

        return devices

    # ---------------- Уровень 1: Нативный usbmux + lockdownd (pymobiledevice3) ----------------
    def _scan_usbmux_native(
        self, win32_entries: list[AppleUsbWin32Entry]
    ) -> list[ConnectedDevice]:
        try:
            return asyncio.run(self._async_scan_usbmux(win32_entries))
        except Exception as exc:
            log.debug("Опрос usbmux не дал ответа: %s", exc)
            return []

    async def _async_scan_usbmux(
        self, win32_entries: list[AppleUsbWin32Entry]
    ) -> list[ConnectedDevice]:
        from pymobiledevice3 import usbmux
        from pymobiledevice3.service_connection import ServiceConnection

        mux_devices = await asyncio.wait_for(usbmux.list_devices(), timeout=1.8)
        found: list[ConnectedDevice] = []

        for mux_dev in mux_devices:
            if not getattr(mux_dev, "is_usb", True):
                continue
            serial = str(getattr(mux_dev, "serial", "") or "").strip()
            if not serial:
                continue

            info: dict[str, Any] = {}
            mode = "normal"
            conn = None
            try:
                conn = await asyncio.wait_for(
                    ServiceConnection.create_using_usbmux(
                        serial, LOCKDOWN_PORT, connection_type="USB"
                    ),
                    timeout=1.5,
                )
                qtype = await asyncio.wait_for(
                    conn.send_recv_plist(
                        {"Label": "AppleFlashStudio", "Request": "QueryType"}
                    ),
                    timeout=1.0,
                )
                if qtype.get("Type") == "com.apple.mobile.restored":
                    mode = "restore"
                else:
                    for key in (
                        "DeviceName",
                        "ProductType",
                        "ProductVersion",
                        "BuildVersion",
                        "UniqueChipID",
                        "ChipID",
                        "BoardId",
                        "HardwareModel",
                        "SerialNumber",
                    ):
                        resp = await asyncio.wait_for(
                            conn.send_recv_plist(
                                {
                                    "Label": "AppleFlashStudio",
                                    "Request": "GetValue",
                                    "Key": key,
                                }
                            ),
                            timeout=0.8,
                        )
                        if "Value" in resp and resp["Value"] is not None:
                            info[key] = resp["Value"]
            except Exception as exc:
                log.debug("Не удалось прочитать ключи lockdownd для %s: %s", serial, exc)
            finally:
                if conn is not None:
                    try:
                        await conn.close()
                    except Exception:
                        pass

            pt = str(info.get("ProductType") or "") or None
            cpid_raw = info.get("ChipID")
            bdid_raw = info.get("BoardId")
            cpid = int(cpid_raw) if isinstance(cpid_raw, int) else None
            bdid = int(bdid_raw) if isinstance(bdid_raw, int) else None
            ecid = _norm_hex_ecid(info.get("UniqueChipID"))
            hw_model = str(info.get("HardwareModel") or "") or None

            # Подтягиваем имя драйвера Windows из снимка SetupAPI, если доступно
            win_drv = self._match_win32_driver(win32_entries, udid=serial, ecid=ecid, mode="normal")

            found.append(
                ConnectedDevice(
                    uid=serial,
                    mode=mode,
                    product_type=pt,
                    marketing_name=resolve_product_name(pt, cpid, bdid),
                    family=infer_device_family(pt, cpid),
                    ecid=ecid,
                    udid=serial,
                    cpid=cpid,
                    bdid=bdid,
                    board_config=hw_model,
                    os_version=str(info.get("ProductVersion") or "") or None,
                    build_version=str(info.get("BuildVersion") or "") or None,
                    serial_number=str(info.get("SerialNumber") or "") or None,
                    device_name=str(info.get("DeviceName") or "") or None,
                    usb_driver=win_drv or "usbmuxd (Apple USB)",
                    source_backend="pymobiledevice3 (usbmux)",
                )
            )
        return found

    # ---------------- Уровень 2: DFU / Recovery через libusb-1.0 + IRecv ----------------
    def _scan_irecv_libusb(
        self, win32_entries: list[AppleUsbWin32Entry]
    ) -> list[ConnectedDevice]:
        found: list[ConnectedDevice] = []
        try:
            import usb.core
            from usb.util import dispose_resources

            usb_devs = list(usb.core.find(find_all=True, idVendor=0x05AC) or [])
        except Exception as exc:
            log.debug("pyusb scan недоступен: %s", exc)
            return found

        boot_devs = [
            d
            for d in usb_devs
            if classify_apple_pid(int(getattr(d, "idProduct", 0))) in {"dfu", "recovery", "wtf"}
        ]
        if not boot_devs:
            return found

        # Пробуем прочитать полные параметры через IRecv (и обязательно освобождаем дескриптор!)
        try:
            from pymobiledevice3.irecv import IRecv

            irecv = IRecv(timeout=0.25)
            try:
                mode_val = irecv.mode.value
                mode_str = classify_apple_pid(mode_val) or "recovery"
                cpid = irecv.chip_id
                bdid = irecv.board_id
                ecid_hex = f"0x{irecv.ecid:X}"
                srnm = irecv.srnm or None

                pt: str | None = None
                hw_model: str | None = None
                disp_name: str | None = None
                try:
                    pt = irecv.product_type
                    hw_model = irecv.hardware_model
                    disp_name = irecv.display_name
                except Exception:
                    pt, hw_model, disp_name = lookup_hardware_by_cpid_bdid(cpid, bdid)

                marketing = resolve_product_name(pt, cpid, bdid) if pt else (disp_name or resolve_product_name(None, cpid, bdid))
                win_drv = self._match_win32_driver(win32_entries, udid=None, ecid=ecid_hex, mode=mode_str)

                found.append(
                    ConnectedDevice(
                        uid=ecid_hex,
                        mode=mode_str,
                        product_type=pt,
                        marketing_name=marketing,
                        family=infer_device_family(pt, cpid),
                        ecid=ecid_hex,
                        cpid=cpid,
                        bdid=bdid,
                        board_config=hw_model,
                        serial_number=srnm,
                        usb_driver=win_drv or "libusb-1.0 (готов к прошивке)",
                        usb_pid=mode_val,
                        source_backend="pymobiledevice3 (IRecv / libusb)",
                    )
                )
            finally:
                if getattr(irecv, "_device", None) is not None:
                    try:
                        dispose_resources(irecv._device)
                    except Exception:
                        pass
        except Exception as exc:
            log.debug("IRecv не смог открыть USB-интерфейс напрямую (%s) — сработает уровень SetupAPI", exc)

        # Освобождаем ссылки pyusb
        for d in usb_devs:
            try:
                from usb.util import dispose_resources

                dispose_resources(d)
            except Exception:
                pass

        return found

    # ---------------- Уровень 3: Нативный Win32 SetupAPI (ловит устройства без драйверов) ----------------
    def _scan_win32_unmatched(
        self,
        win32_entries: list[AppleUsbWin32Entry],
        seen_ecids: set[str],
        seen_udids: set[str],
    ) -> list[ConnectedDevice]:
        if not win32_entries:
            return []

        amds_installed, amds_running, _ = probe_amds_windows()
        found: list[ConnectedDevice] = []

        for entry in win32_entries:
            ecid_norm = _norm_hex_ecid(entry.ecid)
            udid_norm = entry.udid.lower() if entry.udid else None
            if ecid_norm and ecid_norm in seen_ecids:
                continue
            if udid_norm and udid_norm in seen_udids:
                continue

            pt, hw_model, disp_name = lookup_hardware_by_cpid_bdid(entry.cpid, entry.bdid)
            family = infer_device_family(pt, entry.cpid)
            if family == "unknown" and entry.mode == "normal":
                if entry.pid == 0x12AB or "ipad" in entry.description.lower():
                    family = "ipad"
                else:
                    family = "iphone"

            marketing = (
                resolve_product_name(pt, entry.cpid, entry.bdid)
                if (pt or entry.cpid)
                else (
                    "iPad (подключён по USB)"
                    if family == "ipad"
                    else "iPhone / iPad (подключён по USB)"
                )
            )
            if disp_name and not pt:
                marketing = disp_name

            drv_upper = (entry.service or "").upper()
            warning: str | None = None
            if entry.mode == "normal":
                if not amds_installed:
                    warning = (
                        "Устройство подключено к USB, но в Windows не установлен драйвер Apple Mobile Device Service. "
                        "Установите «Устройства Apple» из Microsoft Store (кнопка ниже), чтобы прочитать модель и начать прошивку."
                    )
                elif not amds_running:
                    warning = (
                        "Служба Apple Mobile Device Service остановлена в Windows. "
                        "Переподключите кабель или запустите службу на вкладке «Драйверы и USB»."
                    )
                else:
                    warning = (
                        "Устройство обнаружено по USB — разблокируйте экран телефона и подтвердите «Доверять», если появится запрос."
                    )
            elif entry.mode in {"dfu", "recovery", "wtf"}:
                if not drv_upper:
                    warning = (
                        f"Устройство в режиме {entry.mode.upper()}, но Windows не назначила ему USB-драйвер. "
                        "Установите драйвер Apple USB или WinUSB (Zadig) на вкладке «Драйверы и USB»."
                    )
                elif "USBAAPL" in drv_upper:
                    warning = (
                        f"Устройство обнаружено в режиме {entry.mode.upper()} (драйвер {entry.service}). "
                        "Для прямой прошивки через libusb на Windows замените драйвер DFU/Recovery на WinUSB через утилиту Zadig (вкладка «Драйверы и USB»)."
                    )

            uid = ecid_norm or entry.udid or entry.instance_id
            found.append(
                ConnectedDevice(
                    uid=uid,
                    mode=entry.mode,
                    product_type=pt,
                    marketing_name=marketing,
                    family=family,
                    ecid=ecid_norm,
                    udid=entry.udid,
                    cpid=entry.cpid,
                    bdid=entry.bdid,
                    board_config=hw_model,
                    serial_number=entry.serial_number,
                    usb_driver=entry.service or "Нет драйвера Windows",
                    usb_pid=entry.pid,
                    driver_warning=warning,
                    source_backend="Windows USB (SetupAPI)",
                )
            )
        return found

    @staticmethod
    def _match_win32_driver(
        entries: list[AppleUsbWin32Entry],
        *,
        udid: str | None,
        ecid: str | None,
        mode: str,
    ) -> str | None:
        norm_ecid = _norm_hex_ecid(ecid)
        norm_udid = udid.lower() if udid else None
        for e in entries:
            if norm_ecid and _norm_hex_ecid(e.ecid) == norm_ecid and e.service:
                return e.service
            if norm_udid and e.udid and e.udid.lower() == norm_udid and e.service:
                return e.service
        for e in entries:
            if e.mode == mode and e.service:
                return e.service
        return None

    # ---------------- Резерв: внешние утилиты libimobiledevice ----------------
    def _find_tool(self, name: str) -> str | None:
        exe = f"{name}.exe" if sys.platform == "win32" else name
        if self.tools_dir:
            cand = self.tools_dir / exe
            if cand.is_file():
                return str(cand)
        return shutil.which(exe) or shutil.which(name)

    def _scan_libimobiledevice(self) -> list[ConnectedDevice]:
        idevice_id = self._find_tool("idevice_id")
        ideviceinfo = self._find_tool("ideviceinfo")
        if not idevice_id:
            return []
        found: list[ConnectedDevice] = []
        try:
            proc = subprocess.run(
                [idevice_id, "-l"],
                capture_output=True,
                text=True,
                timeout=2,
                check=False,
                **windows_no_window_kwargs(),
            )
            udids = [ln.strip() for ln in proc.stdout.splitlines() if ln.strip()]
            for udid in udids:
                kv: dict[str, str] = {}
                if ideviceinfo:
                    inf = subprocess.run(
                        [ideviceinfo, "-u", udid],
                        capture_output=True,
                        text=True,
                        timeout=3,
                        check=False,
                        **windows_no_window_kwargs(),
                    )
                    for line in inf.stdout.splitlines():
                        if ":" in line:
                            k, _, v = line.partition(":")
                            kv[k.strip()] = v.strip()
                pt = kv.get("ProductType")
                ecid = _norm_hex_ecid(kv.get("UniqueChipID"))
                found.append(
                    ConnectedDevice(
                        uid=udid,
                        mode="normal",
                        product_type=pt,
                        marketing_name=resolve_product_name(pt),
                        family=infer_device_family(pt),
                        ecid=ecid,
                        udid=udid,
                        board_config=kv.get("HardwareModel"),
                        os_version=kv.get("ProductVersion"),
                        build_version=kv.get("BuildVersion"),
                        serial_number=kv.get("SerialNumber"),
                        device_name=kv.get("DeviceName"),
                        usb_driver="libimobiledevice",
                        source_backend="libimobiledevice",
                    )
                )
        except (OSError, subprocess.SubprocessError):
            pass
        return found

    @staticmethod
    def virtual_devices() -> list[ConnectedDevice]:
        """Тестовые профили (используются только в модульных автотестах при include_virtual=True)."""
        return [
            ConnectedDevice(
                uid="00008130-001A2B3C4D5E6F01",
                mode="normal",
                product_type="iPhone16,1",
                marketing_name="iPhone 15 Pro",
                family="iphone",
                ecid="0x1A2B3C4D5E6F01",
                udid="00008130-001A2B3C4D5E6F01",
                cpid=0x8130,
                board_config="D83AP",
                os_version="18.2",
                build_version="22C152",
                serial_number="F2LTEST15PRO",
                device_name="iPhone 15 Pro",
                battery_percent=84,
                usb_driver="usbmuxd",
                source_backend="virtual",
                is_virtual=True,
            ),
            ConnectedDevice(
                uid="0x00813299AABBCC02",
                mode="recovery",
                product_type="iPad16,3",
                marketing_name="iPad Pro 11\" (M4, Wi-Fi)",
                family="ipad",
                ecid="0x00813299AABBCC02",
                cpid=0x8132,
                board_config="J717AP",
                os_version="18.2",
                usb_driver="WinUSB",
                source_backend="virtual",
                is_virtual=True,
            ),
            ConnectedDevice(
                uid="0x008122FFEEDDCC03",
                mode="dfu",
                product_type="Mac15,3",
                marketing_name="MacBook Pro 14\" (M3, 2023)",
                family="macbook",
                ecid="0x008122FFEEDDCC03",
                cpid=0x8122,
                bdid=0x22,
                board_config="J504AP",
                usb_driver="WinUSB",
                source_backend="virtual",
                is_virtual=True,
            ),
        ]
