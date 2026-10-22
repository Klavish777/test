"""Переиспользуемые UI-компоненты Apple Flash Studio."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLayout,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)


def breakable(text: str) -> str:
    """Добавляет невидимые точки переноса (\u200b) для длинных имён файлов, путей и SHA-256."""
    if not text:
        return ""
    out: list[str] = []
    run = 0
    for ch in text:
        out.append(ch)
        if ch in {"_", "/", "\\", "-", "."}:
            out.append("\u200b")
            run = 0
        elif ch == " ":
            run = 0
        else:
            run += 1
            if run >= 20:
                out.append("\u200b")
                run = 0
    return "".join(out)


class StudioCard(QFrame):
    def __init__(self, parent: QWidget | None = None, *, hero: bool = False) -> None:
        super().__init__(parent)
        self.setObjectName("HeroCard" if hero else "Card")
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(16, 14, 16, 14)
        self._layout.setSpacing(8)

    def body(self) -> QVBoxLayout:
        return self._layout


class MetricTile(QFrame):
    def __init__(self, label: str, value: str = "0", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("MetricTile")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(2)
        self.value_lbl = QLabel(value, self)
        self.value_lbl.setObjectName("MetricValue")
        self.caption_lbl = QLabel(label, self)
        self.caption_lbl.setObjectName("Muted")
        self.caption_lbl.setWordWrap(True)
        layout.addWidget(self.value_lbl)
        layout.addWidget(self.caption_lbl)

    def set_value(self, value: str) -> None:
        self.value_lbl.setText(value)


def make_title(text: str, *, object_name: str = "CardTitle", parent: QWidget | None = None) -> QLabel:
    lbl = QLabel(text, parent)
    lbl.setObjectName(object_name)
    lbl.setWordWrap(True)
    return lbl


def make_muted(text: str, parent: QWidget | None = None) -> QLabel:
    lbl = QLabel(text, parent)
    lbl.setObjectName("Muted")
    lbl.setWordWrap(True)
    return lbl


def make_pill(text: str, tone: str = "neutral", parent: QWidget | None = None) -> QLabel:
    lbl = QLabel(text, parent)
    lbl.setObjectName("Pill")
    lbl.setProperty("tone", tone)
    lbl.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Fixed)
    return lbl


def set_pill(lbl: QLabel, text: str, tone: str) -> None:
    lbl.setText(text)
    lbl.setProperty("tone", tone)
    lbl.style().unpolish(lbl)
    lbl.style().polish(lbl)


def make_divider(parent: QWidget | None = None) -> QFrame:
    line = QFrame(parent)
    line.setObjectName("Divider")
    line.setFrameShape(QFrame.HLine)
    return line


def kv_row(label: str, value: str, parent: QWidget | None = None, *, wrap_long: bool = True) -> QWidget:
    row = QWidget(parent)
    layout = QHBoxLayout(row)
    layout.setContentsMargins(0, 2, 0, 2)
    layout.setSpacing(10)
    k = QLabel(label, row)
    k.setObjectName("Dim")
    k.setMinimumWidth(132)
    k.setMaximumWidth(155)
    k.setWordWrap(True)
    k.setAlignment(Qt.AlignTop | Qt.AlignLeft)
    v = QLabel(breakable(value) if wrap_long else value, row)
    v.setWordWrap(True)
    v.setTextInteractionFlags(Qt.TextSelectableByMouse)
    layout.addWidget(k)
    layout.addWidget(v, 1)
    return row


def clear_layout(layout: QLayout) -> None:
    """Мгновенно скрывает, отсоединяет и освобождает все виджеты и вложенные макеты."""
    while layout.count():
        item = layout.takeAt(0)
        widget = item.widget()
        child_layout = item.layout()
        if widget is not None:
            widget.hide()
            widget.setParent(None)
            widget.deleteLater()
        elif child_layout is not None:
            clear_layout(child_layout)
            child_layout.deleteLater()
