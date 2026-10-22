"""Фоновые рабочие потоки QThread (автопоиск USB-устройств, расчёт SHA-256 и реальная прошивка)."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QThread, Signal

from apple_flash.core.security import compute_hashes
from apple_flash.data.models import FlashJobConfig
from apple_flash.services.device_detector import DeviceDetector
from apple_flash.services.flash_engine import FlashEngine


class DeviceScanWorker(QThread):
    """Неблокирующий фоновый опрос USB-шины Apple."""

    devices_ready = Signal(object)  # list[ConnectedDevice]

    def __init__(self, detector: DeviceDetector, parent=None) -> None:
        super().__init__(parent)
        self.detector = detector

    def run(self) -> None:
        try:
            devices = self.detector.scan_devices(include_virtual=False)
        except Exception:
            devices = []
        self.devices_ready.emit(devices)


class HashWorker(QThread):
    progress = Signal(int)
    finished_ok = Signal(str, str)  # sha256, sha1
    failed = Signal(str)

    def __init__(self, path: Path, parent=None) -> None:
        super().__init__(parent)
        self.path = path
        self._cancelled = False

    def cancel(self) -> None:
        self._cancelled = True

    def run(self) -> None:
        try:
            def _on_prog(done: int, total: int) -> None:
                pct = int(done * 100 / total) if total > 0 else 100
                self.progress.emit(pct)

            sha256, sha1 = compute_hashes(
                self.path,
                progress_cb=_on_prog,
                cancel_check=lambda: self._cancelled,
            )
            self.finished_ok.emit(sha256, sha1)
        except Exception as exc:
            self.failed.emit(str(exc))


class FlashWorker(QThread):
    progress = Signal(int, str)
    log_line = Signal(str)
    finished_session = Signal(object)  # FlashSessionRecord
    failed = Signal(str)

    def __init__(self, engine: FlashEngine, job: FlashJobConfig, parent=None) -> None:
        super().__init__(parent)
        self.engine = engine
        self.job = job
        self._cancelled = False

    def cancel(self) -> None:
        self._cancelled = True
        self.engine.request_cancel()

    def run(self) -> None:
        try:
            session = self.engine.execute(
                self.job,
                progress_cb=lambda pct, stage: self.progress.emit(pct, stage),
                log_cb=lambda line: self.log_line.emit(line),
                cancel_check=lambda: self._cancelled,
                dry_run_step_delay=0.05,
            )
            self.finished_session.emit(session)
        except Exception as exc:
            self.failed.emit(str(exc))
