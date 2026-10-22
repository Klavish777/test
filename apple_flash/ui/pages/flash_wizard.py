"""Мастер перепрошивки и восстановления IPSW (iPhone, iPad, MacBook)."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QRadioButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from apple_flash.data.models import (
    ConnectedDevice,
    FlashJobConfig,
    FlashSessionRecord,
    IpswManifestInfo,
    IpswRecord,
)
from apple_flash.services.compatibility import evaluate_compatibility
from apple_flash.services.context import StudioContext
from apple_flash.ui.dialogs import EraseConfirmDialog, ManifestDetailsDialog
from apple_flash.ui.widgets import (
    StudioCard,
    clear_layout,
    make_muted,
    make_pill,
    make_title,
    set_pill,
)
from apple_flash.ui.workers import FlashWorker


class FlashWizardPage(QWidget):
    def __init__(self, context: StudioContext, window) -> None:
        super().__init__()
        self.context = context
        self.window = window
        self._current_manifest: IpswManifestInfo | None = None
        self._worker: FlashWorker | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 16, 22, 16)
        layout.setSpacing(12)

        header = QHBoxLayout()
        vbox = QVBoxLayout()
        vbox.setSpacing(2)
        vbox.addWidget(make_title("Прошивка и восстановление (.ipsw)", object_name="PageTitle"))
        vbox.addWidget(
            make_muted(
                "Предполётная проверка совместимости модели, режимы Update / Clean Restore / MacBook Revive и живой журнал процесса."
            )
        )
        header.addLayout(vbox, 1)
        layout.addLayout(header)

        splitter = QSplitter(Qt.Horizontal, self)
        splitter.setChildrenCollapsible(False)
        splitter.addWidget(self._build_left_panel())
        splitter.addWidget(self._build_right_panel())
        splitter.setSizes([580, 620])
        layout.addWidget(splitter, 1)

    # ------------------------------------------------------------------ Левая панель настроек
    def _build_left_panel(self) -> QWidget:
        panel = QWidget(self)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 8, 0)
        layout.setSpacing(10)

        # 1. Устройство
        dev_card = StudioCard(panel)
        db = dev_card.body()
        db.addWidget(make_title("1. Целевое устройство Apple"))
        dev_row = QHBoxLayout()
        self.device_combo = QComboBox(dev_card)
        self.device_combo.currentIndexChanged.connect(self._recalculate_state)
        dev_row.addWidget(self.device_combo, 1)
        refresh_btn = QPushButton("Обновить USB", dev_card)
        refresh_btn.setObjectName("Ghost")
        refresh_btn.clicked.connect(self.window.refresh_devices)
        dev_row.addWidget(refresh_btn)
        db.addLayout(dev_row)
        layout.addWidget(dev_card)

        # 2. Образ IPSW
        ipsw_card = StudioCard(panel)
        ib = ipsw_card.body()
        ib.addWidget(make_title("2. Локальный образ прошивки (.ipsw)"))
        lib_row = QHBoxLayout()
        self.ipsw_combo = QComboBox(ipsw_card)
        self.ipsw_combo.currentIndexChanged.connect(self._on_library_ipsw_selected)
        lib_row.addWidget(self.ipsw_combo, 1)
        browse_btn = QPushButton("Файл с диска…", ipsw_card)
        browse_btn.clicked.connect(self._browse_ipsw_file)
        lib_row.addWidget(browse_btn)
        inspect_btn = QPushButton("Манифест", ipsw_card)
        inspect_btn.setObjectName("Ghost")
        inspect_btn.clicked.connect(self._show_manifest_dialog)
        lib_row.addWidget(inspect_btn)
        ib.addLayout(lib_row)

        shsh_row = QHBoxLayout()
        self.shsh_edit = QLineEdit(ipsw_card)
        self.shsh_edit.setPlaceholderText("Необязательно: локальный билет подписи .shsh2 / .shsh (для idevicerestore -T)")
        self.shsh_edit.textChanged.connect(self._recalculate_state)
        shsh_row.addWidget(self.shsh_edit, 1)
        shsh_btn = QPushButton("SHSH…", ipsw_card)
        shsh_btn.setObjectName("Ghost")
        shsh_btn.clicked.connect(self._browse_shsh_file)
        shsh_row.addWidget(shsh_btn)
        ib.addLayout(shsh_row)
        layout.addWidget(ipsw_card)

        # 3. Режим операции
        mode_card = StudioCard(panel)
        mb = mode_card.body()
        mb.addWidget(make_title("3. Режим перепрошивки"))
        self.action_group = QButtonGroup(self)
        self.rb_update = QRadioButton(
            "Обновление с сохранением данных (Update)", mode_card
        )
        self.rb_erase = QRadioButton(
            "Чистая перепрошивка со стиранием (Clean Restore)", mode_card
        )
        self.rb_revive = QRadioButton(
            "Оживление MacBook DFU без потери данных (Revive)", mode_card
        )
        self.rb_update.setChecked(True)
        for rb in (self.rb_update, self.rb_erase, self.rb_revive):
            self.action_group.addButton(rb)
            rb.toggled.connect(self._recalculate_state)
            mb.addWidget(rb)
        layout.addWidget(mode_card)

        # 4. Бэкенд и Dry-Run
        exec_card = StudioCard(panel)
        eb = exec_card.body()
        eb.addWidget(make_title("4. Движок и защита запуска"))
        b_row = QHBoxLayout()
        b_row.addWidget(QLabel("CLI-бэкенд:", exec_card))
        self.backend_combo = QComboBox(exec_card)
        self.backend_combo.addItem("Автовыбор (idevicerestore / pymobiledevice3)", "auto")
        self.backend_combo.addItem("pymobiledevice3 (Python USB/Restore)", "pymobiledevice3")
        self.backend_combo.addItem("idevicerestore (libimobiledevice)", "idevicerestore")
        self.backend_combo.currentIndexChanged.connect(self._recalculate_state)
        b_row.addWidget(self.backend_combo, 1)
        eb.addLayout(b_row)

        self.dry_run_cb = QCheckBox(
            "Безопасная репетиция (Dry-Run — проверка без записи в устройство)",
            exec_card,
        )
        self.dry_run_cb.setChecked(True)
        self.dry_run_cb.toggled.connect(self._recalculate_state)
        eb.addWidget(self.dry_run_cb)

        cmd_row = QHBoxLayout()
        self.cmd_preview = QLineEdit(exec_card)
        self.cmd_preview.setObjectName("CmdPreview")
        self.cmd_preview.setReadOnly(True)
        cmd_row.addWidget(self.cmd_preview, 1)
        copy_btn = QPushButton("Копировать", exec_card)
        copy_btn.setObjectName("Ghost")
        copy_btn.clicked.connect(self._copy_command)
        cmd_row.addWidget(copy_btn)
        eb.addLayout(cmd_row)

        layout.addWidget(exec_card)
        layout.addStretch(1)
        return panel

    # ------------------------------------------------------------------ Правая панель проверки и консоли
    def _build_right_panel(self) -> QWidget:
        panel = QWidget(self)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(8, 0, 0, 0)
        layout.setSpacing(10)

        # Карточка совместимости
        self.compat_card = StudioCard(panel)
        cb = self.compat_card.body()
        top = QHBoxLayout()
        top.addWidget(make_title("Предполётная проверка совместимости", parent=self.compat_card), 1)
        self.compat_pill = make_pill("Ожидание", "neutral", self.compat_card)
        top.addWidget(self.compat_pill)
        cb.addLayout(top)
        self.compat_headline = QLabel("", self.compat_card)
        self.compat_headline.setWordWrap(True)
        cb.addWidget(self.compat_headline)
        self.compat_details_box = QVBoxLayout()
        self.compat_details_box.setSpacing(4)
        cb.addLayout(self.compat_details_box)
        layout.addWidget(self.compat_card)

        # Консоль и шкала выполнения
        console_card = StudioCard(panel)
        con_b = console_card.body()
        con_top = QHBoxLayout()
        con_top.addWidget(make_title("Выполнение и журнал операций", parent=console_card), 1)
        self.stage_label = make_muted("Готово к запуску", console_card)
        con_top.addWidget(self.stage_label)
        con_b.addLayout(con_top)

        self.progress_bar = QProgressBar(console_card)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        con_b.addWidget(self.progress_bar)

        self.console = QPlainTextEdit(console_card)
        self.console.setObjectName("ConsoleBox")
        self.console.setReadOnly(True)
        self.console.setPlaceholderText(
            "Здесь отображается полный ход проверки BuildManifest.plist, подписи TSS и этапов прошивки…"
        )
        con_b.addWidget(self.console, 1)

        btn_row = QHBoxLayout()
        self.start_btn = QPushButton("Запустить прошивку / репетицию", console_card)
        self.start_btn.setObjectName("Primary")
        self.start_btn.clicked.connect(self._start_flash)
        self.cancel_btn = QPushButton("Остановить", console_card)
        self.cancel_btn.setObjectName("Danger")
        self.cancel_btn.setEnabled(False)
        self.cancel_btn.clicked.connect(self._cancel_flash)
        clear_btn = QPushButton("Очистить лог", console_card)
        clear_btn.setObjectName("Ghost")
        clear_btn.clicked.connect(self.console.clear)
        btn_row.addWidget(self.start_btn, 1)
        btn_row.addWidget(self.cancel_btn)
        btn_row.addWidget(clear_btn)
        con_b.addLayout(btn_row)

        layout.addWidget(console_card, 1)
        return panel

    # ------------------------------------------------------------------ Логика данных
    def on_show(self) -> None:
        self._reload_devices()
        self._reload_ipsw_combo()
        self._recalculate_state()

    def preselect_device(self, device: ConnectedDevice) -> None:
        self._reload_devices()
        for idx in range(self.device_combo.count()):
            item: ConnectedDevice | None = self.device_combo.itemData(idx)
            if item and item.uid == device.uid:
                self.device_combo.setCurrentIndex(idx)
                break
        if device.family == "macbook":
            self.rb_revive.setChecked(True)
        self._recalculate_state()

    def preselect_ipsw(self, record: IpswRecord) -> None:
        self._reload_ipsw_combo()
        for idx in range(self.ipsw_combo.count()):
            data = self.ipsw_combo.itemData(idx)
            if isinstance(data, str) and Path(data) == Path(record.local_path):
                self.ipsw_combo.setCurrentIndex(idx)
                break
        self._recalculate_state()

    def _reload_devices(self) -> None:
        prev_uid = None
        curr = self.device_combo.currentData()
        if isinstance(curr, ConnectedDevice):
            prev_uid = curr.uid
        self.device_combo.blockSignals(True)
        self.device_combo.clear()
        devices = self.window.connected_devices
        if not devices:
            self.device_combo.addItem("Нет подключённых USB-устройств (доступна репетиция Dry-Run)", None)
        else:
            for d in devices:
                self.device_combo.addItem(f"{d.display_title} · {d.mode_label}", d)
            if prev_uid:
                for i in range(self.device_combo.count()):
                    it = self.device_combo.itemData(i)
                    if isinstance(it, ConnectedDevice) and it.uid == prev_uid:
                        self.device_combo.setCurrentIndex(i)
                        break
        self.device_combo.blockSignals(False)

    def _reload_ipsw_combo(self) -> None:
        prev_path = self.ipsw_combo.currentData()
        self.ipsw_combo.blockSignals(True)
        self.ipsw_combo.clear()
        records = self.context.store.list_ipsw()
        if not records:
            self.ipsw_combo.addItem("— Выберите файл .ipsw на диске —", None)
        else:
            for r in records:
                tag = "[ДЕМО] " if r.is_demo else ""
                label = f"{tag}{r.file_name} · ОС {r.product_version} ({r.build_version})"
                self.ipsw_combo.addItem(label, r.local_path)
            if prev_path:
                idx = self.ipsw_combo.findData(prev_path)
                if idx >= 0:
                    self.ipsw_combo.setCurrentIndex(idx)
        self.ipsw_combo.blockSignals(False)
        self._load_manifest_for_current()

    def _on_library_ipsw_selected(self) -> None:
        self._load_manifest_for_current()
        self._recalculate_state()

    def _load_manifest_for_current(self) -> None:
        path_str = self.ipsw_combo.currentData()
        if not path_str or not Path(path_str).is_file():
            self._current_manifest = None
            return
        try:
            self._current_manifest = self.context.inspector.inspect(path_str)
        except Exception:
            self._current_manifest = None

    def _browse_ipsw_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Выберите локальный файл прошивки Apple (.ipsw)",
            "",
            "Образы прошивок Apple (*.ipsw);;Все файлы (*.*)",
        )
        if not path:
            return
        try:
            manifest = self.context.inspector.inspect(path)
            rec = self.context.store.upsert_ipsw_from_manifest(manifest)
            self._reload_ipsw_combo()
            self.preselect_ipsw(rec)
            self.window.set_status(f"Загружен образ {manifest.file_name} ({manifest.build_version})")
        except Exception as exc:
            QMessageBox.critical(self, "Ошибка чтения .ipsw", str(exc))

    def _browse_shsh_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Выберите билет подписи SHSH2 / SHSH",
            "",
            "Файлы SHSH (*.shsh2 *.shsh *.plist);;Все файлы (*.*)",
        )
        if path:
            self.shsh_edit.setText(path)

    def _show_manifest_dialog(self) -> None:
        if not self._current_manifest:
            QMessageBox.information(self, "Нет образа", "Сначала выберите корректный файл .ipsw.")
            return
        ManifestDetailsDialog(self._current_manifest, self).exec()

    def _selected_action(self) -> str:
        if self.rb_erase.isChecked():
            return "erase"
        if self.rb_revive.isChecked():
            return "revive_mac"
        return "update"

    def _build_current_job(self) -> FlashJobConfig:
        dev = self.device_combo.currentData()
        ipsw_str = self.ipsw_combo.currentData()
        shsh_str = self.shsh_edit.text().strip()
        return FlashJobConfig(
            action=self._selected_action(),
            device=dev if isinstance(dev, ConnectedDevice) else None,
            ipsw_path=Path(ipsw_str) if ipsw_str else None,
            shsh_path=Path(shsh_str) if shsh_str else None,
            backend=self.backend_combo.currentData() or "auto",
            dry_run=self.dry_run_cb.isChecked(),
        )

    def _recalculate_state(self) -> None:
        job = self._build_current_job()
        verdict = evaluate_compatibility(job.device, self._current_manifest, job.action)

        tone_map = {
            "compatible": ("Совместимо", "ok"),
            "warning": ("Внимание", "warning"),
            "incompatible": ("Заблокировано", "danger"),
        }
        badge_txt, tone = tone_map.get(verdict.level, ("Проверка", "neutral"))
        set_pill(self.compat_pill, badge_txt, tone)
        self.compat_headline.setText(verdict.headline)

        clear_layout(self.compat_details_box)
        for line in verdict.details:
            self.compat_details_box.addWidget(make_muted(f"• {line}", self.compat_card))

        try:
            if job.ipsw_path:
                _, cmd_args = self.context.flash_engine.build_command(job)
                self.cmd_preview.setText(self.context.flash_engine.format_command(cmd_args))
            else:
                self.cmd_preview.setText("")
        except Exception as exc:
            self.cmd_preview.setText(f"# {exc}")

        if self._worker is None or not self._worker.isRunning():
            self.start_btn.setEnabled(verdict.can_proceed and job.ipsw_path is not None)
            self.start_btn.setText(
                "▶ Старт (Dry-Run)"
                if job.dry_run
                else (
                    "▶ Стереть и прошить"
                    if job.action == "erase"
                    else "▶ Прошить устройство"
                )
            )

    def _copy_command(self) -> None:
        text = self.cmd_preview.text().strip()
        if text:
            QGuiApplication.clipboard().setText(text)
            self.window.set_status("Команда CLI скопирована в буфер обмена")

    def _start_flash(self) -> None:
        job = self._build_current_job()
        if not job.dry_run:
            if job.device is None or job.device.is_virtual:
                QMessageBox.warning(
                    self,
                    "Требуется физическое устройство",
                    "Для реальной прошивки подключите физический iPhone, iPad или MacBook по USB.\n"
                    "Для тестирования на макете включите флажок «Безопасная репетиция (Dry-Run)».",
                )
                return
            if self._current_manifest and self._current_manifest.is_demo_mockup:
                QMessageBox.warning(
                    self,
                    "Демонстрационный макет IPSW",
                    "Выбранный файл помечен как ДЕМО-макет и предназначен только для режима Dry-Run.\n"
                    "Выберите настоящий скачанный образ .ipsw от Apple.",
                )
                return
            if job.action == "erase":
                dlg = EraseConfirmDialog(
                    "Подтверждение полной очистки (Clean Restore)",
                    f"Все пользовательские данные на устройстве «{job.device.display_title}» будут БЕЗВОЗВРАТНО УДАЛЕНЫ.\n"
                    "Если на устройстве включён «Локатор» (Find My), после перепрошивки потребуется ввод Apple ID владельца.",
                    keyword="СТЕРЕТЬ",
                    parent=self,
                )
                if not dlg.exec():
                    return
            else:
                reply = QMessageBox.question(
                    self,
                    "Подтверждение запуска прошивки",
                    f"Начать операцию на устройстве «{job.device.display_title}»?\n"
                    "Не отсоединяйте USB-кабель до полного завершения процесса.",
                    QMessageBox.Yes | QMessageBox.No,
                )
                if reply != QMessageBox.Yes:
                    return

        self.console.clear()
        self.progress_bar.setValue(0)
        self.start_btn.setEnabled(False)
        self.cancel_btn.setEnabled(True)
        self.stage_label.setText("Инициализация…")

        self._worker = FlashWorker(self.context.flash_engine, job, self)
        self._worker.progress.connect(self._on_worker_progress)
        self._worker.log_line.connect(self.console.appendPlainText)
        self._worker.finished_session.connect(self._on_worker_finished)
        self._worker.failed.connect(self._on_worker_failed)
        self._worker.start()

    def _cancel_flash(self) -> None:
        if self._worker and self._worker.isRunning():
            self._worker.cancel()
            self.stage_label.setText("Отмена операции…")

    def _on_worker_progress(self, pct: int, stage: str) -> None:
        self.progress_bar.setValue(pct)
        self.stage_label.setText(stage)

    def _on_worker_finished(self, session: FlashSessionRecord) -> None:
        self.cancel_btn.setEnabled(False)
        self._recalculate_state()
        if session.status == "success":
            self.window.set_status(
                "Репетиция Dry-Run успешно завершена"
                if session.dry_run
                else "Прошивка устройства успешно завершена!"
            )
        else:
            self.window.set_status(f"Операция завершилась со статусом: {session.status}")

    def _on_worker_failed(self, err_msg: str) -> None:
        self.cancel_btn.setEnabled(False)
        self.stage_label.setText("Остановлено из-за ошибки")
        self.console.appendPlainText(f"[ОШИБКА] {err_msg}")
        self._recalculate_state()
        QMessageBox.warning(self, "Операция остановлена", err_msg)
