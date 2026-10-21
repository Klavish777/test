"""Точка входа Smartphone Repair OS.

Запуск:
    python main.py                 # обычный запуск (Windows/Linux/macOS)
    python main.py --no-demo       # пустая база без демонстрационных записей
    python main.py --data-dir DIR  # собственный каталог данных

Служебные ключи (для разработки и проверки интерфейса):
    --screenshot DIR               # отрисовать страницы в PNG и выйти
    --check                        # проверить базу и выйти с кодом 0/1
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from repair_os.core.i18n import set_language
from repair_os.core.logging_setup import install_exception_hook, setup_logging
from repair_os.core.paths import build_paths
from repair_os.services.context import AppContext
from repair_os.version import APP_NAME, APP_VERSION, SCHEMA_VERSION_EXPECTED

log = logging.getLogger(__name__)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="smartphone-repair-os", description=APP_NAME)
    parser.add_argument("--data-dir", help="Каталог данных (по умолчанию — профиль пользователя)")
    parser.add_argument("--no-demo", action="store_true", help="Не загружать демонстрационные данные")
    parser.add_argument("--reset-demo", action="store_true", help="Перезалить демонстрационные данные")
    parser.add_argument("--language", choices=["ru", "en"], help="Язык интерфейса на этот запуск")
    parser.add_argument("--screenshot", metavar="DIR", help="Сохранить снимки страниц и выйти")
    parser.add_argument("--check", action="store_true", help="Проверить базу и выйти")
    parser.add_argument("--version", action="version", version=f"{APP_NAME} {APP_VERSION}")
    return parser


def create_context(args: argparse.Namespace) -> AppContext:
    paths = build_paths(args.data_dir)
    setup_logging(paths.logs_dir)
    install_exception_hook()
    context = AppContext.create(paths.root, seed_demo=not args.no_demo)
    if args.reset_demo and not args.no_demo:
        context.seeder.seed(force=True)
    language = args.language or context.settings.get("language") or "ru"
    set_language(str(language))
    return context


def run_check(context: AppContext) -> int:
    ok = context.db.integrity_check()
    print("Каталог данных:", context.paths.root)
    print("База:", context.paths.database)
    schema = context.db.schema_version()
    schema_ok = schema == SCHEMA_VERSION_EXPECTED
    print("Схема:", schema, "(ожидалась %d)" % SCHEMA_VERSION_EXPECTED)
    print("Целостность:", "ok" if ok else "FAILED")
    if not schema_ok:
        print("ВНИМАНИЕ: версия схемы не совпадает с ожидаемой приложением")
    for table in (
        "brands",
        "devices",
        "device_variants",
        "firmware",
        "firmware_sources",
        "board_models",
        "board_components",
        "technical_documents",
        "component_references",
        "repair_notes",
        "favorites",
        "recent_devices",
        "app_settings",
    ):
        print(f"  {table}: {context.db.table_count(table)}")
    return 0 if ok and schema_ok else 1


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    from PySide6.QtWidgets import QApplication

    from repair_os.ui.main_window import MainWindow
    from repair_os.ui.theme import apply_theme

    app = QApplication(sys.argv[:1])
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(APP_VERSION)
    app.setOrganizationName("Smartphone Repair OS")
    apply_theme(app)

    context = create_context(args)

    if args.check:
        return run_check(context)

    window = MainWindow(context)
    saved_geometry = context.settings.get("window_geometry")
    if isinstance(saved_geometry, str) and saved_geometry:
        try:
            window.restoreGeometry(bytes.fromhex(saved_geometry))
        except ValueError:
            log.warning("Некорректная сохранённая геометрия окна")
    window.show()

    if args.screenshot:
        from repair_os.ui.screenshot import capture_pages

        return capture_pages(app, window, Path(args.screenshot))

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
