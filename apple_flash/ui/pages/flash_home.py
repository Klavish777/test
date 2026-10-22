"""Главный рабочий экран Apple Flash Studio v2.0: подключённое устройство + выбор .ipsw + реальная прошивка."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QComboBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from apple_flash.core.security import human_bytes
from apple_flash.data.models import (
    ConnectedDevice,
    FlashJobConfig,
    FlashSessionRecord,
    IpswManifestInfo,
    IpswRecord,
)
from apple_flash.services.compatibility import evaluate_compatibility
from apple_flash.services.context import StudioContext
from apple_flash.ui.widgets import (
    StudioCard,
    breakable,
    clear_layout,
    kv_row,
    make_divider,
    make_muted,
    make_pill,
    make_title,
    set_pill,
)
from apple_flash.ui.workers import FlashWorker

MODE_TONES = {
    "normal": "ok",
    "recovery": "warning",
    "dfu": "info",
    "restore": "info",
    "wtf": "warning",
}


class FlashHomePage(QWidget):
    """Единый понятный экран: слева подключённое по USB устройство, справа файл .ipsw и кнопка прошивки."""

    def __init__(self, context: StudioContext, window) -> None:
        super().__init__()
        self.context = context
        self.window = window
        self._selected_ipsw_path: Path | None = None
        self._selected_manifest: IpswManifestInfo | None = None
        self._selected_shsh_path: Path | None = None
        self._worker: FlashWorker | None = None

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        outer.addWidget(scroll)

        content = QWidget(scroll)
        scroll.setWidget(content)
        root = QHBoxLayout(content)
        root.setContentsMargins(20, 16, 20, 16)
        root.setSpacing(16)

        # ==================== ЛЕВАЯ КОЛОНКА: УСТРОЙСТВО ====================
        left_col = QVBoxLayout()
        left_col.setSpacing(12)

        self.device_card = StudioCard(content, hero=True)
        db = self.device_card.body()
        db.setSpacing(10)

        dev_hdr = QHBoxLayout()
        dev_hdr.addWidget(make_title("1. Подключённое устройство", parent=self.device_card), 1)
        self.usb_count_pill = make_pill("Ожидание USB", "neutral", self.device_card)
        dev_hdr.addWidget(self.usb_count_pill)
        db.addLayout(dev_hdr)

        # Выбор устройства (показывается только если одновременно подключено 2 и более устройств Apple)
        self.multi_device_combo = QComboBox(self.device_card)
        self.multi_device_combo.hide()
        self.multi_device_combo.currentIndexChanged.connect(self._on_device_combo_changed)
        db.addWidget(self.multi_device_combo)

        self.device_body_host = QWidget(self.device_card)
        self.device_body_layout = QVBoxLayout(self.device_body_host)
        self.device_body_layout.setContentsMargins(0, 0, 0, 0)
        self.device_body_layout.setSpacing(8)
        db.addWidget(self.device_body_host)

        left_col.addWidget(self.device_card)

        # Краткая памятка под карточкой устройства
        tips_card = StudioCard(content)
        tb = tips_card.body()
        tb.addWidget(make_title("Подсказка перед прошивкой", parent=tips_card))
        tb.addWidget(
            make_muted(
                "• Используйте оригинальный или качественный дата-кабель напрямую в USB-порт компьютера (без дешёвых хабов).\n"
                "• Для прошивки официальной системой нужен интернет — программа запрашивает цифровую подпись у сервера Apple.\n"
                "• Заряд аккумулятора iPhone / iPad желательно держать не ниже 30%.",
                tips_card,
            )
        )
        left_col.addWidget(tips_card)
        left_col.addStretch(1)

        # ==================== ПРАВАЯ КОЛОНКА: ПРОШИВКА И ЗАПУСК ====================
        right_col = QVBoxLayout()
        right_col.setSpacing(12)

        # --- Карточка 2: Файл прошивки (.ipsw) ---
        ipsw_card = StudioCard(content)
        ib = ipsw_card.body()
        ib.setSpacing(10)

        ipsw_hdr = QHBoxLayout()
        ipsw_hdr.addWidget(make_title("2. Файл прошивки (.ipsw)", parent=ipsw_card), 1)
        self.compat_pill = make_pill("Файл не выбран", "neutral", ipsw_card)
        ipsw_hdr.addWidget(self.compat_pill)
        ib.addLayout(ipsw_hdr)

        pick_row = QHBoxLayout()
        self.pick_ipsw_btn = QPushButton("+ Выбрать файл .ipsw на компьютере…", ipsw_card)
        self.pick_ipsw_btn.setObjectName("Primary")
        self.pick_ipsw_btn.clicked.connect(self.browse_ipsw_file)
        pick_row.addWidget(self.pick_ipsw_btn)

        self.recent_ipsw_combo = QComboBox(ipsw_card)
        self.recent_ipsw_combo.setMinimumWidth(220)
        self.recent_ipsw_combo.currentIndexChanged.connect(self._on_recent_ipsw_selected)
        self.recent_ipsw_combo.hide()
        pick_row.addWidget(self.recent_ipsw_combo, 1)
        ib.addLayout(pick_row)

        self.ipsw_summary_lbl = make_muted(
            "Нажмите кнопку выше или перетащите скачанный файл прошивки .ipsw прямо в это окно.",
            ipsw_card,
        )
        ib.addWidget(self.ipsw_summary_lbl)

        # Блок вердикта совместимости
        self.verdict_frame = QFrame(ipsw_card)
        self.verdict_frame.setObjectName("Card")
        vf_lay = QVBoxLayout(self.verdict_frame)
        vf_lay.setContentsMargins(12, 9, 12, 9)
        vf_lay.setSpacing(4)
        self.verdict_title_lbl = QLabel("Выберите файл .ipsw для автоматической проверки совместимости", self.verdict_frame)
        self.verdict_title_lbl.setWordWrap(True)
        self.verdict_details_lbl = make_muted("", self.verdict_frame)
        self.verdict_details_lbl.hide()
        vf_lay.addWidget(self.verdict_title_lbl)
        vf_lay.addWidget(self.verdict_details_lbl)
        ib.addWidget(self.verdict_frame)

        # Необязательный билет SHSH2 (свёрнут по умолчанию, чтобы не путать обычных пользователей)
        shsh_toggle_row = QHBoxLayout()
        self.shsh_toggle_btn = QPushButton("Дополнительно: указать локальный билет SHSH2", ipsw_card)
        self.shsh_toggle_btn.setObjectName("Ghost")
        self.shsh_toggle_btn.clicked.connect(self._toggle_shsh_row)
        shsh_toggle_row.addWidget(self.shsh_toggle_btn)
        shsh_toggle_row.addStretch(1)
        ib.addLayout(shsh_toggle_row)

        self.shsh_box = QWidget(ipsw_card)
        shsh_lay = QHBoxLayout(self.shsh_box)
        shsh_lay.setContentsMargins(0, 0, 0, 0)
        self.shsh_edit = QLineEdit(self.shsh_box)
        self.shsh_edit.setReadOnly(True)
        self.shsh_edit.setPlaceholderText("Не указан — подпись запрашивается у сервера Apple автоматически")
        shsh_pick = QPushButton("Выбрать .shsh2…", self.shsh_box)
        shsh_pick.clicked.connect(self._browse_shsh)
        shsh_clear = QPushButton("Сбросить", self.shsh_box)
        shsh_clear.setObjectName("Ghost")
        shsh_clear.clicked.connect(self._clear_shsh)
        shsh_lay.addWidget(self.shsh_edit, 1)
        shsh_lay.addWidget(shsh_pick)
        shsh_lay.addWidget(shsh_clear)
        self.shsh_box.hide()
        ib.addWidget(self.shsh_box)

        right_col.addWidget(ipsw_card)

        # --- Карточка 3: Режим и запуск прошивки ---
        run_card = StudioCard(content)
        rb = run_card.body()
        rb.setSpacing(10)
        rb.addWidget(make_title("3. Что сделать с данными при прошивке?", parent=run_card))

        self.mode_group = QButtonGroup(self)
        self.rb_update = QRadioButton(
            "Обновить систему — СОХРАНИТЬ все данные, фото и настройки", run_card
        )
        self.rb_erase = QRadioButton(
            "Чистая перепрошивка со сбросом — СТЕРЕТЬ все данные и сбросить пароль экрана",
            run_card,
        )
        self.rb_revive = QRadioButton(
            "Оживить MacBook (Revive DFU) — обновить контроллер без удаления данных",
            run_card,
        )
        self.rb_revive.hide()
        self.rb_update.setChecked(True)
        for btn in (self.rb_update, self.rb_erase, self.rb_revive):
            self.mode_group.addButton(btn)
            btn.toggled.connect(self._refresh_compatibility)
            rb.addWidget(btn)

        self.mode_hint_lbl = make_muted(
            "Режим обновления установит новую систему поверх текущей без потери личных файлов.",
            run_card,
        )
        rb.addWidget(self.mode_hint_lbl)
        rb.addWidget(make_divider(run_card))

        # Кнопка старта + отмена
        action_row = QHBoxLayout()
        self.start_flash_btn = QPushButton("⚡ ПРОШИТЬ УСТРОЙСТВО", run_card)
        self.start_flash_btn.setObjectName("FlashActionBtn")
        self.start_flash_btn.setMinimumHeight(44)
        self.start_flash_btn.clicked.connect(self._on_start_flash_clicked)
        action_row.addWidget(self.start_flash_btn, 1)

        self.cancel_btn = QPushButton("Остановить", run_card)
        self.cancel_btn.setObjectName("Danger")
        self.cancel_btn.setMinimumHeight(44)
        self.cancel_btn.setEnabled(False)
        self.cancel_btn.clicked.connect(self._on_cancel_clicked)
        action_row.addWidget(self.cancel_btn)
        rb.addLayout(action_row)

        self.progress_bar = QProgressBar(run_card)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        rb.addWidget(self.progress_bar)

        status_row = QHBoxLayout()
        self.stage_lbl = QLabel("Готов к работе", run_card)
        self.stage_lbl.setWordWrap(True)
        status_row.addWidget(self.stage_lbl, 1)

        save_log_btn = QPushButton("Сохранить журнал", run_card)
        save_log_btn.setObjectName("Ghost")
        save_log_btn.clicked.connect(self._save_log_to_file)
        status_row.addWidget(save_log_btn)
        rb.addLayout(status_row)

        self.log_box = QPlainTextEdit(run_card)
        self.log_box.setObjectName("ConsoleBox")
        self.log_box.setReadOnly(True)
        self.log_box.setMinimumHeight(145)
        self.log_box.setPlaceholderText(
            "Здесь в реальном времени отображаются все этапы проверки, подписи Apple TSS и записи прошивки…"
        )
        rb.addWidget(self.log_box)

        right_col.addWidget(run_card)
        right_col.addStretch(1)

        root.addLayout(left_col, 44)
        root.addLayout(right_col, 56)

        self._reload_recent_ipsw_combo()
        self.update_devices_view()

    # ==================== Публичные методы ====================
    @property
    def is_busy(self) -> bool:
        return self._worker is not None and self._worker.isRunning()

    def current_device(self) -> ConnectedDevice | None:
        devs = self.window.connected_devices
        if not devs:
            return None
        idx = self.multi_device_combo.currentIndex()
        if 0 <= idx < len(devs):
            return devs[idx]
        return devs[0]

    def current_action(self) -> str:
        if not self.rb_revive.isHidden() and self.rb_revive.isChecked():
            return "revive_mac"
        if self.rb_erase.isChecked():
            return "erase"
        return "update"

    def on_show(self) -> None:
        self._reload_recent_ipsw_combo()
        self.update_devices_view()

    def load_ipsw_path(self, path: Path) -> bool:
        """Загружает и проверяет локальный файл .ipsw (при выборе кнопкой или перетаскивании мышью)."""
        if not path.is_file():
            QMessageBox.warning(self, "Файл не найден", f"Файл не существует:\n{path}")
            return False
        try:
            manifest = self.context.inspector.inspect(path)
        except Exception as exc:
            QMessageBox.critical(
                self,
                "Ошибка чтения файла .ipsw",
                f"Не удалось прочитать паспорт прошивки (BuildManifest.plist):\n\n{exc}",
            )
            return False

        self._selected_ipsw_path = path.resolve()
        self._selected_manifest = manifest
        if not manifest.is_demo_mockup:
            try:
                self.context.store.upsert_ipsw_from_manifest(manifest)
            except Exception:
                pass
        self._reload_recent_ipsw_combo()
        self._render_ipsw_summary()
        self._refresh_compatibility()
        return True

    def select_ipsw_record(self, rec: IpswRecord) -> None:
        p = Path(rec.local_path)
        if p.is_file():
            self.load_ipsw_path(p)

    def browse_ipsw_file(self) -> None:
        file_str, _ = QFileDialog.getOpenFileName(
            self,
            "Выберите файл прошивки Apple (.ipsw)",
            str(Path.home() / "Downloads"),
            "Прошивки Apple (*.ipsw);;Все файлы (*.*)",
        )
        if file_str:
            self.load_ipsw_path(Path(file_str))

    # ==================== Отрисовка карточки устройства ====================
    def update_devices_view(self) -> None:
        devs = self.window.connected_devices

        self.multi_device_combo.blockSignals(True)
        prev_uid = self.multi_device_combo.currentData()
        self.multi_device_combo.clear()
        for d in devs:
            self.multi_device_combo.addItem(f"{d.display_title} — {d.mode_label}", d.uid)
        if prev_uid:
            idx = self.multi_device_combo.findData(prev_uid)
            if idx >= 0:
                self.multi_device_combo.setCurrentIndex(idx)
        self.multi_device_combo.setVisible(len(devs) > 1)
        self.multi_device_combo.blockSignals(False)

        clear_layout(self.device_body_layout)

        if not devs:
            set_pill(self.usb_count_pill, "Нет подключённых устройств", "neutral")
            empty_title = make_title(
                "Подключите iPhone, iPad или MacBook по USB",
                parent=self.device_body_host,
            )
            self.device_body_layout.addWidget(empty_title)
            self.device_body_layout.addWidget(
                make_muted(
                    "1. Подключите устройство кабелем к USB-порту компьютера — оно появится здесь автоматически.\n"
                    "2. Если устройство включается, разблокируйте экран.\n"
                    "3. Если телефон завис на логотипе Apple или забыт код-пароль — переведите его в режим Recovery или DFU.\n"
                    "4. Если кабель уже вставлен, но устройство не определяется — проверьте драйвер на вкладке «Драйверы и USB».",
                    self.device_body_host,
                )
            )
            btn_row = QHBoxLayout()
            dfu_btn = QPushButton("◉ Как перевести в Recovery / DFU", self.device_body_host)
            dfu_btn.clicked.connect(lambda: self.window.navigate("dfu"))
            drv_btn = QPushButton("⚙ Проверить драйверы USB", self.device_body_host)
            drv_btn.clicked.connect(lambda: self.window.navigate("drivers"))
            btn_row.addWidget(dfu_btn)
            btn_row.addWidget(drv_btn)
            self.device_body_layout.addLayout(btn_row)
            self._adapt_mode_radios(None)
            self._refresh_compatibility()
            return

        dev = self.current_device()
        assert dev is not None
        set_pill(
            self.usb_count_pill,
            f"Подключено по USB ({len(devs)})" if len(devs) > 1 else "Подключено по USB",
            "ok" if not dev.driver_warning else "warning",
        )

        # Заголовок модели + бейдж режима
        title_row = QHBoxLayout()
        hero_lbl = make_title(dev.display_title, object_name="HeroTitle", parent=self.device_body_host)
        title_row.addWidget(hero_lbl, 1)
        title_row.addWidget(
            make_pill(dev.mode_label, MODE_TONES.get(dev.mode, "info"), self.device_body_host)
        )
        self.device_body_layout.addLayout(title_row)

        # Баннер предупреждения о драйвере (если в Windows нет AMDS или нужен WinUSB)
        if dev.driver_warning:
            warn_box = QFrame(self.device_body_host)
            warn_box.setObjectName("WarnBanner")
            wb = QVBoxLayout(warn_box)
            wb.setContentsMargins(12, 9, 12, 9)
            wb.setSpacing(6)
            w_txt = QLabel(dev.driver_warning, warn_box)
            w_txt.setWordWrap(True)
            wb.addWidget(w_txt)
            w_btns = QHBoxLayout()
            if dev.mode == "normal":
                store_btn = QPushButton("Установить «Устройства Apple» (Microsoft Store)", warn_box)
                store_btn.setObjectName("Primary")
                store_btn.clicked.connect(self._open_apple_devices_store)
                w_btns.addWidget(store_btn)
            fix_btn = QPushButton("Открыть диагностику драйверов", warn_box)
            fix_btn.clicked.connect(lambda: self.window.navigate("drivers"))
            w_btns.addWidget(fix_btn)
            w_btns.addStretch(1)
            wb.addLayout(w_btns)
            self.device_body_layout.addWidget(warn_box)

        # Таблица понятных характеристик
        self.device_body_layout.addWidget(make_divider(self.device_body_host))
        if dev.device_name:
            self.device_body_layout.addWidget(
                kv_row("Имя устройства", dev.device_name, self.device_body_host)
            )
        model_code = f"{dev.display_title} ({dev.product_type})" if dev.product_type else dev.display_title
        self.device_body_layout.addWidget(
            kv_row("Модель", model_code, self.device_body_host)
        )
        if dev.os_version:
            ver_txt = f"{dev.os_version} (сборка {dev.build_version})" if dev.build_version else dev.os_version
            self.device_body_layout.addWidget(
                kv_row("Версия системы", ver_txt, self.device_body_host)
            )
        if dev.cpid is not None:
            self.device_body_layout.addWidget(
                kv_row("Процессор", dev.chip_label, self.device_body_host)
            )
        if dev.serial_number:
            self.device_body_layout.addWidget(
                kv_row("Серийный номер", dev.serial_number, self.device_body_host)
            )
        id_val = dev.ecid or dev.udid or dev.uid
        self.device_body_layout.addWidget(
            kv_row("Идентификатор (ECID / UDID)", id_val, self.device_body_host)
        )
        if dev.usb_driver:
            self.device_body_layout.addWidget(
                kv_row("Драйвер USB", dev.usb_driver, self.device_body_host)
            )

        self.device_body_layout.addWidget(make_divider(self.device_body_host))

        # Кнопки прямого управления устройством
        ctrl_row = QHBoxLayout()
        if dev.mode == "normal":
            to_rec_btn = QPushButton("Перевести в Recovery", self.device_body_host)
            to_rec_btn.clicked.connect(lambda: self._run_quick_device_action("enter_recovery"))
            reboot_btn = QPushButton("Перезагрузить", self.device_body_host)
            reboot_btn.clicked.connect(lambda: self._run_quick_device_action("reboot"))
            ctrl_row.addWidget(to_rec_btn)
            ctrl_row.addWidget(reboot_btn)
        elif dev.mode == "recovery":
            exit_rec_btn = QPushButton("Выйти из режима Recovery", self.device_body_host)
            exit_rec_btn.setObjectName("Primary")
            exit_rec_btn.clicked.connect(lambda: self._run_quick_device_action("exit_recovery"))
            reboot_btn = QPushButton("Перезагрузить", self.device_body_host)
            reboot_btn.clicked.connect(lambda: self._run_quick_device_action("reboot"))
            ctrl_row.addWidget(exit_rec_btn)
            ctrl_row.addWidget(reboot_btn)
        else:
            dfu_help_btn = QPushButton("Инструкция по кнопкам DFU", self.device_body_host)
            dfu_help_btn.clicked.connect(lambda: self.window.navigate("dfu"))
            ctrl_row.addWidget(dfu_help_btn)

        copy_btn = QPushButton("Копировать ID", self.device_body_host)
        copy_btn.setObjectName("Ghost")
        copy_btn.clicked.connect(lambda: QApplication.clipboard().setText(id_val))
        ctrl_row.addWidget(copy_btn)
        ctrl_row.addStretch(1)
        self.device_body_layout.addLayout(ctrl_row)

        self._adapt_mode_radios(dev)
        self._refresh_compatibility()

    # ==================== Вспомогательная логика ====================
    def _on_device_combo_changed(self) -> None:
        self.update_devices_view()

    def _adapt_mode_radios(self, dev: ConnectedDevice | None) -> None:
        is_mac = bool(dev and dev.family == "macbook")
        self.rb_revive.setVisible(is_mac)
        if is_mac and self.rb_update.isChecked():
            self.rb_revive.setChecked(True)
        elif not is_mac and self.rb_revive.isChecked():
            self.rb_update.setChecked(True)

    def _reload_recent_ipsw_combo(self) -> None:
        records = [r for r in self.context.store.list_ipsw() if not r.is_demo and r.file_exists]
        self.recent_ipsw_combo.blockSignals(True)
        self.recent_ipsw_combo.clear()
        self.recent_ipsw_combo.addItem("Недавние файлы .ipsw…", "")
        for r in records[:15]:
            self.recent_ipsw_combo.addItem(
                f"{r.file_name} (ОС {r.product_version} · {r.build_version})",
                r.local_path,
            )
            if self._selected_ipsw_path and Path(r.local_path).resolve() == self._selected_ipsw_path:
                self.recent_ipsw_combo.setCurrentIndex(self.recent_ipsw_combo.count() - 1)
        self.recent_ipsw_combo.setVisible(len(records) > 0)
        self.recent_ipsw_combo.blockSignals(False)

    def _on_recent_ipsw_selected(self) -> None:
        p_str = self.recent_ipsw_combo.currentData()
        if p_str:
            p = Path(str(p_str))
            if p.is_file() and p.resolve() != self._selected_ipsw_path:
                self.load_ipsw_path(p)

    def _render_ipsw_summary(self) -> None:
        m = self._selected_manifest
        if m is None or self._selected_ipsw_path is None:
            self.ipsw_summary_lbl.setText(
                "Нажмите кнопку выше или перетащите скачанный файл прошивки .ipsw прямо в это окно."
            )
            return
        models_preview = ", ".join(m.supported_product_types[:5])
        if len(m.supported_product_types) > 5:
            models_preview += f" (+{len(m.supported_product_types) - 5})"
        self.ipsw_summary_lbl.setText(
            f"Выбран файл: {breakable(m.file_name)} ({human_bytes(m.file_size)})\n"
            f"Версия ОС: {m.product_version} · Сборка: {m.build_version} · Модели: {models_preview or '—'}"
        )

    def _refresh_compatibility(self) -> None:
        act = self.current_action()
        if act == "erase":
            self.mode_hint_lbl.setText(
                "Внимание: все пользовательские данные на устройстве будут удалены. Если был включён «Локатор» (Find My), после прошивки потребуется пароль Apple ID владельца."
            )
        elif act == "revive_mac":
            self.mode_hint_lbl.setText(
                "Обновит прошивку загрузчика и чипа безопасности MacBook в режиме DFU без удаления файлов пользователя."
            )
        else:
            self.mode_hint_lbl.setText(
                "Режим обновления установит систему поверх текущей — фотографии, контакты и приложения сохранятся."
            )

        if self._selected_manifest is None:
            set_pill(self.compat_pill, "Файл не выбран", "neutral")
            self.verdict_frame.setObjectName("Card")
            self._repolish(self.verdict_frame)
            self.verdict_title_lbl.setText(
                "Выберите локальный файл прошивки .ipsw на компьютере, чтобы проверить его совместимость."
            )
            self.verdict_details_lbl.hide()
            return

        dev = self.current_device()
        verdict = evaluate_compatibility(dev, self._selected_manifest, act)
        if verdict.level == "compatible":
            set_pill(self.compat_pill, "Совместима", "ok")
            self.verdict_frame.setObjectName("OkBanner")
        elif verdict.level == "warning":
            set_pill(self.compat_pill, "Проверьте условия", "warning")
            self.verdict_frame.setObjectName("WarnBanner")
        else:
            set_pill(self.compat_pill, "Не подходит", "danger")
            self.verdict_frame.setObjectName("ErrBanner")
        self._repolish(self.verdict_frame)

        self.verdict_title_lbl.setText(verdict.headline)
        if verdict.details:
            self.verdict_details_lbl.setText("\n".join(f"• {d}" for d in verdict.details[:3]))
            self.verdict_details_lbl.show()
        else:
            self.verdict_details_lbl.hide()

    @staticmethod
    def _repolish(widget: QWidget) -> None:
        widget.style().unpolish(widget)
        widget.style().polish(widget)

    def _toggle_shsh_row(self) -> None:
        self.shsh_box.setVisible(not self.shsh_box.isVisible())

    def _browse_shsh(self) -> None:
        f_str, _ = QFileDialog.getOpenFileName(
            self,
            "Выберите файл билета SHSH / SHSH2",
            str(Path.home()),
            "SHSH blobs (*.shsh *.shsh2 *.plist);;Все файлы (*.*)",
        )
        if f_str:
            self._selected_shsh_path = Path(f_str)
            self.shsh_edit.setText(f_str)

    def _clear_shsh(self) -> None:
        self._selected_shsh_path = None
        self.shsh_edit.clear()

    def _open_apple_devices_store(self) -> None:
        if not QDesktopServices.openUrl(QUrl("ms-windows-store://pdp/?ProductId=9NP83LWLPZ9K")):
            QDesktopServices.openUrl(QUrl("https://apps.microsoft.com/detail/9NP83LWLPZ9K"))

    # ==================== Запуск прошивки и быстрых команд USB ====================
    def _run_quick_device_action(self, action: str) -> None:
        if self.is_busy:
            return
        dev = self.current_device()
        if dev is None:
            QMessageBox.information(self, "Нет устройства", "Подключите устройство Apple по USB.")
            return
        job = FlashJobConfig(
            action=action,
            device=dev,
            dry_run=bool(dev.is_virtual),
        )
        self._launch_worker(job)

    def _on_start_flash_clicked(self) -> None:
        if self.is_busy:
            return
        dev = self.current_device()
        if dev is None:
            QMessageBox.warning(
                self,
                "Устройство не подключено",
                "Сначала подключите iPhone, iPad или MacBook кабелем USB к компьютеру.\n\n"
                "Если устройство не включается — переведите его в режим Recovery или DFU (см. вкладку «Вход в Recovery и DFU»).",
            )
            return

        if self._selected_ipsw_path is None or self._selected_manifest is None:
            QMessageBox.warning(
                self,
                "Не выбран файл прошивки",
                "Нажмите «Выбрать файл .ipsw на компьютере…» и укажите скачанный файл прошивки для вашего устройства.",
            )
            return

        action = self.current_action()
        verdict = evaluate_compatibility(dev, self._selected_manifest, action)
        if not verdict.can_proceed:
            QMessageBox.critical(
                self,
                "Прошивка заблокирована защитой совместимости",
                f"{verdict.headline}\n\n" + "\n".join(verdict.details),
            )
            return

        is_test = bool(dev.is_virtual or self._selected_manifest.is_demo_mockup)
        if action == "erase" and not is_test:
            ans = QMessageBox.warning(
                self,
                "Подтверждение полной перепрошивки со сбросом",
                f"Вы выбрали ЧИСТУЮ ПЕРЕПРОШИВКУ устройства «{dev.display_title}».\n\n"
                f"Файл прошивки: {self._selected_manifest.file_name} (ОС {self._selected_manifest.product_version})\n\n"
                "ВСЕ ДАННЫЕ, ФОТО И НАСТРОЙКИ НА УСТРОЙСТВЕ БУДУТ УДАЛЕНЫ!\n"
                "Не отсоединяйте USB-кабель до завершения процесса.\n\n"
                "Начать прошивку?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if ans != QMessageBox.Yes:
                return

        job = FlashJobConfig(
            action=action,
            device=dev,
            ipsw_path=self._selected_ipsw_path,
            shsh_path=self._selected_shsh_path,
            dry_run=is_test,
        )
        self._launch_worker(job)

    def _launch_worker(self, job: FlashJobConfig) -> None:
        self.log_box.clear()
        self.progress_bar.setValue(2)
        self.stage_lbl.setText("Запуск операции…")
        self.start_flash_btn.setEnabled(False)
        self.pick_ipsw_btn.setEnabled(False)
        self.cancel_btn.setEnabled(True)

        self._worker = FlashWorker(self.context.flash_engine, job, self)
        self._worker.progress.connect(self._on_worker_progress)
        self._worker.log_line.connect(self._on_worker_log)
        self._worker.finished_session.connect(self._on_worker_finished)
        self._worker.failed.connect(self._on_worker_failed)
        self._worker.start()

    def _on_cancel_clicked(self) -> None:
        if self._worker is not None:
            self._worker.cancel()
            self.stage_lbl.setText("Остановка операции…")

    def _on_worker_progress(self, pct: int, stage: str) -> None:
        self.progress_bar.setValue(max(0, min(100, pct)))
        self.stage_lbl.setText(stage)

    def _on_worker_log(self, line: str) -> None:
        if line:
            self.log_box.appendPlainText(line)

    def _on_worker_finished(self, session: FlashSessionRecord) -> None:
        self.start_flash_btn.setEnabled(True)
        self.pick_ipsw_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)
        self._worker = None
        self.window.refresh_devices()

        if session.status == "success":
            self.progress_bar.setValue(100)
            QMessageBox.information(
                self,
                "Операция выполнена",
                f"Операция успешно завершена!\n\nУстройство: {session.device_title}",
            )
        elif session.status == "failed":
            last_lines = "\n".join(session.log_text.splitlines()[-4:])
            QMessageBox.warning(
                self,
                "Операция не завершена",
                f"Не удалось завершить операцию для «{session.device_title}».\n\n{last_lines}",
            )

    def _on_worker_failed(self, err_msg: str) -> None:
        self.start_flash_btn.setEnabled(True)
        self.pick_ipsw_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)
        self._worker = None
        self.stage_lbl.setText(f"Ошибка: {err_msg}")
        self.log_box.appendPlainText(f"[ОШИБКА] {err_msg}")
        QMessageBox.critical(self, "Ошибка выполнения", err_msg)

    def _save_log_to_file(self) -> None:
        text = self.log_box.toPlainText().strip()
        if not text:
            QMessageBox.information(self, "Журнал пуст", "Пока нет записей для сохранения.")
            return
        out_str, _ = QFileDialog.getSaveFileName(
            self,
            "Сохранить журнал прошивки",
            str(Path.home() / "apple_flash_log.txt"),
            "Текстовые файлы (*.txt);;Все файлы (*.*)",
        )
        if out_str:
            Path(out_str).write_text(text, encoding="utf-8")
