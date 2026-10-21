"""Просмотрщик фотографий платы с интерактивными метками.

Используется, когда 3D-модели нет или когда нужно сопоставить компонент с фото.
Масштаб/панорама/выбор метки — полностью интерактивны, координаты меток берутся
из базы (``marker_u``/``marker_v``), а не вычисляются «на глаз».
"""

from __future__ import annotations

import logging

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import (
    QColor,
    QFont,
    QMouseEvent,
    QPainter,
    QPen,
    QPixmap,
    QWheelEvent,
)
from PySide6.QtWidgets import QSizePolicy, QWidget

from repair_os.data.models import BoardComponent

log = logging.getLogger(__name__)

SIDE_COLORS = {"top": QColor("#3d8bfd"), "bottom": QColor("#f0a35e")}


class BoardPhotoView(QWidget):
    componentSelected = Signal(object)
    componentActivated = Signal(object)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumSize(240, 180)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setMouseTracking(True)
        self._pixmap: QPixmap | None = None
        self._components: list[BoardComponent] = []
        self._selected_id: int | None = None
        self._hover_id: int | None = None
        self._zoom = 1.0
        self._offset = QPointF(0, 0)
        self._drag_origin: QPointF | None = None
        self._drag_offset = QPointF(0, 0)
        self._show_labels = True

    # ------------------------------------------------------------------ данные
    def set_photo(self, path: str | None, *, components: list[BoardComponent] | None = None) -> None:
        self._pixmap = None
        if path:
            pixmap = QPixmap(path)
            if pixmap.isNull():
                log.warning("Не удалось загрузить фото платы: %s", path)
            else:
                self._pixmap = pixmap
        if components is not None:
            self._components = [c for c in components if c.marker_u is not None and c.marker_v is not None]
        self.reset_view()

    def set_components(self, components: list[BoardComponent]) -> None:
        self._components = [c for c in components if c.marker_u is not None and c.marker_v is not None]
        self.update()

    def markers_count(self) -> int:
        return len(self._components)

    def has_photo(self) -> bool:
        return self._pixmap is not None

    def set_selected_component(self, component_id: int | None) -> None:
        self._selected_id = component_id
        self.update()

    def set_show_labels(self, enabled: bool) -> None:
        self._show_labels = enabled
        self.update()

    def reset_view(self) -> None:
        self._zoom = 1.0
        self._offset = QPointF(0, 0)
        self.update()

    # ------------------------------------------------------------------ геометрия
    def _image_rect(self) -> QRectF:
        if self._pixmap is None:
            return QRectF()
        widget_w, widget_h = self.width(), self.height()
        pixmap_w, pixmap_h = self._pixmap.width(), self._pixmap.height()
        base_scale = min(widget_w / pixmap_w, widget_h / pixmap_h)
        scale = base_scale * self._zoom
        width = pixmap_w * scale
        height = pixmap_h * scale
        left = (widget_w - width) / 2 + self._offset.x()
        top = (widget_h - height) / 2 + self._offset.y()
        return QRectF(left, top, width, height)

    def _marker_position(self, component: BoardComponent) -> QPointF:
        rect = self._image_rect()
        return QPointF(
            rect.left() + rect.width() * float(component.marker_u or 0),
            rect.top() + rect.height() * float(component.marker_v or 0),
        )

    # ------------------------------------------------------------------ события
    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.LeftButton:
            self._drag_origin = event.position()
            self._drag_offset = QPointF(self._offset)
            component = self._pick(event.position())
            self._selected_id = component.id if component else None
            self.componentSelected.emit(component)
            self.update()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._drag_origin is not None:
            delta = event.position() - self._drag_origin
            if abs(delta.x()) > 3 or abs(delta.y()) > 3:
                self._offset = self._drag_offset + delta
                self.update()
            return
        component = self._pick(event.position())
        hover_id = component.id if component else None
        if hover_id != self._hover_id:
            self._hover_id = hover_id
            self.update()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        self._drag_origin = None
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        component = self._pick(event.position())
        if component:
            self.componentActivated.emit(component)
        super().mouseDoubleClickEvent(event)

    def wheelEvent(self, event: QWheelEvent) -> None:
        steps = event.angleDelta().y() / 120.0
        if steps:
            self._zoom = max(0.2, min(12.0, self._zoom * (1.15 ** steps)))
            self.update()
        event.accept()

    def _pick(self, position: QPointF) -> BoardComponent | None:
        if self._pixmap is None:
            return None
        best: tuple[float, BoardComponent] | None = None
        for component in self._components:
            point = self._marker_position(component)
            distance = (point - position).manhattanLength()
            if distance <= 9 and (best is None or distance < best[0]):
                best = (distance, component)
        return best[1] if best else None

    # ------------------------------------------------------------------ отрисовка
    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.fillRect(self.rect(), QColor("#0b1626"))

        if self._pixmap is None:
            painter.setPen(QPen(QColor("#8fb0d8")))
            font = QFont(self.font())
            font.setPointSizeF(font.pointSizeF() + 1.5)
            painter.setFont(font)
            painter.drawText(self.rect(), Qt.AlignCenter, "Фотография платы не загружена")
            painter.setFont(self.font())
            painter.setPen(QPen(QColor("#5f7fa6")))
            painter.drawText(
                self.rect().adjusted(0, 32, 0, 0),
                Qt.AlignCenter,
                "Добавьте фото в карточку платы или импортируйте пакет с изображениями",
            )
            painter.end()
            return

        rect = self._image_rect()
        painter.drawPixmap(rect, self._pixmap, QRectF(self._pixmap.rect()))
        painter.setPen(QPen(QColor(40, 62, 90), 1.0))
        painter.setBrush(Qt.NoBrush)
        painter.drawRect(rect)

        label_font = QFont(self.font())
        label_font.setPointSizeF(max(6.5, self.font().pointSizeF() - 1.0))
        for component in self._components:
            point = self._marker_position(component)
            if not rect.contains(point):
                continue
            selected = component.id == self._selected_id
            hovered = component.id == self._hover_id
            color = SIDE_COLORS.get(component.side, QColor("#3d8bfd"))
            radius = 5.0 if selected else (4.0 if hovered else 2.6)
            painter.setPen(QPen(QColor(8, 16, 28, 220), 1.0))
            painter.setBrush(color.lighter(115) if selected or hovered else color)
            painter.drawEllipse(point, radius, radius)
            if selected or hovered or (self._show_labels and self._zoom > 1.6):
                label = component.designator
                painter.setFont(label_font)
                metrics = painter.fontMetrics()
                text_rect = metrics.boundingRect(label)
                bubble = QRectF(
                    point.x() + 7,
                    point.y() - text_rect.height() / 2 - 3,
                    text_rect.width() + 10,
                    text_rect.height() + 6,
                )
                painter.setBrush(QColor(10, 22, 38, 235))
                painter.setPen(QPen(color, 1.0))
                painter.drawRoundedRect(bubble, 4, 4)
                painter.setPen(QPen(QColor("#e8f0fb")))
                painter.drawText(bubble, Qt.AlignCenter, label)

        painter.setPen(QPen(QColor(110, 140, 175, 190)))
        painter.drawText(
            12,
            self.height() - 12,
            f"фото платы · масштаб {self._zoom * 100:.0f}% · меток {len(self._components)}",
        )
        painter.end()
