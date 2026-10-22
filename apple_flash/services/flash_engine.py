"""Движок перепрошивки и восстановления Apple Flash Studio.

Поддерживает:
- Безопасный режим репетиции (Dry-Run) с полной проверкой манифеста, совместимости и формированием точной команды.
- Реальный запуск через `idevicerestore` / `irecovery` / `ideviceenterrecovery` или `pymobiledevice3`
  без использования `shell=True`, с потоковым чтением лога, распознаванием этапов (0..100 %) и отменой.
"""

from __future__ import annotations

import importlib.util
import shlex
import shutil
import subprocess
import sys
import time
from collections.abc import Callable
from pathlib import Path

from apple_flash.core.errors import CompatibilityError, FlashExecutionError
from apple_flash.core.security import resolve_pmb3_command, windows_no_window_kwargs
from apple_flash.data.models import (
    FLASH_ACTION_LABELS,
    FlashJobConfig,
    FlashSessionRecord,
    IpswManifestInfo,
)
from apple_flash.data.store import StudioStore, now_iso
from apple_flash.services.compatibility import evaluate_compatibility
from apple_flash.services.ipsw_inspector import IpswInspector

ProgressCallback = Callable[[int, str], None]
LogCallback = Callable[[str], None]
CancelCheck = Callable[[], bool]

# Ключевые подстроки вывода idevicerestore / pymobiledevice3 -> (процент, этап на русском)
STAGE_MARKERS: tuple[tuple[str, int, str], ...] = (
    ("extracting buildmanifest", 8, "Чтение BuildManifest.plist…"),
    ("signing", 16, "Запрос цифровой подписи SHSH у сервера Apple TSS…"),
    ("tss", 18, "Получение билета авторизации ApTicket (TSS)…"),
    ("ibss", 26, "Отправка загрузчика iBSS по USB…"),
    ("ibec", 34, "Отправка загрузчика iBEC и переход в iBoot…"),
    ("ramdisk", 45, "Загрузка сервисного Restore Ramdisk в память устройства…"),
    ("kernelcache", 54, "Передача ядра KernelCache…"),
    ("filesystem", 68, "Запись системного образа ОС на флеш-накопитель NAND…"),
    ("sending rootfs", 70, "Запись корневой файловой системы…"),
    ("sep", 84, "Обновление прошивки сопроцессора безопасности SEP…"),
    ("baseband", 90, "Обновление прошивки модема сотовой связи (Baseband)…"),
    ("verifying restore", 95, "Финальная проверка разделов…"),
    ("done: restoring succeeded", 100, "Прошивка успешно завершена!"),
    ("restore succeeded", 100, "Восстановление успешно завершено!"),
)


class FlashEngine:
    def __init__(
        self,
        store: StudioStore,
        inspector: IpswInspector,
        default_tools_dir: Path | None = None,
    ) -> None:
        self.store = store
        self.inspector = inspector
        self.default_tools_dir = default_tools_dir

    def _find_tool(self, name: str, custom_dir: Path | None = None) -> str | None:
        exe = f"{name}.exe" if sys.platform == "win32" else name
        for folder in (custom_dir, self.default_tools_dir):
            if folder:
                for cand in (folder / exe, folder / name):
                    if cand.is_file():
                        return str(cand)
        return shutil.which(name)

    def _pmb3_base(self, custom_dir: Path | None = None) -> list[str]:
        found = resolve_pmb3_command(custom_dir or self.default_tools_dir)
        if found:
            return found
        return ["pymobiledevice3"]

    def _has_pymobiledevice3(self) -> bool:
        return resolve_pmb3_command(self.default_tools_dir) is not None

    def resolve_backend(self, requested: str, custom_dir: Path | None = None) -> str:
        if requested in {"idevicerestore", "pymobiledevice3"}:
            return requested
        if self._find_tool("idevicerestore", custom_dir):
            return "idevicerestore"
        if self._has_pymobiledevice3():
            return "pymobiledevice3"
        return "idevicerestore"

    def build_command(self, job: FlashJobConfig) -> tuple[str, list[str]]:
        """Формирует безопасный массив аргументов CLI для выбранной операции и бэкенда."""
        backend = self.resolve_backend(job.backend, job.custom_tools_dir)
        dev = job.device

        if job.action == "exit_recovery":
            if backend == "idevicerestore":
                irec = self._find_tool("irecovery", job.custom_tools_dir) or "irecovery"
                return backend, [irec, "-n"]
            base = self._pmb3_base(job.custom_tools_dir)
            return "pymobiledevice3", [*base, "restore", "exit-recovery"]

        if job.action == "enter_recovery":
            udid = (dev.udid or dev.uid) if dev else ""
            if backend == "idevicerestore":
                enter_bin = (
                    self._find_tool("ideviceenterrecovery", job.custom_tools_dir)
                    or "ideviceenterrecovery"
                )
                return backend, [enter_bin, udid] if udid else [enter_bin]
            base = self._pmb3_base(job.custom_tools_dir)
            cmd = [*base, "lockdown", "recovery"]
            if udid and not udid.startswith("ECID:"):
                cmd.extend(["--udid", udid])
            return "pymobiledevice3", cmd

        if not job.ipsw_path:
            raise FlashExecutionError("Не указан путь к локальному файлу прошивки .ipsw.")
        ipsw_str = str(job.ipsw_path.resolve())

        if backend == "idevicerestore":
            idr = self._find_tool("idevicerestore", job.custom_tools_dir) or "idevicerestore"
            cmd = [idr]
            if job.action == "erase":
                cmd.append("-e")
            if dev and dev.ecid:
                ecid_clean = dev.ecid.replace("ECID:", "").strip()
                cmd.extend(["-i", ecid_clean])
            elif dev and dev.udid:
                cmd.extend(["-u", dev.udid])
            if job.shsh_path:
                cmd.extend(["-T", str(job.shsh_path.resolve())])
            cmd.append(ipsw_str)
            return "idevicerestore", cmd

        # pymobiledevice3
        base = self._pmb3_base(job.custom_tools_dir)
        subcmd = "erase" if job.action == "erase" else "update"
        cmd = [*base, "restore", subcmd, "-i", ipsw_str]
        if dev and dev.ecid:
            ecid_clean = dev.ecid.replace("ECID:", "").strip()
            cmd.extend(["--ecid", ecid_clean])
        elif dev and dev.udid:
            cmd.extend(["--udid", dev.udid])
        return "pymobiledevice3", cmd

    @staticmethod
    def format_command(args: list[str]) -> str:
        if sys.platform == "win32":
            return subprocess.list2cmdline(args)
        return shlex.join(args)

    def execute(
        self,
        job: FlashJobConfig,
        *,
        progress_cb: ProgressCallback | None = None,
        log_cb: LogCallback | None = None,
        cancel_check: CancelCheck | None = None,
        dry_run_step_delay: float = 0.08,
    ) -> FlashSessionRecord:
        started_at = now_iso()
        lines: list[str] = []

        def emit(msg: str) -> None:
            stamp = time.strftime("%H:%M:%S")
            formatted = f"[{stamp}] {msg}"
            lines.append(formatted)
            if log_cb:
                log_cb(formatted)

        def report(pct: int, stage: str) -> None:
            if progress_cb:
                progress_cb(pct, stage)

        action_title = FLASH_ACTION_LABELS.get(job.action, job.action)
        emit(f"Операция: {action_title}")
        emit(f"Режим запуска: {'БЕЗОПАСНАЯ РЕПЕТИЦИЯ (Dry-Run)' if job.dry_run else 'БОЕВАЯ ПРОШИВКА УСТРОЙСТВА'}")

        manifest: IpswManifestInfo | None = None
        if job.action not in {"exit_recovery", "enter_recovery"}:
            if not job.ipsw_path:
                raise FlashExecutionError("Для операции перепрошивки необходимо выбрать файл .ipsw.")
            report(4, "Проверка структуры локального архива .ipsw…")
            manifest = self.inspector.inspect(job.ipsw_path)
            emit(
                f"Проверен IPSW: {manifest.file_name} · ОС {manifest.product_version} ({manifest.build_version})"
            )

        verdict = evaluate_compatibility(job.device, manifest, job.action)
        for detail in verdict.details:
            emit(f"Проверка совместимости: {detail}")
        if not verdict.can_proceed:
            emit(f"ОСТАНОВЛЕНО: {verdict.headline}")
            raise CompatibilityError(verdict.headline + "\n" + "\n".join(verdict.details))

        if not job.dry_run:
            if job.device is None:
                raise FlashExecutionError(
                    "Не обнаружено подключённое по USB устройство Apple. "
                    "Подключите устройство или включите режим Dry-Run."
                )
            if job.device.is_virtual:
                raise FlashExecutionError(
                    "Подключён виртуальный тестовый макет [МАКЕТ]. Реальная запись возможна только для физического устройства."
                )
            if manifest and manifest.is_demo_mockup:
                raise FlashExecutionError(
                    "Выбран демонстрационный макет прошивки (ДЕМО). Для реальной прошивки укажите настоящий файл .ipsw от Apple."
                )

        backend, cmd_args = self.build_command(job)
        cmd_str = self.format_command(cmd_args)
        emit(f"Выбран бэкенд: {backend}")
        emit(f"Команда CLI: {cmd_str}")

        dev_title = job.device.display_title if job.device else "Без устройства (проверка)"
        dev_uid = job.device.uid if job.device else "—"
        dev_pt = job.device.product_type if job.device else None
        dev_family = (
            job.device.family
            if job.device
            else (manifest.family if manifest else "unknown")
        )

        # ------------------------------- DRY-RUN -------------------------------
        if job.dry_run:
            dry_stages = self._build_dry_run_stages(job, manifest)
            for idx, (pct, stage_label, detail_line) in enumerate(dry_stages):
                if cancel_check and cancel_check():
                    emit("Операция Dry-Run отменена пользователем.")
                    return self.store.record_session(
                        FlashSessionRecord(
                            id=None,
                            started_at=started_at,
                            finished_at=now_iso(),
                            device_title=dev_title,
                            device_uid=dev_uid,
                            product_type=dev_pt,
                            family=dev_family,
                            action=job.action,
                            backend=backend,
                            ipsw_name=manifest.file_name if manifest else None,
                            ipsw_build=manifest.build_version if manifest else None,
                            dry_run=True,
                            status="cancelled",
                            exit_code=-1,
                            command_line=cmd_str,
                            log_text="\n".join(lines),
                        )
                    )
                report(pct, stage_label)
                emit(detail_line)
                if dry_run_step_delay > 0 and idx < len(dry_stages) - 1:
                    time.sleep(dry_run_step_delay)

            return self.store.record_session(
                FlashSessionRecord(
                    id=None,
                    started_at=started_at,
                    finished_at=now_iso(),
                    device_title=dev_title,
                    device_uid=dev_uid,
                    product_type=dev_pt,
                    family=dev_family,
                    action=job.action,
                    backend=backend,
                    ipsw_name=manifest.file_name if manifest else None,
                    ipsw_build=manifest.build_version if manifest else None,
                    dry_run=True,
                    status="success",
                    exit_code=0,
                    command_line=cmd_str,
                    log_text="\n".join(lines),
                )
            )

        # ---------------------------- БОЕВОЙ ЗАПУСК ----------------------------
        exe_check = cmd_args[0]
        if not Path(exe_check).is_file() and shutil.which(exe_check) is None:
            msg = (
                f"Исполняемый файл '{exe_check}' не найден. "
                "Откройте раздел «Драйверы и окружение» для установки pymobiledevice3 или idevicerestore."
            )
            emit(f"ОШИБКА: {msg}")
            rec = self.store.record_session(
                FlashSessionRecord(
                    id=None,
                    started_at=started_at,
                    finished_at=now_iso(),
                    device_title=dev_title,
                    device_uid=dev_uid,
                    product_type=dev_pt,
                    family=dev_family,
                    action=job.action,
                    backend=backend,
                    ipsw_name=manifest.file_name if manifest else None,
                    ipsw_build=manifest.build_version if manifest else None,
                    dry_run=False,
                    status="failed",
                    exit_code=127,
                    command_line=cmd_str,
                    log_text="\n".join(lines),
                )
            )
            raise FlashExecutionError(msg) from None

        report(10, "Запуск процесса прошивки…")
        status = "failed"
        exit_code = 1
        try:
            proc = subprocess.Popen(
                cmd_args,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
                **windows_no_window_kwargs(),
            )
            current_pct = 10
            assert proc.stdout is not None
            for raw_line in proc.stdout:
                if cancel_check and cancel_check():
                    proc.terminate()
                    emit("Получен сигнал отмены — процесс остановлен.")
                    status = "cancelled"
                    exit_code = -1
                    break
                clean_line = raw_line.rstrip()
                if not clean_line:
                    continue
                emit(clean_line)
                lower = clean_line.lower()
                for marker, pct, ru_stage in STAGE_MARKERS:
                    if marker in lower and pct >= current_pct:
                        current_pct = pct
                        report(current_pct, ru_stage)
                        break

            proc.wait(timeout=15)
            if status != "cancelled":
                exit_code = int(proc.returncode or 0)
                if exit_code == 0:
                    status = "success"
                    report(100, "Операция успешно завершена!")
                    emit("Процесс завершился со статусом 0 (Успешно).")
                else:
                    status = "failed"
                    emit(f"Процесс завершился с кодом ошибки {exit_code}.")
        except Exception as exc:
            emit(f"Исключение при выполнении процесса: {exc}")
            status = "failed"
            exit_code = 1

        return self.store.record_session(
            FlashSessionRecord(
                id=None,
                started_at=started_at,
                finished_at=now_iso(),
                device_title=dev_title,
                device_uid=dev_uid,
                product_type=dev_pt,
                family=dev_family,
                action=job.action,
                backend=backend,
                ipsw_name=manifest.file_name if manifest else None,
                ipsw_build=manifest.build_version if manifest else None,
                dry_run=False,
                status=status,
                exit_code=exit_code,
                command_line=cmd_str,
                log_text="\n".join(lines),
            )
        )

    @staticmethod
    def _build_dry_run_stages(
        job: FlashJobConfig, manifest: IpswManifestInfo | None
    ) -> list[tuple[int, str, str]]:
        if job.action in {"exit_recovery", "enter_recovery"}:
            return [
                (35, "Проверка канала USB / Lockdown…", "[Dry-Run] Канал связи проверен, аргументы валидны."),
                (100, "Репетиция завершена (без отправки команды в устройство)", "[Dry-Run] Готово к реальному выполнению."),
            ]
        assert manifest is not None
        return [
            (
                15,
                "Анализ BuildIdentities и выбор профиля платы…",
                f"[Dry-Run] Доступные конфигурации плат: {', '.join(manifest.board_configs) or 'универсальный профиль'}.",
            ),
            (
                35,
                "Проверка наличия загрузчиков iBSS / iBEC и ядра…",
                f"[Dry-Run] Проверено элементов в архиве IPSW: {manifest.zip_entries_count}, пропусков нет.",
            ),
            (
                60,
                "Проверка компонентов безопасности SEP и модема…",
                f"[Dry-Run] Наличие SEP: {'да' if manifest.has_sep else 'не требуется'} · "
                f"Модем Baseband: {'да' if manifest.has_baseband else 'Wi-Fi / Mac без модема'}.",
            ),
            (
                85,
                "Формирование сценария записи…",
                f"[Dry-Run] Режим записи: {FLASH_ACTION_LABELS.get(job.action, job.action)} — данные устройства НЕ затрагивались.",
            ),
            (
                100,
                "Репетиция Dry-Run успешно пройдена!",
                "[Dry-Run] Все предполётные проверки пройдены. Для реальной прошивки снимите флажок «Dry-Run».",
            ),
        ]
