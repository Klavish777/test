"""Дымовые тесты интерфейса (Qt offscreen): окно, страницы, диалоги."""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

PySide6 = pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication  # noqa: E402

from repair_os.ui.theme import apply_theme  # noqa: E402


@pytest.fixture(scope="module")
def app():
    application = QApplication.instance() or QApplication([])
    apply_theme(application)
    yield application


@pytest.fixture()
def window(app, context):
    from repair_os.ui.main_window import MainWindow

    win = MainWindow(context)
    win.resize(1400, 900)
    win.show()
    app.processEvents()
    yield win
    win.close()
    app.processEvents()


def test_main_window_navigation(app, window):
    for key in ("home", "catalog", "boardview", "firmware", "library", "settings"):
        window.navigate(key)
        app.processEvents()
        assert window.stack.currentWidget() is window.pages[key]
    window.navigate("search")
    window.show_search("SM-G991B")
    app.processEvents()
    assert window.search_page.query == "SM-G991B"


def test_open_device_and_board(app, window):
    device = window.context.devices.find_by_model_code("SM-A525F")
    window.open_device(device.id)
    app.processEvents()
    assert window.device_page.device.id == device.id

    window.navigate("boardview")
    app.processEvents()
    assert window.board_page.board is not None
    scene = window.board_page.viewer_3d.scene()
    assert scene is not None and scene.boxes


def test_viewer_selection_and_layers(app, window):
    window.navigate("boardview")
    app.processEvents()
    page = window.board_page
    component = next((box.component for box in page.viewer_3d.scene().boxes if box.component.layer), None)
    assert component is not None
    page._select_component(component)
    app.processEvents()
    assert page.viewer_3d.selected_component() is component
    assert page.selected.id == component.id

    page.viewer_3d.set_hidden_layers([component.layer])
    assert component.layer in page.viewer_3d.hidden_layers()
    page.viewer_3d.set_hidden_layers([])
    page.viewer_3d.flip_side()
    page.viewer_3d.reset_view()


def test_device_editor_dialog(app, window):
    from repair_os.ui.dialogs.device_editor import DeviceEditorDialog

    dialog = DeviceEditorDialog(window.context, parent=window)
    dialog.name.setText("Новый аппарат")
    dialog.model_code.setText("SM-NEW-001")
    dialog._on_accept()
    app.processEvents()
    saved = window.context.devices.find_by_model_code("SM-NEW-001")
    assert saved and saved.name == "Новый аппарат"


def test_device_editor_validates(app, window):
    from repair_os.ui.dialogs.device_editor import DeviceEditorDialog

    dialog = DeviceEditorDialog(window.context, parent=window)
    dialog.name.setText("")
    dialog._on_accept()
    app.processEvents()
    assert dialog.result() != dialog.DialogCode.Accepted
    assert dialog._error.text(), "должно показываться сообщение об ошибке"


def test_firmware_page_filters(app, window):
    window.navigate("firmware")
    app.processEvents()
    page = window.firmware_page
    assert page.model.rows
    page.search.setText("oriole")
    app.processEvents()
    assert len(page.model.rows) == 1
    page.search.setText("")
    app.processEvents()
    assert len(page.model.rows) >= 5


def test_library_page_selection(app, window):
    window.navigate("library")
    app.processEvents()
    page = window.library_page
    assert page.model.rows
    page.table.selectRow(0)
    app.processEvents()
    assert page._selected is not None


def test_catalog_filters(app, window):
    window.navigate("catalog")
    app.processEvents()
    page = window.catalog_page
    assert page.model.rows
    page.search.setText("iphone")
    app.processEvents()
    assert all("iphone" in (row.name or "").lower() for row in page.model.rows)
    page.search.setText("")
    app.processEvents()


def test_home_cards_render(app, window):
    window.navigate("home")
    app.processEvents()
    assert window.home_page.stat_devices._value.text() != "—"


def test_i18n_catalog(app):
    from repair_os.core.i18n import available_languages, current_language, set_language, tr

    assert "ru" in available_languages()
    assert tr("nav.home") == "Главная"
    assert tr("missing.key", default="Резерв") == "Резерв"
    set_language("en")
    assert tr("nav.home") == "Home"
    set_language(current_language() if current_language() == "ru" else "ru")
    assert tr("nav.home") == "Главная"
