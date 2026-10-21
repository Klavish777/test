"""Базовые диалоги: форма с валидацией, подтверждение опасных операций."""

from __future__ import annotations

from typing import Any, Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QFrame,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from repair_os.core.errors import RepairOSError, ValidationError
from repair_os.ui.theme import COLORS
from repair_os.ui.widgets import muted


class FormDialog(QDialog):
    """Диалог с формой: принимает данные, валидирует и сохраняет через callback."""

    def __init__(
        self,
        title: str,
        *,
        subtitle: str = "",
        save_text: str = "Сохранить",
        parent: QWidget | None = None,
        width: int = 560,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)
        self.resize(width, 520)
        self._save_handler: Callable[[dict[str, Any]], Any] | None = None
        self._saved_value: Any = None

        outer = QVBoxLayout(self)
        outer.setContentsMargins(20, 18, 20, 16)
        outer.setSpacing(10)

        heading = QLabel(title, self)
        heading.setObjectName("PageTitle")
        outer.addWidget(heading)
        if subtitle:
            hint = muted(subtitle, self)
            outer.addWidget(hint)

        self._error = QLabel("", self)
        self._error.setWordWrap(True)
        self._error.setStyleSheet(
            f"background-color: rgba(229,83,75,0.12); border: 1px solid {COLORS['danger']};"
            f"border-radius: 8px; padding: 8px 10px; color: {COLORS['danger']};"
        )
        self._error.hide()
        outer.addWidget(self._error)

        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        self.container = QWidget(scroll)
        self.form = QFormLayout(self.container)
        self.form.setContentsMargins(0, 4, 8, 4)
        self.form.setSpacing(10)
        self.form.setLabelAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        scroll.setWidget(self.container)
        outer.addWidget(scroll, 1)

        buttons = QDialogButtonBox(self)
        self.save_button = buttons.addButton(save_text, QDialogButtonBox.AcceptRole)
        self.save_button.setObjectName("Primary")
        cancel = buttons.addButton("Отмена", QDialogButtonBox.RejectRole)
        cancel.setObjectName("Ghost")
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        outer.addWidget(buttons)

    # ------------------------------------------------------------------ поля
    def add_line(self, label: str, value: str = "", *, placeholder: str = "", required: bool = False) -> QLineEdit:
        field = QLineEdit(self.container)
        field.setText(value or "")
        if placeholder:
            field.setPlaceholderText(placeholder)
        if required:
            field.setProperty("required", True)
        self.form.addRow(label, field)
        return field

    def add_text(self, label: str, value: str = "", *, height: int = 90, placeholder: str = "") -> QPlainTextEdit:
        field = QPlainTextEdit(self.container)
        field.setPlainText(value or "")
        field.setFixedHeight(height)
        if placeholder:
            field.setPlaceholderText(placeholder)
        self.form.addRow(label, field)
        return field

    def add_combo(self, label: str, items: list[tuple[str, Any]], *, current: Any = None) -> QComboBox:
        field = QComboBox(self.container)
        for text, data in items:
            field.addItem(text, data)
        if current is not None:
            index = field.findData(current)
            if index >= 0:
                field.setCurrentIndex(index)
        self.form.addRow(label, field)
        return field

    def add_spin(self, label: str, value: int = 0, *, minimum: int = 0, maximum: int = 1_000_000) -> QSpinBox:
        field = QSpinBox(self.container)
        field.setRange(minimum, maximum)
        field.setValue(value)
        self.form.addRow(label, field)
        return field

    def add_widget(self, label: str, widget: QWidget) -> QWidget:
        self.form.addRow(label, widget)
        return widget

    # ------------------------------------------------------------------ обработка
    def on_save(self, handler: Callable[[dict[str, Any]], Any]) -> None:
        self._save_handler = handler

    def collect(self) -> dict[str, Any]:  # pragma: no cover - переопределяется
        return {}

    def _on_accept(self) -> None:
        self._error.hide()
        try:
            payload = self.collect()
        except ValidationError as exc:
            self.show_error(str(exc))
            return
        if self._save_handler is None:
            self.accept()
            return
        try:
            self._saved_value = self._save_handler(payload)
        except ValidationError as exc:
            self.show_error(str(exc))
            return
        except RepairOSError as exc:
            self.show_error(str(exc))
            return
        except Exception as exc:  # pragma: no cover - неожиданная ошибка
            self.show_error(f"Не удалось сохранить: {exc}")
            return
        self.accept()

    def show_error(self, message: str) -> None:
        self._error.setText(message)
        self._error.show()

    @property
    def saved_value(self) -> Any:
        return self._saved_value


def confirm(
    parent: QWidget | None,
    title: str,
    message: str,
    *,
    confirm_text: str = "Продолжить",
    danger: bool = False,
) -> bool:
    box = QMessageBox(parent)
    box.setWindowTitle(title)
    box.setText(message)
    box.setIcon(QMessageBox.Warning if danger else QMessageBox.Question)
    ok = box.addButton(confirm_text, QMessageBox.AcceptRole)
    if danger:
        ok.setObjectName("Danger")
    cancel = box.addButton("Отмена", QMessageBox.RejectRole)
    box.setDefaultButton(cancel)
    box.exec()
    return box.clickedButton() is ok


def info(parent: QWidget | None, title: str, message: str) -> None:
    box = QMessageBox(parent)
    box.setWindowTitle(title)
    box.setText(message)
    box.setIcon(QMessageBox.Information)
    box.exec()


def error(parent: QWidget | None, title: str, message: str) -> None:
    box = QMessageBox(parent)
    box.setWindowTitle(title)
    box.setText(message)
    box.setIcon(QMessageBox.Critical)
    box.exec()


def wrap_message(text: str, limit: int = 700) -> str:
    return text if len(text) <= limit else text[:limit] + "…"


class DangerDialog(QDialog):
    """Диалог подтверждения опасной операции с явным вводом слова."""

    def __init__(
        self,
        title: str,
        message: str,
        *,
        keyword: str = "ПОДТВЕРЖДАЮ",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)
        self.setMinimumWidth(520)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 16)
        layout.setSpacing(12)
        heading = QLabel(title, self)
        heading.setObjectName("PageTitle")
        layout.addWidget(heading)
        body = QLabel(message, self)
        body.setWordWrap(True)
        layout.addWidget(body)
        hint = QLabel(f'Введите «{keyword}», чтобы подтвердить действие:', self)
        hint.setObjectName("Muted")
        layout.addWidget(hint)
        self.input = QLineEdit(self)
        self.input.setPlaceholderText(keyword)
        layout.addWidget(self.input)
        buttons = QDialogButtonBox(self)
        self._ok = buttons.addButton("Выполнить", QDialogButtonBox.AcceptRole)
        self._ok.setObjectName("Danger")
        self._ok.setEnabled(False)
        buttons.addButton("Отмена", QDialogButtonBox.RejectRole)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self._keyword = keyword
        self.input.textChanged.connect(
            lambda text: self._ok.setEnabled(text.strip().upper() == self._keyword.upper())
        )

    @classmethod
    def ask(cls, parent: QWidget | None, title: str, message: str, *, keyword: str = "ПОДТВЕРЖДАЮ") -> bool:
        dialog = cls(title, message, keyword=keyword, parent=parent)
        return dialog.exec() == QDialog.Accepted


class ReportDialog(QDialog):
    """Показывает отчёт импорта/проверки."""

    def __init__(self, title: str, summary: str, lines: list[str], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(640, 480)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 14)
        heading = QLabel(title, self)
        heading.setObjectName("PageTitle")
        layout.addWidget(heading)
        summary_label = QLabel(summary, self)
        summary_label.setObjectName("Muted")
        summary_label.setWordWrap(True)
        layout.addWidget(summary_label)
        view = QPlainTextEdit(self)
        view.setReadOnly(True)
        view.setPlainText("\n".join(lines) if lines else "Замечаний нет")
        layout.addWidget(view, 1)
        buttons = QDialogButtonBox(QDialogButtonBox.Close, self)
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)
        layout.addWidget(buttons)
