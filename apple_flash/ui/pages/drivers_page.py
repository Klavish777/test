"""Страница диагностики драйверов Windows 10/11 (USBMux, WinUSB/Zadig для DFU) и CLI-инструментов."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QHBoxLayout,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from apple_flash.services.context import StudioContext
from apple_flash.ui.widgets import (
    StudioCard,
    clear_layout,
    make_muted,
    make_pill,
    make_title,
)

STATUS_MAP = {
    "ok": ("Готово", "ok"),
    "warning": ("Внимание", "warning"),
    "missing": ("Не найдено", "danger"),
    "info": ("Справка", "info"),
}


class DriversPage(QWidget):
    def __init__(self, context: StudioContext, window) -> None:
        super().__init__()
        self.context = context
        self.window = window

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        outer.addWidget(scroll)

        self.scroll_content = QWidget(scroll)
        scroll.setWidget(self.scroll_content)
        layout = QVBoxLayout(self.scroll_content)
        layout.setContentsMargins(22, 16, 22, 16)
        layout.setSpacing(12)

        head = QHBoxLayout()
        box = QVBoxLayout()
        box.setSpacing(2)
        box.addWidget(make_title("Драйверы и окружение Windows", object_name="PageTitle"))
        box.addWidget(
            make_muted(
                "Автоматическая диагностика служб Apple Mobile Device, драйвера WinUSB для DFU и прошивальщиков."
            )
        )
        head.addLayout(box, 1)

        recheck_btn = QPushButton("Повторить диагностику", self.scroll_content)
        recheck_btn.setObjectName("Primary")
        recheck_btn.clicked.connect(self.on_show)
        head.addWidget(recheck_btn)
        layout.addLayout(head)

        self.cards_host = QWidget(self.scroll_content)
        self.cards_container = QVBoxLayout(self.cards_host)
        self.cards_container.setContentsMargins(0, 0, 0, 0)
        self.cards_container.setSpacing(10)
        layout.addWidget(self.cards_host)

        # Памятка для Windows
        guide_card = StudioCard(self.scroll_content)
        gb = guide_card.body()
        gb.addWidget(make_title("Быстрая шпаргалка по настройке Windows 10/11 для прошивки Apple"))
        for tip in (
            "1. Обычный режим (iPhone / iPad): установите «Устройства Apple» (Microsoft Store) или классический iTunes x64 — это ставит драйвер usbaapl64.sys и службу AppleMobileDeviceService.",
            "2. Режим прошивки через Python: выполните `pip install pymobiledevice3` в виртуальном окружении `.venv` проекта.",
            "3. Режим прошивки через libimobiledevice: скопируйте Windows-сборку (`idevicerestore.exe`, `irecovery.exe`, `ideviceinfo.exe`, `idevice_id.exe`) в каталог `tools` приложения (кнопка в разделе Настройки).",
            "4. Прошивка MacBook (M1–M4 / T2) и DFU на Windows: когда устройство находится в DFU (`VID_05AC&PID_1227`), при ошибке захвата USB откройте бесплатную утилиту Zadig → Options → List All Devices → выберите `Apple Mobile Device (DFU Mode)` и замените драйвер на `WinUSB`.",
        ):
            gb.addWidget(make_muted(tip, guide_card))
        layout.addWidget(guide_card)
        layout.addStretch(1)

    def on_show(self) -> None:
        clear_layout(self.cards_container)
        results = self.context.diagnostics.run_all_checks()
        for item in results:
            card = StudioCard(self.cards_host)
            cb = card.body()
            cb.setSizeConstraint(QVBoxLayout.SetMinimumSize)
            row = QHBoxLayout()
            row.addWidget(make_title(item.title, parent=card), 1)
            label, tone = STATUS_MAP.get(item.status, (item.status, "neutral"))
            row.addWidget(make_pill(label, tone, card))
            cb.addLayout(row)
            cb.addWidget(make_muted(item.summary, card))
            if item.recommendation:
                rec_lbl = make_muted(f"Рекомендация: {item.recommendation}", card)
                rec_lbl.setMinimumHeight(34)
                cb.addWidget(rec_lbl)
            self.cards_container.addWidget(card)
