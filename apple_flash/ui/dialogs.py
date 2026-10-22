"""Модальные диалоги подтверждения опасных операций (Clean Restore) и детального просмотра IPSW."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from apple_flash.core.security import human_bytes
from apple_flash.data.apple_catalog import CHIP_BY_CPID, resolve_product_name
from apple_flash.data.models import IpswManifestInfo
from apple_flash.ui.widgets import make_muted, make_title


class EraseConfirmDialog(QDialog):
    """Запрашивает ручной ввод ключевого слова перед стиранием данных на устройстве Apple."""

    def __init__(
        self,
        title_text: str,
        description: str,
        *,
        keyword: str = "СТЕРЕТЬ",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.keyword = keyword
        self.setWindowTitle(title_text)
        self.setMinimumWidth(480)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(10)

        layout.addWidget(make_title(title_text, parent=self))
        desc = QLabel(description, self)
        desc.setWordWrap(True)
        layout.addWidget(desc)

        hint = make_muted(
            f"Для подтверждения операции введите слово «{keyword}» заглавными буквами:",
            self,
        )
        layout.addWidget(hint)

        self.input_edit = QLineEdit(self)
        self.input_edit.setPlaceholderText(keyword)
        self.input_edit.textChanged.connect(self._on_text_changed)
        layout.addWidget(self.input_edit)

        btns = QHBoxLayout()
        btns.addStretch(1)
        cancel_btn = QPushButton("Отмена", self)
        cancel_btn.setObjectName("Ghost")
        cancel_btn.clicked.connect(self.reject)
        self.confirm_btn = QPushButton("Подтвердить и продолжить", self)
        self.confirm_btn.setObjectName("Danger")
        self.confirm_btn.setEnabled(False)
        self.confirm_btn.clicked.connect(self.accept)
        btns.addWidget(cancel_btn)
        btns.addWidget(self.confirm_btn)
        layout.addLayout(btns)

    def _on_text_changed(self, value: str) -> None:
        self.confirm_btn.setEnabled(value.strip().upper() == self.keyword.upper())


class ManifestDetailsDialog(QDialog):
    """Показывает полный технический отчёт о структуре BuildManifest.plist выбранного .ipsw."""

    def __init__(self, info: IpswManifestInfo, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"Манифест IPSW · {info.file_name}")
        self.resize(680, 520)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(10)
        layout.addWidget(make_title(info.file_name, parent=self))

        lines = [
            f"Путь к файлу:      {info.path}",
            f"Размер архива:     {human_bytes(info.file_size)} ({info.file_size:,} байт)",
            f"Версия ОС:         {info.product_version} (сборка {info.build_version})",
            f"Элементов в ZIP:   {info.zip_entries_count}",
            f"Наличие SEP:       {'Да' if info.has_sep else 'Нет'}",
            f"Модем Baseband:    {'Да' if info.has_baseband else 'Нет (Wi-Fi / Mac)'}",
            f"Сценарии записи:   {', '.join(info.restore_variants) or 'Стандартный'}",
            f"Платы (Board):     {', '.join(info.board_configs) or '—'}",
            f"Чипы (CPID):       {', '.join(CHIP_BY_CPID.get(c, hex(c)) for c in info.supported_cpids) or '—'}",
            "",
            f"Поддерживаемые модели ({len(info.supported_product_types)}):",
        ]
        for pt in info.supported_product_types:
            lines.append(f"  • {pt:<16} — {resolve_product_name(pt)}")

        if info.warnings:
            lines.append("")
            lines.append("Предупреждения:")
            for w in info.warnings:
                lines.append(f"  ! {w}")

        viewer = QPlainTextEdit(self)
        viewer.setObjectName("ConsoleBox")
        viewer.setReadOnly(True)
        viewer.setPlainText("\n".join(lines))
        layout.addWidget(viewer, 1)

        row = QHBoxLayout()
        row.addStretch(1)
        close_btn = QPushButton("Закрыть", self)
        close_btn.setObjectName("Primary")
        close_btn.clicked.connect(self.accept)
        row.addWidget(close_btn)
        layout.addLayout(row)
