"""Главное окно приложения: компактная навигация, рабочая область, статус-бар."""

from __future__ import annotations

import logging
from typing import Callable

from PySide6.QtCore import QSize, Qt, QTimer
from PySide6.QtGui import QAction, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMenu,
    QPushButton,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from repair_os.core.i18n import tr
from repair_os.services.context import AppContext
from repair_os.ui.pages.boardview import BoardViewPage
from repair_os.ui.pages.catalog import CatalogPage
from repair_os.ui.pages.device_detail import DeviceDetailPage
from repair_os.ui.pages.firmware import FirmwarePage
from repair_os.ui.pages.home import HomePage
from repair_os.ui.pages.library import LibraryPage
from repair_os.ui.pages.search_results import SearchResultsPage
from repair_os.ui.pages.settings_page import SettingsPage
from repair_os.ui.theme import COLORS
from repair_os.ui.widgets import LogoMark, SearchInput, badge
from repair_os.version import APP_VERSION

log = logging.getLogger(__name__)

NAV_ITEMS = [
    ("home", "Главная", "⌂"),
    ("catalog", "Каталог устройств", "▤"),
    ("boardview", "3D BoardView", "◈"),
    ("firmware", "Firmware Center", "⇩"),
    ("library", "Technical Library", "▣"),
]


class NavButton(QPushButton):
    def __init__(self, key: str, label: str, icon: str, parent: QWidget | None = None) -> None:
        super().__init__(f"  {icon}   {label}", parent)
        self.key = key
        self.setObjectName("NavButton")
        self.setCheckable(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setMinimumHeight(38)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)


class MainWindow(QMainWindow):
    def __init__(self, context: AppContext) -> None:
        super().__init__()
        self.context = context
        self.setWindowTitle(f"Smartphone Repair OS · {APP_VERSION}")
        self.resize(1440, 900)
        self.setMinimumSize(1100, 700)

        root = QWidget(self)
        root.setObjectName("Root")
        self.setCentralWidget(root)
        layout = QHBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        layout.addWidget(self._build_sidebar())

        right = QWidget(root)
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)
        right_layout.addWidget(self._build_topbar())

        self.stack = QStackedWidget(right)
        right_layout.addWidget(self.stack, 1)
        layout.addWidget(right, 1)

        self.pages: dict[str, QWidget] = {}
        self._register_pages()
        self._build_status_bar()
        self._install_shortcuts()
        self._update_nav("home")
        self.set_status("Готово")
        QTimer.singleShot(0, self._announce_demo)

    # ------------------------------------------------------------------ построение
    def _build_sidebar(self) -> QWidget:
        sidebar = QFrame(self)
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(218)
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(0, 14, 0, 8)
        layout.setSpacing(2)

        header = QWidget(sidebar)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(14, 0, 12, 6)
        header_layout.setSpacing(10)
        header_layout.addWidget(LogoMark(32, header))
        text_box = QVBoxLayout()
        text_box.setSpacing(0)
        brand = QLabel("Smartphone", header)
        brand.setObjectName("BrandMark")
        brand_sub = QLabel("REPAIR OS", header)
        brand_sub.setObjectName("BrandSub")
        text_box.addWidget(brand)
        text_box.addWidget(brand_sub)
        header_layout.addLayout(text_box)
        header_layout.addStretch(1)
        layout.addWidget(header)

        section = QLabel("РАБОЧЕЕ ПРОСТРАНСТВО", sidebar)
        section.setObjectName("NavSection")
        layout.addWidget(section)

        self.nav_buttons: dict[str, NavButton] = {}
        for key, label, icon in NAV_ITEMS:
            button = NavButton(key, tr(f"nav.{key}", default=label), icon, sidebar)
            button.clicked.connect(lambda _checked=False, page_key=key: self.navigate(page_key))
            self.nav_buttons[key] = button
            layout.addWidget(button)
            layout.setContentsMargins(8, layout.contentsMargins().top(), 8, layout.contentsMargins().bottom())

        section2 = QLabel("СИСТЕМА", sidebar)
        section2.setObjectName("NavSection")
        layout.addWidget(section2)
        settings_button = NavButton("settings", tr("nav.settings", default="Настройки"), "⚙", sidebar)
        settings_button.clicked.connect(lambda: self.navigate("settings"))
        self.nav_buttons["settings"] = settings_button
        layout.addWidget(settings_button)

        layout.addStretch(1)

        demo_box = QWidget(sidebar)
        demo_layout = QVBoxLayout(demo_box)
        demo_layout.setContentsMargins(14, 0, 14, 6)
        demo_layout.setSpacing(4)
        counts = self.context.demo_counts()
        demo_badge = badge("ДЕМО-ДАННЫЕ", "demo", demo_box)
        demo_layout.addWidget(demo_badge)
        demo_hint = QLabel(
            f"{counts.get('devices', 0)} демо-устройств · {counts.get('firmware', 0)} прошивок\n"
            "не являются проверенными",
            demo_box,
        )
        demo_hint.setObjectName("Dim")
        demo_hint.setWordWrap(True)
        demo_layout.addWidget(demo_hint)
        layout.addWidget(demo_box)

        version = QLabel(f"v{APP_VERSION} · SQLite · PySide6", sidebar)
        version.setObjectName("VersionLabel")
        layout.addWidget(version)
        return sidebar

    def _build_topbar(self) -> QWidget:
        bar = QFrame(self)
        bar.setFixedHeight(64)
        bar.setStyleSheet(
            f"QFrame {{ background-color: {COLORS['bg_alt']}; border-bottom: 1px solid {COLORS['border']}; }}"
        )
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(20, 10, 20, 10)
        layout.setSpacing(10)

        self.search = SearchInput("Поиск по бренду, названию и точному коду модели…", bar)
        self.search.setMinimumWidth(320)
        self.search.setMaximumWidth(640)
        self.search.returnPressed.connect(self._on_global_search)
        layout.addWidget(self.search, 1)

        import_button = QPushButton("Импорт", bar)
        import_button.setObjectName("Ghost")
        import_button.setCursor(Qt.PointingHandCursor)
        menu = QMenu(import_button)
        menu.addAction("Устройства (CSV/JSON)…", lambda: self.run_import("devices"))
        menu.addAction("Прошивки (CSV/JSON)…", lambda: self.run_import("firmware"))
        menu.addAction("Материалы библиотеки (CSV/JSON)…", lambda: self.run_import("documents"))
        menu.addSeparator()
        menu.addAction("Пакет BoardView (JSON/ZIP)…", self.run_board_import)
        menu.addSeparator()
        menu.addAction("Скачать шаблоны CSV…", self.download_templates)
        import_button.setMenu(menu)
        layout.addWidget(import_button)

        backup_button = QPushButton("Резервная копия", bar)
        backup_button.setObjectName("Ghost")
        backup_button.setCursor(Qt.PointingHandCursor)
        backup_menu = QMenu(backup_button)
        backup_menu.addAction("Создать копию", self.create_backup)
        backup_menu.addAction("Восстановить из копии…", self.restore_backup)
        backup_button.setMenu(backup_menu)
        layout.addWidget(backup_button)

        add_button = QPushButton("+ Устройство", bar)
        add_button.setObjectName("Primary")
        add_button.setCursor(Qt.PointingHandCursor)
        add_button.clicked.connect(self.add_device)
        layout.addWidget(add_button)
        return bar

    def _register_pages(self) -> None:
        self.home_page = HomePage(self.context, self)
        self.catalog_page = CatalogPage(self.context, self)
        self.device_page = DeviceDetailPage(self.context, self)
        self.board_page = BoardViewPage(self.context, self)
        self.firmware_page = FirmwarePage(self.context, self)
        self.library_page = LibraryPage(self.context, self)
        self.search_page = SearchResultsPage(self.context, self)
        self.settings_page = SettingsPage(self.context, self)

        for key, page in (
            ("home", self.home_page),
            ("catalog", self.catalog_page),
            ("device", self.device_page),
            ("boardview", self.board_page),
            ("firmware", self.firmware_page),
            ("library", self.library_page),
            ("search", self.search_page),
            ("settings", self.settings_page),
        ):
            self.pages[key] = page
            self.stack.addWidget(page)
            page_key = "catalog" if key == "device" else key
            setattr(page, "route_key", page_key)

    def _build_status_bar(self) -> None:
        status = self.statusBar()
        status.setSizeGripEnabled(False)
        self._status_label = QLabel("Готово", self)
        status.addWidget(self._status_label, 1)
        self._db_label = QLabel(
            f"База: {self.context.devices.count()} устройств · {self.context.brands.count()} брендов",
            self,
        )
        self._db_label.setObjectName("Dim")
        status.addPermanentWidget(self._db_label)
        status.addPermanentWidget(badge("Локальный режим · офлайн", "info", self))
        _ = self.context

    def _install_shortcuts(self) -> None:
        QShortcut(QKeySequence("Ctrl+K"), self, activated=self.focus_search)
        QShortcut(QKeySequence("Ctrl+N"), self, activated=self.add_device)
        QShortcut(QKeySequence("Ctrl+B"), self, activated=self.create_backup)
        QShortcut(QKeySequence("F5"), self, activated=self.refresh_current)

    # ------------------------------------------------------------------ навигация
    def navigate(self, key: str, *, refresh: bool = True) -> None:
        page = self.pages.get(key)
        if page is None:
            log.warning("Неизвестная страница: %s", key)
            return
        self.stack.setCurrentWidget(page)
        self._update_nav(key)
        if refresh and hasattr(page, "on_show"):
            try:
                page.on_show()  # type: ignore[attr-defined]
            except Exception:  # pragma: no cover - страница не должна ломать навигацию
                log.exception("Ошибка обновления страницы %s", key)
        self._update_db_label()

    def _update_nav(self, key: str) -> None:
        route = "catalog" if key == "device" else key
        for nav_key, button in self.nav_buttons.items():
            button.setChecked(nav_key == route)

    def _update_db_label(self) -> None:
        self._db_label.setText(
            f"База: {self.context.devices.count()} устройств · "
            f"{self.context.brands.count()} брендов · "
            f"{self.context.db.table_count('firmware')} прошивок"
        )

    def open_device(self, device_id: int) -> None:
        try:
            self.context.devices.record_open(device_id)
        except Exception:  # pragma: no cover
            log.exception("Не удалось обновить историю")
        self.device_page.load(device_id)
        self.navigate("device", refresh=False)

    def open_board(self, board_model_id: int | None) -> None:
        self.board_page.select_board(board_model_id)
        self.navigate("boardview", refresh=False)

    def open_firmware(self, firmware_id: int | None) -> None:
        self.firmware_page.focus_firmware(firmware_id)
        self.navigate("firmware", refresh=False)

    def open_document(self, document_id: int | None) -> None:
        self.library_page.focus_document(document_id)
        self.navigate("library", refresh=False)

    def show_search(self, query: str) -> None:
        self.search.setText(query)
        self.search_page.run_search(query)
        self.navigate("search", refresh=False)

    def refresh_current(self) -> None:
        page = self.stack.currentWidget()
        if hasattr(page, "on_show"):
            page.on_show()  # type: ignore[attr-defined]
        self._update_db_label()
        self.set_status("Данные обновлены")

    def focus_search(self) -> None:
        self.search.setFocus()
        self.search.selectAll()

    def _on_global_search(self) -> None:
        query = self.search.text().strip()
        if query:
            self.show_search(query)

    # ------------------------------------------------------------------ действия
    def set_status(self, message: str) -> None:
        self._status_label.setText(message)

    def _announce_demo(self) -> None:
        counts = self.context.demo_counts()
        if counts.get("devices"):
            self.set_status(
                "Загружены демонстрационные данные — они помечены как ДЕМО и не являются проверенными."
            )

    def add_device(self) -> None:
        from repair_os.ui.dialogs.device_editor import DeviceEditorDialog

        dialog = DeviceEditorDialog(self.context, parent=self)
        if dialog.exec():
            saved = dialog.result_device
            self.refresh_after_change()
            if saved and saved.id:
                self.open_device(saved.id)
            self.set_status("Устройство сохранено")

    def run_import(self, kind: str) -> None:
        from repair_os.ui.dialogs.import_dialog import ImportDialog

        dialog = ImportDialog(self.context, kind=kind, parent=self)
        dialog.exec()
        self.refresh_after_change()

    def run_board_import(self) -> None:
        from repair_os.ui.dialogs.import_dialog import BoardImportDialog

        dialog = BoardImportDialog(self.context, parent=self)
        if dialog.exec():
            self.refresh_after_change()
            if dialog.imported_board_id:
                self.open_board(dialog.imported_board_id)

    def download_templates(self) -> None:
        from PySide6.QtWidgets import QFileDialog

        from repair_os.services.import_export import install_sample_files
        from repair_os.ui.dialogs.base import info

        directory = QFileDialog.getExistingDirectory(self, "Каталог для шаблонов")
        if not directory:
            return
        try:
            files = install_sample_files(__import__("pathlib").Path(directory))
        except Exception as exc:  # pragma: no cover
            info(self, "Ошибка", str(exc))
            return
        info(self, "Шаблоны сохранены", "\n".join(str(path) for path in files))

    def create_backup(self) -> None:
        from repair_os.ui.dialogs.backup_dialog import BackupDialog

        dialog = BackupDialog(self.context, parent=self)
        dialog.exec()

    def restore_backup(self) -> None:
        from repair_os.ui.dialogs.backup_dialog import RestoreDialog

        dialog = RestoreDialog(self.context, parent=self)
        if dialog.exec():
            self.refresh_after_change()
            self.set_status("База восстановлена из резервной копии")

    def refresh_after_change(self) -> None:
        for page in self.pages.values():
            if hasattr(page, "on_show"):
                try:
                    page.on_show()  # type: ignore[attr-defined]
                except Exception:  # pragma: no cover
                    log.exception("Ошибка обновления страницы после изменения данных")
        self._update_db_label()

    def closeEvent(self, event) -> None:  # noqa: N802
        try:
            self.context.settings.set("window_geometry", self.saveGeometry().toHex().data().decode())
            self.context.close()
        except Exception:  # pragma: no cover
            log.exception("Ошибка при закрытии приложения")
        super().closeEvent(event)


def _unused(action: QAction) -> None:  # pragma: no cover
    _ = action


AddDeviceCallback = Callable[[], None]
