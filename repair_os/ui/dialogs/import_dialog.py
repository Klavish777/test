"""Импорт данных: CSV/JSON (устройства, прошивки, материалы) и пакеты BoardView."""

from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
)

from repair_os.core.errors import RepairOSError
from repair_os.services.board_packages import read_package, summarize
from repair_os.services.context import AppContext
from repair_os.services.import_export import ImportReport, write_template
from repair_os.ui.dialogs.base import ReportDialog, error, info
from repair_os.ui.widgets import muted, title

log = logging.getLogger(__name__)

KIND_LABELS = {
    "devices": "Устройства",
    "firmware": "Прошивки",
    "documents": "Материалы библиотеки",
}


class ImportDialog(QDialog):
    def __init__(self, context: AppContext, *, kind: str = "devices", parent=None) -> None:
        super().__init__(parent)
        self.context = context
        self.kind = kind
        self.setWindowTitle(f"Импорт: {KIND_LABELS.get(kind, kind)}")
        self.resize(660, 440)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 16)
        layout.setSpacing(10)
        layout.addWidget(title(f"Импорт: {KIND_LABELS.get(kind, kind)}", object_name="PageTitle"))
        layout.addWidget(
            muted(
                "Поддерживаются CSV (UTF-8/Windows-1251, разделитель «;» или «,») и JSON. "
                "Сначала выполняется проверка, затем запись. Дубликаты обновляются, а не дублируются."
            )
        )

        file_row = QHBoxLayout()
        self.path_edit = QLineEdit(self)
        self.path_edit.setPlaceholderText("Путь к файлу CSV/JSON")
        browse = QPushButton("Выбрать…", self)
        browse.clicked.connect(self._browse)
        template = QPushButton("Скачать шаблон", self)
        template.setObjectName("Ghost")
        template.clicked.connect(self._save_template)
        file_row.addWidget(self.path_edit, 1)
        file_row.addWidget(browse)
        file_row.addWidget(template)
        layout.addLayout(file_row)

        self.create_brands = QCheckBox("Создавать отсутствующие бренды", self)
        self.create_brands.setChecked(True)
        if kind == "devices":
            layout.addWidget(self.create_brands)

        self.preview = QLabel("Проверка ещё не выполнялась.", self)
        self.preview.setObjectName("Muted")
        self.preview.setWordWrap(True)
        layout.addWidget(self.preview)
        layout.addStretch(1)

        buttons = QHBoxLayout()
        self.check_button = QPushButton("Проверить", self)
        self.check_button.setObjectName("Ghost")
        self.check_button.clicked.connect(lambda: self._run(dry_run=True))
        self.import_button = QPushButton("Импортировать", self)
        self.import_button.setObjectName("Primary")
        self.import_button.clicked.connect(lambda: self._run(dry_run=False))
        close = QPushButton("Закрыть", self)
        close.setObjectName("Ghost")
        close.clicked.connect(self.reject)
        buttons.addWidget(self.check_button)
        buttons.addWidget(self.import_button)
        buttons.addStretch(1)
        buttons.addWidget(close)
        layout.addLayout(buttons)

    def _browse(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Выберите файл", "", "Таблицы и JSON (*.csv *.json);;Все файлы (*.*)"
        )
        if path:
            self.path_edit.setText(path)

    def _save_template(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "Сохранить шаблон", f"{self.kind}_template.csv", "CSV (*.csv)"
        )
        if not path:
            return
        try:
            target = write_template(self.kind, Path(path))
        except Exception as exc:
            error(self, "Ошибка", str(exc))
            return
        info(self, "Шаблон сохранён", f"{target}\n\nЗаполните файл и повторите импорт.")

    def _run(self, *, dry_run: bool) -> None:
        path = self.path_edit.text().strip()
        if not path:
            error(self, "Файл не выбран", "Укажите путь к CSV или JSON.")
            return
        try:
            if self.kind == "devices":
                report = self.context.imports.import_devices(
                    path, dry_run=dry_run, create_brands=self.create_brands.isChecked()
                )
            elif self.kind == "firmware":
                report = self.context.imports.import_firmware(path, dry_run=dry_run)
            else:
                report = self.context.imports.import_documents(path, dry_run=dry_run)
        except RepairOSError as exc:
            error(self, "Импорт не выполнен", str(exc))
            return
        except Exception as exc:  # pragma: no cover
            log.exception("Ошибка импорта")
            error(self, "Импорт не выполнен", str(exc))
            return

        self._show_report(report)
        if dry_run:
            self.preview.setText(
                f"Проверка: строк {report.total}, ошибок {len(report.errors)}. "
                "Если ошибок нет — нажмите «Импортировать»."
            )
        else:
            self.preview.setText(report.summary())
            if report.ok:
                self.accept()

    def _show_report(self, report: ImportReport) -> None:
        lines = [
            f"Строка {issue.row}: {issue.message}"
            + ("  [предупреждение]" if issue.severity == "warning" else "")
            for issue in report.issues
        ]
        ReportDialog(
            "Отчёт импорта",
            report.summary() + ("\nПроверка не изменила базу." if report.dry_run else ""),
            lines,
            self,
        ).exec()


class BoardImportDialog(QDialog):
    def __init__(self, context: AppContext, parent=None) -> None:
        super().__init__(parent)
        self.context = context
        self.imported_board_id: int | None = None
        self.setWindowTitle("Импорт пакета BoardView")
        self.resize(700, 500)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 16)
        layout.setSpacing(10)
        layout.addWidget(title("Импорт платы BoardView", object_name="PageTitle"))
        layout.addWidget(
            muted(
                "Поддерживается JSON-пакет формата smartphone-repair-os-board v1 и ZIP с пакетом "
                "и изображениями. Приложение не генерирует геометрию: если в пакете нет координат "
                "и размеров, компоненты будут доступны только как метки."
            )
        )

        device_row = QHBoxLayout()
        device_row.addWidget(QLabel("Устройство", self))
        self.device_combo = QComboBox(self)
        self.device_combo.addItem("— без привязки —", None)
        for device in context.devices.list(limit=2000):
            self.device_combo.addItem(
                f"{device.brand_name} {device.name} · {device.model_code}", device.id
            )
        device_row.addWidget(self.device_combo, 1)
        layout.addLayout(device_row)

        file_row = QHBoxLayout()
        self.path_edit = QLineEdit(self)
        self.path_edit.setPlaceholderText("Путь к .json или .zip")
        browse = QPushButton("Выбрать…", self)
        browse.clicked.connect(self._browse)
        file_row.addWidget(self.path_edit, 1)
        file_row.addWidget(browse)
        layout.addLayout(file_row)

        self.existing_combo = QComboBox(self)
        self.existing_combo.addItem("— создать новую плату —", None)
        for board in context.boards.list_models(limit=500):
            self.existing_combo.addItem(
                f"Заменить: {board.name} · {board.board_code or 'без кода'}", board.id
            )
        layout.addWidget(self.existing_combo)

        self.summary_label = QLabel("Файл не проверен.", self)
        self.summary_label.setObjectName("Muted")
        self.summary_label.setWordWrap(True)
        layout.addWidget(self.summary_label)
        layout.addStretch(1)

        buttons = QHBoxLayout()
        check = QPushButton("Проверить файл", self)
        check.setObjectName("Ghost")
        check.clicked.connect(self._inspect)
        self.import_button = QPushButton("Импортировать", self)
        self.import_button.setObjectName("Primary")
        self.import_button.clicked.connect(self._import)
        cancel = QPushButton("Отмена", self)
        cancel.setObjectName("Ghost")
        cancel.clicked.connect(self.reject)
        buttons.addWidget(check)
        buttons.addWidget(self.import_button)
        buttons.addStretch(1)
        buttons.addWidget(cancel)
        layout.addLayout(buttons)

    def _browse(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Выберите пакет платы", "", "Пакеты BoardView (*.json *.zip)"
        )
        if path:
            self.path_edit.setText(path)
            self._inspect()

    def _inspect(self) -> None:
        path = Path(self.path_edit.text().strip())
        if not path.exists():
            self.summary_label.setText("Файл не найден.")
            return
        try:
            if path.suffix.lower() == ".zip":
                from repair_os.core.security import safe_extract_zip

                tmp = self.context.paths.cache_dir / "board_inspect"
                files = safe_extract_zip(path, tmp)
                json_files = [item for item in files if item.suffix.lower() == ".json"]
                if not json_files:
                    raise RepairOSError("В архиве нет JSON-пакета платы")
                payload = read_package(json_files[0])
            else:
                payload = read_package(path)
            summary = summarize(payload)
        except RepairOSError as exc:
            self.summary_label.setText(f"Ошибка: {exc}")
            return
        except Exception as exc:  # pragma: no cover
            self.summary_label.setText(f"Ошибка чтения пакета: {exc}")
            return
        lines = [
            f"Плата: {summary.name}",
            f"Код: {summary.board_code or '—'} · компонентов: {summary.components} · "
            f"меток: {summary.annotations}",
            f"Стороны: {', '.join(summary.sides) or '—'} · "
            f"размеры: {'заданы' if summary.has_dimensions else 'не заданы'}",
        ]
        if summary.warnings:
            lines.append("Предупреждения:")
            lines.extend(f"• {warning}" for warning in summary.warnings[:15])
        self.summary_label.setText("\n".join(lines))

    def _import(self) -> None:
        path = Path(self.path_edit.text().strip())
        if not path.exists():
            error(self, "Файл не найден", "Укажите существующий JSON или ZIP.")
            return
        device_id = self.device_combo.currentData()
        replace_id = self.existing_combo.currentData()
        try:
            if path.suffix.lower() == ".zip":
                board = self.context.packages.import_zip(path, device_id=device_id)
            else:
                board = self.context.packages.import_package(
                    path, device_id=device_id, replace_board_id=replace_id
                )
        except RepairOSError as exc:
            error(self, "Импорт не выполнен", str(exc))
            return
        except Exception as exc:  # pragma: no cover
            log.exception("Ошибка импорта платы")
            error(self, "Импорт не выполнен", str(exc))
            return
        self.imported_board_id = board.id
        info(
            self,
            "Плата импортирована",
            f"{board.name}\nКомпонентов: {board.component_count}\n"
            f"{'3D-данные загружены' if board.has_3d else '3D-данных нет — только метки'}",
        )
        self.accept()
