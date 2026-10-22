"""Тёмная студийная тема оформления Apple Flash Studio (Space Graphite + Cupertino Blue)."""

from __future__ import annotations

from PySide6.QtGui import QColor, QFont, QPalette
from PySide6.QtWidgets import QApplication

STUDIO_COLORS = {
    "bg": "#0b0e14",
    "bg_alt": "#10151f",
    "surface": "#151c28",
    "surface_alt": "#1b2434",
    "surface_hover": "#222e42",
    "border": "#263247",
    "border_strong": "#354766",
    "text": "#eef3fb",
    "text_muted": "#98abc6",
    "text_dim": "#6e82a0",
    "accent": "#0a84ff",
    "accent_hover": "#3399ff",
    "accent_pressed": "#006ee6",
    "accent_soft": "#132c4c",
    "success": "#30d158",
    "warning": "#ff9f0a",
    "danger": "#ff453a",
}

FONT_STACK = ["Segoe UI", "Inter", "Noto Sans", "DejaVu Sans", "Arial"]

STUDIO_QSS = """
* {{
    font-family: "Segoe UI", "Inter", "Noto Sans", "DejaVu Sans", sans-serif;
    font-size: 13px;
    color: {text};
    outline: none;
}}

QMainWindow, QDialog, QWidget#StudioRoot {{
    background-color: {bg};
}}

QFrame#Sidebar {{
    background-color: {bg_alt};
    border-right: 1px solid {border};
}}
QFrame#TopBar {{
    background-color: {bg_alt};
    border-bottom: 1px solid {border};
}}
QLabel#AppTitle {{
    font-size: 15px;
    font-weight: 700;
    color: #ffffff;
}}
QLabel#AppSub {{
    font-size: 10px;
    color: {accent};
    font-weight: 600;
    letter-spacing: 1.1px;
}}
QLabel#NavHeader {{
    font-size: 10px;
    font-weight: 700;
    color: {text_dim};
    letter-spacing: 1.3px;
    padding: 12px 12px 4px 12px;
}}
QPushButton#NavBtn {{
    background: transparent;
    border: none;
    border-radius: 9px;
    padding: 9px 12px;
    text-align: left;
    color: {text_muted};
    font-size: 13px;
}}
QPushButton#NavBtn:hover {{
    background-color: {surface_alt};
    color: {text};
}}
QPushButton#NavTab {{
    background: transparent;
    border: 1px solid transparent;
    border-radius: 9px;
    padding: 8px 16px;
    color: {text_muted};
    font-size: 13px;
    font-weight: 600;
}}
QPushButton#NavTab:hover {{
    background-color: {surface_alt};
    color: {text};
}}
QPushButton#NavTab:checked {{
    background-color: {accent_soft};
    border: 1px solid rgba(10, 132, 255, 0.55);
    color: #ffffff;
}}
QPushButton#FlashActionBtn {{
    background-color: {accent};
    border: 1px solid {accent};
    border-radius: 10px;
    padding: 11px 20px;
    color: #ffffff;
    font-size: 15px;
    font-weight: 700;
}}
QPushButton#FlashActionBtn:hover {{
    background-color: {accent_hover};
    border-color: {accent_hover};
}}
QPushButton#FlashActionBtn:disabled {{
    background-color: {surface_alt};
    border-color: {border};
    color: {text_dim};
}}
QFrame#WarnBanner {{
    background-color: rgba(255, 159, 10, 0.13);
    border: 1px solid rgba(255, 159, 10, 0.48);
    border-radius: 10px;
}}
QFrame#OkBanner {{
    background-color: rgba(48, 209, 88, 0.12);
    border: 1px solid rgba(48, 209, 88, 0.44);
    border-radius: 10px;
}}
QFrame#ErrBanner {{
    background-color: rgba(255, 69, 58, 0.13);
    border: 1px solid rgba(255, 69, 58, 0.48);
    border-radius: 10px;
}}

/* Карточки */
QFrame#Card {{
    background-color: {surface};
    border: 1px solid {border};
    border-radius: 12px;
}}
QFrame#HeroCard {{
    background-color: {surface_alt};
    border: 1px solid {border_strong};
    border-radius: 14px;
}}
QFrame#MetricTile {{
    background-color: {surface};
    border: 1px solid {border};
    border-radius: 11px;
}}
QLabel#PageTitle {{
    font-size: 21px;
    font-weight: 700;
    color: #ffffff;
}}
QLabel#CardTitle {{
    font-size: 15px;
    font-weight: 600;
    color: #ffffff;
}}
QLabel#HeroTitle {{
    font-size: 20px;
    font-weight: 700;
    color: #ffffff;
}}
QLabel#BigTimer {{
    font-size: 38px;
    font-weight: 800;
    color: {accent};
}}
QLabel#MetricValue {{
    font-size: 21px;
    font-weight: 700;
    color: #ffffff;
}}
QLabel#Muted {{
    color: {text_muted};
    font-size: 12px;
}}
QLabel#Dim {{
    color: {text_dim};
    font-size: 11px;
}}

/* Бейджи */
QLabel#Pill {{
    border-radius: 9px;
    padding: 4px 12px;
    font-size: 11px;
    font-weight: 600;
}}
QLabel#Pill[tone="ok"] {{
    background-color: rgba(48, 209, 88, 0.16);
    color: {success};
    border: 1px solid rgba(48, 209, 88, 0.42);
}}
QLabel#Pill[tone="info"] {{
    background-color: rgba(10, 132, 255, 0.16);
    color: #5cb0ff;
    border: 1px solid rgba(10, 132, 255, 0.45);
}}
QLabel#Pill[tone="warning"] {{
    background-color: rgba(255, 159, 10, 0.16);
    color: {warning};
    border: 1px solid rgba(255, 159, 10, 0.45);
}}
QLabel#Pill[tone="danger"] {{
    background-color: rgba(255, 69, 58, 0.16);
    color: {danger};
    border: 1px solid rgba(255, 69, 58, 0.45);
}}
QLabel#Pill[tone="neutral"] {{
    background-color: {surface_alt};
    color: {text_muted};
    border: 1px solid {border};
}}

/* Кнопки */
QPushButton {{
    background-color: {surface_alt};
    color: {text};
    border: 1px solid {border};
    border-radius: 8px;
    padding: 7px 14px;
}}
QPushButton:hover {{
    background-color: {surface_hover};
    border-color: {border_strong};
}}
QPushButton:disabled {{
    color: {text_dim};
    background-color: {bg_alt};
    border-color: {border};
}}
QPushButton#Primary {{
    background-color: {accent};
    border: 1px solid {accent};
    color: #ffffff;
    font-weight: 600;
}}
QPushButton#Primary:hover {{
    background-color: {accent_hover};
    border-color: {accent_hover};
}}
QPushButton#Primary:pressed {{
    background-color: {accent_pressed};
}}
QPushButton#Danger {{
    background-color: rgba(255, 69, 58, 0.12);
    border: 1px solid {danger};
    color: #ff6961;
    font-weight: 600;
}}
QPushButton#Danger:hover {{
    background-color: rgba(255, 69, 58, 0.24);
}}
QPushButton#Ghost {{
    background: transparent;
    border: 1px solid {border};
    color: {text_muted};
}}
QPushButton#Ghost:hover {{
    background-color: {surface_alt};
    color: {text};
}}

/* Поля ввода */
QLineEdit, QPlainTextEdit, QTextEdit, QComboBox {{
    background-color: {bg_alt};
    border: 1px solid {border};
    border-radius: 8px;
    padding: 7px 10px;
    selection-background-color: {accent};
    selection-color: #ffffff;
}}
QLineEdit:focus, QPlainTextEdit:focus, QTextEdit:focus, QComboBox:focus {{
    border-color: {accent};
}}
QPlainTextEdit#ConsoleBox {{
    background-color: #070a0f;
    border: 1px solid {border};
    border-radius: 10px;
    font-family: "Cascadia Mono", "Consolas", "DejaVu Sans Mono", monospace;
    font-size: 12px;
    color: #c9d8ee;
    padding: 8px;
}}
QLineEdit#CmdPreview {{
    background-color: #070a0f;
    border: 1px solid {border};
    font-family: "Cascadia Mono", "Consolas", "DejaVu Sans Mono", monospace;
    font-size: 12px;
    color: #7cc0ff;
}}
QComboBox::drop-down {{
    border: none;
    width: 24px;
}}
QComboBox QAbstractItemView {{
    background-color: {surface_alt};
    border: 1px solid {border_strong};
    selection-background-color: {accent_soft};
    selection-color: #ffffff;
    padding: 4px;
}}
QCheckBox, QRadioButton {{
    color: {text};
    spacing: 8px;
}}
QCheckBox::indicator, QRadioButton::indicator {{
    width: 16px;
    height: 16px;
    border: 1px solid {border_strong};
    border-radius: 4px;
    background-color: {bg_alt};
}}
QRadioButton::indicator {{
    border-radius: 8px;
}}
QCheckBox::indicator:checked, QRadioButton::indicator:checked {{
    background-color: {accent};
    border-color: {accent};
}}

/* Таблицы и скролл */
QTableWidget, QTableView, QListWidget {{
    background-color: {surface};
    alternate-background-color: {bg_alt};
    border: 1px solid {border};
    border-radius: 10px;
    gridline-color: {border};
    selection-background-color: {accent_soft};
    selection-color: #ffffff;
}}
QHeaderView::section {{
    background-color: {bg_alt};
    color: {text_muted};
    border: none;
    border-bottom: 1px solid {border};
    border-right: 1px solid {border};
    padding: 7px 8px;
    font-size: 11px;
    font-weight: 600;
}}
QProgressBar {{
    background-color: {bg_alt};
    border: 1px solid {border};
    border-radius: 7px;
    text-align: center;
    color: #ffffff;
    font-weight: 600;
    min-height: 18px;
}}
QProgressBar::chunk {{
    background-color: {accent};
    border-radius: 6px;
}}
QScrollArea {{
    border: none;
    background: transparent;
}}
QScrollBar:vertical {{
    background: transparent;
    width: 10px;
}}
QScrollBar::handle:vertical {{
    background: {border_strong};
    border-radius: 5px;
    min-height: 28px;
}}
QStatusBar {{
    background-color: {bg_alt};
    border-top: 1px solid {border};
    color: {text_dim};
}}
QFrame#Divider {{
    background-color: {border};
    max-height: 1px;
}}
"""


def apply_studio_theme(app: QApplication) -> None:
    app.setStyle("Fusion")
    pal = QPalette()
    pal.setColor(QPalette.Window, QColor(STUDIO_COLORS["bg"]))
    pal.setColor(QPalette.WindowText, QColor(STUDIO_COLORS["text"]))
    pal.setColor(QPalette.Base, QColor(STUDIO_COLORS["bg_alt"]))
    pal.setColor(QPalette.AlternateBase, QColor(STUDIO_COLORS["surface"]))
    pal.setColor(QPalette.Text, QColor(STUDIO_COLORS["text"]))
    pal.setColor(QPalette.Button, QColor(STUDIO_COLORS["surface_alt"]))
    pal.setColor(QPalette.ButtonText, QColor(STUDIO_COLORS["text"]))
    pal.setColor(QPalette.Highlight, QColor(STUDIO_COLORS["accent"]))
    pal.setColor(QPalette.HighlightedText, QColor("#ffffff"))
    pal.setColor(QPalette.PlaceholderText, QColor(STUDIO_COLORS["text_dim"]))
    app.setPalette(pal)

    font = QFont()
    font.setFamilies(FONT_STACK)
    font.setPointSize(9 if app.platformName() == "windows" else 10)
    app.setFont(font)
    app.setStyleSheet(STUDIO_QSS.format(**STUDIO_COLORS))
