"""Карточка устройства: технические данные, варианты, платы, прошивки, материалы, заметки."""

from __future__ import annotations

import logging

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from repair_os.data.models import Device, human_size
from repair_os.services.context import AppContext
from repair_os.ui.dialogs.base import confirm, error
from repair_os.ui.dialogs.device_editor import DeviceEditorDialog
from repair_os.ui.widgets import (
    Card,
    ClickableCard,
    EmptyState,
    badge,
    clear_layout,
    field_row,
    muted,
    separator,
    title,
)

log = logging.getLogger(__name__)


class DeviceDetailPage(QWidget):
    route_key = "catalog"

    def __init__(self, context: AppContext, window) -> None:
        super().__init__()
        self.context = context
        self.window = window
        self.device: Device | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 16, 22, 16)
        layout.setSpacing(10)

        top = QHBoxLayout()
        back = QPushButton("← Каталог", self)
        back.setObjectName("Ghost")
        back.clicked.connect(lambda: self.window.navigate("catalog"))
        top.addWidget(back)
        top.addStretch(1)
        self.edit_button = QPushButton("Изменить", self)
        self.edit_button.setObjectName("Ghost")
        self.edit_button.clicked.connect(self._edit)
        top.addWidget(self.edit_button)
        self.favorite_button = QPushButton("★", self)
        self.favorite_button.setObjectName("Ghost")
        self.favorite_button.setToolTip("Добавить в избранное")
        self.favorite_button.clicked.connect(self._toggle_favorite)
        top.addWidget(self.favorite_button)
        self.delete_button = QPushButton("Удалить", self)
        self.delete_button.setObjectName("Danger")
        self.delete_button.clicked.connect(self._delete)
        top.addWidget(self.delete_button)
        layout.addLayout(top)

        self.title_label = title("Устройство", object_name="PageTitle")
        self.subtitle_label = muted("")
        self.badges = QHBoxLayout()
        self.badges.setSpacing(6)
        header = QVBoxLayout()
        header.setSpacing(4)
        header.addWidget(self.title_label)
        header.addWidget(self.subtitle_label)
        header.addLayout(self.badges)
        layout.addLayout(header)

        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        self.container = QWidget(scroll)
        self.body = QHBoxLayout(self.container)
        self.body.setContentsMargins(0, 4, 0, 4)
        self.body.setSpacing(14)
        self.left = QVBoxLayout()
        self.left.setSpacing(14)
        self.right = QVBoxLayout()
        self.right.setSpacing(14)
        self.body.addLayout(self.left, 3)
        self.body.addLayout(self.right, 2)
        scroll.setWidget(self.container)
        layout.addWidget(scroll, 1)

        self.empty = EmptyState("Устройство не выбрано", "Откройте модель из каталога.")
        layout.addWidget(self.empty)
        self.empty.hide()

    # ------------------------------------------------------------------ загрузка
    def load(self, device_id: int) -> None:
        try:
            self.device = self.context.devices.get(device_id)
        except Exception as exc:
            error(self.window, "Не удалось открыть устройство", str(exc))
            self.device = None
            return
        self._render()

    def on_show(self) -> None:
        if self.device and self.device.id:
            try:
                self.device = self.context.devices.get(self.device.id)
            except Exception:  # pragma: no cover - устройство могли удалить
                self.device = None
        if self.device:
            self._render()
        else:
            self.container.hide()
            self.empty.show()

    def _render(self) -> None:
        device = self.device
        if not device:
            return
        self.container.show()
        self.empty.hide()
        self.title_label.setText(f"{device.brand_name} {device.name}")
        self.subtitle_label.setText(
            f"Код модели: {device.model_code}"
            + (f" · кодовое имя: {device.codename}" if device.codename else "")
            + (f" · ревизия: {device.hardware_revision}" if device.hardware_revision else "")
        )
        clear_layout(self.badges)
        if device.is_demo:
            self.badges.addWidget(badge("ДЕМО-ДАННЫЕ", "demo"))
        if device.verified:
            self.badges.addWidget(badge("Проверено вручную", "verified"))
        else:
            self.badges.addWidget(badge("Не проверено", "neutral"))
        self.badges.addWidget(
            badge(f"Прошивки: {device.firmware_count}", "info")
        )
        self.badges.addWidget(badge(f"Материалы: {device.document_count}", "info"))
        self.badges.addStretch(1)
        self.favorite_button.setText("★ В избранном" if device.is_favorite else "☆ В избранное")

        clear_layout(self.left)
        clear_layout(self.right)
        self._build_specs()
        self._build_variants()
        self._build_notes()

        self._build_board()
        self._build_firmware()
        self._build_documents()
        self.left.addStretch(1)
        self.right.addStretch(1)

    # ------------------------------------------------------------------ блоки
    def _build_specs(self) -> None:
        device = self.device
        card = Card(self.container)
        body = card.body()
        body.addWidget(title("Технические данные", object_name="CardTitle"))
        body.addWidget(
            muted(
                "Внутренние технические данные. Источник: " + (device.source or "не указан"),
                card,
            )
        )
        grid = QHBoxLayout()
        left = QVBoxLayout()
        right = QVBoxLayout()
        left.addWidget(field_row("Производитель", device.brand_name, card))
        left.addWidget(field_row("Название", device.name, card))
        left.addWidget(field_row("Точный код модели", device.model_code, card))
        left.addWidget(field_row("Кодовое имя", device.codename or "неизвестно", card))
        left.addWidget(field_row("Аппаратная ревизия", device.hardware_revision or "неизвестна", card))
        right.addWidget(field_row("Процессор", device.soc or "неизвестен", card))
        right.addWidget(field_row("Платформа", device.soc_platform or "не указана", card))
        right.addWidget(field_row("ОЗУ", device.ram or "не указано", card))
        right.addWidget(field_row("Память", device.storage or "не указано", card))
        right.addWidget(field_row("Версии ОС", device.os_versions or "не указаны", card))
        grid.addLayout(left, 1)
        grid.addLayout(right, 1)
        body.addLayout(grid)
        if device.release_year:
            body.addWidget(field_row("Год выпуска", str(device.release_year), card))
        if device.notes:
            body.addWidget(separator(card))
            body.addWidget(field_row("Примечания", device.notes, card))
        self.left.addWidget(card)

    def _build_variants(self) -> None:
        device = self.device
        card = Card(self.container)
        body = card.body()
        header = QHBoxLayout()
        header.addWidget(title("Варианты и регионы", object_name="CardTitle"))
        header.addStretch(1)
        add = QPushButton("+ Вариант", card)
        add.setObjectName("Ghost")
        add.clicked.connect(self._add_variant)
        header.addWidget(add)
        body.addLayout(header)
        body.addWidget(
            muted("Регион, CSC и загрузчик учитываются при проверке совместимости прошивок.", card)
        )
        variants = self.context.devices.variants(int(device.id or 0))
        if not variants:
            body.addWidget(muted("Варианты не заведены.", card))
        for variant in variants:
            row = QFrame(card)
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0, 2, 0, 2)
            text = QVBoxLayout()
            name = QLabel(variant.name, row)
            name.setObjectName("FieldValue")
            details = QLabel(
                f"{variant.model_code}"
                + (f" · регион {variant.region}" if variant.region else "")
                + (f" · CSC {variant.csc}" if variant.csc else "")
                + (f" · загрузчик {variant.bootloader}" if variant.bootloader else ""),
                row,
            )
            details.setObjectName("Muted")
            details.setWordWrap(True)
            text.addWidget(name)
            text.addWidget(details)
            row_layout.addLayout(text, 1)
            if variant.is_demo:
                row_layout.addWidget(badge("ДЕМО", "demo", row))
            remove = QPushButton("Удалить", row)
            remove.setObjectName("LinkButton")
            remove.clicked.connect(lambda _checked=False, vid=variant.id: self._delete_variant(vid))
            row_layout.addWidget(remove)
            body.addWidget(row)
        self.left.addWidget(card)

    def _build_board(self) -> None:
        device = self.device
        card = Card(self.container)
        body = card.body()
        body.addWidget(title("BoardView", object_name="CardTitle"))
        board = self.context.boards.model_for_device(int(device.id or 0))
        if not board:
            body.addWidget(
                EmptyState(
                    "3D-модель не загружена",
                    "Для этого устройства нет данных платы. Импортируйте пакет BoardView "
                    "или фотографии платы — приложение не генерирует геометрию.",
                    "Импорт платы",
                    self.window.run_board_import,
                    card,
                )
            )
        else:
            body.addWidget(
                field_row(
                    "Плата",
                    f"{board.name} · код {board.board_code or '—'} · ревизия {board.revision or '—'}",
                    card,
                )
            )
            body.addWidget(
                field_row(
                    "Компонентов",
                    f"{board.component_count} · 3D: {'да' if board.has_3d else 'нет (только фото)'}",
                    card,
                )
            )
            if board.is_demo:
                body.addWidget(badge("ДЕМО-ПЛАТА: геометрия условная", "demo", card))
            open_button = QPushButton("Открыть BoardView", card)
            open_button.setObjectName("Primary")
            open_button.clicked.connect(lambda: self.window.open_board(board.id))
            body.addWidget(open_button)
        self.right.addWidget(card)

    def _build_firmware(self) -> None:
        device = self.device
        card = Card(self.container)
        body = card.body()
        header = QHBoxLayout()
        header.addWidget(title("Прошивки", object_name="CardTitle"))
        header.addStretch(1)
        add = QPushButton("+ Прошивка", card)
        add.setObjectName("Ghost")
        add.clicked.connect(self._add_firmware)
        header.addWidget(add)
        body.addLayout(header)
        firmware = self.context.firmware.list(device_id=int(device.id or 0), limit=10)
        if not firmware:
            body.addWidget(muted("Записей о прошивках нет.", card))
        for item in firmware:
            row = ClickableCard(card, padding=10)
            row_layout = row.body()
            head = QHBoxLayout()
            name = QLabel(item.file_name, row)
            name.setObjectName("FieldValue")
            name.setWordWrap(True)
            head.addWidget(name, 1)
            if item.is_demo:
                head.addWidget(badge("ДЕМО", "demo", row))
            row_layout.addLayout(head)
            details = QLabel(
                f"{item.os_version or 'ОС —'} · {item.build_number or 'сборка —'} · "
                f"{item.region or 'регион —'} · {human_size(item.file_size)}",
                row,
            )
            details.setObjectName("Muted")
            details.setWordWrap(True)
            row_layout.addWidget(details)
            row.clicked.connect(lambda fid=item.id: self.window.open_firmware(fid))
            body.addWidget(row)
        self.right.addWidget(card)

    def _build_documents(self) -> None:
        device = self.device
        card = Card(self.container)
        body = card.body()
        header = QHBoxLayout()
        header.addWidget(title("Технические материалы", object_name="CardTitle"))
        header.addStretch(1)
        add = QPushButton("+ Материал", card)
        add.setObjectName("Ghost")
        add.clicked.connect(self._add_document)
        header.addWidget(add)
        body.addLayout(header)
        documents = self.context.library.list_documents(device_id=int(device.id or 0), limit=10)
        if not documents:
            body.addWidget(muted("Материалов нет.", card))
        for document in documents:
            row = ClickableCard(card, padding=10)
            row_layout = row.body()
            head = QHBoxLayout()
            name = QLabel(document.title, row)
            name.setObjectName("FieldValue")
            name.setWordWrap(True)
            head.addWidget(name, 1)
            if document.is_demo:
                head.addWidget(badge("ДЕМО", "demo", row))
            row_layout.addLayout(head)
            details = QLabel(f"{document.doc_type} · {document.category}", row)
            details.setObjectName("Muted")
            row_layout.addWidget(details)
            row.clicked.connect(lambda did=document.id: self.window.open_document(did))
            body.addWidget(row)
        self.right.addWidget(card)

    def _build_notes(self) -> None:
        device = self.device
        card = Card(self.container)
        body = card.body()
        header = QHBoxLayout()
        header.addWidget(title("Заметки мастера", object_name="CardTitle"))
        header.addStretch(1)
        add = QPushButton("+ Заметка", card)
        add.setObjectName("Ghost")
        add.clicked.connect(self._add_note)
        header.addWidget(add)
        body.addLayout(header)
        notes = self.context.library.notes(device_id=int(device.id or 0), limit=10)
        if not notes:
            body.addWidget(muted("Заметок нет.", card))
        for note in notes:
            row = QVBoxLayout()
            head = QHBoxLayout()
            name = QLabel(note.title, card)
            name.setObjectName("FieldValue")
            head.addWidget(name, 1)
            remove = QPushButton("Удалить", card)
            remove.setObjectName("LinkButton")
            remove.clicked.connect(lambda _checked=False, nid=note.id: self._delete_note(nid))
            head.addWidget(remove)
            row.addLayout(head)
            text = QLabel(note.body or "", card)
            text.setObjectName("Muted")
            text.setWordWrap(True)
            row.addWidget(text)
            body.addLayout(row)
            body.addWidget(separator(card))
        self.left.addWidget(card)

    # ------------------------------------------------------------------ действия
    def _edit(self) -> None:
        if not self.device:
            return
        dialog = DeviceEditorDialog(self.context, device=self.device, parent=self.window)
        if dialog.exec():
            self.device = dialog.result_device or self.device
            self._render()
            self.window.set_status("Изменения сохранены")

    def _toggle_favorite(self) -> None:
        if not self.device or not self.device.id:
            return
        state = self.context.devices.toggle_favorite(self.device.id)
        self.device.is_favorite = int(state)
        self.favorite_button.setText("★ В избранном" if state else "☆ В избранное")
        self.window.set_status("Избранное обновлено")

    def _delete(self) -> None:
        if not self.device:
            return
        if not confirm(
            self.window,
            "Удалить устройство",
            f"Удалить «{self.device.brand_name} {self.device.name}» "
            "вместе со связанными записями?",
            confirm_text="Удалить",
            danger=True,
        ):
            return
        try:
            self.context.devices.delete(int(self.device.id or 0))
        except Exception as exc:
            error(self.window, "Ошибка", str(exc))
            return
        self.device = None
        self.window.navigate("catalog")

    def _add_variant(self) -> None:
        from repair_os.ui.dialogs.variant_editor import VariantEditorDialog

        if not self.device:
            return
        dialog = VariantEditorDialog(self.context, device=self.device, parent=self.window)
        if dialog.exec():
            self.on_show()

    def _delete_variant(self, variant_id: int) -> None:
        if confirm(self.window, "Удалить вариант", "Удалить выбранный вариант?", confirm_text="Удалить", danger=True):
            self.context.devices.delete_variant(int(variant_id))
            self.on_show()

    def _add_firmware(self) -> None:
        from repair_os.ui.dialogs.firmware_editor import FirmwareEditorDialog

        if not self.device:
            return
        dialog = FirmwareEditorDialog(
            self.context, preset_device=self.device, parent=self.window
        )
        if dialog.exec():
            saved = dialog.result_firmware
            self.on_show()
            self.window.set_status("Запись прошивки добавлена")
            if saved and saved.id:
                self.window.open_firmware(saved.id)

    def _add_document(self) -> None:
        from repair_os.ui.dialogs.document_editor import DocumentEditorDialog

        if not self.device:
            return
        dialog = DocumentEditorDialog(
            self.context, preset_device=self.device, parent=self.window
        )
        if dialog.exec():
            self.on_show()

    def _add_note(self) -> None:
        from repair_os.ui.dialogs.document_editor import NoteEditorDialog

        if not self.device:
            return
        dialog = NoteEditorDialog(self.context, preset_device=self.device, parent=self.window)
        if dialog.exec():
            self.on_show()

    def _delete_note(self, note_id: int) -> None:
        if confirm(self.window, "Удалить заметку", "Удалить заметку?", confirm_text="Удалить", danger=True):
            self.context.library.delete_note(int(note_id))
            self.on_show()
