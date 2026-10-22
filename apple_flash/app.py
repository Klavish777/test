"""Точка входа CLI и запуск QApplication для Apple Flash Studio."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from apple_flash.services.context import StudioContext
from apple_flash.version import APP_NAME, APP_VERSION


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="apple-flash-studio",
        description=f"{APP_NAME} v{APP_VERSION} — перепрошивка и восстановление iPhone, iPad и MacBook на Windows",
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=None,
        help="Собственный каталог данных вместо %%LOCALAPPDATA%%\\AppleFlashStudio",
    )
    parser.add_argument(
        "--no-demo",
        action="store_true",
        help="Не устанавливать демонстрационные макеты .ipsw при первом запуске",
    )
    parser.add_argument(
        "--reset-demo",
        action="store_true",
        help="Пересоздать демонстрационные макеты .ipsw",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Проверить целостность базы SQLite и сервисов (без открытия окна) и завершиться с кодом 0/1",
    )
    parser.add_argument(
        "--export-ico",
        type=Path,
        default=None,
        help="Сгенерировать многоразмерный файл иконки Windows (.ico) по указанному пути и выйти",
    )
    parser.add_argument(
        "--screenshot",
        type=Path,
        default=None,
        help="Сохранить PNG-снимки всех страниц интерфейса в указанный каталог и выйти",
    )
    parser.add_argument("--verbose", action="store_true", help="Подробное логирование")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.check:
        ctx = StudioContext.create(
            args.data_dir,
            seed_demo=not args.no_demo,
            verbose=args.verbose,
        )
        ok = ctx.store.integrity_ok()
        ctx.close()
        return 0 if ok else 1

    from PySide6.QtWidgets import QApplication

    from apple_flash.ui.icon_gen import write_windows_ico
    from apple_flash.ui.main_window import AppleFlashMainWindow
    from apple_flash.ui.screenshot import capture_studio_screenshots
    from apple_flash.ui.theme import apply_studio_theme

    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(APP_VERSION)
    apply_studio_theme(app)

    if args.export_ico:
        write_windows_ico(args.export_ico)
        return 0

    ctx = StudioContext.create(
        args.data_dir,
        seed_demo=not args.no_demo,
        verbose=args.verbose,
    )
    if args.reset_demo:
        ctx.install_demo_mockups()

    window = AppleFlashMainWindow(ctx)
    if args.screenshot:
        window.show()
        return capture_studio_screenshots(app, window, args.screenshot)

    window.show()
    return int(app.exec())


if __name__ == "__main__":
    raise SystemExit(main())
