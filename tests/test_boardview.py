"""Тесты 3D BoardView: геометрия, камера, импорт/экспорт пакетов, метки."""

from __future__ import annotations

import json
import zipfile

import pytest

from repair_os.boardview.scene import Camera, Vec3, board_faces, box_faces, build_scene
from repair_os.core.errors import ImportErrorOS
from repair_os.data.models import BoardComponent, BoardModel
from repair_os.services.board_packages import (
    PACKAGE_FORMAT,
    PACKAGE_VERSION,
    read_package,
    summarize,
)


def _package(components, dimensions=None):
    return {
        "format": PACKAGE_FORMAT,
        "version": PACKAGE_VERSION,
        "board": {
            "name": "Test board",
            "board_code": "TB-1",
            "revision": "r1",
            "dimensions": dimensions or {"width": 60.0, "length": 120.0, "thickness": 1.0},
            "source": "unit-test",
        },
        "components": components,
        "annotations": [{"label": "Проверить питание", "component": "U1", "body": "тест"}],
    }


def _write(tmp_path, payload, name="board.json"):
    path = tmp_path / name
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return path


# --------------------------------------------------------------------------- камера
def test_camera_projection_and_controls():
    camera = Camera()
    camera.fit(60, 120)
    assert camera.target.x == pytest.approx(30)
    x, y, depth = camera.project(Vec3(30, 60, 0), 800, 600)
    assert 0 < x < 800 and 0 < y < 600
    assert depth > 0

    before = camera.copy()
    camera.rotate(30, 10)
    assert camera.yaw != before.yaw
    camera.zoom(0.5)
    assert camera.distance < before.distance
    camera.zoom(0.0001)
    assert camera.distance >= 25.0
    yaw_before_flip = camera.yaw
    camera.flip_side()
    assert camera.yaw == pytest.approx((yaw_before_flip + 180) % 360)
    camera.reset()
    assert camera.pitch == 45.0


def test_camera_zoom_limits():
    camera = Camera()
    camera.zoom(0.001)
    assert camera.distance == 25.0
    camera.zoom(1000)
    assert camera.distance == 2000.0


def test_board_and_box_faces():
    faces = board_faces(10, 20, 1)
    assert len(faces) == 6
    assert all(len(face.points) == 4 for face in faces)
    box = box_faces(Vec3(5, 5, 1), Vec3(2, 2, 1), rotation_deg=45)
    assert len(box) == 6
    top = [face for face in box if face.shade == 1.0][0]
    assert all(point.z == pytest.approx(1.5) for point in top.points)


# --------------------------------------------------------------------------- сцена
def test_build_scene_skips_components_without_geometry():
    model = BoardModel(id=1, name="B", width_mm=50, length_mm=100, thickness_mm=1)
    with_geometry = BoardComponent(
        id=1,
        board_model_id=1,
        designator="U1",
        side="top",
        component_type="IC",
        pos_x=10,
        pos_y=20,
        size_x=3,
        size_y=3,
        size_z=1,
    )
    without_geometry = BoardComponent(
        id=2, board_model_id=1, designator="C2", side="top", marker_u=0.5, marker_v=0.5
    )
    scene = build_scene(model, [with_geometry, without_geometry])
    assert len(scene.boxes) == 1
    assert len(scene.markers_only) == 1
    assert scene.markers_only[0].designator == "C2"
    assert scene.boxes[0].center.z > 0, "компонент верхней стороны должен быть над платой"


# --------------------------------------------------------------------------- пакеты
def test_import_package_creates_board(context, tmp_path):
    path = _write(
        tmp_path,
        _package(
            [
                {
                    "designator": "U1",
                    "side": "top",
                    "layer": "power",
                    "type": "IC",
                    "marking": "TEST1",
                    "purpose": "PMIC",
                    "position": {"x": 10, "y": 10, "z": 1},
                    "size": {"x": 3, "y": 3, "z": 1},
                    "marker": {"u": 0.2, "v": 0.3},
                },
                {
                    "designator": "C2",
                    "side": "bottom",
                    "layer": "power",
                    "type": "Capacitor",
                    "marker": {"u": 0.8, "v": 0.1},
                },
            ]
        ),
    )
    board = context.packages.import_package(path)
    assert board.has_3d == 1
    assert board.component_count == 2
    assert board.width_mm == 60.0
    assert board.package_checksum

    scene = context.packages.load_scene(board.id)
    assert len(scene["components"]) == 2
    assert "power" in scene["layers"]
    assert scene["annotations"][0]["label"] == "Проверить питание"


def test_import_package_validation(context, tmp_path):
    bad_format = _package([])
    bad_format["format"] = "something-else"
    with pytest.raises(ImportErrorOS):
        read_package(_write(tmp_path, bad_format, "bad_format.json"))

    bad_version = _package([])
    bad_version["version"] = 99
    with pytest.raises(ImportErrorOS):
        read_package(_write(tmp_path, bad_version, "bad_version.json"))

    with pytest.raises(ImportErrorOS):
        read_package(_write(tmp_path, {"components": []}, "no_board.json"))

    broken = tmp_path / "broken.json"
    broken.write_text("{", encoding="utf-8")
    with pytest.raises(ImportErrorOS):
        read_package(broken)

    wrong_ext = tmp_path / "board.brd"
    wrong_ext.write_text("{}", encoding="utf-8")
    with pytest.raises(ImportErrorOS):
        read_package(wrong_ext)


def test_summary_warns_about_missing_geometry(context, tmp_path):
    payload = _package([{"designator": "R1"}, {"side": "top"}])
    summary = summarize(payload)
    assert summary.components == 2
    assert summary.has_dimensions
    assert any("маркер" in warning for warning in summary.warnings)
    assert any("обозначения" in warning for warning in summary.warnings)


def test_export_and_roundtrip(context, tmp_path):
    source = _write(
        tmp_path,
        _package(
            [
                {
                    "designator": "U5",
                    "side": "top",
                    "type": "IC",
                    "position": {"x": 5, "y": 5, "z": 1},
                    "size": {"x": 2, "y": 2, "z": 0.5},
                    "marker": {"u": 0.5, "v": 0.5},
                }
            ]
        ),
    )
    board = context.packages.import_package(source)
    exported = context.packages.export_package(board.id, tmp_path / "exported.json")
    payload = json.loads(exported.read_text(encoding="utf-8"))
    assert payload["format"] == PACKAGE_FORMAT
    assert payload["components"][0]["designator"] == "U5"
    assert payload["components"][0]["position"]["x"] == 5

    reimported = context.packages.import_package(exported)
    assert reimported.component_count == 1


def test_import_zip_package(context, tmp_path):
    payload = _package([])
    archive = tmp_path / "board.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("board.json", json.dumps(payload, ensure_ascii=False))
    board = context.packages.import_zip(archive)
    assert board.board_code == "TB-1"


def test_annotations_and_search_in_board(context):
    board = context.boards.list_models()[0]
    before = len(context.boards.annotations(board.id))
    context.boards.add_annotation(board.id, "Тест", body="Проверить U1201")
    assert len(context.boards.annotations(board.id)) == before + 1
    assert context.boards.components(board.id, search="U1201")


def test_demo_board_is_marked_demo(context):
    board = context.boards.list_models()[0]
    assert board.is_demo == 1
    assert "ДЕМО" in board.name
    components = context.boards.components(board.id)
    assert components and all(component.is_demo for component in components)
    assert any("условн" in (component.notes or "").lower() for component in components)
