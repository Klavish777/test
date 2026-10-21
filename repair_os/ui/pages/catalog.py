"""Каталог устройств: бренды, поиск, таблица и карточки."""

from __future__ import annotations

import logging

from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from repair_os.data.models import Device
from repair_os.services.context import AppContext
from repair_os.ui.dialogs.base import confirm, error
from repair_os.ui.dialogs.device_editor import DeviceEditorDialog
from repair_os.ui.table_models import DeviceTableModel, SearchProxy
from repair_os.ui.widgets import (
    ClickableCard,
    EmptyState,
    FlowLayout,
    FittedTableView,
    SearchInput,
    badge,
    clear_layout,
    muted,
    title,
)

log = logging.getLogger(__name__)


class CatalogPage(QWidget):
    route_key = "catalog"

    def __init__(self, context: AppContext, window) -> None:
        super().__init__()
        self.context = context
        self.window = window
        self._current_brand: int | None = None
        self._view_mode = "table"

        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 18, 22, 18)
        layout.setSpacing(12)

        header = QHBoxLayout()
        header_box = QVBoxLayout()
        header_box.setSpacing(2)
        header_box.addWidget(title("Каталог устройств", object_name="PageTitle"))
        subtitle = muted("Только бренды и модели. Новые модели добавляются без изменения кода.")
        subtitle.setMaximumWidth(520)
        header_box.addWidget(subtitle)
        header.addLayout(header_box)
        header.addStretch(1)
        self.count_label = QLabel("", self)
        self.count_label.setObjectName("Muted")
        header.addWidget(self.count_label)
        add_button = QPushButton("+ Устройство", self)
        add_button.setObjectName("Primary")
        add_button.setCursor(Qt.PointingHandCursor)
        add_button.clicked.connect(self.add_device)
        header.addWidget(add_button)
        layout.addLayout(header)

        body = QHBoxLayout()
        body.setSpacing(14)
        body.addWidget(self._build_brand_panel())
        body.addWidget(self._build_content(), 1)
        layout.addLayout(body, 1)

    # ------------------------------------------------------------------ панель брендов
    def _build_brand_panel(self) -> QWidget:
        panel = QFrame(self)
        panel.setObjectName("Card")
        panel.setFixedWidth(220)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)
        layout.addWidget(title("Бренды", object_name="CardTitle"))
        self.brand_list = QListWidget(panel)
        self.brand_list.itemClicked.connect(self._on_brand_clicked)
        layout.addWidget(self.brand_list, 1)
        manage = QPushButton("Управление брендами", panel)
        manage.setObjectName("Ghost")
        manage.clicked.connect(self._manage_brands)
        layout.addWidget(manage)
        return panel

    def _build_content(self) -> QWidget:
        content = QWidget(self)
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        filters = QHBoxLayout()
        filters.setSpacing(8)
        self.search = SearchInput(
            "Поиск: бренд, название, точный код модели, кодовое имя, процессор…", content
        )
        self.search.textChanged.connect(self.refresh)
        filters.addWidget(self.search, 1)

        self.sort_combo = QComboBox(content)
        self.sort_combo.addItem("По названию", "name")
        self.sort_combo.addItem("По коду модели", "code")
        self.sort_combo.addItem("По году", "year")
        self.sort_combo.addItem("По изменению", "recent")
        self.sort_combo.currentIndexChanged.connect(self.refresh)
        filters.addWidget(self.sort_combo)

        self.favorites_only = QCheckBox("Избранные", content)
        self.favorites_only.stateChanged.connect(self.refresh)
        filters.addWidget(self.favorites_only)

        self.threed_only = QCheckBox("С 3D", content)
        self.threed_only.stateChanged.connect(self.refresh)
        filters.addWidget(self.threed_only)

        view_toggle = QToolButton(content)
        view_toggle.setText("Вид")
        view_toggle.setPopupMode(QToolButton.InstantPopup)
        view_menu = QMenu(view_toggle)
        view_menu.addAction("Таблица", lambda: self._set_view("table"))
        view_menu.addAction("Карточки", lambda: self._set_view("cards"))
        view_toggle.setMenu(view_menu)
        filters.addWidget(view_toggle)
        layout.addLayout(filters)

        self.views = QStackedWidget(content)
        self.views.addWidget(self._build_table())
        self.views.addWidget(self._build_cards())
        layout.addWidget(self.views, 1)

        actions = QHBoxLayout()
        self.selection_label = QLabel("", content)
        self.selection_label.setObjectName("Muted")
        actions.addWidget(self.selection_label, 1)

        self.open_button = QPushButton("Открыть карточку", content)
        self.open_button.setObjectName("Primary")
        self.open_button.clicked.connect(self._open_selected)
        actions.addWidget(self.open_button)

        self.favorite_button = QPushButton("★ В избранное", content)
        self.favorite_button.setObjectName("Ghost")
        self.favorite_button.clicked.connect(self._toggle_favorite_selected)
        actions.addWidget(self.favorite_button)

        self.edit_button = QPushButton("Изменить", content)
        self.edit_button.setObjectName("Ghost")
        self.edit_button.clicked.connect(self._edit_selected)
        actions.addWidget(self.edit_button)

        self.delete_button = QPushButton("Удалить", content)
        self.delete_button.setObjectName("Danger")
        self.delete_button.clicked.connect(self._delete_selected)
        actions.addWidget(self.delete_button)
        layout.addLayout(actions)
        return content

    def _build_table(self) -> QWidget:
        self.model = DeviceTableModel(self)
        self.proxy = SearchProxy(self)
        self.proxy.setSourceModel(self.model)
        self.table = FittedTableView(self)
        self.table.setModel(self.proxy)
        self.table.setSortingEnabled(True)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.doubleClicked.connect(lambda _index: self._open_selected())
        self.table.selectionModel().selectionChanged.connect(self._on_selection)
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._context_menu)
        self.table.setup_columns(
            1,
            minimum_widths={0: 96, 1: 180, 2: 120, 3: 108, 4: 84, 5: 130, 6: 96, 7: 74, 8: 52, 9: 84},
            priorities={3: 1, 9: 2, 4: 3, 0: 4, 6: 5, 5: 6, 7: 7, 8: 8},
        )
        return self.table

    def _build_cards(self) -> QWidget:
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        self.cards_container = QWidget(scroll)
        self.cards_layout = FlowLayout(self.cards_container, spacing=12)
        scroll.setWidget(self.cards_container)
        return scroll

    # ------------------------------------------------------------------ данные
    def on_show(self) -> None:
        self._refresh_brands()
        self.refresh()

    def select_brand(self, brand_id: int | None) -> None:
        self._current_brand = brand_id
        self._refresh_brands()
        self.refresh()

    def _refresh_brands(self) -> None:
        self.brand_list.blockSignals(True)
        self.brand_list.clear()
        total = self.context.devices.count()
        all_item = QListWidgetItem(f"Все бренды · {total}")
        all_item.setData(Qt.UserRole, None)
        self.brand_list.addItem(all_item)
        selected_row = 0
        for row, brand in enumerate(self.context.brands.list(), start=1):
            item = QListWidgetItem(f"{brand.name} · {brand.device_count}")
            item.setData(Qt.UserRole, brand.id)
            self.brand_list.addItem(item)
            if brand.id == self._current_brand:
                selected_row = row
        self.brand_list.setCurrentRow(selected_row)
        self.brand_list.blockSignals(False)

    def refresh(self) -> None:
        search = self.search.text().strip() or None
        devices = self.context.devices.list(
            search=search,
            brand_id=self._current_brand,
            favorites_only=self.favorites_only.isChecked(),
            has_3d=self.threed_only.isChecked(),
            order=self.sort_combo.currentData() or "name",
            limit=2000,
        )
        self.model.set_rows(devices)
        self.count_label.setText(f"Найдено: {len(devices)}")
        self._refresh_cards(devices)
        if not devices:
            self.selection_label.setText("Ничего не найдено — измените фильтры или добавьте устройство")
        else:
            self.selection_label.setText("")

    def _refresh_cards(self, devices: list[Device]) -> None:
        clear_layout(self.cards_layout)
        if not devices:
            self.cards_layout.addWidget(
                EmptyState(
                    "Устройства не найдены",
                    "Измените фильтры, добавьте модель вручную или импортируйте CSV/JSON.",
                    "Добавить устройство",
                    self.add_device,
                    self.cards_container,
                )
            )
            return
        for device in devices[:400]:
            self.cards_layout.addWidget(self._device_card(device))

    def _device_card(self, device: Device) -> QWidget:
        card = ClickableCard(self.cards_container, padding=14)
        card.setFixedWidth(292)
        card.setMinimumHeight(148)
        layout = card.body()
        header = QHBoxLayout()
        brand_label = QLabel(device.brand_name.upper(), card)
        brand_label.setObjectName("Dim")
        header.addWidget(brand_label)
        header.addStretch(1)
        if device.is_demo:
            header.addWidget(badge("ДЕМО", "demo", card))
        if device.has_3d:
            header.addWidget(badge("3D", "info", card))
        star = QToolButton(card)
        star.setText("★" if device.is_favorite else "☆")
        star.setToolTip("В избранное")
        star.setCursor(Qt.PointingHandCursor)
        star.clicked.connect(lambda: self._toggle_favorite(device))
        header.addWidget(star)
        layout.addLayout(header)

        name = QLabel(device.name, card)
        name.setObjectName("CardTitle")
        name.setWordWrap(True)
        layout.addWidget(name)

        code = QLabel(device.model_code + (f" · {device.codename}" if device.codename else ""), card)
        code.setStyleSheet("color: #66a3ff; font-size: 12px;")
        layout.addWidget(code)

        meta = QLabel(
            " · ".join(
                part
                for part in (
                    device.soc,
                    device.ram,
                    device.storage,
                    str(device.release_year) if device.release_year else None,
                )
                if part
            )
            or "Технические данные не заполнены",
            card,
        )
        meta.setObjectName("Muted")
        meta.setWordWrap(True)
        layout.addWidget(meta)

        footer = QLabel(
            f"Прошивки: {device.firmware_count} · Материалы: {device.document_count}", card
        )
        footer.setObjectName("Dim")
        layout.addWidget(footer)
        card.clicked.connect(lambda: self.window.open_device(int(device.id or 0)))
        return card

    # ------------------------------------------------------------------ действия
    def _on_brand_clicked(self, item: QListWidgetItem) -> None:
        self._current_brand = item.data(Qt.UserRole)
        self.refresh()

    def _set_view(self, mode: str) -> None:
        self._view_mode = mode
        self.views.setCurrentIndex(0 if mode == "table" else 1)

    def _selected_device(self) -> Device | None:
        indexes = self.table.selectionModel().selectedRows() if self.table.selectionModel() else []
        if not indexes:
            return None
        source_index = self.proxy.mapToSource(indexes[0])
        return self.model.row_at(source_index)

    def _on_selection(self, *_args) -> None:
        device = self._selected_device()
        if device:
            self.selection_label.setText(
                f"{device.brand_name} {device.name} · {device.model_code} · "
                f"прошивок {device.firmware_count} · материалов {device.document_count}"
            )
        else:
            self.selection_label.setText("")

    def _context_menu(self, position: QPoint) -> None:
        index = self.table.indexAt(position)
        if not index.isValid():
            return
        self.table.selectRow(index.row())
        device = self._selected_device()
        if not device:
            return
        menu = QMenu(self)
        open_action = QAction("Открыть карточку", menu)
        open_action.triggered.connect(self._open_selected)
        menu.addAction(open_action)
        favorite_action = QAction(
            "Убрать из избранного" if device.is_favorite else "В избранное", menu
        )
        favorite_action.triggered.connect(self._toggle_favorite_selected)
        menu.addAction(favorite_action)
        firmware_action = QAction("Прошивки устройства", menu)
        firmware_action.triggered.connect(
            lambda: (
                self.window.firmware_page.select_device(device.id),
                self.window.navigate("firmware"),
            )
        )
        menu.addAction(firmware_action)
        board_action = QAction("Открыть BoardView", menu)
        board_action.triggered.connect(
            lambda: self.window.open_board(self._board_id_for(device))
        )
        menu.addAction(board_action)
        menu.addSeparator()
        edit_action = QAction("Изменить", menu)
        edit_action.triggered.connect(self._edit_selected)
        menu.addAction(edit_action)
        delete_action = QAction("Удалить", menu)
        delete_action.triggered.connect(self._delete_selected)
        menu.addAction(delete_action)
        menu.exec(self.table.viewport().mapToGlobal(position))

    def _board_id_for(self, device: Device) -> int | None:
        board = self.context.boards.model_for_device(int(device.id or 0))
        return board.id if board else None

    def _open_selected(self) -> None:
        device = self._selected_device()
        if device and device.id:
            self.window.open_device(device.id)

    def _toggle_favorite(self, device: Device) -> None:
        if not device.id:
            return
        state = self.context.devices.toggle_favorite(device.id)
        self.window.set_status(
            f"{device.brand_name} {device.name}: {'в избранном' if state else 'не в избранном'}"
        )
        self.refresh()

    def _toggle_favorite_selected(self) -> None:
        device = self._selected_device()
        if device:
            self._toggle_favorite(device)

    def add_device(self) -> None:
        dialog = DeviceEditorDialog(
            self.context, preset_brand_id=self._current_brand, parent=self.window
        )
        if dialog.exec():
            saved = dialog.result_device
            self.on_show()
            if saved and saved.id:
                self.window.open_device(saved.id)

    def _edit_selected(self) -> None:
        device = self._selected_device()
        if not device:
            return
        dialog = DeviceEditorDialog(self.context, device=device, parent=self.window)
        if dialog.exec():
            self.on_show()
            self.window.set_status("Изменения сохранены")

    def _delete_selected(self) -> None:
        device = self._selected_device()
        if not device:
            return
        if not confirm(
            self.window,
            "Удалить устройство",
            f"Удалить «{device.brand_name} {device.name}»?\n"
            "Будут удалены связанные варианты, прошивки, метки избранного и история. "
            "Материалы библиотеки останутся, но потеряют привязку.",
            confirm_text="Удалить",
            danger=True,
        ):
            return
        try:
            self.context.devices.delete(int(device.id or 0))
        except Exception as exc:
            error(self.window, "Ошибка удаления", str(exc))
            return
        self.on_show()
        self.window.set_status("Устройство удалено")

    def _manage_brands(self) -> None:
        from repair_os.ui.dialogs.brand_manager import BrandManagerDialog

        dialog = BrandManagerDialog(self.context, parent=self.window)
        dialog.exec()
        self.on_show()
