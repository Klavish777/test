"""Модели таблиц Qt для устройств, прошивок, документов и компонентов."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Sequence

from PySide6.QtCore import QAbstractTableModel, QModelIndex, QSortFilterProxyModel, Qt
from PySide6.QtGui import QBrush, QColor, QFont

from repair_os.data.models import (
    CATEGORIES,
    DOC_TYPES,
    VERIFICATION_LABELS,
    BoardComponent,
    Device,
    Firmware,
    TechnicalDocument,
    human_size,
)
from repair_os.ui.theme import COLORS


@dataclass(frozen=True)
class Column:
    key: str
    title: str
    width: int = 120
    formatter: Callable[[Any], str] | None = None
    align: Qt.AlignmentFlag = Qt.AlignLeft | Qt.AlignVCenter


class BaseTableModel(QAbstractTableModel):
    columns: Sequence[Column] = ()
    rows: list[Any] = []

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.rows = []
        self._font_bold = QFont()
        self._font_bold.setBold(True)

    # ------------------------------------------------------------------ Qt API
    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: N802
        return 0 if parent.isValid() else len(self.rows)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: N802
        return 0 if parent.isValid() else len(self.columns)

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.DisplayRole):  # noqa: N802
        if role != Qt.DisplayRole or orientation != Qt.Horizontal:
            return None
        return self.columns[section].title

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole):
        if not index.isValid():
            return None
        row = self.rows[index.row()]
        column = self.columns[index.column()]
        value = self._value(row, column)
        if role == Qt.DisplayRole:
            return value
        if role == Qt.ToolTipRole and value:
            return value
        if role == Qt.TextAlignmentRole:
            return int(column.align)
        if role == Qt.ForegroundRole:
            return self._foreground(row, column)
        if role == Qt.FontRole and column.key in {"name", "file_name", "title", "designator"}:
            return self._font_bold
        return None

    # ------------------------------------------------------------------ данные
    def set_rows(self, rows: list[Any]) -> None:
        self.beginResetModel()
        self.rows = list(rows)
        self.endResetModel()

    def row_at(self, index: QModelIndex | int) -> Any:
        if isinstance(index, QModelIndex):
            if not index.isValid():
                return None
            index = index.row()
        if 0 <= index < len(self.rows):
            return self.rows[index]
        return None

    def _value(self, row: Any, column: Column) -> str:
        raw = getattr(row, column.key, None) if not isinstance(row, dict) else row.get(column.key)
        if column.formatter:
            return column.formatter(raw)
        if raw is None:
            return "—"
        return str(raw)

    def _foreground(self, row: Any, column: Column) -> QBrush | None:
        return None


def _yes_no(value: Any) -> str:
    return "Да" if value else "—"


def _status(value: Any) -> str:
    return VERIFICATION_LABELS.get(str(value), str(value or "—"))


def _category(value: Any) -> str:
    return CATEGORIES.get(str(value), str(value or "—"))


def _doc_type(value: Any) -> str:
    return DOC_TYPES.get(str(value), str(value or "—"))


class DeviceTableModel(BaseTableModel):
    columns = (
        Column("brand_name", "Бренд", 130),
        Column("name", "Модель", 230),
        Column("model_code", "Код модели", 150),
        Column("codename", "Кодовое имя", 130),
        Column("hardware_revision", "Ревизия", 90),
        Column("soc", "Процессор", 160),
        Column("os_versions", "ОС", 130),
        Column("firmware_count", "Прошивки", 80, align=Qt.AlignCenter),
        Column("has_3d", "3D", 60, formatter=_yes_no, align=Qt.AlignCenter),
        Column("verified", "Проверено", 90, formatter=_yes_no, align=Qt.AlignCenter),
    )

    def _foreground(self, row: Device, column: Column) -> QBrush | None:
        if column.key == "verified":
            return QBrush(QColor(COLORS["success"] if row.verified else COLORS["text_dim"]))
        if column.key == "model_code":
            return QBrush(QColor(COLORS["accent"]))
        if column.key == "codename" and row.codename:
            return QBrush(QColor(COLORS["text_muted"]))
        return None


class FirmwareTableModel(BaseTableModel):
    columns = (
        Column("file_name", "Файл", 280),
        Column("brand_name", "Бренд", 110),
        Column("model_code", "Модель", 120),
        Column("os_version", "ОС", 120),
        Column("build_number", "Сборка", 150),
        Column("region", "Регион/CSC", 90),
        Column("release_date", "Дата", 95),
        Column("size_human", "Размер", 85, align=Qt.AlignRight | Qt.AlignVCenter),
        Column("source_name", "Источник", 150),
        Column("verification_status", "Проверка", 120, formatter=_status),
    )

    def _value(self, row: Firmware, column: Column) -> str:
        if column.key == "size_human":
            return human_size(row.file_size)
        return super()._value(row, column)

    def _foreground(self, row: Firmware, column: Column) -> QBrush | None:
        if column.key == "verification_status":
            color = {
                "verified": COLORS["success"],
                "community": COLORS["accent"],
                "unverified": COLORS["text_dim"],
                "rejected": COLORS["danger"],
            }.get(row.verification_status, COLORS["text_muted"])
            return QBrush(QColor(color))
        if column.key == "file_name" and row.is_demo:
            return QBrush(QColor(COLORS["text"]))
        return None


class DocumentTableModel(BaseTableModel):
    columns = (
        Column("title", "Материал", 300),
        Column("category", "Категория", 130, formatter=_category),
        Column("doc_type", "Тип", 110, formatter=_doc_type),
        Column("device_name", "Устройство", 180),
        Column("tags", "Теги", 160),
        Column("verification_status", "Проверка", 140, formatter=_status),
        Column("verified_at", "Проверено", 100),
    )

    def _foreground(self, row: TechnicalDocument, column: Column) -> QBrush | None:
        if column.key == "verification_status":
            color = {
                "verified": COLORS["success"],
                "community": COLORS["accent"],
                "unverified": COLORS["text_dim"],
                "rejected": COLORS["danger"],
            }.get(row.verification_status, COLORS["text_muted"])
            return QBrush(QColor(color))
        return None


class ComponentTableModel(BaseTableModel):
    columns = (
        Column("designator", "Обозначение", 110),
        Column("side", "Сторона", 70),
        Column("layer", "Слой", 90),
        Column("component_type", "Тип", 100),
        Column("part_marking", "Маркировка", 120),
        Column("purpose", "Назначение", 200),
    )


class DictTableModel(BaseTableModel):
    def __init__(self, columns: Sequence[Column], parent=None) -> None:
        self.columns = tuple(columns)
        super().__init__(parent)


class SearchProxy(QSortFilterProxyModel):
    """Фильтрация по подстроке во всех колонках."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setFilterCaseSensitivity(Qt.CaseInsensitive)
        self._needle = ""

    def set_needle(self, needle: str) -> None:
        self._needle = (needle or "").strip().lower()
        self.invalidateFilter()

    def filterAcceptsRow(self, source_row: int, source_parent: QModelIndex) -> bool:  # noqa: N802
        if not self._needle:
            return True
        model = self.sourceModel()
        if model is None:
            return True
        for column in range(model.columnCount()):
            index = model.index(source_row, column, source_parent)
            value = model.data(index, Qt.DisplayRole)
            if value and self._needle in str(value).lower():
                return True
        return False
