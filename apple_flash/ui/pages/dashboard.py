"""Главная страница: подключённое устройство Apple, быстрые операции Recovery и сводка станции."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QHBoxLayout,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from apple_flash.data.models import ConnectedDevice, FlashJobConfig
from apple_flash.services.context import StudioContext
from apple_flash.ui.widgets import (
    MetricTile,
    StudioCard,
    clear_layout,
    kv_row,
    make_divider,
    make_muted,
    make_pill,
    make_title,
)


class DashboardPage(QWidget):
    def __init__(self, context: StudioContext, window) -> None:
        super().__init__()
        self.context = context
        self.window = window

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        outer.addWidget(scroll)

        content = QWidget(scroll)
        scroll.setWidget(content)
        layout = QVBoxLayout(content)
        layout.setSizeConstraint(QVBoxLayout.SetMinAndMaxSize)
        layout.setContentsMargins(22, 18, 22, 18)
        layout.setSpacing(14)

        head = QHBoxLayout()
        title_box = QVBoxLayout()
        title_box.setSpacing(2)
        title_box.addWidget(make_title("Станция перепрошивки Apple", object_name="PageTitle"))
        title_box.addWidget(
            make_muted(
                "Локальная прошивка и восстановление iPhone, iPad и MacBook (Apple Silicon M1–M4 / Intel T2) на Windows 10/11."
            )
        )
        head.addLayout(title_box, 1)

        scan_btn = QPushButton("Обновить USB", content)
        scan_btn.setObjectName("Ghost")
        scan_btn.clicked.connect(self.window.refresh_devices)
        head.addWidget(scan_btn)

        flash_btn = QPushButton("Открыть мастер прошивки →", content)
        flash_btn.setObjectName("Primary")
        flash_btn.clicked.connect(lambda: self.window.navigate("flash"))
        head.addWidget(flash_btn)
        layout.addLayout(head)

        # Плитки метрик
        metrics_row = QHBoxLayout()
        metrics_row.setSpacing(10)
        self.tile_devices = MetricTile("Устройств на шине USB", "0", content)
        self.tile_ipsw = MetricTile("Образов .ipsw в библиотеке", "0", content)
        self.tile_sessions = MetricTile("Записей в журнале", "0", content)
        self.tile_backend = MetricTile("Активный CLI-движок", "Авто", content)
        for tile in (self.tile_devices, self.tile_ipsw, self.tile_sessions, self.tile_backend):
            metrics_row.addWidget(tile, 1)
        layout.addLayout(metrics_row)

        # Карточка активного устройства
        self.device_card = StudioCard(content, hero=True)
        self.device_body = self.device_card.body()
        layout.addWidget(self.device_card)

        # Три платформы: iPhone, iPad, MacBook
        fam_row = QHBoxLayout()
        fam_row.setSpacing(12)
        for fam_title, badge_txt, desc, dfu_key in (
            (
                "iPhone (iOS)",
                "Lightning / USB-C",
                "Обновление с сохранением данных (Update), чистый сброс (Clean Restore) и вывод из петли Recovery в 1 клик.",
                "iphone_faceid",
            ),
            (
                "iPad (iPadOS)",
                "A-серия и M1–M4",
                "Проверка точного ProductType (Wi-Fi vs Cellular) по BuildManifest.plist перед прошивкой исключает ошибку несовместимого образа.",
                "ipad_top_button",
            ),
            (
                "MacBook (M1–M4 и T2)",
                "DFU USB-C Revive / Restore",
                "Оживление контроллера без потери данных (Revive) и полная перепрошивка UniversalMac / bridgeOS .ipsw через сервисный DFU-порт.",
                "mac_apple_silicon",
            ),
        ):
            card = StudioCard(content)
            cb = card.body()
            top = QHBoxLayout()
            top.addWidget(make_title(fam_title, parent=card), 1)
            top.addWidget(make_pill(badge_txt, "info", card))
            cb.addLayout(top)
            cb.addWidget(make_muted(desc, card))
            cb.addStretch(1)
            guide_btn = QPushButton("Как перевести в DFU →", card)
            guide_btn.setObjectName("Ghost")
            guide_btn.clicked.connect(lambda _c=False, k=dfu_key: self.window.open_dfu_guide(k))
            cb.addWidget(guide_btn)
            fam_row.addWidget(card, 1)
        layout.addLayout(fam_row)
        layout.addStretch(1)

    def on_show(self) -> None:
        devices = self.window.connected_devices
        ipsw_rows = self.context.store.list_ipsw()
        sessions = self.context.store.list_sessions(limit=500)
        pref_backend = self.context.store.get_setting("preferred_backend", "auto")
        resolved = self.context.flash_engine.resolve_backend(pref_backend)

        self.tile_devices.set_value(str(len(devices)))
        self.tile_ipsw.set_value(str(len(ipsw_rows)))
        self.tile_sessions.set_value(str(len(sessions)))
        self.tile_backend.set_value(resolved)

        self._render_device_card(devices[0] if devices else None)

    def _render_device_card(self, dev: ConnectedDevice | None) -> None:
        clear_layout(self.device_body)
        if dev is None:
            top = QHBoxLayout()
            top.addWidget(make_title("Устройство Apple не обнаружено", object_name="HeroTitle"))
            top.addStretch(1)
            top.addWidget(make_pill("Ожидание USB", "neutral"))
            self.device_body.addLayout(top)
            self.device_body.addWidget(
                make_muted(
                    "Подключите iPhone, iPad или MacBook (в режиме Normal, Recovery или DFU) кабелем напрямую к USB-порту ПК Windows.\n"
                    "Для знакомства с интерфейсом без кабеля можно включить тестовый макет на верхней панели («Тестовый стенд»)."
                )
            )
            btn_row = QHBoxLayout()
            btn_lib = QPushButton("Открыть библиотеку .ipsw", self.device_card)
            btn_lib.clicked.connect(lambda: self.window.navigate("library"))
            btn_drv = QPushButton("Проверить драйверы Windows", self.device_card)
            btn_drv.setObjectName("Ghost")
            btn_drv.clicked.connect(lambda: self.window.navigate("drivers"))
            btn_mock = QPushButton("Подключить макет MacBook M3 (DFU)", self.device_card)
            btn_mock.setObjectName("Ghost")
            btn_mock.clicked.connect(lambda: self.window.select_virtual_preset("macbook_dfu"))
            btn_row.addWidget(btn_lib)
            btn_row.addWidget(btn_drv)
            btn_row.addWidget(btn_mock)
            btn_row.addStretch(1)
            self.device_body.addLayout(btn_row)
            return

        tone = "warning" if dev.is_virtual else ("ok" if dev.mode == "normal" else "info")
        top = QHBoxLayout()
        top.addWidget(make_title(dev.display_title, object_name="HeroTitle"))
        top.addStretch(1)
        if dev.is_virtual:
            top.addWidget(make_pill("ТЕСТОВЫЙ МАКЕТ (только Dry-Run)", "warning"))
        top.addWidget(make_pill(dev.mode_label, tone))
        self.device_body.addLayout(top)

        cols = QHBoxLayout()
        left_col = QVBoxLayout()
        right_col = QVBoxLayout()
        for k, v in (
            ("Семейство:", dev.family_label),
            ("Код модели (ProductType):", dev.product_type or "Скрыт в DFU (определяется по CPID)"),
            ("Процессор / CPID:", dev.chip_label),
            ("Плата (BoardConfig):", dev.board_config or "—"),
        ):
            left_col.addWidget(kv_row(k, v, self.device_card))
        for k, v in (
            ("Идентификатор ECID / UDID:", dev.ecid or dev.udid or dev.uid),
            ("Текущая версия ОС:", f"{dev.os_version or '—'} ({dev.build_version or '—'})"),
            ("Драйвер USB Windows:", dev.usb_driver or dev.source_backend),
            ("Заряд аккумулятора:", f"{dev.battery_percent}%" if dev.battery_percent is not None else "—"),
        ):
            right_col.addWidget(kv_row(k, v, self.device_card))
        cols.addLayout(left_col, 1)
        cols.addLayout(right_col, 1)
        self.device_body.addLayout(cols)
        self.device_body.addWidget(make_divider(self.device_card))

        actions = QHBoxLayout()
        go_flash = QPushButton("Выбрать .ipsw и прошить →", self.device_card)
        go_flash.setObjectName("Primary")
        go_flash.clicked.connect(lambda: self.window.open_flash_for_device(dev))
        actions.addWidget(go_flash)

        exit_rec = QPushButton("Выйти из Recovery (1 клик)", self.device_card)
        exit_rec.setObjectName("Ghost")
        exit_rec.clicked.connect(lambda: self._quick_recovery_action(dev, "exit_recovery"))
        actions.addWidget(exit_rec)

        enter_rec = QPushButton("Ввести в Recovery", self.device_card)
        enter_rec.setObjectName("Ghost")
        enter_rec.clicked.connect(lambda: self._quick_recovery_action(dev, "enter_recovery"))
        actions.addWidget(enter_rec)

        dfu_map = {
            "iphone": "iphone_faceid",
            "ipad": "ipad_top_button",
            "macbook": "mac_apple_silicon",
        }
        dfu_btn = QPushButton("Инструкция DFU для этой модели", self.device_card)
        dfu_btn.setObjectName("Ghost")
        dfu_btn.clicked.connect(
            lambda: self.window.open_dfu_guide(dfu_map.get(dev.family, "iphone_faceid"))
        )
        actions.addWidget(dfu_btn)
        actions.addStretch(1)
        self.device_body.addLayout(actions)

    def _quick_recovery_action(self, dev: ConnectedDevice, action: str) -> None:
        dry = dev.is_virtual
        job = FlashJobConfig(
            action=action,
            device=dev,
            backend=self.context.store.get_setting("preferred_backend", "auto"),
            dry_run=dry,
        )
        try:
            session = self.context.flash_engine.execute(job, dry_run_step_delay=0.0)
            mode_note = " (в режиме Dry-Run для макета)" if dry else ""
            QMessageBox.information(
                self,
                "Команда выполнена",
                f"Статус: {session.status}{mode_note}\nКоманда: {session.command_line}",
            )
            self.window.refresh_devices()
        except Exception as exc:
            QMessageBox.warning(self, "Не удалось выполнить команду", str(exc))
