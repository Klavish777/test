"""Интерактивный 3D-просмотрщик платы (QWidget + QPainter, программный рендер)."""

from __future__ import annotations

import logging
import math
from typing import Iterable

from PySide6.QtCore import QPoint, QPointF, QRectF, Qt, Signal
from PySide6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QFontMetrics,
    QMouseEvent,
    QPainter,
    QPen,
    QPolygonF,
    QWheelEvent,
)
from PySide6.QtWidgets import QSizePolicy, QWidget

from repair_os.boardview.scene import (
    Camera,
    SceneData,
    Vec3,
    board_faces,
    box_faces,
    shaded,
)
from repair_os.data.models import BoardComponent

log = logging.getLogger(__name__)

BACKGROUND_TOP = QColor("#0b1626")
BACKGROUND_BOTTOM = QColor("#0f1d31")
BOARD_TOP = QColor("#1d4a3a")
BOARD_SIDE = QColor("#153329")
EDGE_COLOR = QColor("#2f6f57")
SELECT_COLOR = QColor("#3d8bfd")
HOVER_COLOR = QColor("#63b3ff")


class BoardViewer3D(QWidget):
    """Честный 3D-просмотр платы: вращение, зум, панорама, выбор компонентов."""

    componentSelected = Signal(object)  # BoardComponent | None
    componentActivated = Signal(object)  # двойной клик
    viewChanged = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setMinimumSize(260, 200)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setCursor(Qt.OpenHandCursor)

        self._scene: SceneData | None = None
        self._camera = Camera()
        self._selected_id: int | None = None
        self._hover_id: int | None = None
        self._hidden_layers: set[str] = set()
        self._hidden_types: set[str] = set()
        self._show_labels = True
        self._show_board = True
        self._last_pos: QPoint | None = None
        self._mode = "rotate"
        self._projected: list[tuple[BoardComponent, QRectF, float]] = []
        self._label_font = QFont(self.font())
        self._label_font.setPointSizeF(max(6.5, self.font().pointSizeF() - 1.5))
        self._hint_font = QFont(self.font())
        self._hint_font.setPointSizeF(max(7.0, self.font().pointSizeF() - 1.0))

    # ------------------------------------------------------------------ данные
    def set_scene(self, scene: SceneData | None) -> None:
        self._scene = scene
        self._selected_id = None
        self._hover_id = None
        if scene:
            self._camera.reset()
            self._camera.fit(scene.width, scene.length)
        self.update()
        self.viewChanged.emit()

    def clear(self) -> None:
        self.set_scene(None)

    def scene(self) -> SceneData | None:
        return self._scene

    def set_selected_component(self, component_id: int | None) -> None:
        if self._selected_id == component_id:
            return
        self._selected_id = component_id
        self.update()

    def selected_component(self) -> BoardComponent | None:
        return self._find_component(self._selected_id)

    def select_designator(self, designator: str) -> BoardComponent | None:
        if not self._scene:
            return None
        wanted = designator.strip().upper()
        for box in self._scene.boxes:
            if box.component.designator.upper() == wanted:
                self._selected_id = box.component.id
                self.update()
                self.componentSelected.emit(box.component)
                return box.component
        for component in self._scene.markers_only:
            if component.designator.upper() == wanted:
                self._selected_id = component.id
                self.update()
                self.componentSelected.emit(component)
                return component
        return None

    def visible_components(self) -> list[BoardComponent]:
        if not self._scene:
            return []
        result = []
        for box in self._scene.boxes:
            component = box.component
            if (component.layer or "") in self._hidden_layers:
                continue
            if (component.component_type or "") in self._hidden_types:
                continue
            result.append(component)
        result.extend(
            component
            for component in self._scene.markers_only
            if (component.layer or "") not in self._hidden_layers
            and (component.component_type or "") not in self._hidden_types
        )
        return result

    # ------------------------------------------------------------------ настройки вида
    def set_hidden_layers(self, layers: Iterable[str]) -> None:
        self._hidden_layers = set(layers)
        self.update()

    def hidden_layers(self) -> set[str]:
        return set(self._hidden_layers)

    def set_hidden_types(self, types: Iterable[str]) -> None:
        self._hidden_types = set(types)
        self.update()

    def hidden_types(self) -> set[str]:
        return set(self._hidden_types)

    def set_show_labels(self, enabled: bool) -> None:
        self._show_labels = enabled
        self.update()

    def set_show_board(self, enabled: bool) -> None:
        self._show_board = enabled
        self.update()

    def flip_side(self) -> None:
        self._camera.flip_side()
        self.update()

    def reset_view(self) -> None:
        self._camera.reset()
        if self._scene:
            self._camera.fit(self._scene.width, self._scene.length)
        self.update()
        self.viewChanged.emit()

    def camera_state(self) -> dict[str, float]:
        return {
            "yaw": self._camera.yaw,
            "pitch": self._camera.pitch,
            "distance": self._camera.distance,
            "x": self._camera.target.x,
            "y": self._camera.target.y,
        }

    def set_camera_state(self, state: dict[str, float]) -> None:
        try:
            self._camera.yaw = float(state.get("yaw", self._camera.yaw))
            self._camera.pitch = float(state.get("pitch", self._camera.pitch))
            self._camera.distance = float(state.get("distance", self._camera.distance))
            self._camera.target = Vec3(
                float(state.get("x", self._camera.target.x)),
                float(state.get("y", self._camera.target.y)),
                0.0,
            )
        except (TypeError, ValueError):
            log.warning("Некорректное состояние камеры")
        self.update()

    # ------------------------------------------------------------------ события мыши
    def mousePressEvent(self, event: QMouseEvent) -> None:
        self.setFocus()
        if event.button() in (Qt.LeftButton, Qt.MiddleButton):
            self._last_pos = event.position().toPoint()
            self.setCursor(Qt.ClosedHandCursor)
        if event.button() == Qt.LeftButton:
            component = self._pick(event.position().x(), event.position().y())
            self._selected_id = component.id if component else None
            self.componentSelected.emit(component)
            self.update()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        position = event.position()
        if self._last_pos is not None:
            delta = position.toPoint() - self._last_pos
            self._last_pos = position.toPoint()
            right_button = bool(event.buttons() & Qt.RightButton)
            shift = bool(event.modifiers() & Qt.ShiftModifier)
            if right_button or shift:
                self._pan(delta.x(), delta.y())
            else:
                self._camera.rotate(-delta.x() * 0.45, -delta.y() * 0.4)
            self.update()
            self.viewChanged.emit()
            return
        component = self._pick(position.x(), position.y())
        hover_id = component.id if component else None
        if hover_id != self._hover_id:
            self._hover_id = hover_id
            self.update()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        self._last_pos = None
        self.setCursor(Qt.OpenHandCursor)
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.LeftButton:
            component = self._pick(event.position().x(), event.position().y())
            if component:
                self.componentActivated.emit(component)
        super().mouseDoubleClickEvent(event)

    def wheelEvent(self, event: QWheelEvent) -> None:
        steps = event.angleDelta().y() / 120.0
        if steps:
            self._camera.zoom(math.pow(0.86, steps))
            self.update()
            self.viewChanged.emit()
        event.accept()

    def keyPressEvent(self, event) -> None:
        key = event.key()
        if key == Qt.Key_F:
            self.reset_view()
        elif key == Qt.Key_S:
            self.flip_side()
        elif key == Qt.Key_Left:
            self._camera.rotate(-8, 0)
            self.update()
        elif key == Qt.Key_Right:
            self._camera.rotate(8, 0)
            self.update()
        elif key == Qt.Key_Up:
            self._camera.rotate(0, 6)
            self.update()
        elif key == Qt.Key_Down:
            self._camera.rotate(0, -6)
            self.update()
        elif key in (Qt.Key_Plus, Qt.Key_Equal):
            self._camera.zoom(0.85)
            self.update()
        elif key == Qt.Key_Minus:
            self._camera.zoom(1.18)
            self.update()
        else:
            super().keyPressEvent(event)

    def _pan(self, dx: float, dy: float) -> None:
        scale = self._camera.distance / (max(1, min(self.width(), self.height())) * self._camera.focal)
        yaw = math.radians(self._camera.yaw)
        # Компенсируем поворот, чтобы панорамирование ощущалось «по экрану».
        world_dx = (-dx * scale) * math.cos(yaw) - (dy * scale) * math.sin(yaw)
        world_dy = (-dx * scale) * math.sin(yaw) + (dy * scale) * math.cos(yaw)
        self._camera.pan(world_dx, world_dy)

    # ------------------------------------------------------------------ выбор
    def _find_component(self, component_id: int | None) -> BoardComponent | None:
        if component_id is None or not self._scene:
            return None
        for box in self._scene.boxes:
            if box.component.id == component_id:
                return box.component
        for component in self._scene.markers_only:
            if component.id == component_id:
                return component
        return None

    def _pick(self, x: float, y: float) -> BoardComponent | None:
        if not self._scene:
            return None
        hidden = self._hidden_layers
        hidden_types = self._hidden_types
        needle = QPoint(int(x), int(y))
        best: tuple[float, BoardComponent] | None = None
        for component, rect, depth in self._projected:
            if (component.layer or "") in hidden or (component.component_type or "") in hidden_types:
                continue
            if rect.contains(needle.x(), needle.y()):
                area = max(1.0, rect.width() * rect.height())
                score = depth + area * 0.001
                if best is None or score < best[0]:
                    best = (score, component)
        return best[1] if best else None

    # ------------------------------------------------------------------ отрисовка
    def paintEvent(self, event) -> None:  # noqa: N802 - Qt API
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.fillRect(self.rect(), QColor(BACKGROUND_TOP))

        if not self._scene or not self._scene.boxes:
            self._paint_placeholder(painter)
            painter.end()
            return

        width, height = float(self.width()), float(self.height())
        scene = self._scene
        camera = self._camera

        faces: list[tuple[float, Face, BoardComponent | None, tuple[int, int, int]]] = []
        projected_ids: set[int] = set()
        if self._show_board:
            for face in board_faces(scene.width, scene.length, scene.thickness):
                faces.append((self._face_depth(face), face, None, (29, 74, 58)))
        for box in scene.boxes:
            component = box.component
            if (component.layer or "") in self._hidden_layers:
                continue
            if (component.component_type or "") in self._hidden_types:
                continue
            selected = component.id == self._selected_id
            hovered = component.id == self._hover_id
            for face in box_faces(box.center, box.size, component.rotation or 0.0):
                faces.append((self._face_depth(face), face, component, box.color))
            del selected, hovered

        faces.sort(key=lambda item: item[0], reverse=True)
        self._projected = []

        for _depth, face, component, color in faces:
            polygon = QPolygonF(
                [
                    QPointF(*camera.project(point, width, height)[:2])
                    for point in face.points
                ]
            )
            if component is None:
                shade = face.shade
                base = BOARD_TOP if shade > 0.9 else BOARD_SIDE
                painter.setBrush(QBrush(base.darker(int(100 - face.shade * 70))))
                painter.setPen(QPen(EDGE_COLOR, 0.8))
            else:
                selected = component.id == self._selected_id
                hovered = component.id == self._hover_id
                rgb = shaded(color, face.shade, selected=selected)
                brush = QBrush(QColor(*rgb))
                if hovered:
                    brush = QBrush(QColor(*rgb).lighter(140))
                painter.setBrush(brush)
                painter.setPen(
                    QPen(SELECT_COLOR if selected else QColor(10, 18, 28, 170), 1.0 if selected else 0.6)
                )
            painter.drawPolygon(polygon)

            if component is not None and component.id not in projected_ids:
                projected_ids.add(component.id)
                rect = polygon.boundingRect()
                depth_value = camera.transform(
                    Vec3(component.pos_x or 0, component.pos_y or 0, component.pos_z or 0)
                )[2]
                self._projected.append((component, rect, depth_value))

        self._paint_highlight(painter, width, height)
        if self._show_labels:
            self._paint_labels(painter, width, height)
        self._paint_overlay(painter)
        painter.end()

    def _face_depth(self, face) -> float:
        sx = sum(point.x for point in face.points) / 4
        sy = sum(point.y for point in face.points) / 4
        sz = sum(point.z for point in face.points) / 4
        return self._camera.transform(Vec3(sx, sy, sz))[2]

    def _paint_highlight(self, painter: QPainter, width: float, height: float) -> None:
        for component, rect, _depth in self._projected:
            if component.id not in (self._selected_id, self._hover_id):
                continue
            color = SELECT_COLOR if component.id == self._selected_id else HOVER_COLOR
            pen = QPen(color, 1.6, Qt.SolidLine)
            painter.setPen(pen)
            painter.setBrush(Qt.NoBrush)
            painter.drawRoundedRect(rect.adjusted(-3, -3, 3, 3), 2.0, 2.0)
            if component.id == self._selected_id:
                label = component.designator
                painter.setFont(self._label_font)
                metrics = QFontMetrics(self._label_font)
                text_rect = metrics.boundingRect(label)
                bubble = QRectF(
                    rect.center().x() - text_rect.width() / 2 - 6,
                    rect.top() - text_rect.height() - 10,
                    text_rect.width() + 12,
                    text_rect.height() + 6,
                )
                painter.setBrush(QBrush(QColor(13, 27, 48, 235)))
                painter.setPen(QPen(color, 1.0))
                painter.drawRoundedRect(bubble, 4, 4)
                painter.setPen(QPen(QColor("#e8f0fb")))
                painter.drawText(bubble, Qt.AlignCenter, label)

    def _paint_labels(self, painter: QPainter, width: float, height: float) -> None:
        painter.setFont(self._label_font)
        painter.setPen(QPen(QColor(190, 210, 235, 200)))
        shown = 0
        for component, rect, _depth in sorted(self._projected, key=lambda item: item[2]):
            if shown > 60 or rect.width() < 14 or rect.height() < 8:
                continue
            if component.id in (self._selected_id, self._hover_id):
                continue
            painter.drawText(rect, Qt.AlignCenter, component.designator)
            shown += 1

    def _paint_overlay(self, painter: QPainter) -> None:
        painter.setFont(self._hint_font)
        hint = "ЛКМ — вращение · ПКМ — панорама · колесо — зум · F — сброс"
        painter.setPen(QPen(QColor(120, 150, 185, 190)))
        painter.drawText(12, self.height() - 12, hint)
        side = "верхняя сторона" if math.cos(math.radians(self._camera.pitch)) >= 0 else "нижняя сторона"
        painter.setPen(QPen(QColor(90, 120, 155, 190)))
        painter.drawText(
            QRectF(0, 8, self.width() - 12, 18),
            Qt.AlignRight | Qt.AlignVCenter,
            f"{len(self._projected)} комп. · {side}",
        )

    def _paint_placeholder(self, painter: QPainter) -> None:
        painter.setPen(QPen(QColor("#8fb0d8")))
        font = QFont(self.font())
        font.setPointSizeF(self.font().pointSizeF() + 2)
        painter.setFont(font)
        text = (
            "3D-данные для этой платы не загружены"
            if self._scene
            else "Плата не выбрана"
        )
        painter.drawText(self.rect(), Qt.AlignCenter, text)
        painter.setFont(self._hint_font)
        painter.setPen(QPen(QColor("#5f7fa6")))
        painter.drawText(
            self.rect().adjusted(0, 34, 0, 0),
            Qt.AlignCenter,
            "Импортируйте пакет BoardView (JSON) — см. документацию",
        )
