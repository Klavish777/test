"""Диагностика драйверов Windows 10/11, службы Apple Mobile Device Service и встроенного движка USB."""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

from apple_flash.core.usb_runtime import check_runtime_health, initialize_runtime
from apple_flash.data.models import DriverCheckItem
from apple_flash.services.win32_usb import (
    AppleUsbWin32Entry,
    check_usbmux_tcp_port,
    enumerate_apple_usb_win32,
    probe_amds_windows,
)


class DriverDiagnostics:
    """Проверяет готовность Windows к обнаружению и прошивке iPhone, iPad и MacBook."""

    def __init__(self, tools_dir: Path | None = None) -> None:
        self.tools_dir = tools_dir
        initialize_runtime()

    def raw_usb_entries(self) -> list[AppleUsbWin32Entry]:
        """Возвращает список текущих интерфейсов Apple VID_05AC на шине USB Windows."""
        return enumerate_apple_usb_win32() if sys.platform == "win32" else []

    def run_checks(self) -> list[DriverCheckItem]:
        health = check_runtime_health()
        items: list[DriverCheckItem] = []

        # 1. Встроенный движок прошивки pymobiledevice3
        pmb_ok, pmb_msg = health.get("pymobiledevice3", (False, "Не найден"))
        items.append(
            DriverCheckItem(
                key="builtin_engine",
                title="Встроенный движок прошивки Apple (pymobiledevice3)",
                status="ok" if pmb_ok else "missing",
                summary=pmb_msg,
                recommendation=(
                    "Работает из коробки внутри программы — устанавливать Python или сторонние скрипты не нужно."
                    if pmb_ok
                    else "Переустановите полную сборку Apple Flash Studio."
                ),
            )
        )

        # 2. Низкоуровневая библиотека USB (libusb-1.0 для Recovery и DFU)
        usb_ok, usb_msg = health.get("libusb", (False, "Не найдена"))
        usb_display = Path(usb_msg).name if ("/" in usb_msg or "\\" in usb_msg) else usb_msg
        items.append(
            DriverCheckItem(
                key="libusb",
                title="Драйвер прямого обмена с DFU и Recovery (libusb-1.0)",
                status="ok" if usb_ok else "missing",
                summary=f"Библиотека активна: {usb_display}",
                recommendation=(
                    "Библиотека libusb-1.0 встроена в программу и готова к отправке загрузчиков iBSS/iBEC."
                    if usb_ok
                    else "Проверьте целостность папки программы (файл libusb-1.0.dll)."
                ),
            )
        )

        # 3. Служба Apple Mobile Device Service (usbmuxd) для обычного режима
        if sys.platform == "win32":
            installed, running, detail = probe_amds_windows()
            if installed and running:
                items.append(
                    DriverCheckItem(
                        key="amds",
                        title="Драйвер обычного режима iOS / iPadOS (Apple Mobile Device Service)",
                        status="ok",
                        summary=detail,
                        recommendation="Включённые iPhone и iPad определяются автоматически при подключении кабеля.",
                    )
                )
            elif installed and not running:
                items.append(
                    DriverCheckItem(
                        key="amds",
                        title="Драйвер обычного режима iOS / iPadOS (Apple Mobile Device Service)",
                        status="warning",
                        summary=detail,
                        recommendation=(
                            "Откройте приложение «Устройства Apple» (или iTunes) один раз либо перезапустите службу "
                            "«Apple Mobile Device Service» в окне services.msc."
                        ),
                    )
                )
            else:
                items.append(
                    DriverCheckItem(
                        key="amds",
                        title="Драйвер обычного режима iOS / iPadOS (Apple Mobile Device Service)",
                        status="missing",
                        summary=detail,
                        recommendation=(
                            "Нажмите кнопку «Установить Устройства Apple из Microsoft Store» выше — официальное приложение "
                            "Apple бесплатно установит подписанный драйвер Apple USB и службу usbmuxd."
                        ),
                    )
                )
        else:
            port_up = check_usbmux_tcp_port() or Path("/var/run/usbmuxd").exists()
            items.append(
                DriverCheckItem(
                    key="amds",
                    title="Системная служба Apple USB (usbmuxd)",
                    status="ok" if port_up else "info",
                    summary=(
                        "Служба usbmuxd активна в системе."
                        if port_up
                        else f"Среда {sys.platform}: полная проверка драйверов выполняется при запуске на Windows 10/11."
                    ),
                    recommendation="На Windows 10/11 установите «Устройства Apple» из Microsoft Store для работы с включёнными iPhone/iPad.",
                )
            )

        # 4. Состояние драйвера для подключённых прямо сейчас устройств в DFU / Recovery
        usb_entries = self.raw_usb_entries()
        boot_entries = [e for e in usb_entries if e.mode in {"dfu", "recovery", "wtf"}]
        if boot_entries:
            e = boot_entries[0]
            svc = (e.service or "").upper()
            if any(k in svc for k in ("WINUSB", "LIBUSB")):
                items.append(
                    DriverCheckItem(
                        key="dfu_driver",
                        title=f"Драйвер текущего устройства в режиме {e.mode.upper()}",
                        status="ok",
                        summary=f"Назначен совместимый драйвер {e.service} ({e.description}).",
                        recommendation="Устройство полностью готово к прямой прошивке и выходу из Recovery.",
                    )
                )
            else:
                items.append(
                    DriverCheckItem(
                        key="dfu_driver",
                        title=f"Драйвер текущего устройства в режиме {e.mode.upper()}",
                        status="warning",
                        summary=(
                            f"Назначен драйвер «{e.service or 'не установлен'}» — он блокирует прямой доступ libusb в режиме DFU/Recovery."
                        ),
                        recommendation=(
                            "Скачайте бесплатную утилиту Zadig (zadig.akeo.ie), выберите «Apple Mobile Device (DFU/Recovery Mode)» "
                            "и нажмите «Replace Driver» → WinUSB."
                        ),
                    )
                )
        else:
            items.append(
                DriverCheckItem(
                    key="dfu_driver",
                    title="Драйвер для режима DFU и MacBook (WinUSB)",
                    status="info",
                    summary="Сейчас нет подключённых устройств в режиме DFU / Recovery.",
                    recommendation=(
                        "Если при прошивке из чёрного экрана DFU (включая MacBook M1–M4) возникнет ошибка доступа к USB, "
                        "замените драйвер устройства DFU с USBAAPL64 на WinUSB через утилиту Zadig."
                    ),
                )
            )

        # 5. Дополнительный внешний idevicerestore (необязателен)
        ext_irestore = self._find_tool("idevicerestore")
        items.append(
            DriverCheckItem(
                key="idevicerestore",
                title="Дополнительная утилита idevicerestore (необязательно)",
                status="ok" if ext_irestore else "info",
                summary=(
                    f"Обнаружена: {ext_irestore}"
                    if ext_irestore
                    else "Не используется — прошивка выполняется встроенным движком pymobiledevice3."
                ),
                recommendation="При желании опытные мастера могут положить idevicerestore.exe в папку tools.",
            )
        )

        return items

    def _find_tool(self, name: str) -> str | None:
        exe = f"{name}.exe" if sys.platform == "win32" else name
        if self.tools_dir:
            cand = self.tools_dir / exe
            if cand.is_file():
                return str(cand)
        return shutil.which(exe) or shutil.which(name)
