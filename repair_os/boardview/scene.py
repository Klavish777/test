"""Минимальный программный 3D-движок для BoardView.

Почему собственный рендерер, а не Qt Quick 3D / WebEngine:
  * нет зависимости от GPU, драйверов и WebEngine (работает на любом ПК мастера,
    в том числе по RDP и в виртуальных машинах);
  * одинаково ведёт себя на Windows 10/11 и при запуске из исходников на Linux;
  * даёт полный контроль над выбором компонентов, подсветкой и слоями.

Рендеринг честный: вершины корпусов проецируются перспективной камерой,
грани сортируются по глубине (painter's algorithm) и рисуются QPainter-ом.
Это не фотография и не предварительно отрисованное изображение.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Iterable

from repair_os.data.models import BoardComponent, BoardModel


# --------------------------------------------------------------------------- векторы
@dataclass(frozen=True, slots=True)
class Vec3:
    x: float
    y: float
    z: float

    def __add__(self, other: "Vec3") -> "Vec3":
        return Vec3(self.x + other.x, self.y + other.y, self.z + other.z)

    def __sub__(self, other: "Vec3") -> "Vec3":
        return Vec3(self.x - other.x, self.y - other.y, self.z - other.z)

    def scaled(self, factor: float) -> "Vec3":
        return Vec3(self.x * factor, self.y * factor, self.z * factor)


@dataclass(frozen=True, slots=True)
class Face:
    points: tuple[Vec3, Vec3, Vec3, Vec3]
    shade: float
    kind: str  # "board" | "component" | "contact"


@dataclass
class RenderBox:
    component: BoardComponent
    center: Vec3
    size: Vec3
    color: tuple[int, int, int]
    label: str
    has_geometry: bool = True


@dataclass
class SceneData:
    board: BoardModel
    boxes: list[RenderBox] = field(default_factory=list)
    markers_only: list[BoardComponent] = field(default_factory=list)
    width: float = 70.0
    length: float = 140.0
    thickness: float = 1.0
    min_z: float = 0.0
    max_z: float = 0.0

    @property
    def has_3d(self) -> bool:
        return bool(self.boxes)


TYPE_COLORS: dict[str, tuple[int, int, int]] = {
    "ic": (58, 92, 140),
    "chip": (58, 92, 140),
    "capacitor": (150, 110, 60),
    "resistor": (110, 120, 130),
    "inductor": (140, 100, 120),
    "diode": (130, 90, 90),
    "connector": (170, 170, 175),
    "shield": (160, 165, 175),
    "testpoint": (200, 170, 70),
    "switch": (120, 150, 120),
    "crystal": (120, 130, 160),
}


def color_for_type(component_type: str | None) -> tuple[int, int, int]:
    key = (component_type or "").strip().lower()
    for name, color in TYPE_COLORS.items():
        if name in key:
            return color
    return (90, 105, 125)


def build_scene(model: BoardModel, components: Iterable[BoardComponent]) -> SceneData:
    width = float(model.width_mm or 70.0)
    length = float(model.length_mm or 140.0)
    thickness = float(model.thickness_mm or 1.0)
    scene = SceneData(board=model, width=width, length=length, thickness=thickness)
    for component in components:
        has_geometry = (
            component.pos_x is not None
            and component.pos_y is not None
            and (component.size_x or 0) > 0
            and (component.size_y or 0) > 0
        )
        if not has_geometry:
            scene.markers_only.append(component)
            continue
        size = Vec3(
            max(0.1, float(component.size_x or 0.5)),
            max(0.1, float(component.size_y or 0.4)),
            max(0.05, float(component.size_z or 0.3)),
        )
        z = component.pos_z
        if z is None:
            z = (thickness / 2 + size.z / 2) if component.side == "top" else -(thickness / 2 + size.z / 2)
        center = Vec3(float(component.pos_x or 0), float(component.pos_y or 0), float(z))
        scene.boxes.append(
            RenderBox(
                component=component,
                center=center,
                size=size,
                color=color_for_type(component.component_type),
                label=component.designator,
            )
        )
        scene.min_z = min(scene.min_z, center.z - size.z / 2)
        scene.max_z = max(scene.max_z, center.z + size.z / 2)
    return scene


def box_faces(center: Vec3, size: Vec3, rotation_deg: float = 0.0) -> list[Face]:
    """Возвращает 6 граней параллелепипеда с оценкой освещённости."""
    hx, hy, hz = size.x / 2, size.y / 2, size.z / 2
    corners = [
        Vec3(-hx, -hy, -hz),
        Vec3(hx, -hy, -hz),
        Vec3(hx, hy, -hz),
        Vec3(-hx, hy, -hz),
        Vec3(-hx, -hy, hz),
        Vec3(hx, -hy, hz),
        Vec3(hx, hy, hz),
        Vec3(-hx, hy, hz),
    ]
    if rotation_deg:
        angle = math.radians(rotation_deg)
        cos_a, sin_a = math.cos(angle), math.sin(angle)
        rotated = [
            Vec3(point.x * cos_a - point.y * sin_a, point.x * sin_a + point.y * cos_a, point.z)
            for point in corners
        ]
    else:
        rotated = corners
    world = [center + point for point in rotated]

    definitions = [
        ((0, 1, 2, 3), 0.55),  # низ
        ((4, 5, 6, 7), 1.0),  # верх
        ((0, 1, 5, 4), 0.75),  # -y
        ((2, 3, 7, 6), 0.65),  # +y
        ((1, 2, 6, 5), 0.85),  # +x
        ((3, 0, 4, 7), 0.6),  # -x
    ]
    return [
        Face(points=tuple(world[index] for index in indices), shade=shade, kind="component")
        for indices, shade in definitions
    ]


def board_faces(width: float, length: float, thickness: float) -> list[Face]:
    half_t = thickness / 2
    corners = [
        (0.0, 0.0),
        (width, 0.0),
        (width, length),
        (0.0, length),
    ]
    bottom = [Vec3(x, y, -half_t) for x, y in corners]
    top = [Vec3(x, y, half_t) for x, y in corners]
    faces = [
        Face(points=(bottom[0], bottom[1], bottom[2], bottom[3]), shade=0.35, kind="board"),
        Face(points=(top[0], top[1], top[2], top[3]), shade=1.0, kind="board"),
    ]
    for index in range(4):
        next_index = (index + 1) % 4
        faces.append(
            Face(
                points=(bottom[index], bottom[next_index], top[next_index], top[index]),
                shade=0.5,
                kind="board",
            )
        )
    return faces


# --------------------------------------------------------------------------- камера
@dataclass
class Camera:
    yaw: float = -35.0  # градусы, поворот вокруг Z
    pitch: float = 45.0  # градусы
    distance: float = 260.0
    target: Vec3 = field(default_factory=lambda: Vec3(35.0, 70.0, 0.0))
    focal: float = 1.32

    def copy(self) -> "Camera":
        return Camera(self.yaw, self.pitch, self.distance, self.target, self.focal)

    def rotate(self, dyaw: float, dpitch: float) -> None:
        self.yaw = (self.yaw + dyaw) % 360.0
        self.pitch = max(-89.0, min(89.0, self.pitch + dpitch))

    def zoom(self, factor: float, *, min_distance: float = 25.0, max_distance: float = 2000.0) -> None:
        self.distance = max(min_distance, min(max_distance, self.distance * factor))

    def pan(self, dx: float, dy: float) -> None:
        self.target = Vec3(self.target.x + dx, self.target.y + dy, self.target.z)

    def flip_side(self) -> None:
        self.yaw = (self.yaw + 180.0) % 360.0
        self.pitch = -self.pitch

    def reset(self) -> None:
        self.yaw = -35.0
        self.pitch = 45.0
        self.distance = 260.0

    def fit(self, width: float, length: float) -> None:
        self.target = Vec3(width / 2, length / 2, 0.0)
        self.distance = max(width, length) * 1.2 + 20.0

    # ------------------------------------------------------------------ проекция
    def transform(self, point: Vec3) -> tuple[float, float, float]:
        """Мировые координаты → координаты камеры (x, y, depth)."""
        x = point.x - self.target.x
        y = point.y - self.target.y
        z = point.z - self.target.z
        yaw = math.radians(self.yaw)
        cos_y, sin_y = math.cos(yaw), math.sin(yaw)
        x1 = x * cos_y - y * sin_y
        y1 = x * sin_y + y * cos_y
        pitch = math.radians(self.pitch)
        cos_p, sin_p = math.cos(pitch), math.sin(pitch)
        y2 = y1 * cos_p - z * sin_p
        z2 = y1 * sin_p + z * cos_p
        return x1, y2, z2 + self.distance

    def project(self, point: Vec3, viewport_w: float, viewport_h: float) -> tuple[float, float, float]:
        x1, y2, depth = self.transform(point)
        depth = max(1.0, depth)
        scale = self.focal * min(viewport_w, viewport_h)
        screen_x = viewport_w / 2 + (x1 / depth) * scale
        screen_y = viewport_h / 2 - (y2 / depth) * scale
        return screen_x, screen_y, depth


def shaded(color: tuple[int, int, int], shade: float, *, selected: bool = False) -> tuple[int, int, int]:
    if selected:
        base = (61, 139, 253)
        color = tuple(int(channel * 0.35 + base[i] * 0.65) for i, channel in enumerate(color))
    return tuple(max(0, min(255, int(channel * shade))) for channel in color)  # type: ignore[return-value]
