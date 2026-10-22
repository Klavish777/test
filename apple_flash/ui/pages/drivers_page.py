"""Вкладка «Драйверы и USB»: статус Apple Mobile Device Service, libusb и живой список USB-интерфейсов Apple."""

from __future__ import annotations

import subprocess
import sys

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from apple_flash.core.security import windows_no_window_kwargs
from apple_flash.services.context import StudioContext
from apple_flash.ui.widgets import (
    StudioCard,
    make_muted,
    make_pill,
    make_title,
    set_pill,
)

STATUS_MAP = {
    "ok": ("Готово", "ok"),
    "warning": ("Нужна настройка", "warning"),
    "missing": ("Не установлен", "danger"),
    "info": ("Готово к работе", "info"),
}


class _DiagCardSlot(StudioCard):
    """Статическая карточка статуса драйвера/компонента (обновляется без пересоздания виджетов)."""

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        cb = self.body()
        cb.setSpacing(6)
        row = QHBoxLayout()
        self.title_lbl = make_title("Проверка компонента…", parent=self)
        row.addWidget(self.title_lbl, 1)
        self.pill_lbl = make_pill("Проверка", "neutral", self)
        row.addWidget(self.pill_lbl)
        cb.addLayout(row)
        self.summary_lbl = make_muted("—", self)
        cb.addWidget(self.summary_lbl)
        self.rec_lbl = QLabel("", self)
        self.rec_lbl.setObjectName("Dim")
        self.rec_lbl.setWordWrap(True)
        cb.addWidget(self.rec_lbl)


class DriversPage(QWidget):
    def __init__(self, context: StudioContext, window) -> None:
        super().__init__()
        self.context = context
        self.window = window

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        outer.addWidget(scroll)

        self.scroll_content = QWidget(scroll)
        layout = QVBoxLayout(self.scroll_content)
        layout.setContentsMargins(22, 16, 22, 16)
        layout.setSpacing(12)

        head = QHBoxLayout()
        box = QVBoxLayout()
        box.setSpacing(2)
        box.addWidget(make_title("Драйверы и диагностика USB", object_name="PageTitle"))
        box.addWidget(
            make_muted(
                "Проверка драйверов Windows 10/11 и список всех устройств Apple, подключённых к USB-портам прямо сейчас."
            )
        )
        head.addLayout(box, 1)

        recheck_btn = QPushButton("↻ Обновить проверку", self.scroll_content)
        recheck_btn.setObjectName("Primary")
        recheck_btn.clicked.connect(self.on_show)
        head.addWidget(recheck_btn)
        layout.addLayout(head)

        # Быстрые кнопки установки драйверов в 1 клик
        quick_card = StudioCard(self.scroll_content, hero=True)
        qb = quick_card.body()
        qb.addWidget(make_title("Установка официальных драйверов USB для Windows 10/11", parent=quick_card))
        qb.addWidget(
            make_muted(
                "• Для включённых iPhone и iPad нажмите «Установить Устройства Apple» — Microsoft Store бесплатно установит подписанный драйвер Apple USB.\n"
                "• Для прошивки из чёрного экрана DFU (и для MacBook M1–M4) при блокировке драйвера откройте утилиту Zadig и выберите драйвер WinUSB.",
                quick_card,
            )
        )
        btn_row = QHBoxLayout()
        store_btn = QPushButton("⬇ Установить «Устройства Apple» (Microsoft Store)", quick_card)
        store_btn.setObjectName("Primary")
        store_btn.clicked.connect(self._open_ms_store_apple_devices)
        btn_row.addWidget(store_btn)

        zadig_btn = QPushButton("⬇ Скачать Zadig (драйвер WinUSB для DFU)", quick_card)
        zadig_btn.clicked.connect(lambda: QDesktopServices.openUrl(QUrl("https://zadig.akeo.ie/")))
        btn_row.addWidget(zadig_btn)

        if sys.platform == "win32":
            devmgmt_btn = QPushButton("Открыть Диспетчер устройств Windows", quick_card)
            devmgmt_btn.clicked.connect(self._open_device_manager)
            btn_row.addWidget(devmgmt_btn)

        btn_row.addStretch(1)
        qb.addLayout(btn_row)
        layout.addWidget(quick_card)

        # 4 статических слота самодиагностики (идеальная вёрстка без сжатия высоты в QScrollArea)
        self._slots: list[_DiagCardSlot] = []
        for _ in range(4):
            slot = _DiagCardSlot(self.scroll_content)
            self._slots.append(slot)
            layout.addWidget(slot)

        # Живая таблица интерфейсов VID_05AC в ядре Windows
        usb_card = StudioCard(self.scroll_content)
        ub = usb_card.body()
        ub.addWidget(make_title("Устройства Apple (VID_05AC) на USB-шине компьютера", parent=usb_card))
        self.usb_hint_lbl = make_muted("", usb_card)
        ub.addWidget(self.usb_hint_lbl)

        self.usb_table = QTableWidget(0, 5, usb_card)
        self.usb_table.setHorizontalHeaderLabels(
            ["USB PID", "Режим", "Назначенный драйвер", "Описание в системе", "USB Instance ID"]
        )
        self.usb_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.usb_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.usb_table.verticalHeader().setVisible(False)
        self.usb_table.setMinimumHeight(130)
        hdr = self.usb_table.horizontalHeader()
        hdr.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(3, QHeaderView.Stretch)
        hdr.setSectionResizeMode(4, QHeaderView.Stretch)
        ub.addWidget(self.usb_table)
        layout.addWidget(usb_card)

        layout.addStretch(1)
        scroll.setWidget(self.scroll_content)

    def on_show(self) -> None:
        results = self.context.diagnostics.run_checks()
        for idx, slot in enumerate(self._slots):
            if idx < len(results):
                item = results[idx]
                slot.show()
                slot.title_lbl.setText(item.title)
                label, tone = STATUS_MAP.get(item.status, (item.status, "neutral"))
                set_pill(slot.pill_lbl, label, tone)
                slot.summary_lbl.setText(item.summary)
                slot.rec_lbl.setText(item.recommendation)
                slot.rec_lbl.setVisible(bool(item.recommendation))
            else:
                slot.hide()

        entries = self.context.diagnostics.raw_usb_entries()
        self.usb_table.setRowCount(len(entries))
        if entries:
            self.usb_hint_lbl.setText(
                f"Система видит подключённых USB-интерфейсов Apple: {len(entries)}."
            )
        else:
            self.usb_hint_lbl.setText(
                "Сейчас на шине USB нет устройств с кодом производителя Apple (VID_05AC). Проверьте кабель и разъём USB."
            )

        for row_idx, e in enumerate(entries):
            self.usb_table.setItem(row_idx, 0, QTableWidgetItem(f"05AC:{e.pid:04X}"))
            self.usb_table.setItem(row_idx, 1, QTableWidgetItem(e.mode.upper()))
            self.usb_table.setItem(row_idx, 2, QTableWidgetItem(e.service or "Нет драйвера"))
            self.usb_table.setItem(row_idx, 3, QTableWidgetItem(e.description))
            self.usb_table.setItem(row_idx, 4, QTableWidgetItem(e.instance_id))

    @staticmethod
    def _open_ms_store_apple_devices() -> None:
        if not QDesktopServices.openUrl(QUrl("ms-windows-store://pdp/?ProductId=9NP83LWLPZ9K")):
            QDesktopServices.openUrl(QUrl("https://apps.microsoft.com/detail/9NP83LWLPZ9K"))

    @staticmethod
    def _open_device_manager() -> None:
        try:
            subprocess.Popen(["mmc.exe", "devmgmt.msc"], **windows_no_window_kwargs())
        except OSError:
            pass
