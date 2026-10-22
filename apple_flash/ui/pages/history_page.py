"""Журнал операций перепрошивки и проверок с просмотром полного лога и экспортом в файл."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from apple_flash.data.models import FLASH_ACTION_LABELS, FlashSessionRecord
from apple_flash.services.context import StudioContext
from apple_flash.ui.widgets import StudioCard, make_muted, make_title


class HistoryPage(QWidget):
    def __init__(self, context: StudioContext, window) -> None:
        super().__init__()
        self.context = context
        self.window = window
        self._sessions: list[FlashSessionRecord] = []
        self._selected: FlashSessionRecord | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 16, 22, 16)
        layout.setSpacing(10)

        head = QHBoxLayout()
        box = QVBoxLayout()
        box.setSpacing(2)
        box.addWidget(make_title("Журнал операций", object_name="PageTitle"))
        box.addWidget(
            make_muted(
                "История выполненных прошивок и сервисных команд USB с подробным протоколом."
            )
        )
        head.addLayout(box, 1)

        export_btn = QPushButton("Экспорт протокола (.txt)…", self)
        export_btn.clicked.connect(self._export_selected)
        head.addWidget(export_btn)

        clear_btn = QPushButton("Очистить журнал", self)
        clear_btn.setObjectName("Danger")
        clear_btn.clicked.connect(self._clear_all)
        head.addWidget(clear_btn)
        layout.addLayout(head)

        splitter = QSplitter(Qt.Vertical, self)
        splitter.setChildrenCollapsible(False)

        self.table = QTableWidget(0, 7, self)
        self.table.setHorizontalHeaderLabels(
            ["Время старта", "Устройство", "Операция", "Образ IPSW", "Режим", "Бэкенд", "Статус"]
        )
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        hdr = self.table.horizontalHeader()
        hdr.setSectionResizeMode(1, QHeaderView.Stretch)
        hdr.setSectionResizeMode(3, QHeaderView.Stretch)
        for col in (0, 2, 4, 5, 6):
            hdr.setSectionResizeMode(col, QHeaderView.ResizeToContents)
        self.table.itemSelectionChanged.connect(self._on_select)
        splitter.addWidget(self.table)

        log_card = StudioCard(self)
        lb = log_card.body()
        lb.addWidget(make_title("Подробный протокол выбранной сессии"))
        self.log_viewer = QPlainTextEdit(log_card)
        self.log_viewer.setObjectName("ConsoleBox")
        self.log_viewer.setReadOnly(True)
        lb.addWidget(self.log_viewer, 1)
        splitter.addWidget(log_card)
        splitter.setSizes([340, 320])
        layout.addWidget(splitter, 1)

    def on_show(self) -> None:
        self._sessions = self.context.store.list_sessions(limit=300)
        self.table.setRowCount(len(self._sessions))
        for idx, s in enumerate(self._sessions):
            vals = [
                s.started_at,
                s.device_title,
                FLASH_ACTION_LABELS.get(s.action, s.action),
                f"{s.ipsw_name or '—'} ({s.ipsw_build or '—'})" if s.ipsw_name else "—",
                "Проверка" if s.dry_run else "Прошивка",
                s.backend,
                "Успешно" if s.status == "success" else f"Ошибка (код {s.exit_code})",
            ]
            for c, val in enumerate(vals):
                self.table.setItem(idx, c, QTableWidgetItem(val))

        if self._sessions:
            self.table.selectRow(0)
        else:
            self._selected = None
            self.log_viewer.setPlainText("Журнал операций пока пуст.")

    def _on_select(self) -> None:
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            return
        idx = rows[0].row()
        if 0 <= idx < len(self._sessions):
            s = self._sessions[idx]
            self._selected = s
            header = (
                f"Сессия #{s.id} · {s.started_at} → {s.finished_at or '—'}\n"
                f"Устройство: {s.device_title} ({s.device_uid})\n"
                f"Команда:    {s.command_line}\n"
                + ("-" * 72)
                + "\n"
            )
            self.log_viewer.setPlainText(header + (s.log_text or ""))

    def _export_selected(self) -> None:
        if not self._selected:
            QMessageBox.information(self, "Нет записи", "Выберите сессию в таблице.")
            return
        default_name = f"flash_report_{self._selected.id}.txt"
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Сохранить протокол операции",
            str(self.context.paths.reports_dir / default_name),
            "Текстовый отчёт (*.txt)",
        )
        if not path:
            return
        Path(path).write_text(self.log_viewer.toPlainText(), encoding="utf-8")
        self.window.set_status(f"Протокол сохранён: {path}")

    def _clear_all(self) -> None:
        if not self._sessions:
            return
        ans = QMessageBox.question(
            self,
            "Очистить журнал",
            "Удалить все записи из журнала операций?",
            QMessageBox.Yes | QMessageBox.No,
        )
        if ans == QMessageBox.Yes:
            self.context.store.clear_sessions()
            self.on_show()
