"""Реальный встроенный движок прошивки и управления устройствами Apple (pymobiledevice3 + опционально idevicerestore)."""

from __future__ import annotations

import asyncio
import datetime as dt
import logging
import plistlib
import shutil
import subprocess
import sys
import threading
import time
import zipfile
from collections.abc import Callable
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from apple_flash.core.errors import FlashExecutionError
from apple_flash.core.security import human_bytes, resolve_pmb3_command, windows_no_window_kwargs
from apple_flash.core.usb_runtime import initialize_runtime
from apple_flash.data.models import (
    FLASH_ACTION_LABELS,
    FlashJobConfig,
    FlashSessionRecord,
)
from apple_flash.data.store import StudioStore
from apple_flash.services.compatibility import evaluate_compatibility
from apple_flash.services.ipsw_inspector import IpswInspector

ProgressCallback = Callable[[int, str, str], None]

LOCKDOWN_PORT = 62078

STAGE_PATTERNS: tuple[tuple[str, int, str], ...] = (
    ("extracting buildmanifest", 12, "Чтение BuildManifest из архива IPSW…"),
    ("fetching tss", 14, "Запрос цифровой подписи у сервера Apple TSS…"),
    ("requesting shsh", 16, "Получение билетов безопасности SHSH…"),
    ("going into recovery", 20, "Перевод устройства в режим восстановления (Recovery)…"),
    ("waiting for device to reconnect", 23, "Ожидание переподключения устройства по USB…"),
    ("sending ibss", 26, "Отправка первичного загрузчика iBSS…"),
    ("sending ibec", 33, "Отправка загрузчика iBEC…"),
    ("ramdisk", 40, "Загрузка установочного диска (Restore Ramdisk)…"),
    ("devicetree", 44, "Отправка конфигурации платы (DeviceTree)…"),
    ("connecting to asr", 48, "Подключение к службе записи системы (ASR)…"),
    ("validating the filesystem", 50, "Проверка целостности системного раздела…"),
    ("sending filesystem", 56, "Запись операционной системы на устройство…"),
    ("kernelcache", 82, "Прошивка ядра системы (KernelCache)…"),
    ("nordata", 86, "Обновление загрузчика NOR / LLB…"),
    ("rootticket", 89, "Запись корневого сертификата загрузки (RootTicket)…"),
    ("baseband", 92, "Обновление модема сотовой связи (Baseband)…"),
    ("fud", 95, "Обновление контроллеров периферии…"),
    ("restore finished", 99, "Завершение установки и перезагрузка устройства…"),
    ("restoring succeeded", 100, "Прошивка успешно завершена!"),
)


def _parse_ecid_int(ecid_str: str | None) -> int | None:
    if not ecid_str:
        return None
    text = str(ecid_str).strip()
    if not text:
        return None
    try:
        return int(text, 16) if text.lower().startswith("0x") else int(text, 0)
    except ValueError:
        try:
            return int(text, 16)
        except ValueError:
            return None


def _humanize_flash_exception(exc: BaseException) -> str:
    """Переводит низкоуровневые ошибки USB / TSS / libusb на понятный русский язык."""
    raw = str(exc)
    low = raw.lower()
    if "access denied" in low or "insufficient permissions" in low or "errno 13" in low:
        return (
            "Windows заблокировала прямой доступ к USB-устройству в режиме DFU/Recovery (драйвер USBAAPL64). "
            "Откройте вкладку «Драйверы и USB» и замените драйвер DFU/Recovery на WinUSB через утилиту Zadig."
        )
    if "no device in recovery or dfu" in low or "irecvnodeviceconnected" in low:
        return (
            "Устройство не ответило в режиме Recovery/DFU. Проверьте кабель USB и убедитесь, что телефон переведён в Recovery или DFU."
        )
    if "tss" in low and ("not signed" in low or "rejected" in low or "status=94" in low):
        return (
            "Сервер Apple TSS отклонил подпись этой версии прошивки — Apple уже прекратила подписывать выбранный .ipsw. "
            "Используйте актуальную подписанную версию прошивки (.ipsw)."
        )
    if "getaddrinfo" in low or "name or service not known" in low or "connectionerror" in low:
        return (
            "Не удалось связаться с сервером подписи Apple (gs.apple.com). Для официальной прошивки требуется подключение к интернету, "
            "чтобы Apple подписала загрузку для вашего чипа ECID."
        )
    if "notpaired" in low or "pairingdialog" in low or "passwordprotected" in low:
        return (
            "На экране iPhone/iPad не подтверждено доверие компьютеру. Разблокируйте устройство и нажмите «Доверять», "
            "либо переведите устройство кнопками в режим Recovery и повторите."
        )
    return f"Ошибка операции: {raw}"


@contextmanager
def _capture_pmb3_progress_and_logs(emit: Callable[[int, str, str], None]):
    """Перехватывает логи и байтовые прогресс-бары pymobiledevice3 без вывода в консоль."""
    state = {"pct": 10, "stage": "Подготовка операции…"}
    lock = threading.Lock()

    class _LogBridge(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            msg = record.getMessage().strip()
            if not msg:
                return
            low = msg.lower()
            with lock:
                for needle, pct, stage_ru in STAGE_PATTERNS:
                    if needle in low:
                        state["pct"] = max(state["pct"], pct)
                        state["stage"] = stage_ru
                        break
                cur_pct = state["pct"]
                cur_stage = state["stage"]
            emit(cur_pct, cur_stage, msg)

    handler = _LogBridge(level=logging.INFO)
    tracked_loggers = [
        logging.getLogger("pymobiledevice3"),
        logging.getLogger("ipsw_parser"),
    ]
    prev_levels = [lg.level for lg in tracked_loggers]
    for lg in tracked_loggers:
        if lg.level == logging.NOTSET or lg.level > logging.INFO:
            lg.setLevel(logging.INFO)
        lg.addHandler(handler)

    # Перехватываем ProgressBar из pymobiledevice3.progress (чтобы rich не трогал stderr в EXE и отдавал МБ/ГБ в UI)
    patched_modules: list[tuple[Any, Any]] = []
    try:
        import pymobiledevice3.irecv as pmd_irecv
        import pymobiledevice3.progress as pmd_prog
        import pymobiledevice3.restore.asr as pmd_asr

        orig_bar = pmd_prog.ProgressBar

        class _GuiProgressBar:
            def __init__(
                self,
                total: float | None = None,
                desc: str = "",
                unit: str = "it",
                disable: bool = False,
            ) -> None:
                self._n: float = 0.0
                self._total = float(total) if total else None
                self._desc = desc or "передача"
                self._unit = unit
                self._disable = disable
                self._last_ui = 0.0

            @property
            def n(self) -> float:
                return self._n

            @n.setter
            def n(self, val: float) -> None:
                self._n = float(val)
                self._push()

            def update(self, n: float = 1) -> None:
                self._n += float(n)
                self._push()

            def _push(self) -> None:
                if self._disable or not self._total or self._total <= 0:
                    return
                now = time.monotonic()
                if now - self._last_ui < 0.25 and self._n < self._total:
                    return
                self._last_ui = now
                ratio = min(1.0, max(0.0, self._n / self._total))
                is_fs = "filesystem" in self._desc.lower()
                with lock:
                    if is_fs:
                        # Запись образа ОС занимает 54%..80% общего прогресса
                        mapped = 54 + int(ratio * 26)
                        state["pct"] = max(state["pct"], mapped)
                        state["stage"] = (
                            f"Запись системы: {human_bytes(int(self._n))} из {human_bytes(int(self._total))} "
                            f"({int(ratio * 100)}%)"
                        )
                    cur_pct = state["pct"]
                    cur_stage = state["stage"]
                if is_fs:
                    emit(cur_pct, cur_stage, "")

            def close(self) -> None:
                return None

            def __enter__(self) -> _GuiProgressBar:
                return self

            def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
                self.close()

        for mod in (pmd_prog, pmd_irecv, pmd_asr):
            if hasattr(mod, "ProgressBar"):
                patched_modules.append((mod, mod.ProgressBar))
                mod.ProgressBar = _GuiProgressBar  # type: ignore[attr-defined]
        _ = orig_bar
    except Exception:
        pass

    try:
        yield state
    finally:
        for mod, orig_cls in patched_modules:
            mod.ProgressBar = orig_cls
        for lg, prev_lvl in zip(tracked_loggers, prev_levels, strict=False):
            lg.removeHandler(handler)
            lg.setLevel(prev_lvl)


class FlashEngine:
    """Выполняет реальную прошивку IPSW, перевод в Recovery, выход из Recovery и перезагрузку."""

    def __init__(
        self,
        store: StudioStore,
        inspector: IpswInspector,
        default_tools_dir: Path | None = None,
    ) -> None:
        self.store = store
        self.inspector = inspector
        self.default_tools_dir = default_tools_dir
        self._cancel_event = threading.Event()
        self._active_proc: subprocess.Popen[str] | None = None
        initialize_runtime()

    def request_cancel(self) -> None:
        self._cancel_event.set()
        proc = self._active_proc
        if proc and proc.poll() is None:
            try:
                proc.terminate()
            except OSError:
                pass

    def available_backends(self, custom_tools_dir: Path | None = None) -> dict[str, str | None]:
        tdir = custom_tools_dir or self.default_tools_dir
        irestore = self._find_binary("idevicerestore", tdir)
        pmb3_info = "встроенный pymobiledevice3"
        try:
            import pymobiledevice3

            pmb3_info = f"встроенный pymobiledevice3 {getattr(pymobiledevice3, '__version__', '')}".strip()
        except Exception:
            pmb3_cmd = resolve_pmb3_command(tdir)
            pmb3_info = " ".join(pmb3_cmd) if pmb3_cmd else None  # type: ignore[assignment]
        return {
            "pymobiledevice3": pmb3_info,
            "idevicerestore": irestore,
        }

    def _find_binary(self, name: str, tools_dir: Path | None) -> str | None:
        exe = f"{name}.exe" if sys.platform == "win32" else name
        if tools_dir:
            cand = tools_dir / exe
            if cand.is_file():
                return str(cand)
        return shutil.which(exe) or shutil.which(name)

    def build_command(self, cfg: FlashJobConfig) -> tuple[str, list[str]]:
        """Формирует описание команды/операции (для журнала и внешнего idevicerestore, если выбран)."""
        backends = self.available_backends(cfg.custom_tools_dir)
        chosen = cfg.backend
        if chosen == "auto":
            if cfg.custom_tools_dir and backends["idevicerestore"]:
                chosen = "idevicerestore"
            else:
                chosen = "pymobiledevice3"

        dev = cfg.device
        ecid = dev.ecid if dev else None
        udid = dev.udid if dev else None

        if chosen == "idevicerestore":
            exe = backends["idevicerestore"] or "idevicerestore"
            if cfg.action == "exit_recovery":
                irecovery = self._find_binary("irecovery", cfg.custom_tools_dir or self.default_tools_dir) or "irecovery"
                cmd = [irecovery, "-n"]
                if ecid:
                    cmd.extend(["-i", str(ecid)])
                return ("idevicerestore", cmd)
            if cfg.action == "enter_recovery":
                ideviceenter = (
                    self._find_binary("ideviceenterrecovery", cfg.custom_tools_dir or self.default_tools_dir)
                    or "ideviceenterrecovery"
                )
                return ("idevicerestore", [ideviceenter, udid or "<UDID>"])
            if cfg.action == "reboot":
                idevicediag = (
                    self._find_binary("idevicediagnostics", cfg.custom_tools_dir or self.default_tools_dir)
                    or "idevicediagnostics"
                )
                cmd = [idevicediag, "restart"]
                if udid:
                    cmd.extend(["-u", udid])
                return ("idevicerestore", cmd)

            if not cfg.ipsw_path:
                raise FlashExecutionError("Не указан путь к файлу прошивки .ipsw.")
            cmd = [exe]
            if cfg.action == "erase":
                cmd.extend(["-e", "--latest"])
            else:
                cmd.append("--latest")
            if ecid:
                cmd.extend(["-i", str(ecid)])
            if cfg.shsh_path:
                cmd.extend(["-t", str(cfg.shsh_path)])
            cmd.append(str(cfg.ipsw_path))
            return ("idevicerestore", cmd)

        # Встроенный нативный движок pymobiledevice3 (работает прямо внутри процесса EXE!)
        target = f"--ecid {ecid}" if ecid else (f"--udid {udid}" if udid else "")
        if cfg.action == "exit_recovery":
            return ("pymobiledevice3", ["builtin:pymobiledevice3", "irecv.exit_recovery", target])
        if cfg.action == "enter_recovery":
            return ("pymobiledevice3", ["builtin:pymobiledevice3", "lockdown.enter_recovery", target])
        if cfg.action == "reboot":
            return ("pymobiledevice3", ["builtin:pymobiledevice3", "diagnostics.restart", target])
        if not cfg.ipsw_path:
            raise FlashExecutionError("Не указан путь к файлу прошивки .ipsw.")
        mode_flag = "Erase" if cfg.action == "erase" else "Update"
        return (
            "pymobiledevice3",
            ["builtin:pymobiledevice3", f"restore.{mode_flag}", target, str(cfg.ipsw_path)],
        )

    def execute(
        self,
        cfg: FlashJobConfig,
        *,
        progress_cb: Callable[[int, str], None] | None = None,
        log_cb: Callable[[str], None] | None = None,
        cancel_check: Callable[[], bool] | None = None,
        dry_run_step_delay: float = 0.05,
    ) -> FlashSessionRecord:
        """Унифицированный запуск операции для фонового потока QThread и автотестов."""

        def _bridge(pct: int, stage: str, line: str) -> None:
            if cancel_check and cancel_check():
                self.request_cancel()
            if progress_cb:
                progress_cb(pct, stage)
            if log_cb and line:
                log_cb(line)

        return self.run_job(cfg, on_progress=_bridge, dry_run_step_delay=dry_run_step_delay)

    def run_job(
        self,
        cfg: FlashJobConfig,
        on_progress: ProgressCallback | None = None,
        *,
        dry_run_step_delay: float = 0.05,
    ) -> FlashSessionRecord:
        """Выполняет предпроверку, реальную операцию прошивки/управления и сохраняет отчёт в историю."""
        initialize_runtime()
        self._cancel_event.clear()
        started_at = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        logs: list[str] = []

        def emit(pct: int, stage: str, line: str = "") -> None:
            if line:
                ts = dt.datetime.now().strftime("%H:%M:%S")
                logs.append(f"[{ts}] {line}")
            if on_progress:
                on_progress(pct, stage, line)

        dev = cfg.device
        manifest = None

        emit(3, "Проверка устройства и параметров…", f"Операция: {FLASH_ACTION_LABELS.get(cfg.action, cfg.action)}")

        if dev is None and not cfg.dry_run:
            raise FlashExecutionError("Устройство не подключено. Подключите iPhone, iPad или MacBook по USB.")

        if cfg.action in {"update", "erase", "revive_mac"}:
            if not cfg.ipsw_path or not cfg.ipsw_path.is_file():
                raise FlashExecutionError("Файл прошивки .ipsw не найден на диске. Выберите корректный файл .ipsw.")
            emit(6, "Чтение паспорта прошивки BuildManifest.plist…", f"Проверка архива: {cfg.ipsw_path.name}")
            manifest = self.inspector.inspect(cfg.ipsw_path)
            verdict = evaluate_compatibility(dev, manifest, cfg.action)
            emit(9, verdict.headline, f"Совместимость: {verdict.headline}")
            for dline in verdict.details:
                emit(9, verdict.headline, f"  • {dline}")
            if not verdict.can_proceed:
                raise FlashExecutionError(f"Операция остановлена защитой совместимости: {verdict.headline}")
            if (manifest.is_demo_mockup or (dev and dev.is_virtual)) and not cfg.dry_run:
                raise FlashExecutionError("Для тестовых профилей реальная запись недоступна.")

            # Проверка свободного места во временном разделе Windows (для извлечения Ramdisk/iBEC)
            try:
                free_disk = shutil.disk_usage(Path.home()).free
                if free_disk < 1_500_000_000 and not cfg.dry_run:
                    emit(
                        9,
                        "Мало свободного места на диске",
                        f"Внимание: на системном диске свободно всего {human_bytes(free_disk)} (рекомендуется от 5 ГБ).",
                    )
            except OSError:
                pass

        backend_name, cmd = self.build_command(cfg)
        cmd_str = " ".join(x for x in cmd if x)

        status = "success"
        exit_code = 0

        try:
            if cfg.dry_run:
                status, exit_code = self._run_dry_simulation(
                    cfg, manifest, emit, step_delay=dry_run_step_delay
                )
            elif backend_name == "idevicerestore":
                status, exit_code = self._run_external_cli(cmd, emit)
            else:
                status, exit_code = self._run_builtin_pmb3(cfg, emit)
        except FlashExecutionError as exc:
            if not cfg.dry_run and (
                (manifest and manifest.is_demo_mockup)
                or (dev and dev.is_virtual)
                or dev is None
            ):
                raise
            status = "failed"
            exit_code = 2
            emit(100, "Операция завершилась с ошибкой", str(exc))
        except Exception as exc:
            status = "failed"
            exit_code = 1
            friendly = _humanize_flash_exception(exc)
            emit(100, "Ошибка выполнения операции", friendly)
        finally:
            self._active_proc = None

        finished_at = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        rec = FlashSessionRecord(
            id=None,
            started_at=started_at,
            finished_at=finished_at,
            device_title=dev.display_title if dev else "Устройство не выбрано",
            device_uid=dev.uid if dev else "—",
            product_type=dev.product_type if dev else None,
            family=dev.family if dev else (manifest.family if manifest else "unknown"),
            action=cfg.action,
            backend=backend_name,
            ipsw_name=cfg.ipsw_path.name if cfg.ipsw_path else None,
            ipsw_build=manifest.build_version if manifest else None,
            dry_run=cfg.dry_run,
            status=status,
            exit_code=exit_code,
            command_line=cmd_str,
            log_text="\n".join(logs),
        )
        return self.store.record_session(rec)

    # ---------------- Реальный встроенный движок pymobiledevice3 ----------------
    def _run_builtin_pmb3(
        self,
        cfg: FlashJobConfig,
        emit: Callable[[int, str, str], None],
    ) -> tuple[str, int]:
        dev = cfg.device
        assert dev is not None

        if cfg.action == "enter_recovery":
            emit(30, "Отправка команды перехода в режим Recovery…", "Подключение к службе lockdownd по USB…")
            asyncio.run(self._async_enter_recovery(dev))
            emit(
                100,
                "Устройство переводится в режим Recovery",
                "Готово! Через 5–10 секунд на экране устройства появится значок кабеля и компьютера.",
            )
            return ("success", 0)

        if cfg.action == "exit_recovery":
            emit(30, "Отправка команды выхода из режима Recovery…", "Подключение к загрузчику iBoot (IRecv)…")
            self._sync_exit_recovery(dev)
            emit(
                100,
                "Устройство выходит из режима Recovery",
                "Переменная auto-boot=true установлена, отправлена команда перезагрузки в обычную систему.",
            )
            return ("success", 0)

        if cfg.action == "reboot":
            emit(30, "Перезагрузка устройства…", "Отправка команды перезапуска по USB…")
            asyncio.run(self._async_reboot_device(dev))
            emit(100, "Команда перезагрузки отправлена", "Устройство перезапускается.")
            return ("success", 0)

        # Реальная прошивка IPSW (Update / Erase / Revive Mac)
        assert cfg.ipsw_path is not None
        tss_dict: dict[str, Any] | None = None
        if cfg.shsh_path and cfg.shsh_path.is_file():
            emit(10, "Чтение локального файла SHSH…", f"Загрузка билета: {cfg.shsh_path.name}")
            with cfg.shsh_path.open("rb") as fh:
                tss_dict = plistlib.load(fh)

        emit(
            11,
            "Открытие архива прошивки и подключение к устройству…",
            "Не отсоединяйте USB-кабель до полного завершения прошивки!",
        )
        with _capture_pmb3_progress_and_logs(emit):
            asyncio.run(self._async_restore_ipsw(cfg, tss_dict, emit))

        emit(
            100,
            "Прошивка успешно завершена!",
            "Операция успешно выполнена. Устройство перезагружается и завершает настройку системы.",
        )
        return ("success", 0)

    async def _async_enter_recovery(self, dev: Any) -> None:
        from pymobiledevice3 import usbmux
        from pymobiledevice3.service_connection import ServiceConnection

        serial = dev.udid
        if not serial:
            mux_list = [d for d in await usbmux.list_devices() if getattr(d, "is_usb", True)]
            if not mux_list:
                raise FlashExecutionError("Устройство не найдено в обычном режиме USB (usbmux).")
            serial = mux_list[0].serial

        conn = await ServiceConnection.create_using_usbmux(
            serial, LOCKDOWN_PORT, connection_type="USB"
        )
        try:
            resp = await conn.send_recv_plist(
                {"Label": "AppleFlashStudio", "Request": "EnterRecovery"}
            )
            err = resp.get("Error")
            if err:
                raise FlashExecutionError(f"Устройство отклонило переход в Recovery: {err}")
        finally:
            await conn.close()

    def _sync_exit_recovery(self, dev: Any) -> None:
        from pymobiledevice3.irecv import IRecv
        from usb.util import dispose_resources

        ecid_int = _parse_ecid_int(dev.ecid)
        irecv = IRecv(ecid=ecid_int, timeout=4)
        try:
            irecv.set_autoboot(True)
            irecv.reboot()
        finally:
            if getattr(irecv, "_device", None) is not None:
                try:
                    dispose_resources(irecv._device)
                except Exception:
                    pass

    async def _async_reboot_device(self, dev: Any) -> None:
        if dev.mode == "recovery":
            from pymobiledevice3.irecv import IRecv
            from usb.util import dispose_resources

            irecv = IRecv(ecid=_parse_ecid_int(dev.ecid), timeout=4)
            try:
                irecv.reboot()
            finally:
                if getattr(irecv, "_device", None) is not None:
                    try:
                        dispose_resources(irecv._device)
                    except Exception:
                        pass
            return

        from pymobiledevice3.lockdown import create_using_usbmux
        from pymobiledevice3.services.diagnostics import DiagnosticsService

        lockdown = await create_using_usbmux(
            serial=dev.udid, connection_type="USB", autopair=True
        )
        async with DiagnosticsService(lockdown=lockdown) as diag:
            await diag.restart()

    async def _async_restore_ipsw(
        self,
        cfg: FlashJobConfig,
        tss_dict: dict[str, Any] | None,
        emit: Callable[[int, str, str], None],
    ) -> None:
        from ipsw_parser.ipsw import IPSW
        from pymobiledevice3 import usbmux
        from pymobiledevice3.irecv import IRecv
        from pymobiledevice3.lockdown import create_using_usbmux
        from pymobiledevice3.restore.device import Device as RestoreDevice
        from pymobiledevice3.restore.recovery import Behavior
        from pymobiledevice3.restore.restore import Restore

        assert cfg.device is not None
        assert cfg.ipsw_path is not None

        behavior = Behavior.Erase if cfg.action == "erase" else Behavior.Update
        ecid_int = _parse_ecid_int(cfg.device.ecid)
        restore_dev: RestoreDevice | None = None

        # 1. Если устройство в обычном режиме — пробуем подключиться через lockdownd;
        # если телефон заблокирован паролем (не даёт пару), переводим его в Recovery автоматически!
        if cfg.device.mode == "normal":
            try:
                mux_list = [d for d in await usbmux.list_devices() if getattr(d, "is_usb", True)]
                target_serial = cfg.device.udid or (mux_list[0].serial if mux_list else None)
                if target_serial:
                    try:
                        lockdown = await create_using_usbmux(
                            serial=target_serial, connection_type="USB", autopair=True
                        )
                        restore_dev = RestoreDevice(lockdown=lockdown)
                        await restore_dev.get_is_image4_supported()
                    except Exception as pair_exc:
                        emit(
                            16,
                            "Экран заблокирован — автоматический перевод в Recovery…",
                            f"Не удалось открыть парную сессию ({pair_exc}); переводим устройство в Recovery напрямую…",
                        )
                        await self._async_enter_recovery(cfg.device)
                        await asyncio.sleep(4.0)
            except Exception:
                pass

        # 2. Если устройство уже в Recovery / DFU (или только что переведено туда) — подключаем IRecv
        if restore_dev is None:
            emit(18, "Подключение к устройству в режиме Recovery / DFU…", "Ожидание ответа загрузчика Apple по USB…")
            irecv = await asyncio.to_thread(IRecv, ecid=ecid_int, timeout=25)
            restore_dev = RestoreDevice(irecv=irecv)

        assert cfg.ipsw_path is not None
        with zipfile.ZipFile(cfg.ipsw_path, "r") as zf:
            ipsw_obj = IPSW(zf)
            restore_task = Restore(
                ipsw_obj,
                restore_dev,
                tss=tss_dict,
                behavior=behavior,
            )
            await restore_task.update()

    # ---------------- Внешний CLI (если выбран idevicerestore.exe) ----------------
    def _run_external_cli(
        self,
        cmd: list[str],
        emit: Callable[[int, str, str], None],
    ) -> tuple[str, int]:
        exe = cmd[0]
        resolved = shutil.which(exe) if not Path(exe).is_file() else exe
        if not resolved:
            raise FlashExecutionError(f"Внешняя утилита «{exe}» не найдена.")
        cmd[0] = resolved
        emit(12, "Запуск внешней утилиты прошивки…", f"Команда: {' '.join(cmd)}")

        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
            **windows_no_window_kwargs(),
        )
        self._active_proc = proc
        cur_pct = 15
        cur_stage = "Выполнение операции…"

        assert proc.stdout is not None
        for raw_line in proc.stdout:
            if self._cancel_event.is_set():
                proc.terminate()
                emit(cur_pct, "Операция остановлена пользователем", "Отправлена команда остановки.")
                return ("cancelled", -1)
            line = raw_line.rstrip()
            if not line:
                continue
            low = line.lower()
            for needle, pct, stage_ru in STAGE_PATTERNS:
                if needle in low:
                    cur_pct = max(cur_pct, pct)
                    cur_stage = stage_ru
                    break
            emit(cur_pct, cur_stage, line)

        rc = proc.wait()
        if self._cancel_event.is_set():
            return ("cancelled", -1)
        if rc == 0:
            emit(100, "Прошивка успешно завершена!", "Код возврата: 0")
            return ("success", 0)
        emit(cur_pct, f"Ошибка выполнения (код {rc})", f"Процесс завершился с кодом {rc}.")
        return ("failed", rc)

    # ---------------- Тестовая симуляция (только для автотестов pytest при dry_run=True) ----------------
    def _run_dry_simulation(
        self,
        cfg: FlashJobConfig,
        manifest: Any,
        emit: Callable[[int, str, str], None],
        *,
        step_delay: float = 0.05,
    ) -> tuple[str, int]:
        steps = [
            (25, "Проверка параметров устройства", "Тестовый прогон инициализирован."),
            (60, "Проверка компонентов прошивки", f"Сборка: {manifest.build_version if manifest else '—'}"),
            (100, "Проверка завершена", "Реальная запись не выполнялась (dry_run=True)."),
        ]
        for pct, title, detail in steps:
            if self._cancel_event.is_set():
                return ("cancelled", -1)
            if step_delay > 0:
                time.sleep(step_delay)
            emit(pct, title, detail)
        return ("success", 0)
