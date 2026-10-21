"""Главная страница: поиск, быстрые разделы, популярные бренды, недавние и избранные."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from repair_os.data.models import BoardModel, Device, Firmware, TechnicalDocument, human_size
from repair_os.services.context import AppContext
from repair_os.ui.widgets import (
    Card,
    Chip,
    ClickableCard,
    EmptyState,
    FlowLayout,
    SearchInput,
    StatTile,
    badge,
    clear_layout,
    muted,
    separator,
    title,
    breakable,
    wrapped_label,
)


class HomePage(QWidget):
    route_key = "home"

    def __init__(self, context: AppContext, window) -> None:
        super().__init__()
        self.context = context
        self.window = window
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        outer.addWidget(scroll)

        self.container = QWidget(scroll)
        self.layout = QVBoxLayout(self.container)
        self.layout.setContentsMargins(24, 22, 24, 28)
        self.layout.setSpacing(18)
        self.layout.setSizeConstraint(QVBoxLayout.SetMinAndMaxSize)
        scroll.setWidget(self.container)

        self._build_hero()
        self._build_stats()
        self._build_sections()
        self._build_bottom()

    # ------------------------------------------------------------------ блоки
    def _build_hero(self) -> None:
        card = Card(self.container, padding=22)
        card.setStyleSheet(
            "QFrame#Card { background-color: #0f2039; border: 1px solid #24406a;"
            " border-radius: 14px; }"
        )
        layout = card.body()
        top = QHBoxLayout()
        heading_box = QVBoxLayout()
        heading = QLabel("Рабочая станция мастера", card)
        heading.setObjectName("HeroTitle")
        subtitle = QLabel(
            "Каталог устройств, 3D BoardView, прошивки и техническая библиотека — "
            "локально, без обязательного подключения к сети.",
            card,
        )
        subtitle.setObjectName("Muted")
        subtitle.setWordWrap(True)
        heading_box.addWidget(heading)
        heading_box.addWidget(subtitle)
        top.addLayout(heading_box, 1)
        demo_badge = badge("ДЕМО-ДАННЫЕ ВКЛЮЧЕНЫ", "demo", card)
        top.addWidget(demo_badge, 0, Qt.AlignTop)
        layout.addLayout(top)

        self.hero_search = SearchInput("Введите бренд, модель или точный код (например SM-A525F)…", card)
        self.hero_search.returnPressed.connect(self._search)
        layout.addWidget(self.hero_search)

        buttons = QHBoxLayout()
        buttons.setSpacing(8)
        actions = [
            ("Открыть каталог", "Primary", lambda: self.window.navigate("catalog")),
            ("3D BoardView", "Ghost", lambda: self.window.navigate("boardview")),
            ("Firmware Center", "Ghost", lambda: self.window.navigate("firmware")),
            ("Technical Library", "Ghost", lambda: self.window.navigate("library")),
        ]
        for text, style, handler in actions:
            button = QPushButton(text, card)
            button.setObjectName(style)
            button.setCursor(Qt.PointingHandCursor)
            button.clicked.connect(handler)
            buttons.addWidget(button)
        buttons.addStretch(1)
        layout.addLayout(buttons)
        self.layout.addWidget(card)

    def _build_stats(self) -> None:
        grid = QGridLayout()
        grid.setSpacing(12)
        self.stat_devices = StatTile("Устройств в каталоге", "—", parent=self.container)
        self.stat_brands = StatTile("Брендов", "—", parent=self.container)
        self.stat_firmware = StatTile("Записей прошивок", "—", parent=self.container)
        self.stat_docs = StatTile("Материалов", "—", parent=self.container)
        self.stat_boards = StatTile("Платы BoardView", "—", parent=self.container)
        for index, tile in enumerate(
            (
                self.stat_devices,
                self.stat_brands,
                self.stat_firmware,
                self.stat_docs,
                self.stat_boards,
            )
        ):
            grid.addWidget(tile, 0, index)
        self.layout.addLayout(grid)

    def _section_header(self, text: str, action_text: str, handler) -> QHBoxLayout:
        row = QHBoxLayout()
        row.addWidget(title(text))
        row.addStretch(1)
        if action_text:
            button = QPushButton(action_text)
            button.setObjectName("LinkButton")
            button.setCursor(Qt.PointingHandCursor)
            button.clicked.connect(handler)
            row.addWidget(button)
        return row

    def _build_sections(self) -> None:
        columns = QHBoxLayout()
        columns.setSpacing(16)

        left = QVBoxLayout()
        left.setSpacing(16)
        self.board_card = Card(self.container)
        self.board_body = self.board_card.body()
        left.addWidget(self.board_card)

        self.firmware_card = Card(self.container)
        self.firmware_body = self.firmware_card.body()
        left.addWidget(self.firmware_card)
        left.addStretch(1)

        right = QVBoxLayout()
        right.setSpacing(16)
        self.library_card = Card(self.container)
        self.library_body = self.library_card.body()
        right.addWidget(self.library_card)

        self.brands_card = Card(self.container)
        self.brands_body = self.brands_card.body()
        right.addWidget(self.brands_card)
        right.addStretch(1)

        columns.addLayout(left, 3)
        columns.addLayout(right, 2)
        self.layout.addLayout(columns)

    def _build_bottom(self) -> None:
        bottom = QHBoxLayout()
        bottom.setSpacing(16)
        self.favorites_card = Card(self.container)
        self.favorites_body = self.favorites_card.body()
        bottom.addWidget(self.favorites_card, 1)

        self.recent_card = Card(self.container)
        self.recent_body = self.recent_card.body()
        bottom.addWidget(self.recent_card, 1)
        self.layout.addLayout(bottom)
        self.layout.addStretch(1)

    # ------------------------------------------------------------------ данные
    def on_show(self) -> None:
        self._refresh_stats()
        self._refresh_boards()
        self._refresh_firmware()
        self._refresh_library()
        self._refresh_brands()
        self._refresh_favorites()
        self._refresh_recent()

    def _refresh_stats(self) -> None:
        ctx = self.context
        self.stat_devices.set_value(str(ctx.devices.count()))
        self.stat_brands.set_value(str(ctx.brands.count()))
        self.stat_firmware.set_value(str(ctx.db.table_count("firmware")))
        self.stat_docs.set_value(str(ctx.db.table_count("technical_documents")))
        boards = ctx.boards.list_models(limit=1000)
        with_3d = [board for board in boards if board.has_3d]
        self.stat_boards.set_value(f"{len(with_3d)} / {len(boards)}")

    def _refresh_boards(self) -> None:
        clear_layout(self.board_body)
        self.board_body.addLayout(
            self._section_header(
                "3D BoardView", "Все платы →", lambda: self.window.navigate("boardview")
            )
        )
        boards: list[BoardModel] = self.context.boards.list_models(limit=4)
        if not boards:
            self.board_body.addWidget(
                EmptyState(
                    "Нет загруженных плат",
                    "Импортируйте пакет BoardView (JSON/ZIP) — приложение не выдумывает геометрию.",
                    "Импорт платы",
                    self.window.run_board_import,
                )
            )
            return
        for board in boards:
            self.board_body.addWidget(self._board_row(board))
        self.board_body.addWidget(
            muted(
                "Демонстрационная плата имеет условную геометрию и помечена как ДЕМО. "
                "Реальные 3D-данные добавляются импортом.",
                self.board_body.parentWidget(),
            )
        )

    def _board_row(self, board: BoardModel) -> QWidget:
        card = ClickableCard(self.board_card, padding=12)
        layout = card.body()
        layout.setSpacing(4)
        header = QHBoxLayout()
        name = wrapped_label(breakable(board.name), card, object_name="CardTitle", lines=2)
        header.addWidget(name, 1)
        header.addWidget(badge("3D", "info" if board.has_3d else "neutral", card))
        if board.is_demo:
            header.addWidget(badge("ДЕМО", "demo", card))
        layout.addLayout(header)
        detail = wrapped_label(
            f"{board.device_name or 'Без привязки'} · компонентов: {board.component_count}"
            + (f" · {board.width_mm:.0f}×{board.length_mm:.0f} мм" if board.width_mm else ""),
            card,
            object_name="Muted",
            lines=2,
        )
        layout.addWidget(detail)
        card.clicked.connect(lambda: self.window.open_board(board.id))
        return card

    def _refresh_firmware(self) -> None:
        clear_layout(self.firmware_body)
        self.firmware_body.addLayout(
            self._section_header(
                "Firmware Center", "Все прошивки →", lambda: self.window.navigate("firmware")
            )
        )
        firmware = self.context.firmware.recent(limit=4)
        if not firmware:
            self.firmware_body.addWidget(
                muted("Записей пока нет. Добавьте локальный файл или импортируйте CSV/JSON.")
            )
            return
        for item in firmware:
            self.firmware_body.addWidget(self._firmware_row(item))

    def _firmware_row(self, item: Firmware) -> QWidget:
        card = ClickableCard(self.firmware_card, padding=12)
        layout = card.body()
        layout.setSpacing(3)
        header = QHBoxLayout()
        name = wrapped_label(breakable(item.file_name), card, object_name="CardTitle", lines=2)
        header.addWidget(name, 1)
        if item.is_demo:
            header.addWidget(badge("ДЕМО", "demo", card))
        layout.addLayout(header)
        detail = wrapped_label(
            f"{item.model_code or '—'} · {item.os_version or 'ОС не указана'} · "
            f"{human_size(item.file_size)} · {item.build_number or 'сборка не указана'}",
            card,
            object_name="Muted",
            lines=2,
        )
        layout.addWidget(detail)
        card.clicked.connect(lambda: self.window.open_firmware(item.id))
        return card

    def _refresh_library(self) -> None:
        clear_layout(self.library_body)
        self.library_body.addLayout(
            self._section_header(
                "Technical Library", "Все материалы →", lambda: self.window.navigate("library")
            )
        )
        documents = self.context.library.recent(limit=4)
        if not documents:
            self.library_body.addWidget(
                muted("Материалов нет. Добавьте PDF, схемы, фото плат или заметки.")
            )
            return
        for document in documents:
            self.library_body.addWidget(self._document_row(document))

    def _document_row(self, document: TechnicalDocument) -> QWidget:
        card = ClickableCard(self.library_card, padding=12)
        layout = card.body()
        layout.setSpacing(3)
        header = QHBoxLayout()
        name = wrapped_label(breakable(document.title), card, object_name="CardTitle", lines=2)
        header.addWidget(name, 1)
        if document.is_demo:
            header.addWidget(badge("ДЕМО", "demo", card))
        layout.addLayout(header)
        detail = wrapped_label(
            f"{document.device_name or 'Без привязки'} · {document.category} · {document.doc_type}",
            card,
            object_name="Muted",
            lines=2,
        )
        layout.addWidget(detail)
        card.clicked.connect(lambda: self.window.open_document(document.id))
        return card

    def _refresh_brands(self) -> None:
        clear_layout(self.brands_body)
        self.brands_body.addLayout(
            self._section_header(
                "Популярные бренды", "Каталог →", lambda: self.window.navigate("catalog")
            )
        )
        brands = self.context.brands.popular(limit=10)
        container = QWidget(self.brands_card)
        flow = FlowLayout(container, spacing=6)
        for brand in brands:
            chip = Chip(brand.name, count=brand.device_count, parent=container)
            chip.clicked.connect(
                lambda _checked=False, brand_id=brand.id: self._open_brand(brand_id)
            )
            flow.addWidget(chip)
        self.brands_body.addWidget(container)
        if not brands:
            self.brands_body.addWidget(muted("Бренды появятся после импорта данных."))

    def _open_brand(self, brand_id: int) -> None:
        self.window.navigate("catalog")
        self.window.catalog_page.select_brand(brand_id)

    def _refresh_favorites(self) -> None:
        clear_layout(self.favorites_body)
        self.favorites_body.addLayout(
            self._section_header(
                "Избранные устройства", "Каталог →", lambda: self.window.navigate("catalog")
            )
        )
        favorites = self.context.devices.favorites(limit=4)
        if not favorites:
            self.favorites_body.addWidget(
                muted("Добавьте устройство в избранное — звёздочка в карточке устройства.")
            )
            return
        for device in favorites:
            self.favorites_body.addWidget(self._device_row(device))

    def _refresh_recent(self) -> None:
        clear_layout(self.recent_body)
        self.recent_body.addLayout(
            self._section_header(
                "Недавно открытые", "Очистить", self._clear_recent
            )
        )
        recent = self.context.devices.recent(limit=4)
        if not recent:
            self.recent_body.addWidget(muted("Здесь появятся устройства, которые вы открывали."))
            return
        for device, opened_at, count in recent:
            card = self._device_row(device, opened_at)
            self.recent_body.addWidget(card)

    def _device_row(self, device: Device, opened_at: str | None = None) -> QWidget:
        card = ClickableCard(self.recent_card, padding=12)
        layout = card.body()
        layout.setSpacing(3)
        header = QHBoxLayout()
        name = wrapped_label(f"{device.brand_name} {device.name}", card, object_name="CardTitle", lines=1)
        header.addWidget(name, 1)
        if device.is_demo:
            header.addWidget(badge("ДЕМО", "demo", card))
        layout.addLayout(header)
        meta = wrapped_label(
            f"{device.model_code}"
            + (f" · {device.codename}" if device.codename else "")
            + (f" · открыто {opened_at}" if opened_at else ""),
            card,
            object_name="Muted",
            lines=1,
        )
        layout.addWidget(meta)
        card.clicked.connect(lambda: self.window.open_device(int(device.id or 0)))
        return card

    def _clear_recent(self) -> None:
        self.context.devices.clear_recent()
        self._refresh_recent()
        self.window.set_status("История недавних устройств очищена")

    def _search(self) -> None:
        query = self.hero_search.text().strip()
        if query:
            self.window.show_search(query)
