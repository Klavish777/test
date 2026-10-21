"""Настройки, диагностика и сведения о приложении."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from PySide6.QtCore import QUrl, Qt
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from repair_os.core.entitlements import current_entitlements
from repair_os.core.i18n import available_languages, current_language, set_language
from repair_os.services.context import AppContext
from repair_os.ui.dialogs.base import DangerDialog, ReportDialog, confirm, error, info
from repair_os.ui.widgets import Card, badge, field_row, muted, separator, title
from repair_os.version import APP_VERSION

log = logging.getLogger(__name__)


class SettingsPage(QWidget):
    route_key = "settings"

    def __init__(self, context: AppContext, window) -> None:
        super().__init__()
        self.context = context
        self.window = window

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        outer.addWidget(scroll)
        container = QWidget(scroll)
        self.container = container
        self.layout = QVBoxLayout(container)
        self.layout.setContentsMargins(24, 20, 24, 24)
        self.layout.setSpacing(14)
        scroll.setWidget(container)

        self.layout.addWidget(title("Настройки", object_name="PageTitle"))
        self.layout.addWidget(
            muted(
                "Локальные данные хранятся только на этом компьютере. "
                "Все функции доступны без подписки и без подключения к сети."
            )
        )

        self._build_general()
        self._build_data()
        self._build_diagnostics()
        self._build_about()
        self.layout.addStretch(1)

    # ------------------------------------------------------------------ блоки
    def _build_general(self) -> None:
        card = Card(self.container)
        body = card.body()
        body.addWidget(title("Общие", object_name="CardTitle"))
        self.language_combo = QComboBox(card)
        for code, label in available_languages().items():
            self.language_combo.addItem(f"{label} ({code})", code)
        index = self.language_combo.findData(current_language())
        if index >= 0:
            self.language_combo.setCurrentIndex(index)
        row = QHBoxLayout()
        row.addWidget(QLabel("Язык интерфейса", card))
        row.addWidget(self.language_combo)
        save_language = QPushButton("Применить", card)
        save_language.setObjectName("Ghost")
        save_language.clicked.connect(self._apply_language)
        row.addWidget(save_language)
        row.addStretch(1)
        body.addLayout(row)
        body.addWidget(
            muted(
                "Смена языка применяется после перезапуска приложения. "
                "Основной язык — русский; каталоги переводов лежат в resources/i18n.",
                card,
            )
        )
        self.show_demo_check = QCheckBox("Показывать пометку ДЕМО у демонстрационных записей", card)
        self.show_demo_check.setChecked(bool(self.context.settings.get("show_demo_badge", True)))
        self.show_demo_check.stateChanged.connect(
            lambda: self.context.settings.set("show_demo_badge", self.show_demo_check.isChecked())
        )
        body.addWidget(self.show_demo_check)
        self.confirm_check = QCheckBox("Подтверждать потенциально опасные операции", card)
        self.confirm_check.setChecked(
            bool(self.context.settings.get("confirm_dangerous_actions", True))
        )
        self.confirm_check.stateChanged.connect(
            lambda: self.context.settings.set(
                "confirm_dangerous_actions", self.confirm_check.isChecked()
            )
        )
        body.addWidget(self.confirm_check)
        self.layout.addWidget(card)

    def _build_data(self) -> None:
        card = Card(self.container)
        body = card.body()
        body.addWidget(title("Данные и файлы", object_name="CardTitle"))
        body.addWidget(field_row("Каталог данных", str(self.context.paths.root), card))
        body.addWidget(field_row("База данных", str(self.context.paths.database), card))
        body.addWidget(field_row("Резервные копии", str(self.context.paths.backups_dir), card))
        body.addWidget(field_row("Библиотека", str(self.context.library_root()), card))
        buttons = QHBoxLayout()
        open_data = QPushButton("Открыть каталог данных", card)
        open_data.setObjectName("Ghost")
        open_data.clicked.connect(
            lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.context.paths.root)))
        )
        buttons.addWidget(open_data)
        backup = QPushButton("Создать резервную копию", card)
        backup.setObjectName("Primary")
        backup.clicked.connect(self.window.create_backup)
        buttons.addWidget(backup)
        restore = QPushButton("Восстановить…", card)
        restore.setObjectName("Ghost")
        restore.clicked.connect(self.window.restore_backup)
        buttons.addWidget(restore)
        export = QPushButton("Экспорт JSON", card)
        export.setObjectName("Ghost")
        export.clicked.connect(self._export_json)
        buttons.addWidget(export)
        buttons.addStretch(1)
        body.addLayout(buttons)
        body.addWidget(separator(card))

        demo_row = QHBoxLayout()
        counts = self.context.demo_counts()
        demo_row.addWidget(
            QLabel(
                f"Демонстрационные записи: устройств {counts.get('devices', 0)}, "
                f"прошивок {counts.get('firmware', 0)}, материалов {counts.get('documents', 0)}, "
                f"плат {counts.get('boards', 0)}",
                card,
            )
        )
        demo_row.addStretch(1)
        remove_demo = QPushButton("Удалить демо-данные", card)
        remove_demo.setObjectName("Danger")
        remove_demo.clicked.connect(self._remove_demo)
        demo_row.addWidget(remove_demo)
        body.addLayout(demo_row)
        self.layout.addWidget(card)

    def _build_diagnostics(self) -> None:
        card = Card(self.container)
        body = card.body()
        body.addWidget(title("Диагностика", object_name="CardTitle"))
        self.stats_label = muted("", card)
        body.addWidget(self.stats_label)
        buttons = QHBoxLayout()
        check = QPushButton("Проверить целостность базы", card)
        check.setObjectName("Ghost")
        check.clicked.connect(self._integrity_check)
        buttons.addWidget(check)
        vacuum = QPushButton("Оптимизировать базу (VACUUM)", card)
        vacuum.setObjectName("Ghost")
        vacuum.clicked.connect(self._vacuum)
        buttons.addWidget(vacuum)
        logs = QPushButton("Открыть каталог логов", card)
        logs.setObjectName("Ghost")
        logs.clicked.connect(
            lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.context.paths.logs_dir)))
        )
        buttons.addWidget(logs)
        buttons.addStretch(1)
        body.addLayout(buttons)
        self.layout.addWidget(card)

    def _build_about(self) -> None:
        card = Card(self.container)
        body = card.body()
        header = QHBoxLayout()
        header.addWidget(title("О приложении", object_name="CardTitle"))
        header.addStretch(1)
        header.addWidget(badge("MVP · локальная версия", "info", card))
        body.addLayout(header)
        body.addWidget(
            field_row(
                "Smartphone Repair OS",
                f"Версия {APP_VERSION} · схема БД v{self.context.db.schema_version()}",
                card,
            )
        )
        entitlements = current_entitlements()
        body.addWidget(
            field_row(
                "Лицензия",
                f"{entitlements.edition.value} · провайдер {entitlements.provider_name} · "
                "все функции доступны, оплата не требуется",
                card,
            )
        )
        body.addWidget(
            muted(
                "Демонстрационные данные помечены ДЕМО. Приложение не поставляет прошивки, "
                "схемы и 3D-модели реальных устройств и не обходит защиту оборудования.",
                card,
            )
        )
        self.layout.addWidget(card)

    # ------------------------------------------------------------------ действия
    def on_show(self) -> None:
        counts = self.context.demo_counts()
        integrity = "ok" if self.context.db.integrity_check() else "требуется внимание"
        self.stats_label.setText(
            f"Устройств: {self.context.devices.count()} · брендов: {self.context.brands.count()} · "
            f"прошивок: {self.context.db.table_count('firmware')} · "
            f"материалов: {self.context.db.table_count('technical_documents')} · "
            f"компонентов плат: {self.context.db.table_count('board_components')} · "
            f"демо-записей: {sum(counts.values())} · целостность БД: {integrity}"
        )

    def _apply_language(self) -> None:
        code = self.language_combo.currentData()
        if not code:
            return
        set_language(code)
        self.context.settings.set("language", code)
        info(
            self.window,
            "Язык сохранён",
            "Язык интерфейса изменится после перезапуска приложения.",
        )

    def _export_json(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "Экспорт данных", "repair_os_export.json", "JSON (*.json)"
        )
        if not path:
            return
        try:
            target = self.context.backup.export_json(Path(path))
        except Exception as exc:
            error(self.window, "Ошибка экспорта", str(exc))
            return
        info(self.window, "Экспорт завершён", f"Файл сохранён:\n{target}")

    def _remove_demo(self) -> None:
        counts = self.context.demo_counts()
        if not any(counts.values()):
            info(self.window, "Демо-данных нет", "База не содержит демонстрационных записей.")
            return
        if not DangerDialog.ask(
            self.window,
            "Удаление демонстрационных данных",
            "Будут удалены только записи с пометкой ДЕМО (устройства, прошивки, материалы, платы). "
            "Ваши собственные данные останутся. Рекомендуется сначала создать резервную копию.",
            keyword="УДАЛИТЬ",
        ):
            return
        removed = self.context.seeder.clear_demo()
        self.window.refresh_after_change()
        self.window.set_status(f"Удалено демо-устройств: {removed}")

    def _integrity_check(self) -> None:
        ok = self.context.db.integrity_check()
        info(
            self.window,
            "Проверка базы",
            "База данных в порядке." if ok else "Обнаружены проблемы целостности. Восстановите копию.",
        )

    def _vacuum(self) -> None:
        if not confirm(self.window, "Оптимизация", "Выполнить VACUUM? Это может занять время."):
            return
        try:
            self.context.db.vacuum()
        except Exception as exc:
            error(self.window, "Ошибка", str(exc))
            return
        self.window.set_status("База оптимизирована")
