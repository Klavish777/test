"""Диалоги Firmware Center: запись прошивки и источник."""

from __future__ import annotations

from typing import Any

from PySide6.QtWidgets import QCheckBox

from repair_os.data.models import VERIFICATION_LABELS, Device, Firmware, FirmwareSource
from repair_os.services.context import AppContext
from repair_os.ui.dialogs.base import FormDialog
from repair_os.ui.widgets import muted


class FirmwareEditorDialog(FormDialog):
    def __init__(
        self,
        context: AppContext,
        *,
        firmware: Firmware | None = None,
        preset_device: Device | None = None,
        parent=None,
    ) -> None:
        is_edit = firmware is not None
        super().__init__(
            "Редактирование прошивки" if is_edit else "Новая запись прошивки",
            subtitle=(
                "Совместимость определяется точным кодом модели, регионом/CSC и версией "
                "загрузчика — не только названием устройства."
            ),
            save_text="Сохранить",
            parent=parent,
            width=620,
        )
        self.context = context
        self.firmware = firmware

        devices = context.devices.list(limit=2000)
        device_items = [("— не привязывать —", None)] + [
            (f"{device.brand_name} {device.name} · {device.model_code}", device.id)
            for device in devices
        ]
        default_device = (
            firmware.device_id
            if firmware
            else (preset_device.id if preset_device else None)
        )
        self.device = self.add_combo("Устройство", device_items, current=default_device)

        sources = context.firmware.sources()
        source_items = [("— без источника —", None)] + [
            (f"{source.name}{' ✓' if source.trusted else ''}", source.id) for source in sources
        ]
        self.source = self.add_combo(
            "Источник", source_items, current=firmware.source_id if firmware else None
        )

        self.file_name = self.add_line(
            "Имя файла *",
            firmware.file_name if firmware else "",
            placeholder="SM-A525F_...zip",
        )
        self.title = self.add_line("Заголовок", firmware.title if firmware else "")
        self.model_code = self.add_line(
            "Точный код модели *",
            firmware.model_code
            if firmware
            else (
                preset_device.model_code
                if preset_device
                else ""
            ),
            placeholder="SM-A525F",
        )
        self.os_version = self.add_line("Версия ОС", firmware.os_version if firmware else "")
        self.build_number = self.add_line(
            "Номер сборки", firmware.build_number if firmware else "", placeholder="A525FXXU4DWB1"
        )
        self.region = self.add_line("Регион", firmware.region if firmware else "", placeholder="SER / EUX")
        self.csc = self.add_line("CSC", firmware.csc if firmware else "", placeholder="SER")
        self.release_date = self.add_line(
            "Дата выпуска (ГГГГ-ММ-ДД)",
            firmware.release_date if firmware else "",
            placeholder="2023-02-14",
        )
        self.file_size = self.add_line(
            "Размер файла (байт)",
            str(firmware.file_size) if firmware and firmware.file_size else "",
            placeholder="3500000000",
        )
        self.checksum = self.add_line(
            "Эталонная SHA-256",
            (firmware.checksum_reference or firmware.checksum_sha256 or "") if firmware else "",
            placeholder="64 hex-символа (необязательно)",
        )
        self.download_url = self.add_line(
            "Ссылка на загрузку",
            firmware.download_url if firmware else "",
            placeholder="https://…",
        )
        self.min_bootloader = self.add_line(
            "Мин. версия загрузчика", firmware.min_bootloader if firmware else ""
        )
        self.compatibility = self.add_text(
            "Совместимость и ограничения", firmware.compatibility_notes if firmware else "", height=70
        )
        self.instructions = self.add_text(
            "Инструкция по установке", firmware.install_instructions if firmware else "", height=90
        )
        self.status = self.add_combo(
            "Статус проверки",
            [(label, key) for key, label in VERIFICATION_LABELS.items()],
            current=firmware.verification_status if firmware else "unverified",
        )
        self.add_widget(
            "",
            muted(
                "Ссылки ведут на внешние ресурсы. Приложение не скачивает файлы автоматически "
                "и не обходит защиту устройств.",
                self.container,
            ),
        )
        self.on_save(self._save)

    def collect(self) -> dict[str, Any]:
        return {
            "device_id": self.device.currentData(),
            "source_id": self.source.currentData(),
            "file_name": self.file_name.text(),
            "title": self.title.text(),
            "model_code": self.model_code.text(),
            "os_version": self.os_version.text(),
            "build_number": self.build_number.text(),
            "region": self.region.text(),
            "csc": self.csc.text(),
            "release_date": self.release_date.text().strip() or None,
            "file_size": self.file_size.text().strip() or None,
            "checksum_reference": self.checksum.text().strip() or None,
            "download_url": self.download_url.text().strip() or None,
            "min_bootloader": self.min_bootloader.text(),
            "compatibility_notes": self.compatibility.toPlainText(),
            "install_instructions": self.instructions.toPlainText(),
            "verification_status": self.status.currentData(),
            "local_path": self.firmware.local_path if self.firmware else None,
        }

    def _save(self, payload: dict[str, Any]) -> Firmware:
        if self.firmware:
            saved = self.context.firmware.update(int(self.firmware.id or 0), payload)
        else:
            saved = self.context.firmware.create(payload)
        self._created = saved
        return saved

    @property
    def result_firmware(self) -> Firmware | None:
        return getattr(self, "_created", None)


class SourceEditorDialog(FormDialog):
    def __init__(
        self, context: AppContext, *, source: FirmwareSource | None = None, parent=None
    ) -> None:
        super().__init__(
            "Источник прошивок",
            subtitle="Источник отделён от записей: доверенные источники помечаются отдельно.",
            parent=parent,
            width=520,
        )
        self.context = context
        self.source = source
        self.name = self.add_line("Название *", source.name if source else "")
        self.url = self.add_line("Сайт", source.url if source else "", placeholder="https://…")
        self.kind = self.add_combo(
            "Тип",
            [
                ("Официальный сайт производителя", "official"),
                ("Сообщество", "community"),
                ("Локальный источник", "local"),
                ("Инструмент производителя", "vendor_tool"),
            ],
            current=source.kind if source else "community",
        )
        self.trusted = QCheckBox("Доверенный источник", self.container)
        self.trusted.setChecked(bool(source.trusted) if source else False)
        self.add_widget("Доверие", self.trusted)
        self.notes = self.add_text("Примечания", source.notes if source else "", height=70)
        self.on_save(self._save)

    def collect(self) -> dict[str, Any]:
        return {
            "name": self.name.text(),
            "url": self.url.text(),
            "kind": self.kind.currentData(),
            "trusted": self.trusted.isChecked(),
            "notes": self.notes.toPlainText(),
        }

    def _save(self, payload: dict[str, Any]) -> FirmwareSource:
        if self.source:
            return self.context.firmware.update_source(int(self.source.id or 0), payload)
        return self.context.firmware.create_source(payload)
