"""Переиспользуемые элементы интерфейса."""

from __future__ import annotations

from typing import Callable, Iterable

from PySide6.QtCore import QPoint, QRect, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFont, QMouseEvent, QPainter, QPen
from PySide6.QtWidgets import (
    QFrame,
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QLayout,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QTableView,
    QVBoxLayout,
    QWidget,
    QWidgetItem,
)

from repair_os.data.models import VERIFICATION_LABELS, human_size
from repair_os.ui.theme import COLORS

TONE_BY_STATUS = {
    "verified": "verified",
    "community": "info",
    "unverified": "neutral",
    "rejected": "danger",
}


def badge(text: str, tone: str = "neutral", parent: QWidget | None = None) -> QLabel:
    label = QLabel(text, parent)
    label.setObjectName("Badge")
    label.setProperty("tone", tone)
    label.setAlignment(Qt.AlignCenter)
    label.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Fixed)
    return label


def title(text: str, *, object_name: str = "SectionTitle", parent: QWidget | None = None) -> QLabel:
    label = QLabel(text, parent)
    label.setObjectName(object_name)
    return label


def wrapped_label(
    text: str,
    parent: QWidget | None = None,
    *,
    object_name: str = "",
    lines: int = 2,
) -> QLabel:
    """QLabel с переносом и гарантированной минимальной высотой.

    QLabel с wordWrap внутри вложенных карточек часто обрезается до одной строки,
    поэтому высота фиксируется явно.
    """
    label = QLabel(text, parent)
    label.setWordWrap(True)
    if object_name:
        label.setObjectName(object_name)
    metrics = label.fontMetrics()
    label.setMinimumHeight(metrics.lineSpacing() * max(1, lines) + 2)
    label.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.MinimumExpanding)
    return label


def breakable(text: str) -> str:
    """Вставляет мягкие переносы в длинные идентификаторы (имена файлов, коды)."""
    result = []
    for char in str(text):
        result.append(char)
        if char in "_.-/":
            result.append("\u200b")
    return "".join(result)


def muted(text: str, parent: QWidget | None = None) -> QLabel:
    label = QLabel(text, parent)
    label.setObjectName("Muted")
    label.setWordWrap(True)
    return label


def field_row(label_text: str, value: str, parent: QWidget | None = None) -> QWidget:
    container = QWidget(parent)
    layout = QVBoxLayout(container)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(2)
    caption = QLabel(label_text, container)
    caption.setObjectName("FieldLabel")
    text = QLabel(value or "—", container)
    text.setObjectName("FieldValue")
    text.setWordWrap(True)
    text.setTextInteractionFlags(Qt.TextSelectableByMouse)
    layout.addWidget(caption)
    layout.addWidget(text)
    return container


def separator(parent: QWidget | None = None) -> QFrame:
    line = QFrame(parent)
    line.setObjectName("Separator")
    line.setFixedHeight(1)
    return line


class Card(QFrame):
    def __init__(self, parent: QWidget | None = None, *, padding: int = 16) -> None:
        super().__init__(parent)
        self.setObjectName("Card")
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(padding, padding, padding, padding)
        self._layout.setSpacing(10)

    def body(self) -> QVBoxLayout:
        return self._layout

    def add(self, widget: QWidget) -> QWidget:
        self._layout.addWidget(widget)
        return widget


class ClickableCard(Card):
    clicked = Signal()

    def __init__(self, parent: QWidget | None = None, *, padding: int = 14) -> None:
        super().__init__(parent, padding=padding)
        self.setObjectName("ClickableCard")
        self.setCursor(Qt.PointingHandCursor)

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() == Qt.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)


class StatTile(QFrame):
    def __init__(self, label: str, value: str, hint: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("StatTile")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(2)
        self._value = QLabel(value, self)
        self._value.setObjectName("MetricValue")
        self._label = QLabel(label, self)
        self._label.setObjectName("MetricLabel")
        layout.addWidget(self._value)
        layout.addWidget(self._label)
        if hint:
            hint_label = QLabel(hint, self)
            hint_label.setObjectName("Dim")
            layout.addWidget(hint_label)

    def set_value(self, value: str) -> None:
        self._value.setText(value)


class SearchInput(QLineEdit):
    def __init__(
        self,
        placeholder: str = "Поиск по бренду, названию и точному коду модели…",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("SearchInput")
        self.setPlaceholderText(placeholder)
        self.setClearButtonEnabled(True)

    def keyPressEvent(self, event) -> None:  # noqa: N802
        if event.key() in (Qt.Key_Return, Qt.Key_Enter):
            self.returnPressed.emit()
        super().keyPressEvent(event)


class EmptyState(QWidget):
    def __init__(
        self,
        headline: str,
        description: str = "",
        action_text: str = "",
        on_action: Callable[[], None] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)
        layout.setSpacing(8)
        title_label = QLabel(headline, self)
        title_label.setObjectName("CardTitle")
        title_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(title_label)
        if description:
            description_label = QLabel(description, self)
            description_label.setObjectName("Muted")
            description_label.setAlignment(Qt.AlignCenter)
            description_label.setWordWrap(True)
            description_label.setMaximumWidth(480)
            layout.addWidget(description_label, 0, Qt.AlignHCenter)
        if action_text and on_action:
            button = QPushButton(action_text, self)
            button.setObjectName("Primary")
            button.setCursor(Qt.PointingHandCursor)
            button.clicked.connect(on_action)
            layout.addWidget(button, 0, Qt.AlignHCenter)


class FlowLayout(QLayout):
    """Простая реализация «плавающего» макета для чипов и карточек."""

    def __init__(self, parent: QWidget | None = None, *, spacing: int = 8) -> None:
        super().__init__(parent)
        self._items: list[QWidgetItem] = []
        self._spacing = spacing
        self.setContentsMargins(0, 0, 0, 0)

    def addItem(self, item) -> None:  # noqa: N802
        self._items.append(item)

    def count(self) -> int:
        return len(self._items)

    def itemAt(self, index: int):  # noqa: N802
        return self._items[index] if 0 <= index < len(self._items) else None

    def takeAt(self, index: int):  # noqa: N802
        return self._items.pop(index) if 0 <= index < len(self._items) else None

    def expandingDirections(self):  # noqa: N802
        return Qt.Orientations(Qt.Orientation(0))

    def hasHeightForWidth(self) -> bool:  # noqa: N802
        return True

    def heightForWidth(self, width: int) -> int:  # noqa: N802
        return self._do_layout(QRect(0, 0, width, 0), test_only=True)

    def setGeometry(self, rect: QRect) -> None:  # noqa: N802
        super().setGeometry(rect)
        self._do_layout(rect, test_only=False)

    def sizeHint(self) -> QSize:  # noqa: N802
        return self.minimumSize()

    def minimumSize(self) -> QSize:  # noqa: N802
        size = QSize()
        for item in self._items:
            size = size.expandedTo(item.minimumSize())
        margins = self.contentsMargins()
        return size + QSize(margins.left() + margins.right(), margins.top() + margins.bottom())

    def _do_layout(self, rect: QRect, *, test_only: bool) -> int:
        margins = self.contentsMargins()
        effective = rect.adjusted(margins.left(), margins.top(), -margins.right(), -margins.bottom())
        x, y = effective.x(), effective.y()
        line_height = 0
        for item in self._items:
            hint = item.sizeHint()
            next_x = x + hint.width() + self._spacing
            if next_x - self._spacing > effective.right() and line_height > 0:
                x = effective.x()
                y = y + line_height + self._spacing
                next_x = x + hint.width() + self._spacing
                line_height = 0
            if not test_only:
                item.setGeometry(QRect(QPoint(x, y), hint))
            x = next_x
            line_height = max(line_height, hint.height())
        return y + line_height - rect.y() + margins.bottom()


def clear_layout(layout) -> None:
    while layout.count():
        item = layout.takeAt(0)
        widget = item.widget()
        if widget is not None:
            widget.setParent(None)
            widget.deleteLater()
        elif item.layout() is not None:
            clear_layout(item.layout())


class Chip(QPushButton):
    """Кнопка-фильтр (бренд, категория, слой)."""

    def __init__(self, text: str, *, count: int | None = None, parent: QWidget | None = None) -> None:
        label = f"{text}  {count}" if count is not None else text
        super().__init__(label, parent)
        self.setCheckable(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setStyleSheet(
            f"""
            QPushButton {{
                background-color: {COLORS['surface']};
                border: 1px solid {COLORS['border']};
                border-radius: 14px;
                padding: 5px 12px;
                color: {COLORS['text_muted']};
                font-size: 12px;
            }}
            QPushButton:hover {{
                border-color: {COLORS['border_strong']};
                color: {COLORS['text']};
            }}
            QPushButton:checked {{
                background-color: {COLORS['accent_soft']};
                border-color: {COLORS['accent']};
                color: #ffffff;
            }}
            """
        )


class StatusBadge(QLabel):
    def __init__(self, status: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("Badge")
        self.set_status(status)

    def set_status(self, status: str) -> None:
        self.setText(VERIFICATION_LABELS.get(status, status))
        self.setProperty("tone", TONE_BY_STATUS.get(status, "neutral"))
        self.setAlignment(Qt.AlignCenter)
        self.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Fixed)
        self.style().unpolish(self)
        self.style().polish(self)


class MetricRow(QWidget):
    def __init__(self, label: str, value: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        caption = QLabel(label, self)
        caption.setObjectName("Muted")
        text = QLabel(value, self)
        text.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        text.setTextInteractionFlags(Qt.TextSelectableByMouse)
        layout.addWidget(caption)
        layout.addStretch(1)
        layout.addWidget(text)


class LogoMark(QWidget):
    """Простой векторный логотип (плата + контакт)."""

    def __init__(self, size: int = 30, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedSize(size, size)

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        w = self.width()
        painter.setBrush(QColor("#16243a"))
        painter.setPen(QPen(QColor("#3d8bfd"), max(1.0, w / 16)))
        painter.drawRoundedRect(2, 2, w - 4, w - 4, w / 5, w / 5)
        painter.setBrush(QColor("#3d8bfd"))
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(int(w * 0.24), int(w * 0.24), int(w * 0.22), int(w * 0.22), 2, 2)
        painter.drawRoundedRect(int(w * 0.54), int(w * 0.24), int(w * 0.22), int(w * 0.13), 2, 2)
        painter.drawRoundedRect(int(w * 0.24), int(w * 0.54), int(w * 0.13), int(w * 0.22), 2, 2)
        painter.drawRoundedRect(int(w * 0.44), int(w * 0.44), int(w * 0.22), int(w * 0.22), 2, 2)
        painter.end()


def tags_widget(tags: Iterable[str], parent: QWidget | None = None) -> QWidget:
    container = QWidget(parent)
    layout = QHBoxLayout(container)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(6)
    for tag in tags:
        if not tag:
            continue
        layout.addWidget(badge(tag, "neutral"))
    layout.addStretch(1)
    return container


__all__ = [
    "badge",
    "title",
    "wrapped_label",
    "breakable",
    "muted",
    "field_row",
    "separator",
    "Card",
    "ClickableCard",
    "StatTile",
    "SearchInput",
    "EmptyState",
    "FlowLayout",
    "clear_layout",
    "Chip",
    "StatusBadge",
    "MetricRow",
    "LogoMark",
    "tags_widget",
    "human_size",
]


class FittedTableView(QTableView):
    """Таблица с подгонкой ширины столбцов под доступное место.

    Штатный QHeaderView::Stretch делит ширину поровну и обрезает содержимое
    (например, в колонке «Модель» остаётся пара букв). Здесь ширины считаются
    от содержимого и пропорционально сжимаются, если места не хватает;
    растягиваемая колонка сначала получает минимум, а остаток ширины распределяется
    между колонками, у которых есть скрытый текст.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._stretch_column: int | None = None
        self._minimum_widths: dict[int, int] = {}
        self._minimised = False
        self._applying = False
        header = self.horizontalHeader()
        header.setMinimumSectionSize(48)
        header.setSectionResizeMode(QHeaderView.Interactive)
        header.setStretchLastSection(False)
        header.sectionResized.connect(self._on_section_resized)

    # ------------------------------------------------------------------ API
    def setup_columns(
        self,
        stretch_column: int | None = None,
        *,
        minimum_widths: dict[int, int] | None = None,
        priorities: dict[int, int] | None = None,
    ) -> None:
        """Задать растягиваемую колонку, минимальные ширины и приоритеты скрытия.

        ``priorities``: чем меньше число, тем раньше колонка скрывается при
        нехватке места. Колонки без приоритета не скрываются.
        """
        self._stretch_column = stretch_column
        self._minimum_widths = dict(minimum_widths or {})
        self._priorities = dict(priorities or {})
        self.apply_column_fit()

    def apply_column_fit(self) -> None:
        model = self.model()
        if model is None:
            return
        count = model.columnCount()
        available = self.viewport().width()
        if count == 0 or available <= 0:
            return
        minimums = {i: 48 for i in range(count)}
        minimums.update({k: v for k, v in self._minimum_widths.items() if k < count})
        hidden = self._fit_visible_columns(count, minimums, available)
        visible = [i for i in range(count) if i not in hidden]
        if not visible:
            return
        natural = [max(self.sizeHintForColumn(i) + 14, minimums[i]) for i in range(count)]
        natural_total = sum(natural[i] for i in visible)
        widths = [natural[i] if i in visible else 0 for i in range(count)]
        if natural_total <= available:
            if self._stretch_column is not None and self._stretch_column in visible:
                widths[self._stretch_column] += available - natural_total
        else:
            flex_total = sum(max(0, natural[i] - minimums[i]) for i in visible)
            overflow = natural_total - available
            for i in visible:
                flex = max(0, natural[i] - minimums[i])
                share = (flex / flex_total) if flex_total else 0.0
                widths[i] = max(minimums[i], natural[i] - int(round(overflow * share)))
            deficit = sum(widths) - available
            if deficit > 0:
                order = sorted(visible, key=lambda i: widths[i] - minimums[i], reverse=True)
                for i in order:
                    if deficit <= 0:
                        break
                    take = min(deficit, widths[i] - minimums[i])
                    widths[i] -= take
                    deficit -= take
        self._applying = True
        try:
            for index, value in enumerate(widths):
                self.setColumnHidden(index, index not in visible)
                if index in visible:
                    self.setColumnWidth(index, value)
        finally:
            self._applying = False

    def hidden_columns(self) -> list[int]:
        return [i for i in range(self.model().columnCount()) if self.isColumnHidden(i)]

    def _fit_visible_columns(self, count: int, minimums: dict[int, int], available: int) -> set[int]:
        """Скрывает наименее важные колонки, пока минимальная ширина не влезет."""
        priorities = getattr(self, "_priorities", {})
        hideable = sorted(
            (priority, index) for index, priority in priorities.items() if index < count
        )
        hidden: set[int] = set()
        total = sum(minimums[i] for i in range(count))
        for _priority, index in hideable:
            if total <= available:
                break
            hidden.add(index)
            total -= minimums[index]
        return hidden

    # ------------------------------------------------------------------ события
    def resizeEvent(self, event) -> None:  # noqa: N802 - Qt API
        super().resizeEvent(event)
        if not getattr(self, "_applying", False):
            self.apply_column_fit()

    def _on_section_resized(self, index: int, _old: int, _new: int) -> None:
        if getattr(self, "_applying", False) or self._minimised:
            return
        # Пользователь потянул границу — дальше ширины не пересчитываем.
        self._minimised = True
