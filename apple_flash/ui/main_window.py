"""Главное окно Apple Flash Studio."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence, QPixmap, QShortcut
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from apple_flash.data.models import ConnectedDevice, IpswRecord
from apple_flash.services.context import StudioContext
from apple_flash.ui.icon_gen import build_app_icon, render_app_image
from apple_flash.ui.pages.dashboard import DashboardPage
from apple_flash.ui.pages.dfu_guide import DfuGuidePage
from apple_flash.ui.pages.drivers_page import DriversPage
from apple_flash.ui.pages.flash_wizard import FlashWizardPage
from apple_flash.ui.pages.history_page import HistoryPage
from apple_flash.ui.pages.ipsw_library import IpswLibraryPage
from apple_flash.ui.pages.settings_page import SettingsPage
from apple_flash.ui.widgets import make_pill, set_pill
from apple_flash.version import APP_NAME, APP_VERSION

NAV_ROUTES = (
    ("dashboard", "Устройство", "◉"),
    ("flash", "Прошивка IPSW", "⚡"),
    ("library", "Библиотека IPSW", "▣"),
    ("dfu", "Мастер DFU / Recovery", "⏱"),
    ("drivers", "Драйверы Windows", "⚙"),
    ("history", "Журнал операций", "☰"),
)


class AppleFlashMainWindow(QMainWindow):
    def __init__(self, context: StudioContext) -> None:
        super().__init__()
        self.context = context
        self.connected_devices: list[ConnectedDevice] = []

        self.setWindowTitle(f"{APP_NAME} · v{APP_VERSION} (iPhone · iPad · MacBook)")
        self.setWindowIcon(build_app_icon())
        self.resize(1380, 860)
        self.setMinimumSize(1080, 700)

        root = QWidget(self)
        root.setObjectName("StudioRoot")
        self.setCentralWidget(root)
        h_layout = QHBoxLayout(root)
        h_layout.setContentsMargins(0, 0, 0, 0)
        h_layout.setSpacing(0)

        h_layout.addWidget(self._build_sidebar())

        right = QWidget(root)
        r_layout = QVBoxLayout(right)
        r_layout.setContentsMargins(0, 0, 0, 0)
        r_layout.setSpacing(0)
        r_layout.addWidget(self._build_topbar())

        self.stack = QStackedWidget(right)
        r_layout.addWidget(self.stack, 1)
        h_layout.addWidget(right, 1)

        self.pages: dict[str, QWidget] = {}
        self._register_pages()
        self._setup_statusbar()
        self._setup_shortcuts()

        self.refresh_devices(silent=True)
        self.navigate("dashboard")

    def _build_sidebar(self) -> QWidget:
        bar = QFrame(self)
        bar.setObjectName("Sidebar")
        bar.setFixedWidth(254)
        layout = QVBoxLayout(bar)
        layout.setContentsMargins(10, 14, 10, 10)
        layout.setSpacing(3)

        brand_row = QHBoxLayout()
        brand_row.setContentsMargins(6, 0, 6, 8)
        brand_row.setSpacing(10)
        logo = QLabel(bar)
        logo.setPixmap(QPixmap.fromImage(render_app_image(36)))
        brand_row.addWidget(logo)
        tbox = QVBoxLayout()
        tbox.setSpacing(0)
        t1 = QLabel("Apple Flash", bar)
        t1.setObjectName("AppTitle")
        t2 = QLabel("STUDIO · WINDOWS", bar)
        t2.setObjectName("AppSub")
        tbox.addWidget(t1)
        tbox.addWidget(t2)
        brand_row.addLayout(tbox)
        brand_row.addStretch(1)
        layout.addLayout(brand_row)

        sec = QLabel("РАБОЧАЯ СТАНЦИЯ", bar)
        sec.setObjectName("NavHeader")
        layout.addWidget(sec)

        self.nav_buttons: dict[str, QPushButton] = {}
        for key, label, icon in NAV_ROUTES:
            btn = QPushButton(f"  {icon}   {label}", bar)
            btn.setObjectName("NavBtn")
            btn.setCheckable(True)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setMinimumHeight(38)
            btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            btn.clicked.connect(lambda _c=False, k=key: self.navigate(k))
            self.nav_buttons[key] = btn
            layout.addWidget(btn)

        sec2 = QLabel("СИСТЕМА", bar)
        sec2.setObjectName("NavHeader")
        layout.addWidget(sec2)
        set_btn = QPushButton("  ☰   Настройки", bar)
        set_btn.setObjectName("NavBtn")
        set_btn.setCheckable(True)
        set_btn.setCursor(Qt.PointingHandCursor)
        set_btn.setMinimumHeight(38)
        set_btn.clicked.connect(lambda: self.navigate("settings"))
        self.nav_buttons["settings"] = set_btn
        layout.addWidget(set_btn)

        layout.addStretch(1)

        offline_box = QLabel(
            "Офлайн-режим библиотеки IPSW\niPhone · iPad · MacBook M1–M4 / T2",
            bar,
        )
        offline_box.setObjectName("Dim")
        offline_box.setWordWrap(True)
        offline_box.setContentsMargins(8, 4, 8, 4)
        layout.addWidget(offline_box)

        ver = QLabel(f"v{APP_VERSION} · PySide6 · SQLite", bar)
        ver.setObjectName("Dim")
        ver.setContentsMargins(8, 2, 8, 2)
        layout.addWidget(ver)
        return bar

    def _build_topbar(self) -> QWidget:
        top = QFrame(self)
        top.setObjectName("TopBar")
        top.setFixedHeight(58)
        layout = QHBoxLayout(top)
        layout.setContentsMargins(20, 8, 20, 8)
        layout.setSpacing(10)

        self.usb_pill = make_pill("USB: нет устройств", "neutral", top)
        layout.addWidget(self.usb_pill)

        scan_btn = QPushButton("Сканировать USB", top)
        scan_btn.setObjectName("Ghost")
        scan_btn.clicked.connect(self.refresh_devices)
        layout.addWidget(scan_btn)

        layout.addStretch(1)

        bench_lbl = QLabel("Тестовый стенд:", top)
        bench_lbl.setObjectName("Dim")
        layout.addWidget(bench_lbl)

        self.virtual_combo = QComboBox(top)
        self.virtual_combo.addItem("Отключён (только реальный USB)", None)
        self.virtual_combo.addItem("[МАКЕТ] iPhone 15 Pro · Normal", "iphone_normal")
        self.virtual_combo.addItem("[МАКЕТ] iPad Pro 11\" M4 · Recovery", "ipad_recovery")
        self.virtual_combo.addItem("[МАКЕТ] MacBook Pro 14\" M3 · DFU", "macbook_dfu")
        self.virtual_combo.currentIndexChanged.connect(self._on_virtual_changed)
        layout.addWidget(self.virtual_combo)

        add_ipsw_btn = QPushButton("+ Файл .ipsw", top)
        add_ipsw_btn.setObjectName("Primary")
        add_ipsw_btn.clicked.connect(self._quick_add_ipsw)
        layout.addWidget(add_ipsw_btn)
        return top

    def _register_pages(self) -> None:
        self.dashboard_page = DashboardPage(self.context, self)
        self.flash_page = FlashWizardPage(self.context, self)
        self.library_page = IpswLibraryPage(self.context, self)
        self.dfu_page = DfuGuidePage(self.context, self)
        self.drivers_page = DriversPage(self.context, self)
        self.history_page = HistoryPage(self.context, self)
        self.settings_page = SettingsPage(self.context, self)

        for key, widget in (
            ("dashboard", self.dashboard_page),
            ("flash", self.flash_page),
            ("library", self.library_page),
            ("dfu", self.dfu_page),
            ("drivers", self.drivers_page),
            ("history", self.history_page),
            ("settings", self.settings_page),
        ):
            self.pages[key] = widget
            self.stack.addWidget(widget)

    def _setup_statusbar(self) -> None:
        sb = self.statusBar()
        sb.setSizeGripEnabled(False)
        self._status_lbl = QLabel("Готово к работе", self)
        sb.addWidget(self._status_lbl, 1)
        sb.addPermanentWidget(make_pill("Локальные .ipsw · без облака", "info", self))

    def _setup_shortcuts(self) -> None:
        QShortcut(QKeySequence("F5"), self, activated=self.refresh_devices)
        QShortcut(QKeySequence("Ctrl+O"), self, activated=self._quick_add_ipsw)

    # ------------------------------------------------------------------ Навигация и действия
    def navigate(self, key: str) -> None:
        page = self.pages.get(key)
        if not page:
            return
        self.stack.setCurrentWidget(page)
        for k, btn in self.nav_buttons.items():
            btn.setChecked(k == key)
        if hasattr(page, "on_show"):
            page.on_show()  # type: ignore[attr-defined]

    def open_flash_for_device(self, device: ConnectedDevice) -> None:
        self.navigate("flash")
        self.flash_page.preselect_device(device)

    def open_flash_for_ipsw(self, record: IpswRecord) -> None:
        self.navigate("flash")
        self.flash_page.preselect_ipsw(record)

    def open_dfu_guide(self, proc_key: str) -> None:
        self.navigate("dfu")
        self.dfu_page.select_procedure(proc_key)

    def select_virtual_preset(self, preset_key: str | None) -> None:
        idx = self.virtual_combo.findData(preset_key)
        if idx >= 0:
            self.virtual_combo.setCurrentIndex(idx)

    def _on_virtual_changed(self) -> None:
        key = self.virtual_combo.currentData()
        self.context.detector.set_virtual_device(key)
        self.refresh_devices()

    def _quick_add_ipsw(self) -> None:
        self.navigate("library")
        self.library_page.add_ipsw_dialog()

    def refresh_devices(self, *, silent: bool = False) -> None:
        self.connected_devices = self.context.detector.scan()
        if self.connected_devices:
            first = self.connected_devices[0]
            tone = "warning" if first.is_virtual else "ok"
            extra = f" (+{len(self.connected_devices) - 1})" if len(self.connected_devices) > 1 else ""
            set_pill(self.usb_pill, f"USB: {first.display_title} · {first.mode.upper()}{extra}", tone)
            if not silent:
                self.set_status(f"Обнаружено устройств Apple: {len(self.connected_devices)}")
        else:
            set_pill(self.usb_pill, "USB: устройства Apple не подключены", "neutral")
            if not silent:
                self.set_status("Шина USB просканирована — активных устройств Apple не найдено")

        current = self.stack.currentWidget()
        if current and hasattr(current, "on_show"):
            current.on_show()  # type: ignore[attr-defined]

    def set_status(self, message: str) -> None:
        self._status_lbl.setText(message)

    def closeEvent(self, event) -> None:  # noqa: N802
        self.context.close()
        super().closeEvent(event)
