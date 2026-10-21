"""Результаты сквозного поиска по всем разделам."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from repair_os.data.models import SearchHit
from repair_os.services.context import AppContext
from repair_os.ui.widgets import (
    Card,
    ClickableCard,
    EmptyState,
    badge,
    clear_layout,
    muted,
    title,
)

GROUP_TITLES = {
    "device": "Устройства",
    "firmware": "Прошивки",
    "document": "Материалы библиотеки",
    "board": "Платы BoardView",
    "component": "Компоненты",
}


class SearchResultsPage(QWidget):
    route_key = "search"

    def __init__(self, context: AppContext, window) -> None:
        super().__init__()
        self.context = context
        self.window = window
        self.query = ""

        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 18, 22, 18)
        layout.setSpacing(12)
        header = QHBoxLayout()
        box = QVBoxLayout()
        box.setSpacing(2)
        box.addWidget(title("Результаты поиска", object_name="PageTitle"))
        self.subtitle = muted("Введите запрос в строке поиска сверху.")
        box.addWidget(self.subtitle)
        header.addLayout(box)
        header.addStretch(1)
        close = QPushButton("← Каталог", self)
        close.setObjectName("Ghost")
        close.clicked.connect(lambda: self.window.navigate("catalog"))
        header.addWidget(close)
        layout.addLayout(header)

        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        self.container = QWidget(scroll)
        self.body = QVBoxLayout(self.container)
        self.body.setContentsMargins(0, 0, 0, 0)
        self.body.setSpacing(14)
        scroll.setWidget(self.container)
        layout.addWidget(scroll, 1)

    def run_search(self, query: str) -> None:
        self.query = query.strip()
        clear_layout(self.body)
        if not self.query:
            self.subtitle.setText("Пустой запрос")
            return
        hits = self.context.search.search(self.query, limit_per_group=20)
        self.subtitle.setText(f"Найдено: {len(hits)} · запрос «{self.query}»")
        if not hits:
            self.body.addWidget(
                EmptyState(
                    "Ничего не найдено",
                    "Попробуйте точный код модели (например SM-A525F) или название бренда.",
                    "Открыть каталог",
                    lambda: self.window.navigate("catalog"),
                    self.container,
                )
            )
            return
        grouped: dict[str, list[SearchHit]] = {}
        for hit in hits:
            grouped.setdefault(hit.kind, []).append(hit)
        for kind, group in grouped.items():
            card = Card(self.container)
            body = card.body()
            header = QHBoxLayout()
            header.addWidget(title(GROUP_TITLES.get(kind, kind), object_name="CardTitle"))
            header.addStretch(1)
            header.addWidget(badge(str(len(group)), "neutral", card))
            body.addLayout(header)
            for hit in group:
                body.addWidget(self._hit_row(hit, card))
            self.body.addWidget(card)
        self.body.addStretch(1)

    def _hit_row(self, hit: SearchHit, parent: QWidget) -> QWidget:
        row = ClickableCard(parent, padding=10)
        layout = row.body()
        top = QHBoxLayout()
        name = QLabel(hit.title, row)
        name.setObjectName("FieldValue")
        name.setWordWrap(True)
        top.addWidget(name, 1)
        if hit.extra.get("is_demo"):
            top.addWidget(badge("ДЕМО", "demo", row))
        if hit.kind == "firmware" and hit.extra.get("status"):
            from repair_os.ui.widgets import StatusBadge

            top.addWidget(StatusBadge(str(hit.extra["status"]), row))
        layout.addLayout(top)
        subtitle = QLabel(hit.subtitle, row)
        subtitle.setObjectName("Muted")
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)
        row.clicked.connect(lambda: self._open(hit))
        return row

    def _open(self, hit: SearchHit) -> None:
        if hit.kind == "device" and hit.device_id:
            self.window.open_device(hit.device_id)
        elif hit.kind == "firmware" and hit.extra.get("firmware_id"):
            self.window.open_firmware(int(hit.extra["firmware_id"]))
        elif hit.kind == "document" and hit.extra.get("document_id"):
            self.window.open_document(int(hit.extra["document_id"]))
        elif hit.kind == "board" and hit.extra.get("board_model_id"):
            self.window.open_board(int(hit.extra["board_model_id"]))
        elif hit.kind == "component" and hit.extra.get("board_model_id"):
            self.window.open_board(int(hit.extra["board_model_id"]))
            self.window.board_page.component_search.setText(hit.title)
            self.window.board_page._search_component()

    def on_show(self) -> None:
        if self.query:
            self.run_search(self.query)
