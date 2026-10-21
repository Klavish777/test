"""Управление источниками прошивок."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from repair_os.services.context import AppContext
from repair_os.ui.dialogs.base import confirm
from repair_os.ui.dialogs.firmware_editor import SourceEditorDialog
from repair_os.ui.widgets import muted, title

KIND_LABELS = {
    "official": "Официальный",
    "community": "Сообщество",
    "local": "Локальный",
    "vendor_tool": "Инструмент",
}


class SourceManagerDialog(QDialog):
    def __init__(self, context: AppContext, parent=None) -> None:
        super().__init__(parent)
        self.context = context
        self.setWindowTitle("Источники прошивок")
        self.resize(760, 500)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 14)
        layout.setSpacing(10)
        layout.addWidget(title("Источники прошивок", object_name="PageTitle"))
        layout.addWidget(
            muted(
                "Источники хранятся отдельно от записей. Приложение не загружает файлы "
                "автоматически и не обходит защиту устройств."
            )
        )
        self.table = QTableWidget(0, 5, self)
        self.table.setHorizontalHeaderLabels(["Название", "Тип", "Доверенный", "Ссылка", "Записей"])
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(self.table, 1)

        buttons = QHBoxLayout()
        add = QPushButton("+ Источник", self)
        add.setObjectName("Primary")
        add.clicked.connect(self._add)
        edit = QPushButton("Изменить", self)
        edit.clicked.connect(self._edit)
        delete = QPushButton("Удалить", self)
        delete.setObjectName("Danger")
        delete.clicked.connect(self._delete)
        close = QPushButton("Закрыть", self)
        close.setObjectName("Ghost")
        close.clicked.connect(self.accept)
        buttons.addWidget(add)
        buttons.addWidget(edit)
        buttons.addWidget(delete)
        buttons.addStretch(1)
        buttons.addWidget(close)
        layout.addLayout(buttons)
        self._reload()

    def _reload(self) -> None:
        sources = self.context.firmware.sources()
        self.table.setRowCount(len(sources))
        for row, source in enumerate(sources):
            self.table.setItem(row, 0, QTableWidgetItem(source.name))
            self.table.setItem(row, 1, QTableWidgetItem(KIND_LABELS.get(source.kind, source.kind)))
            self.table.setItem(row, 2, QTableWidgetItem("да" if source.trusted else "нет"))
            self.table.setItem(row, 3, QTableWidgetItem(source.url or "—"))
            used = self.context.db.scalar(
                "SELECT COUNT(*) FROM firmware WHERE source_id = ?", (source.id,)
            )
            self.table.setItem(row, 4, QTableWidgetItem(str(used or 0)))
            self.table.item(row, 0).setData(Qt.UserRole, source.id)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)

    def _current_id(self) -> int | None:
        row = self.table.currentRow()
        if row < 0:
            return None
        item = self.table.item(row, 0)
        return item.data(Qt.UserRole) if item else None

    def _add(self) -> None:
        dialog = SourceEditorDialog(self.context, parent=self)
        if dialog.exec():
            self._reload()

    def _edit(self) -> None:
        source_id = self._current_id()
        if not source_id:
            return
        dialog = SourceEditorDialog(
            self.context, source=self.context.firmware.get_source(source_id), parent=self
        )
        if dialog.exec():
            self._reload()

    def _delete(self) -> None:
        source_id = self._current_id()
        if not source_id:
            return
        if not confirm(
            self, "Удалить источник", "Удалить источник?", confirm_text="Удалить", danger=True
        ):
            return
        from repair_os.core.errors import RepairOSError

        try:
            self.context.firmware.delete_source(source_id)
        except RepairOSError as exc:
            from PySide6.QtWidgets import QMessageBox

            QMessageBox.warning(self, "Нельзя удалить", str(exc))
            return
        self._reload()
