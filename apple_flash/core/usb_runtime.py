"""Инициализация встроенной среды USB (libusb-1.0, SSL-сертификаты TSS, потоки stdio для Windows EXE)."""

from __future__ import annotations

import io
import logging
import os
import sys
from pathlib import Path
from typing import Any

log = logging.getLogger("apple_flash.usb_runtime")

_DLL_DIR_HANDLES: list[Any] = []
_INITIALIZED = False


class _SafeNullStream(io.TextIOBase):
    """Безопасный поток для PyInstaller console=False, где sys.stdout/sys.stderr равны None."""

    encoding = "utf-8"

    def write(self, s: str) -> int:
        return len(s) if isinstance(s, str) else 0

    def flush(self) -> None:
        return None

    def isatty(self) -> bool:
        return False

    def writable(self) -> bool:
        return True


def ensure_safe_stdio() -> None:
    """Гарантирует, что sys.stdout и sys.stderr не равны None в оконном режиме Windows (.exe)."""
    if sys.stdout is None:
        sys.stdout = _SafeNullStream()
    if sys.stderr is None:
        sys.stderr = _SafeNullStream()


def ensure_ssl_certificates() -> str | None:
    """Настраивает корневые сертификаты CA для HTTPS-запросов подписи Apple TSS (gs.apple.com)."""
    try:
        import certifi

        ca_file = certifi.where()
        if ca_file and Path(ca_file).is_file():
            os.environ.setdefault("SSL_CERT_FILE", ca_file)
            os.environ.setdefault("REQUESTS_CA_BUNDLE", ca_file)
            return ca_file
    except Exception as exc:
        log.debug("certifi недоступен: %s", exc)
    return None


def ensure_libusb_backend() -> tuple[bool, str]:
    """Подключает встроенную библиотеку libusb-1.0.dll/.so из libusb_package и кэширует её в pyusb."""
    lib_path_str = ""
    try:
        import libusb_package

        lib_path = libusb_package.get_library_path()
        if lib_path is not None:
            resolved = Path(lib_path).resolve()
            if resolved.is_file():
                lib_path_str = str(resolved)
                dll_dir = str(resolved.parent)
                current_path = os.environ.get("PATH", "")
                if dll_dir not in current_path.split(os.pathsep):
                    os.environ["PATH"] = dll_dir + os.pathsep + current_path
                if sys.platform == "win32" and hasattr(os, "add_dll_directory"):
                    try:
                        _DLL_DIR_HANDLES.append(os.add_dll_directory(dll_dir))
                    except OSError:
                        pass

        import usb.backend.libusb1 as libusb1

        backend = libusb1.get_backend(find_library=libusb_package.find_library)
        if backend is not None:
            return True, lib_path_str or "libusb-1.0 (libusb_package)"
    except Exception as exc:
        log.debug("Ошибка инициализации libusb_package: %s", exc)

    # Резервная попытка системного libusb1
    try:
        import usb.backend.libusb1 as libusb1

        backend = libusb1.get_backend()
        if backend is not None:
            return True, lib_path_str or "системная библиотека libusb-1.0"
    except Exception as exc:
        return False, f"libusb недоступна: {exc}"

    return False, "Библиотека libusb-1.0 не найдена"


def initialize_runtime() -> None:
    """Единая точка ранней инициализации рантайма Apple Flash Studio."""
    global _INITIALIZED
    ensure_safe_stdio()
    if _INITIALIZED:
        return
    ensure_ssl_certificates()
    ensure_libusb_backend()
    _INITIALIZED = True


def check_runtime_health() -> dict[str, tuple[bool, str]]:
    """Самодиагностика встроенных модулей (используется в UI и во флаге --check-runtime при сборке EXE)."""
    initialize_runtime()
    results: dict[str, tuple[bool, str]] = {}

    # 1. pymobiledevice3 ядро + irecv_devices + restore
    try:
        import importlib.metadata

        import pymobiledevice3
        from pymobiledevice3.irecv import IRecv  # noqa: F401
        from pymobiledevice3.irecv_devices import IRECV_DEVICES
        from pymobiledevice3.lockdown import create_using_usbmux  # noqa: F401
        from pymobiledevice3.restore.restore import Restore  # noqa: F401
        from pymobiledevice3.usbmux import list_devices  # noqa: F401

        try:
            ver = importlib.metadata.version("pymobiledevice3")
        except Exception:
            ver = getattr(pymobiledevice3, "__version__", "v11+")
        results["pymobiledevice3"] = (
            True,
            f"pymobiledevice3 {ver} встроен (база моделей Apple: {len(IRECV_DEVICES)} устр.)",
        )
    except Exception as exc:
        results["pymobiledevice3"] = (False, f"Ошибка загрузки pymobiledevice3: {exc}")

    # 2. libusb-1.0
    ok_usb, msg_usb = ensure_libusb_backend()
    results["libusb"] = (ok_usb, msg_usb)

    # 3. Корневые сертификаты SSL для Apple TSS
    ca = ensure_ssl_certificates()
    results["certifi"] = (
        bool(ca),
        ca or "Системное хранилище сертификатов ОС",
    )

    # 4. Нативный Win32 SetupAPI на Windows
    if sys.platform == "win32":
        try:
            from apple_flash.services.win32_usb import enumerate_apple_usb_win32

            found = enumerate_apple_usb_win32()
            results["win32_setupapi"] = (
                True,
                f"SetupAPI активен (обнаружено интерфейсов VID_05AC: {len(found)})",
            )
        except Exception as exc:
            results["win32_setupapi"] = (False, f"Ошибка Win32 SetupAPI: {exc}")

    return results
