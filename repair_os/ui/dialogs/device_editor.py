"""Диалог добавления и редактирования устройства."""

from __future__ import annotations

from typing import Any

from PySide6.QtWidgets import QCheckBox

from repair_os.data.models import Brand, Device
from repair_os.services.context import AppContext
from repair_os.ui.dialogs.base import FormDialog
from repair_os.ui.widgets import muted


class DeviceEditorDialog(FormDialog):
    def __init__(
        self,
        context: AppContext,
        *,
        device: Device | None = None,
        preset_brand_id: int | None = None,
        parent=None,
    ) -> None:
        is_edit = device is not None
        super().__init__(
            "Редактирование устройства" if is_edit else "Новое устройство",
            subtitle=(
                "Технические данные сохраняются во внутренней базе. "
                "Отмечайте «Проверено» только после сверки с надёжным источником."
                if not is_edit
                else "Изменения фиксируются в журнале. Пустые поля допустимы."
            ),
            save_text="Сохранить",
            parent=parent,
            width=600,
        )
        self.context = context
        self.device = device
        brands: list[Brand] = context.brands.list()
        self.brand = self.add_combo(
            "Бренд *",
            [(f"{brand.name}", brand.id) for brand in brands],
            current=device.brand_id if device else preset_brand_id,
        )
        self.name = self.add_line("Название модели *", device.name if device else "", placeholder="Galaxy A52")
        self.model_code = self.add_line(
            "Точный код модели *",
            device.model_code if device else "",
            placeholder="SM-A525F / A2402 / M2101K6G",
        )
        self.codename = self.add_line(
            "Кодовое имя", device.codename if device else "", placeholder="a52q (если известно)"
        )
        self.revision = self.add_line(
            "Аппаратная ревизия", device.hardware_revision if device else "", placeholder="rev1 / R2"
        )
        self.soc = self.add_line("Процессор", device.soc if device else "", placeholder="Exynos 9611")
        self.platform = self.add_line(
            "Платформа", device.soc_platform if device else "", placeholder="Внутренние обозначения"
        )
        self.ram = self.add_line("ОЗУ", device.ram if device else "", placeholder="6 GB")
        self.storage = self.add_line("Память", device.storage if device else "", placeholder="128 GB")
        self.os_versions = self.add_line(
            "Версии ОС",
            device.os_versions if device else "",
            placeholder="Android 11, 12, 13",
        )
        self.year = self.add_line(
            "Год выпуска", str(device.release_year) if device and device.release_year else "", placeholder="2021"
        )
        self.source = self.add_line(
            "Источник данных",
            device.source if device else "",
            placeholder="Ссылка или название документа",
        )
        self.notes = self.add_text("Примечания", device.notes if device else "", height=80)
        self.verified = QCheckBox("Данные проверены вручную", self.container)
        self.verified.setChecked(bool(device.verified) if device else False)
        self.add_widget("Проверка", self.verified)
        if not is_edit:
            self.add_widget(
                "",
                muted(
                    "Код модели должен совпадать с реальной маркировкой. "
                    "Приложение не придумывает технические данные.",
                    self.container,
                ),
            )
        self.on_save(self._save)

    def collect(self) -> dict[str, Any]:
        return {
            "brand_id": self.brand.currentData(),
            "name": self.name.text(),
            "model_code": self.model_code.text(),
            "codename": self.codename.text(),
            "hardware_revision": self.revision.text(),
            "soc": self.soc.text(),
            "soc_platform": self.platform.text(),
            "ram": self.ram.text(),
            "storage": self.storage.text(),
            "os_versions": self.os_versions.text(),
            "release_year": self.year.text().strip() or None,
            "source": self.source.text(),
            "notes": self.notes.toPlainText(),
            "verified": self.verified.isChecked(),
        }

    def _save(self, payload: dict[str, Any]) -> Device:
        if self.device:
            saved = self.context.devices.update(int(self.device.id or 0), payload)
        else:
            saved = self.context.devices.create(payload)
        self._created = saved
        return saved

    @property
    def result_device(self) -> Device | None:
        return getattr(self, "_created", None)
