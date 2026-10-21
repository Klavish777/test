"""Диалоги Technical Library: документ, заметка, справка по компоненту."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QCheckBox, QFileDialog, QHBoxLayout, QLineEdit, QPushButton, QWidget

from repair_os.core.security import sanitize_filename
from repair_os.data.models import CATEGORIES, DOC_TYPES, VERIFICATION_LABELS, Device, RepairNote, TechnicalDocument
from repair_os.services.context import AppContext
from repair_os.ui.dialogs.base import FormDialog, info
from repair_os.ui.widgets import muted


class DocumentEditorDialog(FormDialog):
    def __init__(
        self,
        context: AppContext,
        *,
        document: TechnicalDocument | None = None,
        preset_device: Device | None = None,
        parent=None,
    ) -> None:
        super().__init__(
            "Редактирование материала" if document else "Новый материал",
            subtitle=(
                "Файл копируется в локальную библиотеку. Указывайте источник и права "
                "на использование сторонней документации."
            ),
            parent=parent,
            width=620,
        )
        self.context = context
        self.document = document

        self.title = self.add_line("Название *", document.title if document else "")
        self.category = self.add_combo(
            "Категория",
            [(label, key) for key, label in CATEGORIES.items()],
            current=document.category if document else "general",
        )
        self.doc_type = self.add_combo(
            "Тип материала",
            [(label, key) for key, label in DOC_TYPES.items()],
            current=document.doc_type if document else "pdf",
        )
        devices = context.devices.list(limit=2000)
        device_items = [("— не привязывать —", None)] + [
            (f"{device.brand_name} {device.name} · {device.model_code}", device.id)
            for device in devices
        ]
        default_device = document.device_id if document else (preset_device.id if preset_device else None)
        self.device = self.add_combo("Устройство", device_items, current=default_device)

        file_row = QWidget(self.container)
        file_layout = QHBoxLayout(file_row)
        file_layout.setContentsMargins(0, 0, 0, 0)
        file_layout.setSpacing(6)
        self.file_path = QLineEdit(document.file_path if document and document.file_path else "", file_row)
        self.file_path.setPlaceholderText("Путь к файлу (PDF, изображение, схема)")
        browse = QPushButton("Обзор…", file_row)
        browse.clicked.connect(self._browse)
        file_layout.addWidget(self.file_path, 1)
        file_layout.addWidget(browse)
        self.add_widget("Файл", file_row)

        self.source_url = self.add_line(
            "Ссылка на источник", document.source_url if document else "", placeholder="https://…"
        )
        self.tags = self.add_line(
            "Теги (через запятую)", document.tags if document else "", placeholder="power,pmic"
        )
        self.description = self.add_text(
            "Описание", document.description if document else "", height=90
        )
        self.license_note = self.add_line(
            "Права на использование",
            document.license_note if document else "",
            placeholder="Собственная работа / разрешение автора / не использовать",
        )
        self.status = self.add_combo(
            "Статус проверки",
            [(label, key) for key, label in VERIFICATION_LABELS.items()],
            current=document.verification_status if document else "unverified",
        )
        self.add_widget(
            "",
            muted(
                "Не публикуйте чужие схемы и BoardView без разрешения правообладателя.",
                self.container,
            ),
        )
        self.on_save(self._save)

    def _browse(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Выберите материал",
            "",
            "Документы (*.pdf *.png *.jpg *.jpeg *.txt *.md);;Все файлы (*.*)",
        )
        if path:
            self.file_path.setText(path)

    def collect(self) -> dict[str, Any]:
        return {
            "title": self.title.text(),
            "category": self.category.currentData(),
            "doc_type": self.doc_type.currentData(),
            "device_id": self.device.currentData(),
            "file_path": self.file_path.text().strip() or None,
            "source_url": self.source_url.text().strip() or None,
            "tags": self.tags.text(),
            "description": self.description.toPlainText(),
            "license_note": self.license_note.text(),
            "verification_status": self.status.currentData(),
        }

    def _save(self, payload: dict[str, Any]) -> TechnicalDocument:
        # Копируем выбранный файл в локальную библиотеку (без перезаписи чужих файлов).
        file_path = payload.get("file_path")
        if file_path and Path(file_path).exists() and not Path(file_path).is_relative_to(
            self.context.library_root()
        ):
            target_dir = self.context.library_root() / "documents"
            target_dir.mkdir(parents=True, exist_ok=True)
            target = target_dir / sanitize_filename(Path(file_path).name)
            if target.exists() and target.resolve() != Path(file_path).resolve():
                counter = 1
                while target.exists():
                    target = target_dir / f"{Path(file_path).stem}-{counter}{Path(file_path).suffix}"
                    counter += 1
            if not target.exists():
                import shutil

                shutil.copy2(file_path, target)
            payload["file_path"] = str(target)
        if self.document:
            return self.context.library.update_document(int(self.document.id or 0), payload)
        return self.context.library.create_document(payload)


class NoteEditorDialog(FormDialog):
    def __init__(
        self,
        context: AppContext,
        *,
        note: RepairNote | None = None,
        preset_device: Device | None = None,
        component_id: int | None = None,
        default_title: str = "",
        parent=None,
    ) -> None:
        super().__init__(
            "Заметка мастера" if note else "Новая заметка",
            parent=parent,
            width=520,
        )
        self.context = context
        self.note = note
        self.component_id = component_id
        self.title = self.add_line(
            "Заголовок *",
            note.title if note else default_title,
            placeholder="Например: диагностика цепи",
        )
        self.category = self.add_combo(
            "Категория",
            [(label, key) for key, label in CATEGORIES.items()],
            current=note.category if note else "general",
        )
        devices = context.devices.list(limit=2000)
        device_items = [("— не привязывать —", None)] + [
            (f"{device.brand_name} {device.name} · {device.model_code}", device.id)
            for device in devices
        ]
        self.device = self.add_combo(
            "Устройство",
            device_items,
            current=note.device_id if note else (preset_device.id if preset_device else None),
        )
        self.body = self.add_text("Текст заметки", note.body if note else "", height=180)
        self.on_save(self._save)

    def collect(self) -> dict[str, Any]:
        return {
            "title": self.title.text(),
            "category": self.category.currentData(),
            "device_id": self.device.currentData(),
            "board_component_id": self.component_id
            or (self.note.board_component_id if self.note else None),
            "body": self.body.toPlainText(),
        }

    def _save(self, payload: dict[str, Any]) -> RepairNote:
        if self.note:
            return self.context.library.update_note(int(self.note.id or 0), payload)
        return self.context.library.create_note(payload)


class ComponentReferenceDialog(FormDialog):
    def __init__(
        self,
        context: AppContext,
        *,
        preset_device: Device | None = None,
        parent=None,
    ) -> None:
        super().__init__(
            "Справка по компоненту",
            subtitle=(
                "Указывайте только достоверную информацию. Если назначение неизвестно — "
                "оставьте поле пустым."
            ),
            parent=parent,
            width=520,
        )
        self.context = context
        devices = context.devices.list(limit=2000)
        device_items = [("— не привязывать —", None)] + [
            (f"{device.brand_name} {device.name} · {device.model_code}", device.id)
            for device in devices
        ]
        self.device = self.add_combo(
            "Устройство",
            device_items,
            current=preset_device.id if preset_device else None,
        )
        self.designator = self.add_line("Обозначение", "", placeholder="U1201")
        self.component_type = self.add_line("Тип", "", placeholder="PMIC / конденсатор / разъём")
        self.marking = self.add_line("Маркировка", "", placeholder="Как на корпусе")
        self.description = self.add_text("Описание / назначение", "", height=90)
        self.source_url = self.add_line("Источник", "", placeholder="https://…")
        self.on_save(self._save)

    def collect(self) -> dict[str, Any]:
        return {
            "device_id": self.device.currentData(),
            "designator": self.designator.text().strip() or None,
            "component_type": self.component_type.text(),
            "marking": self.marking.text(),
            "description": self.description.toPlainText(),
            "source_url": self.source_url.text().strip() or None,
        }

    def _save(self, payload: dict[str, Any]):
        return self.context.library.add_component_reference(payload)
