"""Управление брендами каталога."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from repair_os.services.context import AppContext
from repair_os.ui.dialogs.base import FormDialog, confirm, error
from repair_os.ui.widgets import muted, title


class BrandManagerDialog(QDialog):
    def __init__(self, context: AppContext, parent=None) -> None:
        super().__init__(parent)
        self.context = context
        self.setWindowTitle("Бренды каталога")
        self.resize(720, 520)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 14)
        layout.setSpacing(10)
        layout.addWidget(title("Бренды каталога", object_name="PageTitle"))
        layout.addWidget(
            muted(
                "Бренды создаются вручную или импортом. Удалить бренд можно только без устройств."
            )
        )

        self.table = QTableWidget(0, 4, self)
        self.table.setHorizontalHeaderLabels(["Название", "Slug", "Страна", "Устройств"])
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(self.table, 1)

        buttons = QHBoxLayout()
        add = QPushButton("+ Бренд", self)
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
        brands = self.context.brands.list()
        self.table.setRowCount(len(brands))
        for row, brand in enumerate(brands):
            self.table.setItem(row, 0, QTableWidgetItem(brand.name))
            self.table.setItem(row, 1, QTableWidgetItem(brand.slug))
            self.table.setItem(row, 2, QTableWidgetItem(brand.country or "—"))
            self.table.setItem(row, 3, QTableWidgetItem(str(brand.device_count)))
            self.table.item(row, 0).setData(Qt.UserRole, brand.id)
        self.table.resizeColumnsToContents()
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)

    def _current_brand_id(self) -> int | None:
        row = self.table.currentRow()
        if row < 0:
            return None
        item = self.table.item(row, 0)
        return item.data(Qt.UserRole) if item else None

    def _add(self) -> None:
        dialog = BrandFormDialog(self.context, parent=self)
        if dialog.exec():
            self._reload()

    def _edit(self) -> None:
        brand_id = self._current_brand_id()
        if not brand_id:
            return
        dialog = BrandFormDialog(self.context, brand_id=brand_id, parent=self)
        if dialog.exec():
            self._reload()

    def _delete(self) -> None:
        brand_id = self._current_brand_id()
        if not brand_id:
            return
        if not confirm(
            self,
            "Удалить бренд",
            "Бренд будет удалён. Если к нему привязаны устройства, удаление будет отклонено.",
            confirm_text="Удалить",
            danger=True,
        ):
            return
        try:
            self.context.brands.delete(brand_id)
        except Exception as exc:
            QMessageBox.warning(self, "Нельзя удалить", str(exc))
            return
        self._reload()


class BrandFormDialog(FormDialog):
    def __init__(self, context: AppContext, *, brand_id: int | None = None, parent=None) -> None:
        super().__init__(
            "Новый бренд" if not brand_id else "Бренд",
            subtitle="Slug используется во внутренних ссылках.",
            parent=parent,
            width=440,
        )
        self.context = context
        self.brand_id = brand_id
        brand = context.brands.get(brand_id) if brand_id else None
        self.name = self.add_line("Название *", brand.name if brand else "")
        self.slug = self.add_line("Slug", brand.slug if brand else "", placeholder="samsung")
        self.country = self.add_line("Страна", brand.country if brand else "")
        self.website = self.add_line("Сайт", brand.website if brand else "")
        self.order = self.add_spin(
            "Порядок сортировки", brand.sort_order if brand else 500, minimum=0, maximum=9999
        )
        self.on_save(self._save)

    def collect(self) -> dict:
        return {
            "name": self.name.text(),
            "slug": self.slug.text().strip() or None,
            "country": self.country.text(),
            "website": self.website.text(),
            "sort_order": self.order.value(),
        }

    def _save(self, payload: dict):
        if self.brand_id:
            return self.context.brands.update(self.brand_id, payload)
        return self.context.brands.create(payload)
