"""Резервное копирование и восстановление."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from repair_os.core.errors import RepairOSError
from repair_os.services.context import AppContext
from repair_os.ui.dialogs.base import DangerDialog, info
from repair_os.ui.widgets import muted, title


def _format_size(size: int) -> str:
    value = float(size)
    for unit in ("Б", "КБ", "МБ", "ГБ"):
        if value < 1024 or unit == "ГБ":
            return f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} ГБ"


class BackupDialog(QDialog):
    def __init__(self, context: AppContext, parent=None) -> None:
        super().__init__(parent)
        self.context = context
        self.created_path: Path | None = None
        self.setWindowTitle("Резервные копии")
        self.resize(760, 540)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 16)
        layout.setSpacing(10)
        layout.addWidget(title("Резервные копии", object_name="PageTitle"))
        layout.addWidget(
            muted(
                "Копия содержит базу данных, манифест с SHA-256 файлов и материалы библиотеки. "
                "Храните копии на отдельном носителе."
            )
        )

        note_row = QHBoxLayout()
        note_row.addWidget(QLabel("Комментарий", self))
        self.note_edit = QLineEdit(self)
        self.note_edit.setPlaceholderText("Например: перед импортом каталога")
        note_row.addWidget(self.note_edit, 1)
        layout.addLayout(note_row)
        self.include_files = QCheckBox("Включать материалы библиотеки (может увеличить размер)", self)
        self.include_files.setChecked(True)
        layout.addWidget(self.include_files)

        self.table = QTableWidget(0, 4, self)
        self.table.setHorizontalHeaderLabels(["Файл", "Создана", "Версия", "Размер"])
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.table, 1)

        buttons = QHBoxLayout()
        create = QPushButton("Создать копию", self)
        create.setObjectName("Primary")
        create.clicked.connect(self._create)
        restore = QPushButton("Восстановить выбранную", self)
        restore.setObjectName("Ghost")
        restore.clicked.connect(self._restore_selected)
        restore_file = QPushButton("Восстановить из файла…", self)
        restore_file.setObjectName("Ghost")
        restore_file.clicked.connect(self._restore_file)
        close = QPushButton("Закрыть", self)
        close.setObjectName("Ghost")
        close.clicked.connect(self.accept)
        buttons.addWidget(create)
        buttons.addWidget(restore)
        buttons.addWidget(restore_file)
        buttons.addStretch(1)
        buttons.addWidget(close)
        layout.addLayout(buttons)
        self._reload()

    def _reload(self) -> None:
        backups = self.context.backup.list_backups()
        self.table.setRowCount(len(backups))
        for row, backup in enumerate(backups):
            self.table.setItem(row, 0, QTableWidgetItem(backup.path.name))
            self.table.setItem(row, 1, QTableWidgetItem(backup.created_at))
            self.table.setItem(row, 2, QTableWidgetItem(backup.app_version))
            self.table.setItem(row, 3, QTableWidgetItem(_format_size(backup.size)))
            self.table.item(row, 0).setData(Qt.UserRole, str(backup.path))

    def _create(self) -> None:
        try:
            info_obj = self.context.backup.create_backup(
                include_attachments=self.include_files.isChecked(),
                note=self.note_edit.text().strip(),
                keep=self.context.settings.get_int("backup_keep_count", 10),
            )
        except RepairOSError as exc:
            info(self, "Копия не создана", str(exc))
            return
        except Exception as exc:  # pragma: no cover
            info(self, "Копия не создана", str(exc))
            return
        self.created_path = info_obj.path
        self._reload()
        info(
            self,
            "Резервная копия создана",
            f"{info_obj.path}\nРазмер: {_format_size(info_obj.size)}",
        )

    def _restore_selected(self) -> None:
        row = self.table.currentRow()
        if row < 0:
            info(self, "Не выбрана копия", "Выберите копию в таблице.")
            return
        path = self.table.item(row, 0).data(Qt.UserRole)
        self._restore(Path(path))

    def _restore_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Выберите резервную копию", str(self.context.paths.backups_dir), "ZIP (*.zip)"
        )
        if path:
            self._restore(Path(path))

    def _restore(self, path: Path) -> None:
        if not DangerDialog.ask(
            self,
            "Восстановление базы данных",
            f"Текущая база будет заменена данными из копии:\n{path.name}\n\n"
            "Перед заменой автоматически создаётся страховочная копия. "
            "После восстановления приложение нужно перезапустить, чтобы обновить все разделы.",
            keyword="ВОССТАНОВИТЬ",
        ):
            return
        try:
            report = self.context.backup.restore_backup(path)
        except RepairOSError as exc:
            info(self, "Восстановление не выполнено", str(exc))
            return
        except Exception as exc:  # pragma: no cover
            info(self, "Восстановление не выполнено", str(exc))
            return
        self._reload()
        info(
            self,
            "База восстановлена",
            f"Источник: {report.restored_from.name}\n"
            f"Страховочная копия: {report.safety_copy.name if report.safety_copy else '—'}\n"
            f"Записей: {report.total_rows}",
        )
        self.accept()


class RestoreDialog(BackupDialog):
    """Открывает менеджер копий с подсказкой о восстановлении."""

    def __init__(self, context: AppContext, parent=None) -> None:
        super().__init__(context, parent)
        self.setWindowTitle("Восстановление данных")
        self.note_edit.setPlaceholderText("Комментарий к страховочной копии")
