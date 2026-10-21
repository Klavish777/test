"""3D BoardView: интерактивная плата, слои, компоненты и пользовательские метки."""

from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QSplitter,
    QTabWidget,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from repair_os.boardview.photo_view import BoardPhotoView
from repair_os.boardview.scene import build_scene
from repair_os.boardview.viewer_3d import BoardViewer3D
from repair_os.data.models import BoardComponent, BoardModel
from repair_os.services.context import AppContext
from repair_os.ui.dialogs.base import confirm, error, info
from repair_os.ui.dialogs.document_editor import NoteEditorDialog
from repair_os.ui.table_models import ComponentTableModel
from repair_os.ui.widgets import (
    Card,
    wrapped_label,
    Chip,
    FlowLayout,
    SearchInput,
    badge,
    clear_layout,
    field_row,
    muted,
    separator,
    title,
)

log = logging.getLogger(__name__)


class BoardViewPage(QWidget):
    route_key = "boardview"

    def __init__(self, context: AppContext, window) -> None:
        super().__init__()
        self.context = context
        self.window = window
        self.board: BoardModel | None = None
        self.components: list[BoardComponent] = []
        self.selected: BoardComponent | None = None
        self._side = "top"

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 14)
        layout.setSpacing(10)

        header = QHBoxLayout()
        box = QVBoxLayout()
        box.setSpacing(2)
        box.addWidget(title("3D BoardView", object_name="PageTitle"))
        subtitle = muted(
            "Геометрия только из импортированных данных. Без 3D доступен просмотр фото с метками."
        )
        subtitle.setMaximumWidth(640)
        box.addWidget(subtitle)
        header.addLayout(box)
        header.addStretch(1)
        self.board_combo = QComboBox(self)
        self.board_combo.setMinimumWidth(280)
        self.board_combo.currentIndexChanged.connect(self._on_board_changed)
        header.addWidget(self.board_combo)
        import_button = QPushButton("Импорт платы", self)
        import_button.setObjectName("Primary")
        import_button.clicked.connect(self.window.run_board_import)
        header.addWidget(import_button)
        export_button = QPushButton("Экспорт", self)
        export_button.setObjectName("Ghost")
        export_button.clicked.connect(self._export_package)
        header.addWidget(export_button)
        layout.addLayout(header)

        self.info_bar = QLabel("", self)
        self.info_bar.setObjectName("Muted")
        self.info_bar.setWordWrap(True)
        layout.addWidget(self.info_bar)

        splitter = QSplitter(Qt.Horizontal, self)
        splitter.addWidget(self._build_left_panel())
        splitter.addWidget(self._build_viewer_area())
        splitter.addWidget(self._build_right_panel())
        splitter.setSizes([190, 690, 340])
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setStretchFactor(2, 0)
        splitter.setChildrenCollapsible(False)
        layout.addWidget(splitter, 1)

    # ------------------------------------------------------------------ панели
    def _build_left_panel(self) -> QWidget:
        panel = QFrame(self)
        panel.setObjectName("Card")
        panel.setFixedWidth(190)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)
        layout.addWidget(title("Слои", object_name="CardTitle"))

        self.layers_container = QWidget(panel)
        self.layers_layout = QVBoxLayout(self.layers_container)
        self.layers_layout.setContentsMargins(0, 0, 0, 0)
        self.layers_layout.setSpacing(4)
        layout.addWidget(self.layers_container)

        layout.addWidget(separator(panel))
        self.types_container = QWidget(panel)
        self.types_layout = QVBoxLayout(self.types_container)
        self.types_layout.setContentsMargins(0, 0, 0, 0)
        self.types_layout.setSpacing(4)
        layout.addWidget(self.types_container)

        layout.addWidget(separator(panel))
        self.labels_check = QCheckBox("Обозначения", panel)
        self.labels_check.setToolTip("Показывать позиционные обозначения в 3D и на фото")
        self.labels_check.setChecked(True)
        self.labels_check.stateChanged.connect(self._update_view_settings)
        layout.addWidget(self.labels_check)
        self.board_check = QCheckBox("Текстолит", panel)
        self.board_check.setToolTip("Показывать подложку платы в 3D-сцене")
        self.board_check.setChecked(True)
        self.board_check.stateChanged.connect(self._update_view_settings)
        layout.addWidget(self.board_check)
        layout.addStretch(1)
        layout.addWidget(
            muted(
                "Слои берутся из данных пакета. Скрытие слоя не удаляет компоненты.",
                panel,
            )
        )
        return panel

    def _build_viewer_area(self) -> QWidget:
        container = QWidget(self)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        toolbar = QHBoxLayout()
        toolbar.setSpacing(6)
        for text, tip, handler in (
            ("Сброс", "Сбросить камеру (F)", lambda: self.viewer_3d.reset_view()),
            ("Реверс", "Показать обратную сторону (S)", self._flip_side),
            ("Сверху", "Вид сверху", lambda: self._set_camera(pitch=89, yaw=0)),
            ("Сбоку", "Вид сбоку", lambda: self._set_camera(pitch=8, yaw=-35)),
            ("Снимок", "Сохранить PNG текущего вида", self._export_view),
        ):
            button = QPushButton(text, container)
            button.setObjectName("Ghost")
            button.setToolTip(tip)
            button.setCursor(Qt.PointingHandCursor)
            button.clicked.connect(handler)
            toolbar.addWidget(button)
        toolbar.addStretch(1)
        self.side_label = QLabel("сторона: верхняя", container)
        self.side_label.setObjectName("Dim")
        toolbar.addWidget(self.side_label)
        layout.addLayout(toolbar)

        tabs = QTabWidget(container)
        self.viewer_3d = BoardViewer3D(tabs)
        self.viewer_3d.componentSelected.connect(self._on_component_selected)
        self.viewer_3d.componentActivated.connect(self._on_component_activated)
        tabs.addTab(self.viewer_3d, "3D-модель")

        photo_container = QWidget(tabs)
        photo_layout = QVBoxLayout(photo_container)
        photo_layout.setContentsMargins(0, 0, 0, 0)
        photo_layout.setSpacing(6)
        photo_toolbar = QHBoxLayout()
        self.photo_side_top = Chip("Верхняя сторона", parent=photo_container)
        self.photo_side_top.setChecked(True)
        self.photo_side_top.clicked.connect(lambda: self._set_photo_side("top"))
        self.photo_side_bottom = Chip("Нижняя сторона", parent=photo_container)
        self.photo_side_bottom.clicked.connect(lambda: self._set_photo_side("bottom"))
        photo_toolbar.addWidget(self.photo_side_top)
        photo_toolbar.addWidget(self.photo_side_bottom)
        photo_toolbar.addStretch(1)
        photo_toolbar.addWidget(muted("колёсико — масштаб, перетаскивание — панорама"))
        photo_layout.addLayout(photo_toolbar)
        self.photo_view = BoardPhotoView(photo_container)
        self.photo_view.componentSelected.connect(self._on_component_selected)
        self.photo_view.componentActivated.connect(self._on_component_activated)
        photo_layout.addWidget(self.photo_view, 1)
        tabs.addTab(photo_container, "Фото с метками")
        self.tabs = tabs
        layout.addWidget(tabs, 1)

        self.missing_banner = QFrame(container)
        self.missing_banner.setStyleSheet(
            "background-color: rgba(201,139,58,0.12); border: 1px solid rgba(201,139,58,0.5);"
            " border-radius: 8px;"
        )
        banner_layout = QHBoxLayout(self.missing_banner)
        banner_layout.setContentsMargins(12, 8, 12, 8)
        self.missing_label = QLabel("", self.missing_banner)
        self.missing_label.setWordWrap(True)
        banner_layout.addWidget(self.missing_label, 1)
        self.missing_banner.hide()
        layout.addWidget(self.missing_banner)
        return container

    def _build_right_panel(self) -> QWidget:
        panel = QWidget(self)
        panel.setMinimumWidth(320)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        list_card = Card(panel, padding=12)
        list_body = list_card.body()
        header = QHBoxLayout()
        header.addWidget(title("Компоненты", object_name="CardTitle"))
        header.addStretch(1)
        self.count_badge = badge("0", "neutral", list_card)
        header.addWidget(self.count_badge)
        list_body.addLayout(header)

        self.component_search = SearchInput("Обозначение (U1201)…", list_card)
        self.component_search.textChanged.connect(self._filter_components)
        self.component_search.returnPressed.connect(self._search_component)
        list_body.addWidget(self.component_search)

        self.component_model = ComponentTableModel(self)
        self.component_table = QTableView(list_card)
        self.component_table.setModel(self.component_model)
        self.component_table.verticalHeader().setVisible(False)
        self.component_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.component_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.component_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.component_table.setAlternatingRowColors(True)
        self.component_table.horizontalHeader().setStretchLastSection(True)
        self.component_table.selectionModel().selectionChanged.connect(self._on_table_selection)
        self.component_table.doubleClicked.connect(self._on_table_double_click)
        header = self.component_table.horizontalHeader()
        for column in range(5):
            header.setSectionResizeMode(column, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.Stretch)
        list_body.addWidget(self.component_table, 1)
        layout.addWidget(list_card, 3)

        self.detail_card = Card(panel, padding=12)
        self.detail_body = self.detail_card.body()
        layout.addWidget(self.detail_card, 3)
        self._render_detail(None)

        self.annotations_card = Card(panel, padding=12)
        self.annotations_card.setMinimumHeight(130)
        self.annotations_body = self.annotations_card.body()
        layout.addWidget(self.annotations_card, 1)
        return panel

    # ------------------------------------------------------------------ данные
    def on_show(self) -> None:
        current = self.board.id if self.board else self.board_combo.currentData()
        self._reload_boards(selected=current)
        target = self.board_combo.currentData()
        if target:
            self._load_board(int(target))
        else:
            self._clear_view()

    def select_board(self, board_model_id: int | None) -> None:
        self._reload_boards(selected=board_model_id)
        if board_model_id:
            self._load_board(board_model_id)
        else:
            first = self.board_combo.currentData()
            if first:
                self._load_board(int(first))

    def _reload_boards(self, *, selected: int | None) -> None:
        self.board_combo.blockSignals(True)
        self.board_combo.clear()
        boards = self.context.boards.list_models(limit=500)
        for board in boards:
            label = board.name
            if board.is_demo:
                label += " · ДЕМО"
            if not board.has_3d:
                label += " · без 3D"
            self.board_combo.addItem(label, board.id)
        if selected is not None:
            index = self.board_combo.findData(selected)
            if index >= 0:
                self.board_combo.setCurrentIndex(index)
        self.board_combo.blockSignals(False)

    def _on_board_changed(self, _index: int) -> None:
        board_id = self.board_combo.currentData()
        if board_id:
            self._load_board(int(board_id))

    def _load_board(self, board_model_id: int) -> None:
        try:
            scene_data = self.context.packages.load_scene(board_model_id)
        except Exception as exc:
            error(self.window, "Не удалось загрузить плату", str(exc))
            return
        board_row = scene_data["board"]
        self.board = BoardModel.from_row(board_row)
        self.components = [
            BoardComponent.from_row(item) for item in scene_data["components"]
        ]
        self.selected = None
        self._side = "top"

        scene = build_scene(self.board, self.components)
        self.viewer_3d.set_scene(scene)
        self._rebuild_layer_filters(scene_data["layers"], scene_data["types"])
        self._update_photo()
        self._filter_components()
        self._render_detail(None)
        self._render_annotations()

        subtitle = f"{self.board.device_name or 'Без привязки'} · код {self.board.board_code or '—'}"
        if self.board.width_mm:
            subtitle += (
                f" · {self.board.width_mm:.1f}×{self.board.length_mm:.1f}×"
                f"{self.board.thickness_mm or 0:.1f} мм"
            )
        subtitle += f" · компонентов: {len(self.components)}"
        if self.board.is_demo:
            subtitle += " · ДЕМО: геометрия условная"
        self.info_bar.setText(subtitle)

        missing_3d = not scene.boxes
        self.tabs.setTabEnabled(0, not missing_3d)
        if missing_3d:
            self.tabs.setCurrentIndex(1)
            self.missing_banner.show()
            self.missing_label.setText(
                "Для этой платы нет 3D-данных: доступен только просмотр фотографий с метками. "
                "Импортируйте пакет BoardView с геометрией, чтобы включить 3D."
            )
        elif not self.photo_view.has_photo():
            self.missing_banner.show()
            self.missing_label.setText(
                "3D-модель загружена, но фотографии платы отсутствуют — на вкладке «Фото с метками» "
                "будет пусто до добавления изображений."
            )
        else:
            self.missing_banner.hide()

    def _clear_view(self) -> None:
        self.board = None
        self.components = []
        self.viewer_3d.clear()
        self.photo_view.set_photo(None, components=[])
        self.component_model.set_rows([])
        self.info_bar.setText(
            "Платы не загружены. Импортируйте пакет BoardView (JSON) — приложение не создаёт "
            "геометрию самостоятельно."
        )
        self._render_detail(None)

    def _rebuild_layer_filters(self, layers: list[str], types: list[str]) -> None:
        clear_layout(self.layers_layout)
        clear_layout(self.types_layout)
        self._layer_checks: dict[str, QCheckBox] = {}
        self._type_checks: dict[str, QCheckBox] = {}
        for layer in layers:
            check = QCheckBox(layer, self.layers_container)
            check.setChecked(True)
            check.stateChanged.connect(self._update_view_settings)
            self._layer_checks[layer] = check
            self.layers_layout.addWidget(check)
        if not layers:
            self.layers_layout.addWidget(muted("Слои не заданы", self.layers_container))
        self.types_layout.addWidget(QLabel("Типы", self.types_container))
        for component_type in types:
            check = QCheckBox(component_type, self.types_container)
            check.setChecked(True)
            check.stateChanged.connect(self._update_view_settings)
            self._type_checks[component_type] = check
            self.types_layout.addWidget(check)
        if not types:
            self.types_layout.addWidget(muted("Типы не заданы", self.types_container))

    def _update_view_settings(self, *_args) -> None:
        hidden_layers = [
            layer for layer, check in getattr(self, "_layer_checks", {}).items() if not check.isChecked()
        ]
        hidden_types = [
            ctype for ctype, check in getattr(self, "_type_checks", {}).items() if not check.isChecked()
        ]
        self.viewer_3d.set_hidden_layers(hidden_layers)
        self.viewer_3d.set_hidden_types(hidden_types)
        self.viewer_3d.set_show_labels(self.labels_check.isChecked())
        self.viewer_3d.set_show_board(self.board_check.isChecked())
        self.photo_view.set_show_labels(self.labels_check.isChecked())
        self._filter_components()

    def _update_photo(self) -> None:
        if not self.board:
            self.photo_view.set_photo(None, components=[])
            return
        path = self.board.photo_top if self._side == "top" else self.board.photo_bottom
        side_components = [component for component in self.components if component.side == self._side]
        self.photo_view.set_photo(str(path) if path else None, components=side_components)
        self.photo_side_top.setChecked(self._side == "top")
        self.photo_side_bottom.setChecked(self._side == "bottom")

    def _set_photo_side(self, side: str) -> None:
        self._side = side
        self._update_photo()

    def _filter_components(self) -> None:
        needle = self.component_search.text().strip().lower()
        hidden_layers = [
            layer for layer, check in getattr(self, "_layer_checks", {}).items() if not check.isChecked()
        ]
        hidden_types = [
            ctype for ctype, check in getattr(self, "_type_checks", {}).items() if not check.isChecked()
        ]
        rows = [
            component
            for component in self.components
            if (not needle
                or needle in component.designator.lower()
                or needle in (component.part_marking or "").lower()
                or needle in (component.purpose or "").lower())
            and (component.layer or "") not in hidden_layers
            and (component.component_type or "") not in hidden_types
        ]
        self.component_model.set_rows(rows)
        self.count_badge.setText(str(len(rows)))

    def _search_component(self) -> None:
        designator = self.component_search.text().strip()
        if not designator:
            return
        component = self.viewer_3d.select_designator(designator)
        if not component:
            info(self.window, "Компонент не найден", f"Обозначение «{designator}» не найдено в этой плате.")
            return
        self._select_component(component)

    # ------------------------------------------------------------------ выбор
    def _on_table_selection(self, *_args) -> None:
        indexes = self.component_table.selectionModel().selectedRows()
        if not indexes:
            return
        component = self.component_model.row_at(indexes[0])
        if component:
            self._select_component(component, update_table=False)

    def _on_table_double_click(self, index) -> None:
        component = self.component_model.row_at(index)
        if component:
            self._on_component_activated(component)

    def _on_component_selected(self, component) -> None:
        if component is not None:
            self._select_component(component)

    def _on_component_activated(self, component) -> None:
        if component is None:
            return
        info(
            self.window,
            f"Компонент {component.designator}",
            self._component_description(component),
        )

    def _select_component(self, component: BoardComponent, *, update_table: bool = True) -> None:
        self.selected = component
        self.viewer_3d.set_selected_component(component.id)
        self.photo_view.set_selected_component(component.id)
        if update_table:
            for row, item in enumerate(self.component_model.rows):
                if item.id == component.id:
                    index = self.component_model.index(row, 0)
                    self.component_table.selectRow(row)
                    self.component_table.scrollTo(index)
                    break
        self._render_detail(component)
        if component.side != self._side:
            self._set_photo_side(component.side)

    def _component_description(self, component: BoardComponent) -> str:
        lines = [
            f"Обозначение: {component.designator}",
            f"Сторона: {'верхняя' if component.side == 'top' else 'нижняя'}",
            f"Слой: {component.layer or 'не указан'}",
            f"Тип: {component.component_type or 'не указан'}",
            f"Маркировка: {component.part_marking or 'не указана'}",
            f"Назначение: {component.purpose or 'не указано'}",
            f"Позиция: X={component.pos_x if component.pos_x is not None else '—'}, "
            f"Y={component.pos_y if component.pos_y is not None else '—'}",
            f"Метка на фото: {component.marker_u if component.marker_u is not None else '—'}, "
            f"{component.marker_v if component.marker_v is not None else '—'}",
        ]
        if component.notes:
            lines.append(f"Примечания: {component.notes}")
        if component.is_demo:
            lines.append("ДЕМО: данные условные и не описывают реальное изделие.")
        return "\n".join(lines)

    # ------------------------------------------------------------------ детали
    def _render_detail(self, component: BoardComponent | None) -> None:
        clear_layout(self.detail_body)
        self.detail_body.addWidget(title("Карточка компонента", object_name="CardTitle"))
        if component is None:
            self.detail_body.addWidget(
                muted(
                    "Выберите компонент в 3D-сцене, на фотографии или в списке. "
                    "Пустые поля означают, что данные отсутствуют в источнике."
                )
            )
            return
        self.detail_body.addWidget(
            field_row("Обозначение", component.designator, self.detail_card)
        )
        side = "верхняя" if component.side == "top" else "нижняя"
        self.detail_body.addWidget(field_row("Сторона / слой", f"{side} / {component.layer or '—'}", self.detail_card))
        self.detail_body.addWidget(
            field_row("Тип", component.component_type or "не указан", self.detail_card)
        )
        self.detail_body.addWidget(
            field_row("Маркировка", component.part_marking or "нет данных", self.detail_card)
        )
        self.detail_body.addWidget(
            field_row("Назначение", component.purpose or "нет данных", self.detail_card)
        )
        if component.pos_x is not None:
            self.detail_body.addWidget(
                field_row(
                    "Координаты, мм",
                    f"X {component.pos_x:.2f} · Y {component.pos_y or 0:.2f} · Z {component.pos_z or 0:.2f}",
                    self.detail_card,
                )
            )
        if component.notes:
            self.detail_body.addWidget(field_row("Примечания", component.notes, self.detail_card))
        if component.is_demo:
            self.detail_body.addWidget(badge("ДЕМО-КОМПОНЕНТ", "demo", self.detail_card))

        buttons = QHBoxLayout()
        note_button = QPushButton("Заметка", self.detail_card)
        note_button.setObjectName("Ghost")
        note_button.clicked.connect(lambda: self._add_note(component))
        buttons.addWidget(note_button)
        annotate_button = QPushButton("Метка", self.detail_card)
        annotate_button.setObjectName("Ghost")
        annotate_button.clicked.connect(lambda: self._add_annotation(component))
        buttons.addWidget(annotate_button)
        buttons.addStretch(1)
        self.detail_body.addLayout(buttons)

    def _render_annotations(self) -> None:
        clear_layout(self.annotations_body)
        header = QHBoxLayout()
        header.addWidget(title("Метки и заметки", object_name="CardTitle"))
        header.addStretch(1)
        if self.selected:
            add = QPushButton("+", self.annotations_card)
            add.setToolTip("Добавить метку к выбранному компоненту")
            add.clicked.connect(lambda: self._add_annotation(self.selected))
            header.addWidget(add)
        self.annotations_body.addLayout(header)
        if not self.board:
            self.annotations_body.addWidget(muted("Плата не выбрана"))
            return
        annotations = self.context.boards.annotations(int(self.board.id or 0))
        if not annotations:
            self.annotations_body.addWidget(
                muted("Меток нет. Добавьте свою метку к компоненту.", self.annotations_card)
            )
        for annotation in annotations[:6]:
            row = QHBoxLayout()
            body = (annotation.body or "").strip()
            if len(body) > 70:
                body = body[:70] + "…"
            text = wrapped_label(
                f"• {annotation.label}" + (f" — {body}" if body else ""),
                self.annotations_card,
                object_name="Muted",
                lines=2,
            )
            row.addWidget(text, 1)
            remove = QPushButton("×", self.annotations_card)
            remove.setObjectName("LinkButton")
            remove.setFixedWidth(22)
            remove.clicked.connect(
                lambda _checked=False, aid=annotation.id: self._delete_annotation(aid)
            )
            row.addWidget(remove)
            self.annotations_body.addLayout(row)

    # ------------------------------------------------------------------ действия
    def _add_note(self, component: BoardComponent) -> None:
        if not self.board:
            return
        dialog = NoteEditorDialog(
            self.context,
            preset_device=(
                self.context.devices.get(int(self.board.device_id))
                if self.board.device_id
                else None
            ),
            component_id=component.id,
            default_title=f"{component.designator} · {self.board.board_code or 'плата'}",
            parent=self.window,
        )
        if dialog.exec():
            self.window.set_status("Заметка сохранена")

    def _add_annotation(self, component: BoardComponent | None) -> None:
        from repair_os.ui.dialogs.base import FormDialog

        if not self.board:
            return
        dialog = FormDialog("Новая метка", parent=self.window, width=440)
        label_field = dialog.add_line(
            "Метка *",
            f"{component.designator}: " if component else "",
            placeholder="Например: нет напряжения",
        )
        body_field = dialog.add_text("Описание", "", height=90)
        dialog.on_save(
            lambda _payload: self.context.boards.add_annotation(
                int(self.board.id or 0),
                label_field.text(),
                body=body_field.toPlainText(),
                component_id=component.id if component else None,
            )
        )
        if dialog.exec():
            self._render_annotations()
            self.window.set_status("Метка добавлена")

    def _delete_annotation(self, annotation_id: int | None) -> None:
        if not annotation_id:
            return
        if confirm(self.window, "Удалить метку", "Удалить выбранную метку?", confirm_text="Удалить"):
            self.context.boards.delete_annotation(int(annotation_id))
            self._render_annotations()

    def _flip_side(self) -> None:
        self.viewer_3d.flip_side()
        self._side = "bottom" if self._side == "top" else "top"
        self._update_photo()
        self.side_label.setText(
            "сторона: нижняя" if self._side == "bottom" else "сторона: верхняя"
        )

    def _set_camera(self, *, pitch: float, yaw: float) -> None:
        state = self.viewer_3d.camera_state()
        state.update({"pitch": pitch, "yaw": yaw})
        self.viewer_3d.set_camera_state(state)

    def _export_view(self) -> None:
        if not self.board:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Сохранить снимок 3D-вида", "boardview.png", "PNG (*.png)"
        )
        if not path:
            return
        pixmap = self.viewer_3d.grab()
        if pixmap.save(path, "PNG"):
            self.window.set_status(f"Снимок сохранён: {path}")
        else:
            error(self.window, "Ошибка", "Не удалось сохранить изображение")

    def _export_package(self) -> None:
        if not self.board:
            info(self.window, "Плата не выбрана", "Сначала выберите плату.")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Экспорт пакета BoardView", "board_package.json", "JSON (*.json)"
        )
        if not path:
            return
        try:
            target = self.context.packages.export_package(int(self.board.id or 0), Path(path))
        except Exception as exc:
            error(self.window, "Ошибка экспорта", str(exc))
            return
        self.window.set_status(f"Пакет сохранён: {target}")
