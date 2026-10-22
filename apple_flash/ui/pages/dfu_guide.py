"""Интерактивный мастер перевода iPhone, iPad и MacBook в режимы DFU и Recovery с таймером по секундам."""

from __future__ import annotations

from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from apple_flash.data.apple_catalog import DFU_PROCEDURES, DfuProcedure
from apple_flash.services.context import StudioContext
from apple_flash.ui.widgets import (
    StudioCard,
    clear_layout,
    make_divider,
    make_muted,
    make_pill,
    make_title,
)


class DfuGuidePage(QWidget):
    def __init__(self, context: StudioContext, window) -> None:
        super().__init__()
        self.context = context
        self.window = window
        self._current_proc: DfuProcedure = DFU_PROCEDURES["iphone_faceid"]
        self._step_idx: int = 0
        self._seconds_left: int = 0
        self._step_total: int = 0

        self._timer = QTimer(self)
        self._timer.setInterval(1000)
        self._timer.timeout.connect(self._on_tick)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        outer.addWidget(scroll)

        content = QWidget(scroll)
        scroll.setWidget(content)
        layout = QVBoxLayout(content)
        layout.setContentsMargins(22, 16, 22, 16)
        layout.setSpacing(12)

        head = QHBoxLayout()
        vbox = QVBoxLayout()
        vbox.setSpacing(2)
        vbox.addWidget(make_title("Как перевести устройство в Recovery или DFU", object_name="PageTitle"))
        vbox.addWidget(
            make_muted(
                "Выберите вашу модель ниже — секундомер подскажет, сколько секунд удерживать каждую кнопку."
            )
        )
        head.addLayout(vbox, 1)

        self.proc_combo = QComboBox(content)
        self.proc_combo.setMinimumWidth(420)
        for key, proc in DFU_PROCEDURES.items():
            self.proc_combo.addItem(proc.title, key)
        self.proc_combo.currentIndexChanged.connect(self._on_proc_changed)
        head.addWidget(self.proc_combo)
        layout.addLayout(head)

        # Тренажёр с таймером
        trainer = StudioCard(content, hero=True)
        tb = trainer.body()
        top_row = QHBoxLayout()
        top_row.addWidget(make_title("Интерактивный секундомер DFU", parent=trainer), 1)
        self.status_pill = make_pill("Готов к старту", "info", trainer)
        top_row.addWidget(self.status_pill)
        tb.addLayout(top_row)

        mid_row = QHBoxLayout()
        self.timer_lbl = QLabel("00 с", trainer)
        self.timer_lbl.setObjectName("BigTimer")
        self.timer_lbl.setMinimumWidth(120)
        self.timer_lbl.setAlignment(Qt.AlignCenter)
        mid_row.addWidget(self.timer_lbl)

        step_col = QVBoxLayout()
        self.active_step_title = make_title("Нажмите «Запустить тренажёр DFU» для отсчёта по шагам", parent=trainer)
        self.cable_lbl = make_muted("", trainer)
        step_col.addWidget(self.active_step_title)
        step_col.addWidget(self.cable_lbl)
        mid_row.addLayout(step_col, 1)
        tb.addLayout(mid_row)

        self.step_progress = QProgressBar(trainer)
        self.step_progress.setRange(0, 100)
        self.step_progress.setValue(0)
        tb.addWidget(self.step_progress)

        ctrl = QHBoxLayout()
        self.start_btn = QPushButton("▶ Запустить тренажёр DFU", trainer)
        self.start_btn.setObjectName("Primary")
        self.start_btn.clicked.connect(self._start_trainer)
        self.next_btn = QPushButton("Следующий шаг →", trainer)
        self.next_btn.clicked.connect(self._advance_step)
        self.stop_btn = QPushButton("Сброс", trainer)
        self.stop_btn.setObjectName("Ghost")
        self.stop_btn.clicked.connect(self._reset_trainer)
        ctrl.addWidget(self.start_btn)
        ctrl.addWidget(self.next_btn)
        ctrl.addWidget(self.stop_btn)
        ctrl.addStretch(1)
        tb.addLayout(ctrl)
        layout.addWidget(trainer)

        # Полная карточка шагов DFU + Recovery + схема портов MacBook
        self.steps_card = StudioCard(content)
        self.steps_body = self.steps_card.body()
        layout.addWidget(self.steps_card)
        layout.addStretch(1)

        self._render_procedure()

    def select_procedure(self, key: str) -> None:
        idx = self.proc_combo.findData(key)
        if idx >= 0:
            self.proc_combo.setCurrentIndex(idx)

    def on_show(self) -> None:
        self._render_procedure()

    def _on_proc_changed(self) -> None:
        key = self.proc_combo.currentData()
        if key in DFU_PROCEDURES:
            self._current_proc = DFU_PROCEDURES[key]
        self._reset_trainer()
        self._render_procedure()

    def _render_procedure(self) -> None:
        proc = self._current_proc
        self.cable_lbl.setText(proc.cable_note)
        clear_layout(self.steps_body)

        self.steps_body.addWidget(make_title(f"Пошаговый вход в DFU — {proc.title}"))
        self.steps_body.addWidget(make_muted(proc.summary, self.steps_card))

        for i, (text, secs) in enumerate(proc.steps, start=1):
            dur = f"  [{secs} сек]" if secs > 0 else ""
            lbl = QLabel(f"{i}. {text}{dur}", self.steps_card)
            lbl.setWordWrap(True)
            self.steps_body.addWidget(lbl)

        if proc.port_diagram:
            self.steps_body.addWidget(make_divider(self.steps_card))
            self.steps_body.addWidget(make_title("Расположение сервисного DFU-порта USB-C на MacBook"))
            port_lbl = make_muted(proc.port_diagram, self.steps_card)
            self.steps_body.addWidget(port_lbl)

        self.steps_body.addWidget(make_divider(self.steps_card))
        self.steps_body.addWidget(make_title("Альтернатива: вход в стандартный режим Recovery"))
        for i, r_step in enumerate(proc.recovery_steps, start=1):
            rlbl = make_muted(f"{i}. {r_step}", self.steps_card)
            self.steps_body.addWidget(rlbl)

    def _start_trainer(self) -> None:
        self._step_idx = 0
        self._load_current_step()

    def _reset_trainer(self) -> None:
        self._timer.stop()
        self._step_idx = 0
        self._seconds_left = 0
        self.timer_lbl.setText("00 с")
        self.step_progress.setValue(0)
        self.active_step_title.setText("Нажмите «Запустить тренажёр DFU» для отсчёта по шагам")

    def _load_current_step(self) -> None:
        steps = self._current_proc.steps
        if self._step_idx >= len(steps):
            self._timer.stop()
            self.timer_lbl.setText("DFU")
            self.step_progress.setValue(100)
            self.active_step_title.setText("Последовательность завершена! Проверяем шину USB…")
            self.window.refresh_devices()
            return

        text, secs = steps[self._step_idx]
        total_steps = len(steps)
        self.active_step_title.setText(f"Шаг {self._step_idx + 1} из {total_steps}: {text}")
        if secs <= 0:
            self._timer.stop()
            self._seconds_left = 0
            self.timer_lbl.setText("—")
            self.step_progress.setValue(int((self._step_idx + 1) * 100 / total_steps))
        else:
            self._step_total = secs
            self._seconds_left = secs
            self.timer_lbl.setText(f"{secs:02d} с")
            self.step_progress.setValue(0)
            self._timer.start()

    def _advance_step(self) -> None:
        self._timer.stop()
        self._step_idx += 1
        self._load_current_step()

    def _on_tick(self) -> None:
        self._seconds_left -= 1
        if self._seconds_left <= 0:
            self._advance_step()
            return
        self.timer_lbl.setText(f"{self._seconds_left:02d} с")
        if self._step_total > 0:
            done = self._step_total - self._seconds_left
            self.step_progress.setValue(int(done * 100 / self._step_total))
