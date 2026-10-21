"""Technical Library: документы, схемы, фотографии, инструкции и заметки."""

from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import QUrl, Qt
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QSplitter,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from repair_os.data.models import CATEGORIES, DOC_TYPES, VERIFICATION_LABELS, TechnicalDocument
from repair_os.services.context import AppContext
from repair_os.ui.dialogs.base import confirm, error, info
from repair_os.ui.dialogs.document_editor import (
    ComponentReferenceDialog,
    DocumentEditorDialog,
    NoteEditorDialog,
)
from repair_os.ui.table_models import DocumentTableModel, SearchProxy
from repair_os.ui.widgets import (
    Card,
    breakable,
    wrapped_label,
    SearchInput,
    StatusBadge,
    badge,
    clear_layout,
    field_row,
    muted,
    separator,
    title,
)

log = logging.getLogger(__name__)


class LibraryPage(QWidget):
    route_key = "library"

    def __init__(self, context: AppContext, window) -> None:
        super().__init__()
        self.context = context
        self.window = window
        self._selected: TechnicalDocument | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 14)
        layout.setSpacing(10)

        header = QHBoxLayout()
        box = QVBoxLayout()
        box.setSpacing(2)
        box.addWidget(title("Technical Library", object_name="PageTitle"))
        subtitle = muted(
            "PDF, схемы, BoardView, фотографии плат, инструкции и заметки. Привязка к модели "
            "и отметка достоверности."
        )
        subtitle.setMaximumWidth(560)
        box.addWidget(subtitle)
        header.addLayout(box)
        header.addStretch(1)
        self.count_label = QLabel("", self)
        self.count_label.setObjectName("Muted")
        header.addWidget(self.count_label)
        ref_button = QPushButton("Справка по компоненту", self)
        ref_button.setObjectName("Ghost")
        ref_button.clicked.connect(self._add_reference)
        header.addWidget(ref_button)
        note_button = QPushButton("+ Заметка", self)
        note_button.setObjectName("Ghost")
        note_button.clicked.connect(self._add_note)
        header.addWidget(note_button)
        import_button = QPushButton("Импорт CSV/JSON", self)
        import_button.setObjectName("Ghost")
        import_button.clicked.connect(lambda: self.window.run_import("documents"))
        header.addWidget(import_button)
        add_button = QPushButton("+ Материал", self)
        add_button.setObjectName("Primary")
        add_button.clicked.connect(self.add_document)
        header.addWidget(add_button)
        layout.addLayout(header)

        filters = QHBoxLayout()
        filters.setSpacing(8)
        self.search = SearchInput("Поиск по названию, устройству, тегам и описанию…", self)
        self.search.textChanged.connect(self.refresh)
        filters.addWidget(self.search, 1)
        self.category_combo = QComboBox(self)
        self.category_combo.addItem("Все категории", None)
        for key, label in CATEGORIES.items():
            self.category_combo.addItem(label, key)
        self.category_combo.currentIndexChanged.connect(self.refresh)
        filters.addWidget(self.category_combo)
        self.type_combo = QComboBox(self)
        self.type_combo.addItem("Все типы", None)
        for key, label in DOC_TYPES.items():
            self.type_combo.addItem(label, key)
        self.type_combo.currentIndexChanged.connect(self.refresh)
        filters.addWidget(self.type_combo)
        self.status_combo = QComboBox(self)
        self.status_combo.addItem("Все статусы", None)
        for key, label in VERIFICATION_LABELS.items():
            self.status_combo.addItem(label, key)
        self.status_combo.currentIndexChanged.connect(self.refresh)
        filters.addWidget(self.status_combo)
        layout.addLayout(filters)

        splitter = QSplitter(Qt.Horizontal, self)
        splitter.addWidget(self._build_table())
        splitter.addWidget(self._build_detail())
        splitter.setSizes([900, 400])
        splitter.setChildrenCollapsible(False)
        layout.addWidget(splitter, 1)

        self.rights_hint = muted(
            "Используйте только документы, на которые у вас есть права. "
            "Приложение не поставляет стороннюю техническую документацию.",
            self,
        )
        layout.addWidget(self.rights_hint)

    # ------------------------------------------------------------------ UI
    def _build_table(self) -> QWidget:
        self.model = DocumentTableModel(self)
        self.proxy = SearchProxy(self)
        self.proxy.setSourceModel(self.model)
        self.table = QTableView(self)
        self.table.setModel(self.proxy)
        self.table.setSortingEnabled(True)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.selectionModel().selectionChanged.connect(self._on_selection)
        self.table.doubleClicked.connect(lambda _index: self._open_file())
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        for column in (1, 2, 5, 6):
            header.setSectionResizeMode(column, QHeaderView.ResizeToContents)
        for column, width in ((3, 160), (4, 140)):
            header.setSectionResizeMode(column, QHeaderView.Interactive)
            self.table.setColumnWidth(column, width)
        return self.table

    def _build_detail(self) -> QWidget:
        from PySide6.QtWidgets import QScrollArea

        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        container = QWidget(scroll)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        layout.setSizeConstraint(QVBoxLayout.SetMinAndMaxSize)
        self.detail_card = Card(container)
        self.detail_body = self.detail_card.body()
        layout.addWidget(self.detail_card)
        self.actions_card = Card(container)
        self.actions_body = self.actions_card.body()
        layout.addWidget(self.actions_card)

        self.notes_card = Card(container)
        self.notes_body = self.notes_card.body()
        layout.addWidget(self.notes_card)
        layout.addStretch(1)
        scroll.setWidget(container)
        self._render_detail(None)
        return scroll

    # ------------------------------------------------------------------ данные
    def on_show(self) -> None:
        self.refresh()
        self._render_notes()

    def refresh(self) -> None:
        rows = self.context.library.list_documents(
            search=self.search.text().strip() or None,
            category=self.category_combo.currentData(),
            doc_type=self.type_combo.currentData(),
            status=self.status_combo.currentData(),
            limit=2000,
        )
        self.model.set_rows(rows)
        self.count_label.setText(f"Материалов: {len(rows)}")
        if rows and self._selected is None:
            self.table.selectRow(0)
        self._render_notes()

    def focus_document(self, document_id: int | None) -> None:
        self.on_show()
        if not document_id:
            return
        for row, item in enumerate(self.model.rows):
            if item.id == document_id:
                proxy_index = self.proxy.mapFromSource(self.model.index(row, 0))
                self.table.selectRow(proxy_index.row())
                self.table.scrollTo(proxy_index)
                self._render_detail(item)
                break

    def _on_selection(self, *_args) -> None:
        indexes = self.table.selectionModel().selectedRows()
        if not indexes:
            self._render_detail(None)
            return
        source_index = self.proxy.mapToSource(indexes[0])
        self._render_detail(self.model.row_at(source_index))

    # ------------------------------------------------------------------ детали
    def _render_detail(self, document: TechnicalDocument | None) -> None:
        self._selected = document
        clear_layout(self.detail_body)
        clear_layout(self.actions_body)
        self.detail_body.addWidget(title("Сведения", object_name="CardTitle"))
        if document is None:
            self.detail_body.addWidget(muted("Выберите материал в таблице."))
            return
        header = QHBoxLayout()
        name = wrapped_label(breakable(document.title), self.detail_card, object_name="CardTitle", lines=2)
        header.addWidget(name, 1)
        if document.is_demo:
            header.addWidget(badge("ДЕМО", "demo", self.detail_card))
        self.detail_body.addLayout(header)
        self.detail_body.addWidget(StatusBadge(document.verification_status, self.detail_card))
        for label, value in (
            ("Категория", CATEGORIES.get(document.category, document.category)),
            ("Тип", DOC_TYPES.get(document.doc_type, document.doc_type)),
            ("Устройство", document.device_name or "не привязано"),
            ("Проверено", document.verified_at or "—"),
            ("Теги", document.tags or "—"),
            ("Источник", document.source_url or "не указан"),
            ("Права", document.license_note or "не указаны"),
            ("Файл", document.file_path or "не приложен"),
        ):
            self.detail_body.addWidget(field_row(label, value, self.detail_card))
        if document.description:
            self.detail_body.addWidget(separator(self.detail_card))
            self.detail_body.addWidget(field_row("Описание", document.description, self.detail_card))

        self.actions_body.addWidget(title("Действия", object_name="CardTitle"))
        open_file = QPushButton("Открыть файл", self.actions_card)
        open_file.setObjectName("Primary")
        open_file.setEnabled(bool(document.file_path and Path(document.file_path).exists()))
        open_file.clicked.connect(self._open_file)
        self.actions_body.addWidget(open_file)
        open_link = QPushButton("Открыть ссылку", self.actions_card)
        open_link.setObjectName("Ghost")
        open_link.setEnabled(bool(document.source_url))
        open_link.clicked.connect(self._open_link)
        self.actions_body.addWidget(open_link)
        edit = QPushButton("Изменить", self.actions_card)
        edit.setObjectName("Ghost")
        edit.clicked.connect(self._edit_selected)
        self.actions_body.addWidget(edit)
        verify = QPushButton("Отметить как проверенный", self.actions_card)
        verify.setObjectName("Ghost")
        verify.clicked.connect(
            lambda: self._set_status("verified") if document else None
        )
        self.actions_body.addWidget(verify)
        delete = QPushButton("Удалить", self.actions_card)
        delete.setObjectName("Danger")
        delete.clicked.connect(self._delete_selected)
        self.actions_body.addWidget(delete)

    def _render_notes(self) -> None:
        clear_layout(self.notes_body)
        header = QHBoxLayout()
        header.addWidget(title("Заметки мастера", object_name="CardTitle"))
        header.addStretch(1)
        add = QPushButton("+", self.notes_card)
        add.clicked.connect(self._add_note)
        header.addWidget(add)
        self.notes_body.addLayout(header)
        notes = self.context.library.notes(limit=8)
        if not notes:
            self.notes_body.addWidget(muted("Заметок нет.", self.notes_card))
        for note in notes:
            row = QHBoxLayout()
            text = QLabel(f"• {note.title}", self.notes_card)
            text.setObjectName("Muted")
            text.setWordWrap(True)
            row.addWidget(text, 1)
            remove = QPushButton("×", self.notes_card)
            remove.setObjectName("LinkButton")
            remove.setFixedWidth(22)
            remove.clicked.connect(lambda _checked=False, nid=note.id: self._delete_note(nid))
            row.addWidget(remove)
            self.notes_body.addLayout(row)

    # ------------------------------------------------------------------ действия
    def add_document(self) -> None:
        dialog = DocumentEditorDialog(self.context, parent=self.window)
        if dialog.exec():
            self.refresh()
            self.window.set_status("Материал добавлен")

    def _edit_selected(self) -> None:
        if not self._selected:
            return
        dialog = DocumentEditorDialog(self.context, document=self._selected, parent=self.window)
        if dialog.exec():
            self.refresh()
            self.window.set_status("Изменения сохранены")

    def _delete_selected(self) -> None:
        if not self._selected:
            return
        if not confirm(
            self.window,
            "Удалить материал",
            f"Удалить «{self._selected.title}» из библиотеки? Файл на диске останется.",
            confirm_text="Удалить",
            danger=True,
        ):
            return
        try:
            self.context.library.delete_document(int(self._selected.id or 0))
        except Exception as exc:
            error(self.window, "Ошибка", str(exc))
            return
        self._selected = None
        self.refresh()
        self._render_detail(None)

    def _set_status(self, status: str) -> None:
        if not self._selected:
            return
        try:
            self.context.library.update_document(
                int(self._selected.id or 0), {"verification_status": status}
            )
        except Exception as exc:
            error(self.window, "Ошибка", str(exc))
            return
        document_id = self._selected.id
        self.refresh()
        self.focus_document(document_id)
        self.window.set_status("Статус проверки обновлён")

    def _open_file(self) -> None:
        if not self._selected or not self._selected.file_path:
            return
        path = Path(self._selected.file_path)
        if not path.exists():
            info(self.window, "Файл не найден", f"Файл отсутствует: {path}")
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))

    def _open_link(self) -> None:
        if not self._selected or not self._selected.source_url:
            return
        if not confirm(
            self.window,
            "Открыть ссылку",
            "Ссылка откроется в браузере. Проверяйте источник и права на материалы.",
            confirm_text="Открыть",
        ):
            return
        QDesktopServices.openUrl(QUrl(self._selected.source_url))

    def _add_note(self) -> None:
        dialog = NoteEditorDialog(self.context, parent=self.window)
        if dialog.exec():
            self._render_notes()
            self.window.set_status("Заметка сохранена")

    def _delete_note(self, note_id: int | None) -> None:
        if not note_id:
            return
        if confirm(self.window, "Удалить заметку", "Удалить заметку?", confirm_text="Удалить"):
            self.context.library.delete_note(int(note_id))
            self._render_notes()

    def _add_reference(self) -> None:
        dialog = ComponentReferenceDialog(self.context, parent=self.window)
        if dialog.exec():
            self.window.set_status("Справка по компоненту сохранена")
