"""Программная генерация фирменной иконки Apple Flash Studio (QIcon + Windows .ico)."""

from __future__ import annotations

import struct
from pathlib import Path

from PySide6.QtCore import QBuffer, QIODevice, QPointF, QRectF, Qt
from PySide6.QtGui import (
    QColor,
    QIcon,
    QImage,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
)


def render_app_image(size: int = 256) -> QImage:
    """Рисует векторную иконку приложения (скруглённый графитовый значок с молнией прошивки USB/IPSW)."""
    img = QImage(size, size, QImage.Format_ARGB32_Premultiplied)
    img.fill(Qt.transparent)

    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing, True)

    pad = size * 0.06
    rect = QRectF(pad, pad, size - 2 * pad, size - 2 * pad)
    radius = size * 0.23

    # Градиент корпуса в стиле macOS / Windows 11 Studio
    bg_grad = QLinearGradient(rect.topLeft(), rect.bottomRight())
    bg_grad.setColorAt(0.0, QColor("#18263e"))
    bg_grad.setColorAt(0.55, QColor("#0d1526"))
    bg_grad.setColorAt(1.0, QColor("#090d16"))

    p.setPen(QPen(QColor("#2c4a78"), max(1.5, size * 0.018)))
    p.setBrush(bg_grad)
    p.drawRoundedRect(rect, radius, radius)

    # Контур микросхемы Apple Silicon внутри
    chip_margin = size * 0.24
    chip_rect = QRectF(chip_margin, chip_margin, size - 2 * chip_margin, size - 2 * chip_margin)
    chip_pen = QPen(QColor(10, 132, 255, 110), max(1.2, size * 0.02))
    p.setPen(chip_pen)
    p.setBrush(QColor(10, 132, 255, 26))
    p.drawRoundedRect(chip_rect, size * 0.10, size * 0.10)

    # Яркая молния перепрошивки (Electric Blue -> Cyan)
    bolt = QPainterPath()
    cx, cy = size * 0.5, size * 0.5
    s = size * 0.30
    bolt.moveTo(QPointF(cx + s * 0.14, cy - s * 0.92))
    bolt.lineTo(QPointF(cx - s * 0.56, cy + s * 0.08))
    bolt.lineTo(QPointF(cx - s * 0.04, cy + s * 0.08))
    bolt.lineTo(QPointF(cx - s * 0.18, cy + s * 0.92))
    bolt.lineTo(QPointF(cx + s * 0.56, cy - s * 0.08))
    bolt.lineTo(QPointF(cx + s * 0.04, cy - s * 0.08))
    bolt.closeSubpath()

    bolt_grad = QLinearGradient(QPointF(cx, cy - s), QPointF(cx, cy + s))
    bolt_grad.setColorAt(0.0, QColor("#64d2ff"))
    bolt_grad.setColorAt(1.0, QColor("#0a84ff"))

    p.setPen(QPen(QColor("#b8ecff"), max(1.0, size * 0.012)))
    p.setBrush(bolt_grad)
    p.drawPath(bolt)

    p.end()
    return img


def build_app_icon() -> QIcon:
    icon = QIcon()
    for sz in (16, 24, 32, 48, 64, 128, 256):
        icon.addPixmap(QPixmap.fromImage(render_app_image(sz)))
    return icon


def write_windows_ico(target: Path) -> Path:
    """Записывает многоразмерный файл .ico (PNG-in-ICO, стандарт Windows Vista/10/11) для PyInstaller и Inno Setup."""
    target.parent.mkdir(parents=True, exist_ok=True)
    sizes = (16, 32, 48, 64, 256)
    png_blobs: list[tuple[int, bytes]] = []
    for sz in sizes:
        img = render_app_image(sz)
        buf = QBuffer()
        buf.open(QIODevice.WriteOnly)
        img.save(buf, "PNG")
        png_blobs.append((sz, bytes(buf.data())))

    header = struct.pack("<HHH", 0, 1, len(png_blobs))
    entries = bytearray()
    payload = bytearray()
    offset = 6 + 16 * len(png_blobs)

    for sz, data in png_blobs:
        dim = 0 if sz >= 256 else sz
        entries.extend(
            struct.pack(
                "<BBBBHHII",
                dim,
                dim,
                0,
                0,
                1,
                32,
                len(data),
                offset,
            )
        )
        payload.extend(data)
        offset += len(data)

    target.write_bytes(bytes(header) + bytes(entries) + bytes(payload))
    return target
