"""Главное окно Apple Flash Studio v2.0: лаконичный интерфейс, автопоиск USB каждые 2.5 сек и Drag & Drop .ipsw."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QDragEnterEvent, QDropEvent, QKeySequence, QPixmap, QShortcut
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from apple_flash.data.models import ConnectedDevice, IpswRecord
from apple_flash.services.context import StudioContext
from apple_flash.ui.icon_gen import build_app_icon, render_app_image
from apple_flash.ui.pages.dfu_guide import DfuGuidePage
from apple_flash.ui.pages.drivers_page import DriversPage
from apple_flash.ui.pages.flash_home import FlashHomePage
from apple_flash.ui.pages.history_page import HistoryPage
from apple_flash.ui.widgets import make_pill, set_pill
from apple_flash.ui.workers import DeviceScanWorker
from apple_flash.version import APP_NAME, APP_VERSION

NAV_TABS = (
    ("flash", "⚡ Прошивка"),
    ("dfu", "◉ Recovery и DFU"),
    ("drivers", "⚙ Драйверы и USB"),
    ("history", "☰ Журнал"),
)


class AppleFlashMainWindow(QMainWindow):
    def __init__(self, context: StudioContext, *, enable_auto_poll: bool = True) -> None:
        super().__init__()
        self.context = context
        self.connected_devices: list[ConnectedDevice] = []
        self._last_usb_signature: tuple[tuple[str, ...], ...] | None = None
        self._scan_worker: DeviceScanWorker | None = None

        self.setWindowTitle(f"{APP_NAME} v{APP_VERSION} — Прошивка iPhone, iPad и MacBook")
        self.setWindowIcon(build_app_icon())
        self.resize(1280, 820)
        self.setMinimumSize(1020, 680)
        self.setAcceptDrops(True)

        root = QWidget(self)
        root.setObjectName("StudioRoot")
        self.setCentralWidget(root)
        v_layout = QVBoxLayout(root)
        v_layout.setContentsMargins(0, 0, 0, 0)
        v_layout.setSpacing(0)

        v_layout.addWidget(self._build_topbar())

        self.stack = QStackedWidget(root)
        v_layout.addWidget(self.stack, 1)

        self.pages: dict[str, QWidget] = {}
        self._register_pages()
        self._setup_statusbar()
        self._setup_shortcuts()

        # Первый синхронный опрос USB при открытии + фоновый таймер автообнаружения каждые 2.5 сек
        self.refresh_devices(silent=True)
        self.navigate("flash")

        self._poll_timer = QTimer(self)
        self._poll_timer.setInterval(2500)
        self._poll_timer.timeout.connect(self._on_auto_poll_tick)
        if enable_auto_poll:
            self._poll_timer.start()

    def _build_topbar(self) -> QWidget:
        top = QFrame(self)
        top.setObjectName("TopBar")
        top.setFixedHeight(62)
        layout = QHBoxLayout(top)
        layout.setContentsMargins(18, 8, 18, 8)
        layout.setSpacing(8)

        # Логотип и название
        logo = QLabel(top)
        logo.setPixmap(QPixmap.fromImage(render_app_image(34)))
        layout.addWidget(logo)

        title_col = QVBoxLayout()
        title_col.setSpacing(0)
        t1 = QLabel("Apple Flash Studio", top)
        t1.setObjectName("AppTitle")
        t2 = QLabel(f"v{APP_VERSION} · WINDOWS USB", top)
        t2.setObjectName("AppSub")
        title_col.addWidget(t1)
        title_col.addWidget(t2)
        layout.addLayout(title_col)
        layout.addSpacing(14)

        # 4 простые и понятные вкладки
        self.nav_buttons: dict[str, QPushButton] = {}
        for key, label in NAV_TABS:
            btn = QPushButton(label, top)
            btn.setObjectName("NavTab")
            btn.setCheckable(True)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setMinimumHeight(38)
            btn.clicked.connect(lambda _c=False, k=key: self.navigate(k))
            self.nav_buttons[key] = btn
            layout.addWidget(btn)

        layout.addStretch(1)

        # Индикатор живого подключения USB + кнопка принудительного опроса
        self.usb_pill = make_pill("Ожидание USB…", "neutral", top)
        layout.addWidget(self.usb_pill)

        scan_btn = QPushButton("↻ Обновить USB", top)
        scan_btn.setObjectName("Ghost")
        scan_btn.setCursor(Qt.PointingHandCursor)
        scan_btn.clicked.connect(lambda: self.refresh_devices(silent=False))
        layout.addWidget(scan_btn)

        return top

    def _register_pages(self) -> None:
        self.flash_page = FlashHomePage(self.context, self)
        self.dfu_page = DfuGuidePage(self.context, self)
        self.drivers_page = DriversPage(self.context, self)
        self.history_page = HistoryPage(self.context, self)

        for key, widget in (
            ("flash", self.flash_page),
            ("dfu", self.dfu_page),
            ("drivers", self.drivers_page),
            ("history", self.history_page),
        ):
            self.pages[key] = widget
            self.stack.addWidget(widget)

    def _setup_statusbar(self) -> None:
        sb = self.statusBar()
        sb.setSizeGripEnabled(False)
        self._status_lbl = QLabel("Автоматический поиск USB-устройств Apple активен", self)
        sb.addWidget(self._status_lbl, 1)
        sb.addPermanentWidget(
            make_pill("Встроенный движок pymobiledevice3 + libusb", "info", self)
        )

    def _setup_shortcuts(self) -> None:
        QShortcut(QKeySequence("F5"), self, activated=self.refresh_devices)
        QShortcut(
            QKeySequence("Ctrl+O"),
            self,
            activated=lambda: self.flash_page.browse_ipsw_file(),
        )

    # ------------------------------------------------------------------ Drag & Drop файла .ipsw
    def dragEnterEvent(self, event: QDragEnterEvent) -> None:  # noqa: N802
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                if url.isLocalFile() and url.toLocalFile().lower().endswith(".ipsw"):
                    event.acceptProposedAction()
                    return
        event.ignore()

    def dropEvent(self, event: QDropEvent) -> None:  # noqa: N802
        for url in event.mimeData().urls():
            if url.isLocalFile() and url.toLocalFile().lower().endswith(".ipsw"):
                self.navigate("flash")
                self.flash_page.load_ipsw_path(Path(url.toLocalFile()))
                event.acceptProposedAction()
                return

    # ------------------------------------------------------------------ Навигация
    def navigate(self, key: str) -> None:
        page = self.pages.get(key)
        if not page:
            return
        self.stack.setCurrentWidget(page)
        for k, btn in self.nav_buttons.items():
            btn.setChecked(k == key)
        if hasattr(page, "on_show"):
            page.on_show()  # type: ignore[attr-defined]

    def open_flash_for_ipsw(self, record: IpswRecord) -> None:
        self.navigate("flash")
        self.flash_page.select_ipsw_record(record)

    def open_dfu_guide(self, proc_key: str) -> None:
        self.navigate("dfu")
        self.dfu_page.select_procedure(proc_key)

    # ------------------------------------------------------------------ Автопоиск USB
    @staticmethod
    def _devices_signature(devs: list[ConnectedDevice]) -> tuple[tuple[str, ...], ...]:
        return tuple(
            (
                d.uid,
                d.mode,
                d.product_type or "",
                d.os_version or "",
                d.usb_driver or "",
                d.driver_warning or "",
            )
            for d in devs
        )

    def _on_auto_poll_tick(self) -> None:
        # Не трогаем USB во время активной прошивки, чтобы не мешать перезагрузкам iBoot/ASR!
        if self.flash_page.is_busy:
            return
        if self._scan_worker is not None and self._scan_worker.isRunning():
            return
        self._scan_worker = DeviceScanWorker(self.context.detector, self)
        self._scan_worker.devices_ready.connect(self._on_bg_devices_ready)
        self._scan_worker.start()

    def _on_bg_devices_ready(self, devs: list[ConnectedDevice]) -> None:
        if self.flash_page.is_busy:
            return
        sig = self._devices_signature(devs)
        if sig != self._last_usb_signature:
            self._apply_scanned_devices(devs, silent=False)

    def refresh_devices(self, *, silent: bool = False) -> None:
        if self.flash_page.is_busy:
            return
        devs = self.context.detector.scan_devices(include_virtual=False)
        self._apply_scanned_devices(devs, silent=silent)

    def set_mock_devices_for_preview(self, devs: list[ConnectedDevice]) -> None:
        """Используется только для генерации скриншотов документации и в модульных UI-тестах."""
        self._poll_timer.stop()
        self._apply_scanned_devices(devs, silent=True)

    def _apply_scanned_devices(
        self, devs: list[ConnectedDevice], *, silent: bool = False
    ) -> None:
        self.connected_devices = devs
        self._last_usb_signature = self._devices_signature(devs)

        if devs:
            first = devs[0]
            tone = "warning" if first.driver_warning else "ok"
            extra = f" (+{len(devs) - 1})" if len(devs) > 1 else ""
            set_pill(self.usb_pill, f"● {first.display_title}{extra}", tone)
            if not silent:
                self.set_status(
                    f"Подключено устройство: {first.display_title} ({first.mode_label})"
                )
        else:
            set_pill(self.usb_pill, "USB не подключён", "neutral")
            if not silent:
                self.set_status("Устройства Apple на шине USB не обнаружены — ожидание подключения…")

        self.flash_page.update_devices_view()
        if self.stack.currentWidget() is self.drivers_page:
            self.drivers_page.on_show()

    def set_status(self, message: str) -> None:
        self._status_lbl.setText(message)

    def closeEvent(self, event) -> None:  # noqa: N802
        self._poll_timer.stop()
        if self._scan_worker is not None and self._scan_worker.isRunning():
            self._scan_worker.wait(800)
        self.context.close()
        super().closeEvent(event)
