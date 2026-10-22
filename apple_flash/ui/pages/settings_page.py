"""Настройки Apple Flash Studio: пути к утилитам, бэкенд по умолчанию и управление ДЕМО-макетами."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from apple_flash.services.context import StudioContext
from apple_flash.ui.widgets import StudioCard, kv_row, make_muted, make_title


class SettingsPage(QWidget):
    def __init__(self, context: StudioContext, window) -> None:
        super().__init__()
        self.context = context
        self.window = window

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        outer.addWidget(scroll)

        content = QWidget(scroll)
        scroll.setWidget(content)
        layout = QVBoxLayout(content)
        layout.setSizeConstraint(QVBoxLayout.SetMinAndMaxSize)
        layout.setContentsMargins(22, 16, 22, 16)
        layout.setSpacing(12)

        layout.addWidget(make_title("Настройки рабочей станции", object_name="PageTitle"))
        layout.addWidget(
            make_muted("Локальное хранение без облака и телеметрии. Все пути находятся под контролем мастера.")
        )

        # Пути и движок
        tools_card = StudioCard(content)
        tb = tools_card.body()
        tb.addWidget(make_title("CLI-инструменты прошивки на Windows"))
        tb.addWidget(
            make_muted(
                "Укажите каталог, где лежат idevicerestore.exe, irecovery.exe и ideviceinfo.exe "
                "(по умолчанию используется папка tools внутри каталога данных приложения)."
            )
        )
        t_row = QHBoxLayout()
        self.tools_edit = QLineEdit(tools_card)
        t_row.addWidget(self.tools_edit, 1)
        browse_btn = QPushButton("Обзор…", tools_card)
        browse_btn.clicked.connect(self._browse_tools)
        save_btn = QPushButton("Сохранить", tools_card)
        save_btn.setObjectName("Primary")
        save_btn.clicked.connect(self._save_settings)
        t_row.addWidget(browse_btn)
        t_row.addWidget(save_btn)
        tb.addLayout(t_row)

        b_row = QHBoxLayout()
        b_row.addWidget(make_muted("Предпочитаемый движок по умолчанию:", tools_card))
        self.pref_backend = QComboBox(tools_card)
        self.pref_backend.addItem("Автоматически (idevicerestore → pymobiledevice3)", "auto")
        self.pref_backend.addItem("pymobiledevice3", "pymobiledevice3")
        self.pref_backend.addItem("idevicerestore (libimobiledevice)", "idevicerestore")
        self.pref_backend.currentIndexChanged.connect(self._save_backend_pref)
        b_row.addWidget(self.pref_backend, 1)
        tb.addLayout(b_row)
        layout.addWidget(tools_card)

        # Каталоги данных
        dirs_card = StudioCard(content)
        db = dirs_card.body()
        db.addWidget(make_title("Локальные каталоги данных"))
        db.addWidget(kv_row("Корень данных:", str(self.context.paths.root), dirs_card))
        db.addWidget(kv_row("База SQLite:", str(self.context.paths.db_file), dirs_card))
        db.addWidget(kv_row("Папка утилит tools:", str(self.context.paths.tools_dir), dirs_card))
        db.addWidget(kv_row("Журналы логов:", str(self.context.paths.logs_dir), dirs_card))
        open_row = QHBoxLayout()
        open_root_btn = QPushButton("Открыть каталог данных", dirs_card)
        open_root_btn.clicked.connect(
            lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.context.paths.root)))
        )
        open_tools_btn = QPushButton("Открыть папку tools", dirs_card)
        open_tools_btn.setObjectName("Ghost")
        open_tools_btn.clicked.connect(
            lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.context.paths.tools_dir)))
        )
        open_row.addWidget(open_root_btn)
        open_row.addWidget(open_tools_btn)
        open_row.addStretch(1)
        db.addLayout(open_row)
        layout.addWidget(dirs_card)

        # Демо-макеты
        demo_card = StudioCard(content)
        dmb = demo_card.body()
        dmb.addWidget(make_title("Учебные ДЕМО-макеты IPSW"))
        dmb.addWidget(
            make_muted(
                "Учебные макеты (iPhone 15 Pro, iPad Pro M4, MacBook UniversalMac) позволяют проверить работу "
                "инспектора BuildManifest.plist и режима Dry-Run сразу после установки на Windows."
            )
        )
        dm_row = QHBoxLayout()
        restore_demo_btn = QPushButton("Пересоздать ДЕМО-макеты IPSW", demo_card)
        restore_demo_btn.setObjectName("Ghost")
        restore_demo_btn.clicked.connect(self._reinstall_demo)
        del_demo_btn = QPushButton("Удалить все ДЕМО-макеты", demo_card)
        del_demo_btn.setObjectName("Danger")
        del_demo_btn.clicked.connect(self._remove_demo)
        dm_row.addWidget(restore_demo_btn)
        dm_row.addWidget(del_demo_btn)
        dm_row.addStretch(1)
        dmb.addLayout(dm_row)
        layout.addWidget(demo_card)
        layout.addStretch(1)

    def on_show(self) -> None:
        custom = self.context.store.get_setting("custom_tools_dir", "")
        self.tools_edit.setText(custom or str(self.context.paths.tools_dir))
        pref = self.context.store.get_setting("preferred_backend", "auto")
        idx = self.pref_backend.findData(pref)
        if idx >= 0:
            self.pref_backend.blockSignals(True)
            self.pref_backend.setCurrentIndex(idx)
            self.pref_backend.blockSignals(False)

    def _browse_tools(self) -> None:
        folder = QFileDialog.getExistingDirectory(
            self, "Выберите папку с бинарными утилитами libimobiledevice", self.tools_edit.text()
        )
        if folder:
            self.tools_edit.setText(folder)

    def _save_settings(self) -> None:
        val = self.tools_edit.text().strip()
        if val and not Path(val).exists():
            QMessageBox.warning(self, "Путь не найден", f"Папка не существует: {val}")
            return
        self.context.update_tools_dir(val)
        self.window.set_status("Настройки каталога утилит сохранены")

    def _save_backend_pref(self) -> None:
        self.context.store.set_setting("preferred_backend", self.pref_backend.currentData() or "auto")
        self.window.set_status("Предпочитаемый движок сохранён")

    def _reinstall_demo(self) -> None:
        count = self.context.install_demo_mockups()
        self.window.set_status(f"Установлено демонстрационных макетов IPSW: {count}")

    def _remove_demo(self) -> None:
        removed = self.context.remove_demo_mockups()
        self.window.set_status(f"Удалено демонстрационных макетов: {removed}")
