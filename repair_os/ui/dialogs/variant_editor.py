"""Диалог варианта устройства (регион, CSC, загрузчик)."""

from __future__ import annotations

from typing import Any

from repair_os.data.models import Device, DeviceVariant
from repair_os.services.context import AppContext
from repair_os.ui.dialogs.base import FormDialog
from repair_os.ui.widgets import muted


class VariantEditorDialog(FormDialog):
    def __init__(
        self,
        context: AppContext,
        *,
        device: Device,
        variant: DeviceVariant | None = None,
        parent=None,
    ) -> None:
        super().__init__(
            "Вариант устройства",
            subtitle="Регион/CSC и версия загрузчика используются для проверки совместимости.",
            parent=parent,
            width=480,
        )
        self.context = context
        self.device = device
        self.variant = variant
        self.name = self.add_line(
            "Название варианта *",
            variant.name if variant else f"{device.name} · вариант",
            placeholder="Например: EU / SER",
        )
        self.model_code = self.add_line(
            "Код модели *", variant.model_code if variant else device.model_code
        )
        self.region = self.add_line("Регион", variant.region if variant else "", placeholder="EUX/SER")
        self.csc = self.add_line("CSC", variant.csc if variant else "", placeholder="SER")
        self.ram = self.add_line("ОЗУ", variant.ram if variant else (device.ram or ""))
        self.storage = self.add_line(
            "Память", variant.storage if variant else (device.storage or "")
        )
        self.bootloader = self.add_line(
            "Версия загрузчика", variant.bootloader if variant else "", placeholder="например A525FXXU4"
        )
        self.notes = self.add_text("Примечания", variant.notes if variant else "", height=70)
        self.add_widget(
            "",
            muted("Не выдумывайте CSC и версии загрузчика — указывайте данные из источника.", self.container),
        )
        self.on_save(self._save)

    def collect(self) -> dict[str, Any]:
        return {
            "device_id": self.device.id,
            "name": self.name.text(),
            "model_code": self.model_code.text(),
            "region": self.region.text(),
            "csc": self.csc.text(),
            "ram": self.ram.text(),
            "storage": self.storage.text(),
            "bootloader": self.bootloader.text(),
            "notes": self.notes.toPlainText(),
        }

    def _save(self, payload: dict[str, Any]) -> DeviceVariant:
        if self.variant:
            return self.context.devices.update_variant(int(self.variant.id or 0), payload)
        return self.context.devices.add_variant(payload)
