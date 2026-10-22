"""Диагностика драйверов Windows (Apple Mobile Device, WinUSB/DFU) и CLI-бэкендов прошивки."""

from __future__ import annotations

import importlib.util
import platform
import shutil
import subprocess
import sys
from pathlib import Path

from apple_flash.core.security import resolve_pmb3_command, windows_no_window_kwargs
from apple_flash.data.models import DriverCheckItem


class DriverDiagnostics:
    """Проверяет готовность рабочей станции Windows к перепрошивке iPhone, iPad и MacBook."""

    def __init__(self, tools_dir: Path | None = None) -> None:
        self.tools_dir = tools_dir

    def _find_tool(self, name: str) -> str | None:
        exe = f"{name}.exe" if sys.platform == "win32" else name
        if self.tools_dir:
            for candidate in (self.tools_dir / exe, self.tools_dir / name):
                if candidate.is_file():
                    return str(candidate)
        return shutil.which(name)

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

    def run_all_checks(self) -> list[DriverCheckItem]:
        items: list[DriverCheckItem] = []

        # 1. Платформа ОС
        os_desc = f"{platform.system()} {platform.release()} ({platform.machine()})"
        if sys.platform == "win32":
            items.append(
                DriverCheckItem(
                    key="os",
                    title="Операционная система Windows",
                    status="ok",
                    summary=f"Обнаружена поддерживаемая среда: {os_desc}.",
                    recommendation="Используйте порты USB 2.0 / 3.0 напрямую на материнской плате (без пассивных USB-хабов).",
                )
            )
        else:
            items.append(
                DriverCheckItem(
                    key="os",
                    title="Среда запуска (кроссплатформенный режим)",
                    status="info",
                    summary=f"Запущено на {os_desc} (целевая платформа сборки EXE — Windows 10/11 x64).",
                    recommendation="На Linux/macOS проверка служб Windows пропускается, но анализ IPSW и CLI работают штатно.",
                )
            )

        # 2. Служба Apple Mobile Device Service (usbmuxd на Windows)
        if sys.platform == "win32":
            sc_res = self._run_quiet(["sc", "query", "AppleMobileDeviceService"])
            if sc_res and "RUNNING" in (sc_res.stdout or "").upper():
                items.append(
                    DriverCheckItem(
                        key="amds",
                        title="Служба Apple Mobile Device Service (USBMux)",
                        status="ok",
                        summary="Служба установлена и запущена (RUNNING) — связь в Обычном режиме активна.",
                    )
                )
            elif sc_res and sc_res.returncode == 0:
                items.append(
                    DriverCheckItem(
                        key="amds",
                        title="Служба Apple Mobile Device Service (USBMux)",
                        status="warning",
                        summary="Служба установлена, но остановлена.",
                        recommendation="Запустите службу в services.msc или переоткройте приложение «Устройства Apple» / iTunes.",
                    )
                )
            else:
                items.append(
                    DriverCheckItem(
                        key="amds",
                        title="Служба Apple Mobile Device Service (USBMux)",
                        status="missing",
                        summary="Служба не найдена в Windows.",
                        recommendation=(
                            "Установите официальное приложение «Устройства Apple» (Apple Devices) из Microsoft Store "
                            "или классический пакет iTunes (x64) с сайта Apple для драйверов usbaapl64."
                        ),
                    )
                )
        else:
            usbmuxd_bin = shutil.which("usbmuxd")
            items.append(
                DriverCheckItem(
                    key="amds",
                    title="Демон связи USBMuxd",
                    status="ok" if usbmuxd_bin else "info",
                    summary=(
                        f"Найден системный usbmuxd: {usbmuxd_bin}"
                        if usbmuxd_bin
                        else "На Windows роль usbmuxd выполняет служба AppleMobileDeviceService."
                    ),
                )
            )

        # 3. Бэкенд pymobiledevice3
        pmb_base = resolve_pmb3_command(self.tools_dir)
        if pmb_base:
            loc = " ".join(pmb_base)
            items.append(
                DriverCheckItem(
                    key="pymobiledevice3",
                    title="Бэкенд прошивки pymobiledevice3 (Python)",
                    status="ok",
                    summary=f"Модуль готов к работе ({loc}). Поддерживает Update, Erase и Recovery.",
                )
            )
        else:
            items.append(
                DriverCheckItem(
                    key="pymobiledevice3",
                    title="Бэкенд прошивки pymobiledevice3 (Python)",
                    status="missing",
                    summary="Пакет pymobiledevice3 не установлен в текущем окружении.",
                    recommendation="Выполните: pip install pymobiledevice3 — для прямой прошивки iPhone, iPad и MacBook.",
                )
            )

        # 4. Бэкенд idevicerestore + irecovery (libimobiledevice)
        idr = self._find_tool("idevicerestore")
        irec = self._find_tool("irecovery")
        if idr:
            items.append(
                DriverCheckItem(
                    key="idevicerestore",
                    title="Бэкенд idevicerestore / irecovery (libimobiledevice)",
                    status="ok",
                    summary=f"Найден idevicerestore: {idr}" + (f" · irecovery: {irec}" if irec else ""),
                )
            )
        else:
            items.append(
                DriverCheckItem(
                    key="idevicerestore",
                    title="Бэкенд idevicerestore / irecovery (libimobiledevice)",
                    status="missing",
                    summary="Бинарные файлы idevicerestore.exe / irecovery.exe не найдены в папке tools и PATH.",
                    recommendation=(
                        "Положите сборки libimobiledevice для Windows (idevicerestore.exe, irecovery.exe, ideviceinfo.exe) "
                        "в каталог tools приложения (Настройки → Открыть папку tools) или используйте pymobiledevice3."
                    ),
                )
            )

        # 5. Памятка по WinUSB для DFU на Windows (критично для MacBook DFU и idevicerestore)
        items.append(
            DriverCheckItem(
                key="dfu_winusb",
                title="Драйвер DFU / Recovery для прошивки MacBook и libusb",
                status="info",
                summary="Для работы idevicerestore и DFU MacBook на Windows интерфейс 05ac:1227 должен быть доступен через WinUSB / libusbK.",
                recommendation=(
                    "Если устройство в DFU видно в Диспетчере устройств, но прошивальщик пишет «Unable to discover device», "
                    "откройте утилиту Zadig при подключённом DFU-устройстве (Apple Mobile Device DFU Mode) и привяжите драйвер WinUSB."
                ),
            )
        )

        return items
