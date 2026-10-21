"""Firmware Center: поиск, фильтры, проверка совместимости и контрольных сумм."""

from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import QUrl, Qt
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QSplitter,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from repair_os.data.models import (
    VERIFICATION_LABELS,
    Firmware,
    human_size,
)
from repair_os.services.context import AppContext
from repair_os.ui.dialogs.base import DangerDialog, ReportDialog, confirm, error, info
from repair_os.ui.dialogs.firmware_editor import FirmwareEditorDialog
from repair_os.ui.dialogs.source_manager import SourceManagerDialog
from repair_os.ui.table_models import FirmwareTableModel, SearchProxy
from repair_os.ui.widgets import (
    Card,
    breakable,
    wrapped_label,
    ClickableCard,
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


class FirmwarePage(QWidget):
    route_key = "firmware"

    def __init__(self, context: AppContext, window) -> None:
        super().__init__()
        self.context = context
        self.window = window
        self._device_filter: int | None = None
        self._selected: Firmware | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 14)
        layout.setSpacing(10)

        header = QHBoxLayout()
        box = QVBoxLayout()
        box.setSpacing(2)
        box.addWidget(title("Firmware Center", object_name="PageTitle"))
        subtitle = muted(
            "Бренд → модель → вариант → прошивки. Совместимость — по коду модели, региону/CSC "
            "и загрузчику, а не по названию телефона."
        )
        subtitle.setMaximumWidth(600)
        box.addWidget(subtitle)
        header.addLayout(box)
        header.addStretch(1)
        self.count_label = QLabel("", self)
        self.count_label.setObjectName("Muted")
        header.addWidget(self.count_label)
        sources_button = QPushButton("Источники", self)
        sources_button.setObjectName("Ghost")
        sources_button.clicked.connect(self._manage_sources)
        header.addWidget(sources_button)
        import_button = QPushButton("Импорт CSV/JSON", self)
        import_button.setObjectName("Ghost")
        import_button.clicked.connect(lambda: self.window.run_import("firmware"))
        header.addWidget(import_button)
        add_button = QPushButton("+ Запись", self)
        add_button.setObjectName("Primary")
        add_button.clicked.connect(self.add_firmware)
        header.addWidget(add_button)
        layout.addLayout(header)

        filters = QHBoxLayout()
        filters.setSpacing(8)
        self.search = SearchInput("Поиск по файлу, коду модели и номеру сборки…", self)
        self.search.textChanged.connect(self.refresh)
        filters.addWidget(self.search, 1)
        self.brand_combo = QComboBox(self)
        self.brand_combo.currentIndexChanged.connect(self._on_brand_changed)
        filters.addWidget(self.brand_combo)
        self.device_combo = QComboBox(self)
        self.device_combo.currentIndexChanged.connect(self._on_device_changed)
        filters.addWidget(self.device_combo)
        self.status_combo = QComboBox(self)
        self.status_combo.addItem("Все статусы", None)
        for key, label in VERIFICATION_LABELS.items():
            self.status_combo.addItem(label, key)
        self.status_combo.currentIndexChanged.connect(self.refresh)
        filters.addWidget(self.status_combo)
        self.sort_combo = QComboBox(self)
        self.sort_combo.addItem("По сборке", "build")
        self.sort_combo.addItem("По дате", "date")
        self.sort_combo.addItem("По размеру", "size")
        self.sort_combo.addItem("По имени", "name")
        self.sort_combo.addItem("По добавлению", "added")
        self.sort_combo.currentIndexChanged.connect(self.refresh)
        filters.addWidget(self.sort_combo)
        layout.addLayout(filters)

        splitter = QSplitter(Qt.Horizontal, self)
        splitter.addWidget(self._build_table())
        splitter.addWidget(self._build_detail())
        splitter.setSizes([900, 400])
        splitter.setChildrenCollapsible(False)
        layout.addWidget(splitter, 1)

        self.empty_hint = muted(
            "Демонстрационные записи помечены ДЕМО и не являются проверенными прошивками. "
            "Загружайте файлы только из доверенных источников.",
            self,
        )
        layout.addWidget(self.empty_hint)

    # ------------------------------------------------------------------ построение
    def _build_table(self) -> QWidget:
        self.model = FirmwareTableModel(self)
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
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.table.selectionModel().selectionChanged.connect(self._on_selection)
        self.table.doubleClicked.connect(lambda _index: self._edit_selected())
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Interactive)
        self.table.setColumnWidth(0, 250)
        for column in (1, 2, 5, 6, 7, 9):
            header.setSectionResizeMode(column, QHeaderView.ResizeToContents)
        for column, width in ((3, 110), (4, 130), (8, 110)):
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
        layout.addStretch(1)
        scroll.setWidget(container)
        self._show_detail(None)
        return scroll

    # ------------------------------------------------------------------ данные
    def on_show(self) -> None:
        self._reload_brand_filter()
        self.refresh()

    def select_device(self, device_id: int | None) -> None:
        self._device_filter = device_id
        self._reload_brand_filter()
        if device_id:
            device = self.context.db.query_one(
                "SELECT brand_id FROM devices WHERE id = ?", (device_id,)
            )
            if device:
                index = self.brand_combo.findData(device["brand_id"])
                if index >= 0:
                    self.brand_combo.blockSignals(True)
                    self.brand_combo.setCurrentIndex(index)
                    self.brand_combo.blockSignals(False)
                self._reload_device_filter(device["brand_id"], selected=device_id)
        self.refresh()

    def focus_firmware(self, firmware_id: int | None) -> None:
        self.on_show()
        if not firmware_id:
            return
        for row, item in enumerate(self.model.rows):
            if item.id == firmware_id:
                proxy_index = self.proxy.mapFromSource(self.model.index(row, 0))
                self.table.selectRow(proxy_index.row())
                self.table.scrollTo(proxy_index)
                self._show_detail(item)
                break

    def _reload_brand_filter(self) -> None:
        self.brand_combo.blockSignals(True)
        self.brand_combo.clear()
        self.brand_combo.addItem("Все бренды", None)
        for brand in self.context.brands.list():
            self.brand_combo.addItem(brand.name, brand.id)
        self.brand_combo.blockSignals(False)
        self._reload_device_filter(self.brand_combo.currentData())

    def _reload_device_filter(self, brand_id: int | None, *, selected: int | None = None) -> None:
        self.device_combo.blockSignals(True)
        self.device_combo.clear()
        self.device_combo.addItem("Все устройства", None)
        if brand_id:
            devices = self.context.devices.by_brand(int(brand_id), limit=1000)
        else:
            devices = self.context.devices.list(limit=1000)
        for device in devices:
            self.device_combo.addItem(f"{device.name} · {device.model_code}", device.id)
        target = selected if selected is not None else self._device_filter
        if target:
            index = self.device_combo.findData(target)
            if index >= 0:
                self.device_combo.setCurrentIndex(index)
        self.device_combo.blockSignals(False)

    def _on_brand_changed(self, _index: int) -> None:
        self._device_filter = None
        self._reload_device_filter(self.brand_combo.currentData())
        self.refresh()

    def _on_device_changed(self, _index: int) -> None:
        self._device_filter = self.device_combo.currentData()
        self.refresh()

    def refresh(self) -> None:
        rows = self.context.firmware.list(
            search=self.search.text().strip() or None,
            brand_id=self.brand_combo.currentData(),
            device_id=self.device_combo.currentData(),
            status=self.status_combo.currentData(),
            sort=self.sort_combo.currentData() or "build",
            limit=2000,
        )
        self.model.set_rows(rows)
        self.count_label.setText(f"Записей: {len(rows)}")
        if rows and self._selected is None:
            self.table.selectRow(0)

    def _on_selection(self, *_args) -> None:
        indexes = self.table.selectionModel().selectedRows()
        if not indexes:
            self._show_detail(None)
            return
        source_index = self.proxy.mapToSource(indexes[0])
        item = self.model.row_at(source_index)
        self._show_detail(item)

    # ------------------------------------------------------------------ детали
    def _show_detail(self, firmware: Firmware | None) -> None:
        self._selected = firmware
        clear_layout(self.detail_body)
        clear_layout(self.actions_body)
        self.detail_body.addWidget(title("Сведения о прошивке", object_name="CardTitle"))
        if firmware is None:
            self.detail_body.addWidget(muted("Выберите запись в таблице."))
            return
        header = QHBoxLayout()
        name = wrapped_label(
            breakable(firmware.file_name), self.detail_card, object_name="CardTitle", lines=2
        )
        header.addWidget(name, 1)
        if firmware.is_demo:
            header.addWidget(badge("ДЕМО", "demo", self.detail_card))
        self.detail_body.addLayout(header)
        status_row = QHBoxLayout()
        status_row.addWidget(StatusBadge(firmware.verification_status, self.detail_card))
        status_row.addStretch(1)
        self.detail_body.addLayout(status_row)

        for label, value in (
            ("Точная модель", firmware.model_code or "—"),
            ("Устройство", firmware.device_name or "не привязано"),
            ("Версия ОС", firmware.os_version or "—"),
            ("Номер сборки", firmware.build_number or "—"),
            ("Регион / CSC", f"{firmware.region or '—'} / {firmware.csc or '—'}"),
            ("Дата выпуска", firmware.release_date or "неизвестна"),
            ("Размер", human_size(firmware.file_size)),
            ("Источник", firmware.source_name or "—"),
            ("SHA-256 (эталон)", firmware.checksum_reference or "не указан"),
            ("SHA-256 (файл)", firmware.checksum_sha256 or "файл не прикреплён"),
            ("Мин. загрузчик", firmware.min_bootloader or "—"),
        ):
            self.detail_body.addWidget(field_row(label, value, self.detail_card))
        if firmware.compatibility_notes:
            self.detail_body.addWidget(separator(self.detail_card))
            self.detail_body.addWidget(
                field_row("Совместимость и ограничения", firmware.compatibility_notes, self.detail_card)
            )
        if firmware.install_instructions:
            self.detail_body.addWidget(
                field_row("Инструкция", firmware.install_instructions, self.detail_card)
            )
        if firmware.download_url:
            self.detail_body.addWidget(
                field_row("Ссылка", firmware.download_url, self.detail_card)
            )
        if firmware.local_path:
            exists = Path(firmware.local_path).exists()
            self.detail_body.addWidget(
                field_row(
                    "Локальный файл",
                    firmware.local_path + (" (найден)" if exists else " (отсутствует)"),
                    self.detail_card,
                )
            )

        self.actions_body.addWidget(title("Действия", object_name="CardTitle"))
        grid = QVBoxLayout()
        grid.setSpacing(6)
        check = QPushButton("Проверить совместимость", self.actions_card)
        check.setObjectName("Primary")
        check.clicked.connect(self._check_compatibility)
        grid.addWidget(check)
        verify = QPushButton("Проверить контрольную сумму", self.actions_card)
        verify.setObjectName("Ghost")
        verify.clicked.connect(self._verify_checksum)
        grid.addWidget(verify)
        attach = QPushButton("Прикрепить локальный файл…", self.actions_card)
        attach.setObjectName("Ghost")
        attach.clicked.connect(self._attach_file)
        grid.addWidget(attach)
        open_source = QPushButton("Открыть страницу источника", self.actions_card)
        open_source.setObjectName("Ghost")
        open_source.enabled = bool(firmware.download_url)
        open_source.clicked.connect(self._open_source)
        grid.addWidget(open_source)
        history = QPushButton("История изменений", self.actions_card)
        history.setObjectName("Ghost")
        history.clicked.connect(self._show_history)
        grid.addWidget(history)
        status_combo = QComboBox(self.actions_card)
        for key, label in VERIFICATION_LABELS.items():
            status_combo.addItem(f"Статус: {label}", key)
        index = status_combo.findData(firmware.verification_status)
        if index >= 0:
            status_combo.setCurrentIndex(index)
        status_combo.currentIndexChanged.connect(
            lambda _i: self._set_status(status_combo.currentData())
        )
        grid.addWidget(status_combo)
        edit = QPushButton("Изменить запись", self.actions_card)
        edit.setObjectName("Ghost")
        edit.clicked.connect(self._edit_selected)
        grid.addWidget(edit)
        delete = QPushButton("Удалить запись", self.actions_card)
        delete.setObjectName("Danger")
        delete.clicked.connect(self._delete_selected)
        grid.addWidget(delete)
        self.actions_body.addLayout(grid)

    # ------------------------------------------------------------------ действия
    def add_firmware(self) -> None:
        device = None
        if self.device_combo.currentData():
            try:
                device = self.context.devices.get(int(self.device_combo.currentData()))
            except Exception:
                device = None
        dialog = FirmwareEditorDialog(self.context, preset_device=device, parent=self.window)
        if dialog.exec():
            saved = dialog.result_firmware
            self.refresh()
            self.window.set_status("Запись прошивки добавлена")
            if saved and saved.id:
                self.focus_firmware(saved.id)

    def _edit_selected(self) -> None:
        if not self._selected:
            return
        dialog = FirmwareEditorDialog(self.context, firmware=self._selected, parent=self.window)
        if dialog.exec():
            self.refresh()
            if dialog.result_firmware and dialog.result_firmware.id:
                self.focus_firmware(dialog.result_firmware.id)

    def _delete_selected(self) -> None:
        if not self._selected:
            return
        if not confirm(
            self.window,
            "Удалить запись прошивки",
            f"Удалить «{self._selected.file_name}» из базы? Файл на диске останется.",
            confirm_text="Удалить",
            danger=True,
        ):
            return
        try:
            self.context.firmware.delete(int(self._selected.id or 0))
        except Exception as exc:
            error(self.window, "Ошибка", str(exc))
            return
        self._selected = None
        self.refresh()
        self._show_detail(None)

    def _set_status(self, status: str | None) -> None:
        if not self._selected or not status or status == self._selected.verification_status:
            return
        try:
            self.context.firmware.set_verification(int(self._selected.id or 0), status)
        except Exception as exc:
            error(self.window, "Ошибка", str(exc))
            return
        firmware_id = self._selected.id
        self.refresh()
        self.focus_firmware(firmware_id)
        self.window.set_status(f"Статус проверки: {VERIFICATION_LABELS.get(status, status)}")

    def _check_compatibility(self) -> None:
        if not self._selected or not self._selected.id:
            return
        result = self.context.firmware_tools.check_compatibility(self._selected.id)
        title = {
            "ok": "Совместимость: явных проблем нет",
            "warning": "Совместимость: есть предупреждения",
            "incompatible": "Совместимость: несовместимо",
        }[result.level]
        ReportDialog(title, self._selected.file_name, result.messages, self.window).exec()

    def _verify_checksum(self) -> None:
        if not self._selected or not self._selected.id:
            return
        firmware = self._selected
        if not firmware.local_path:
            info(
                self.window,
                "Файл не прикреплён",
                "Чтобы проверить контрольную сумму, прикрепите локальный файл к записи.",
            )
            return
        if not (firmware.checksum_reference or firmware.checksum_sha256):
            info(
                self.window,
                "Нет эталона",
                "В записи не указана эталонная SHA-256. Сначала добавьте её вручную из источника.",
            )
            return
        try:
            ok, actual = self.context.firmware_tools.verify_reference(int(firmware.id or 0))
        except Exception as exc:
            error(self.window, "Проверка не пройдена", str(exc))
            return
        if ok:
            info(self.window, "Контрольная сумма совпадает", f"SHA-256: {actual}")
            self.refresh()
            self.focus_firmware(firmware.id)

    def _attach_file(self) -> None:
        if not self._selected or not self._selected.id:
            return
        firmware = self._selected
        confirmed = DangerDialog.ask(
            self.window,
            "Прикрепление файла прошивки",
            "Файл будет проверен (формат, ZIP-целостность, SHA-256) и скопирован в локальную "
            "библиотеку. Приложение не загружает файлы из сети и не обходит защиту устройства.\n\n"
            "Убедитесь, что файл получен из доверенного источника и подходит именно вашей модели "
            "и региону. Продолжайте только если понимаете риски.",
            keyword="ПОДТВЕРЖДАЮ",
        )
        if not confirmed:
            return
        path, _ = QFileDialog.getOpenFileName(
            self.window,
            "Выберите файл прошивки",
            "",
            "Архивы и образы (*.zip *.tar *.tar.md5 *.img *.bin *.ipsw *.7z *.lz4);;Все файлы (*.*)",
        )
        if not path:
            return
        try:
            self.context.firmware_tools.attach_local_file(int(firmware.id or 0), Path(path))
        except Exception as exc:
            error(self.window, "Файл не прикреплён", str(exc))
            return
        self.refresh()
        self.focus_firmware(firmware.id)
        self.window.set_status("Файл прикреплён и проверен")

    def _open_source(self) -> None:
        if not self._selected or not self._selected.download_url:
            return
        if not confirm(
            self.window,
            "Открыть внешний источник",
            "Откроется страница в браузере. Проверяйте сайт и контрольные суммы самостоятельно. "
            "Продолжить?",
            confirm_text="Открыть",
        ):
            return
        QDesktopServices.openUrl(QUrl(self._selected.download_url))

    def _show_history(self) -> None:
        if not self._selected or not self._selected.id:
            return
        history = self.context.firmware.history(int(self._selected.id))
        lines = [
            f"{row['created_at']} · {row['action']} · {row['summary'] or ''}" for row in history
        ]
        ReportDialog(
            "История изменений", self._selected.file_name, lines, self.window
        ).exec()

    def _manage_sources(self) -> None:
        SourceManagerDialog(self.context, parent=self.window).exec()
        self.refresh()
