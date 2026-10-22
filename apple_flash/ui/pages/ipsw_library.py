"""Локальная офлайн-библиотека образов прошивок .ipsw: разбор манифестов и проверка SHA-256 / SHA-1."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from apple_flash.core.security import human_bytes, normalize_hash
from apple_flash.data.models import IpswRecord
from apple_flash.services.context import StudioContext
from apple_flash.ui.dialogs import ManifestDetailsDialog
from apple_flash.ui.widgets import (
    StudioCard,
    clear_layout,
    kv_row,
    make_divider,
    make_muted,
    make_pill,
    make_title,
)
from apple_flash.ui.workers import HashWorker

VERIFY_BADGES: dict[str, tuple[str, str]] = {
    "verified": ("Эталон совпал", "ok"),
    "hashed": ("Хэш рассчитан", "info"),
    "mismatch": ("ХЭШ НЕ СОВПАЛ", "danger"),
    "unchecked": ("Не проверен", "neutral"),
}


class IpswLibraryPage(QWidget):
    def __init__(self, context: StudioContext, window) -> None:
        super().__init__()
        self.context = context
        self.window = window
        self._rows: list[IpswRecord] = []
        self._selected: IpswRecord | None = None
        self._hash_worker: HashWorker | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 16, 22, 16)
        layout.setSpacing(10)

        head = QHBoxLayout()
        box = QVBoxLayout()
        box.setSpacing(2)
        box.addWidget(make_title("Локальная библиотека IPSW (офлайн)", object_name="PageTitle"))
        box.addWidget(
            make_muted(
                "Мгновенное чтение BuildManifest.plist без распаковки архива и потоковая сверка SHA-256 / SHA-1."
            )
        )
        head.addLayout(box, 1)

        scan_dir_btn = QPushButton("Сканировать папку…", self)
        scan_dir_btn.setObjectName("Ghost")
        scan_dir_btn.clicked.connect(self._scan_directory)
        head.addWidget(scan_dir_btn)

        add_btn = QPushButton("+ Добавить файл .ipsw", self)
        add_btn.setObjectName("Primary")
        add_btn.clicked.connect(self.add_ipsw_dialog)
        head.addWidget(add_btn)
        layout.addLayout(head)

        filters = QHBoxLayout()
        self.search_edit = QLineEdit(self)
        self.search_edit.setPlaceholderText("Поиск по имени файла, сборке (22B83), версии ОС или коду модели (iPhone16,1, Mac15,3)…")
        self.search_edit.textChanged.connect(self.refresh)
        filters.addWidget(self.search_edit, 1)

        self.family_combo = QComboBox(self)
        self.family_combo.addItem("Все платформы Apple", "all")
        self.family_combo.addItem("iPhone (iOS)", "iphone")
        self.family_combo.addItem("iPad (iPadOS)", "ipad")
        self.family_combo.addItem("MacBook (macOS / bridgeOS)", "macbook")
        self.family_combo.currentIndexChanged.connect(self.refresh)
        filters.addWidget(self.family_combo)
        layout.addLayout(filters)

        splitter = QSplitter(Qt.Horizontal, self)
        splitter.setChildrenCollapsible(False)

        self.table = QTableWidget(0, 6, self)
        self.table.setHorizontalHeaderLabels(
            ["Файл .ipsw", "Платформа", "Версия ОС", "Сборка", "Размер", "Целостность"]
        )
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        hdr = self.table.horizontalHeader()
        hdr.setSectionResizeMode(0, QHeaderView.Stretch)
        for col in range(1, 6):
            hdr.setSectionResizeMode(col, QHeaderView.ResizeToContents)
        self.table.itemSelectionChanged.connect(self._on_selection)
        splitter.addWidget(self.table)

        from PySide6.QtWidgets import QScrollArea
        from apple_flash.ui.widgets import breakable

        right_scroll = QScrollArea(self)
        right_scroll.setWidgetResizable(True)
        right = QWidget(right_scroll)
        right_scroll.setWidget(right)
        r_layout = QVBoxLayout(right)
        r_layout.setSizeConstraint(QVBoxLayout.SetMinAndMaxSize)
        r_layout.setContentsMargins(8, 0, 0, 0)
        r_layout.setSpacing(10)
        self.detail_card = StudioCard(right)
        self.detail_body = self.detail_card.body()
        r_layout.addWidget(self.detail_card)

        self.hash_progress = QProgressBar(right)
        self.hash_progress.setVisible(False)
        r_layout.addWidget(self.hash_progress)
        r_layout.addStretch(1)
        splitter.addWidget(right_scroll)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        splitter.setSizes([760, 420])
        layout.addWidget(splitter, 1)

    def on_show(self) -> None:
        self.refresh()

    def refresh(self) -> None:
        self._rows = self.context.store.list_ipsw(
            family=self.family_combo.currentData(),
            search=self.search_edit.text(),
        )
        self.table.setRowCount(len(self._rows))
        for row_idx, rec in enumerate(self._rows):
            prefix = "[ДЕМО] " if rec.is_demo else ""
            state_txt, _ = VERIFY_BADGES.get(rec.verified_state, (rec.verified_state, "neutral"))
            if not rec.file_exists:
                state_txt = "Файл не найден"
            values = [
                f"{prefix}{rec.file_name}",
                rec.family_label,
                rec.product_version,
                rec.build_version,
                human_bytes(rec.file_size),
                state_txt,
            ]
            for col_idx, val in enumerate(values):
                item = QTableWidgetItem(val)
                self.table.setItem(row_idx, col_idx, item)

        if self._rows:
            self.table.selectRow(0)
        else:
            self._render_detail(None)

    def _on_selection(self) -> None:
        selected_rows = self.table.selectionModel().selectedRows()
        if not selected_rows:
            self._render_detail(None)
            return
        idx = selected_rows[0].row()
        if 0 <= idx < len(self._rows):
            self._render_detail(self._rows[idx])

    def _render_detail(self, rec: IpswRecord | None) -> None:
        self._selected = rec
        clear_layout(self.detail_body)
        if rec is None:
            self.detail_body.addWidget(make_title("Сведения об образе IPSW"))
            self.detail_body.addWidget(make_muted("Выберите файл в таблице или добавьте .ipsw с диска."))
            return

        from apple_flash.ui.widgets import breakable

        top = QHBoxLayout()
        top.addWidget(make_title(breakable(rec.file_name)), 1)
        if rec.is_demo:
            top.addWidget(make_pill("ДЕМО-МАКЕТ", "warning", self.detail_card))
        st_label, st_tone = VERIFY_BADGES.get(rec.verified_state, (rec.verified_state, "neutral"))
        top.addWidget(make_pill(st_label, st_tone, self.detail_card))
        self.detail_body.addLayout(top)

        for k, v in (
            ("Платформа:", rec.family_label),
            ("Версия ОС / Сборка:", f"{rec.product_version} ({rec.build_version})"),
            ("Размер на диске:", f"{human_bytes(rec.file_size)} ({'доступен' if rec.file_exists else 'файл перемещён'})"),
            ("Модели:", rec.models_preview),
            ("Режимы в манифесте:", f"Update: {'Да' if rec.has_upgrade else 'Нет'} · Erase: {'Да' if rec.has_erase else 'Нет'}"),
            ("SHA-256:", rec.sha256 or "не рассчитан"),
            ("SHA-1:", rec.sha1 or "не рассчитан"),
            ("Эталонный хэш:", rec.expected_hash or "не задан"),
            ("Локальный путь:", rec.local_path),
        ):
            self.detail_body.addWidget(kv_row(k, v, self.detail_card))

        self.detail_body.addWidget(make_divider(self.detail_card))

        use_btn = QPushButton("Использовать для прошивки →", self.detail_card)
        use_btn.setObjectName("Primary")
        use_btn.clicked.connect(lambda: self.window.open_flash_for_ipsw(rec))
        self.detail_body.addWidget(use_btn)

        row1 = QHBoxLayout()
        hash_btn = QPushButton("Проверить SHA-256", self.detail_card)
        hash_btn.clicked.connect(self._compute_selected_hash)
        ref_btn = QPushButton("Эталон хэша…", self.detail_card)
        ref_btn.setObjectName("Ghost")
        ref_btn.clicked.connect(self._set_expected_hash)
        row1.addWidget(hash_btn, 1)
        row1.addWidget(ref_btn, 1)
        self.detail_body.addLayout(row1)

        row2 = QHBoxLayout()
        manifest_btn = QPushButton("Полный BuildManifest", self.detail_card)
        manifest_btn.setObjectName("Ghost")
        manifest_btn.clicked.connect(self._open_manifest_modal)
        del_btn = QPushButton("Убрать из списка", self.detail_card)
        del_btn.setObjectName("Danger")
        del_btn.clicked.connect(self._remove_selected)
        row2.addWidget(manifest_btn)
        row2.addWidget(del_btn)
        self.detail_body.addLayout(row2)

    def add_ipsw_dialog(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Добавить локальные файлы прошивок Apple (.ipsw)",
            "",
            "Образы Apple IPSW (*.ipsw)",
        )
        if not paths:
            return
        added = 0
        errors: list[str] = []
        for p in paths:
            try:
                info = self.context.inspector.inspect(p)
                self.context.store.upsert_ipsw_from_manifest(info)
                added += 1
            except Exception as exc:
                errors.append(f"{Path(p).name}: {exc}")
        self.refresh()
        self.window.set_status(f"Добавлено образов IPSW: {added}")
        if errors:
            QMessageBox.warning(self, "Некоторые файлы пропущены", "\n".join(errors))

    def _scan_directory(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Выберите папку с файлами .ipsw")
        if not folder:
            return
        found_files = sorted(Path(folder).rglob("*.ipsw"))
        added = 0
        for f in found_files:
            try:
                info = self.context.inspector.inspect(f)
                self.context.store.upsert_ipsw_from_manifest(info)
                added += 1
            except Exception:
                continue
        self.refresh()
        QMessageBox.information(
            self,
            "Сканирование завершено",
            f"Найдено и проиндексировано корректных архивов .ipsw: {added}",
        )

    def _compute_selected_hash(self) -> None:
        if not self._selected or not self._selected.id:
            return
        if not self._selected.file_exists:
            QMessageBox.warning(self, "Файл не найден", "Файл отсутствует по сохранённому пути на диске.")
            return
        target_id = self._selected.id
        self.hash_progress.setValue(0)
        self.hash_progress.setVisible(True)
        self._hash_worker = HashWorker(Path(self._selected.local_path), self)
        self._hash_worker.progress.connect(self.hash_progress.setValue)

        def _done(sha256: str, sha1: str) -> None:
            self.hash_progress.setVisible(False)
            self.context.store.update_ipsw_hashes(target_id, sha256=sha256, sha1=sha1)
            self.refresh()
            self.window.set_status(f"SHA-256 рассчитан: {sha256[:16]}…")

        def _err(msg: str) -> None:
            self.hash_progress.setVisible(False)
            QMessageBox.warning(self, "Ошибка расчёта хэша", msg)

        self._hash_worker.finished_ok.connect(_done)
        self._hash_worker.failed.connect(_err)
        self._hash_worker.start()

    def _set_expected_hash(self) -> None:
        if not self._selected or not self._selected.id:
            return
        rec = self._selected
        val, ok = QInputDialog.getText(
            self,
            "Эталонная контрольная сумма",
            "Введите официальный SHA-256 (64 hex) или SHA-1 (40 hex) для сверки целостности файла:",
            text=rec.expected_hash or "",
        )
        if not ok:
            return
        try:
            norm = normalize_hash(val)
        except Exception as exc:
            QMessageBox.warning(self, "Некорректный формат", str(exc))
            return
        sha256 = rec.sha256
        sha1 = rec.sha1
        if not sha256 and rec.file_exists:
            from apple_flash.core.security import compute_hashes

            sha256, sha1 = compute_hashes(rec.local_path)
        self.context.store.update_ipsw_hashes(
            rec.id, sha256=sha256 or "", sha1=sha1 or "", expected_hash=norm or ""
        )
        self.refresh()

    def _open_manifest_modal(self) -> None:
        if not self._selected or not self._selected.file_exists:
            return
        try:
            info = self.context.inspector.inspect(self._selected.local_path)
            ManifestDetailsDialog(info, self).exec()
        except Exception as exc:
            QMessageBox.warning(self, "Ошибка чтения манифеста", str(exc))

    def _remove_selected(self) -> None:
        if not self._selected or not self._selected.id:
            return
        self.context.store.delete_ipsw(self._selected.id)
        self.refresh()
        self.window.set_status("Запись убрана из библиотеки (сам файл на диске сохранён)")
