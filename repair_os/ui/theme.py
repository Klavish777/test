"""Тёмная профессиональная тема оформления (QSS + палитра)."""

from __future__ import annotations

from PySide6.QtGui import QColor, QFont, QPalette
from PySide6.QtWidgets import QApplication

COLORS = {
    "bg": "#0a1220",
    "bg_alt": "#0d1728",
    "surface": "#111d30",
    "surface_alt": "#16243a",
    "surface_hover": "#1b2c46",
    "border": "#22334d",
    "border_strong": "#2c4264",
    "text": "#e6eef8",
    "text_muted": "#8ea5c0",
    "text_dim": "#6c86a5",
    "accent": "#3d8bfd",
    "accent_hover": "#5aa0ff",
    "accent_pressed": "#2f74d8",
    "accent_soft": "#173253",
    "success": "#2fbf71",
    "warning": "#f0a35e",
    "danger": "#e5534b",
    "demo": "#c98b3a",
}

FONT_FAMILIES = ["Segoe UI", "Inter", "Noto Sans", "DejaVu Sans", "Arial"]


QSS = """
* {{
    font-family: "Segoe UI", "Inter", "Noto Sans", "DejaVu Sans", sans-serif;
    font-size: 13px;
    color: {text};
    outline: none;
}}

QWidget#Root {{
    background-color: {bg};
}}

QMainWindow, QDialog {{
    background-color: {bg};
}}

QToolTip {{
    background-color: {surface_alt};
    color: {text};
    border: 1px solid {border_strong};
    padding: 6px 8px;
    border-radius: 6px;
}}

/* --------------------------------------------------------------- навигация */
QFrame#Sidebar {{
    background-color: {bg_alt};
    border-right: 1px solid {border};
}}
QLabel#BrandMark {{
    font-size: 15px;
    font-weight: 700;
    color: {text};
}}
QLabel#BrandSub {{
    font-size: 10px;
    color: {text_dim};
    letter-spacing: 1px;
}}
QPushButton#NavButton {{
    background: transparent;
    border: none;
    border-radius: 8px;
    padding: 9px 12px;
    text-align: left;
    color: {text_muted};
    font-size: 13px;
}}
QPushButton#NavButton:hover {{
    background-color: {surface_alt};
    color: {text};
}}
QPushButton#NavButton:checked {{
    background-color: {accent_soft};
    color: #ffffff;
    font-weight: 600;
    border-left: 3px solid {accent};
}}
QLabel#NavSection {{
    color: {text_dim};
    font-size: 10px;
    letter-spacing: 1.4px;
    padding: 14px 12px 4px 12px;
}}
QLabel#VersionLabel {{
    color: {text_dim};
    font-size: 10px;
    padding: 8px 12px;
}}

/* --------------------------------------------------------------- карточки */
QFrame#Card {{
    background-color: {surface};
    border: 1px solid {border};
    border-radius: 12px;
}}
QFrame#Card:hover {{
    border-color: {border_strong};
}}
QFrame#ClickableCard {{
    background-color: {surface};
    border: 1px solid {border};
    border-radius: 12px;
}}
QFrame#ClickableCard:hover {{
    background-color: {surface_alt};
    border-color: {accent};
}}
QFrame#StatTile {{
    background-color: {surface_alt};
    border: 1px solid {border};
    border-radius: 10px;
}}
QLabel#CardTitle {{
    font-size: 15px;
    font-weight: 600;
    color: {text};
}}
QLabel#SectionTitle {{
    font-size: 17px;
    font-weight: 700;
    color: {text};
}}
QLabel#PageTitle {{
    font-size: 22px;
    font-weight: 700;
    color: #ffffff;
}}
QLabel#PageSubtitle {{
    color: {text_muted};
    font-size: 12px;
}}
QLabel#Muted {{
    color: {text_muted};
    font-size: 12px;
}}
QLabel#Dim {{
    color: {text_dim};
    font-size: 11px;
}}
QLabel#MetricValue {{
    font-size: 22px;
    font-weight: 700;
    color: #ffffff;
}}
QLabel#MetricLabel {{
    color: {text_muted};
    font-size: 11px;
}}
QLabel#HeroTitle {{
    font-size: 26px;
    font-weight: 800;
    color: #ffffff;
}}
QLabel#FieldLabel {{
    color: {text_dim};
    font-size: 11px;
}}
QLabel#FieldValue {{
    color: {text};
    font-size: 13px;
}}

/* --------------------------------------------------------------- кнопки */
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
QPushButton:pressed {{
    background-color: {surface};
}}
QPushButton:disabled {{
    color: {text_dim};
    background-color: {surface};
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
QPushButton#Ghost {{
    background: transparent;
    border: 1px solid {border};
    color: {text_muted};
}}
QPushButton#Ghost:hover {{
    color: {text};
    border-color: {border_strong};
    background-color: {surface_alt};
}}
QPushButton#Danger {{
    background-color: transparent;
    border: 1px solid {danger};
    color: {danger};
}}
QPushButton#Danger:hover {{
    background-color: rgba(229, 83, 75, 0.14);
}}
QPushButton#LinkButton {{
    background: transparent;
    border: none;
    color: {accent};
    padding: 2px 4px;
    text-align: left;
}}
QPushButton#LinkButton:hover {{
    color: {accent_hover};
    text-decoration: underline;
}}
QToolButton {{
    background: transparent;
    border: none;
    color: {text_muted};
    padding: 4px 6px;
    border-radius: 6px;
}}
QToolButton:hover {{
    background-color: {surface_alt};
    color: {text};
}}

/* --------------------------------------------------------------- поля ввода */
QLineEdit, QTextEdit, QPlainTextEdit, QSpinBox, QDoubleSpinBox, QComboBox, QDateEdit {{
    background-color: {bg_alt};
    border: 1px solid {border};
    border-radius: 8px;
    padding: 7px 10px;
    selection-background-color: {accent};
    selection-color: #ffffff;
}}
QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus, QSpinBox:focus,
QDoubleSpinBox:focus, QComboBox:focus, QDateEdit:focus {{
    border-color: {accent};
}}
QLineEdit#SearchInput {{
    padding: 9px 12px;
    font-size: 14px;
    border-radius: 10px;
    background-color: {surface};
}}
QLineEdit#SearchInput:focus {{
    background-color: {surface_alt};
}}
QComboBox::drop-down {{
    border: none;
    width: 22px;
}}
QComboBox QAbstractItemView {{
    background-color: {surface_alt};
    border: 1px solid {border_strong};
    selection-background-color: {accent_soft};
    selection-color: #ffffff;
    padding: 4px;
}}
QCheckBox, QRadioButton {{
    color: {text_muted};
    spacing: 8px;
}}
QCheckBox::indicator, QRadioButton::indicator {{
    width: 15px;
    height: 15px;
    border: 1px solid {border_strong};
    border-radius: 4px;
    background-color: {bg_alt};
}}
QCheckBox::indicator:checked, QRadioButton::indicator:checked {{
    background-color: {accent};
    border-color: {accent};
}}
QRadioButton::indicator {{
    border-radius: 8px;
}}

/* --------------------------------------------------------------- вкладки */
QTabWidget::pane {{
    border: 1px solid {border};
    border-radius: 10px;
    background-color: {surface};
    top: -1px;
}}
QTabBar::tab {{
    background: transparent;
    color: {text_muted};
    padding: 8px 16px;
    border: none;
    border-bottom: 2px solid transparent;
    margin-right: 4px;
}}
QTabBar::tab:hover {{
    color: {text};
}}
QTabBar::tab:selected {{
    color: #ffffff;
    border-bottom: 2px solid {accent};
    font-weight: 600;
}}

/* --------------------------------------------------------------- таблицы */
QTableView, QTreeView, QListView {{
    background-color: {surface};
    alternate-background-color: {bg_alt};
    border: 1px solid {border};
    border-radius: 10px;
    gridline-color: {border};
    selection-background-color: {accent_soft};
    selection-color: #ffffff;
}}
QTableView::item, QTreeView::item {{
    padding: 5px 6px;
    border: none;
}}
QTableView::item:hover, QTreeView::item:hover {{
    background-color: {surface_alt};
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
QTableCornerButton::section {{
    background-color: {bg_alt};
    border: none;
}}

/* --------------------------------------------------------------- списки/скролл */
QListWidget {{
    background-color: transparent;
    border: none;
}}
QListWidget::item {{
    padding: 6px 8px;
    border-radius: 6px;
}}
QListWidget::item:hover {{
    background-color: {surface_alt};
}}
QListWidget::item:selected {{
    background-color: {accent_soft};
    color: #ffffff;
}}
QScrollArea {{
    border: none;
    background-color: transparent;
}}
QScrollBar:vertical {{
    background: transparent;
    width: 10px;
    margin: 2px;
}}
QScrollBar::handle:vertical {{
    background: {border_strong};
    border-radius: 5px;
    min-height: 30px;
}}
QScrollBar::handle:vertical:hover {{
    background: #3b567d;
}}
QScrollBar:horizontal {{
    background: transparent;
    height: 10px;
    margin: 2px;
}}
QScrollBar::handle:horizontal {{
    background: {border_strong};
    border-radius: 5px;
    min-width: 30px;
}}
QScrollBar::add-line, QScrollBar::sub-line {{
    height: 0; width: 0;
}}
QScrollBar::add-page, QScrollBar::sub-page {{
    background: transparent;
}}

/* --------------------------------------------------------------- прочее */
QSplitter::handle {{
    background-color: {border};
    width: 1px;
    height: 1px;
}}
QGroupBox {{
    border: 1px solid {border};
    border-radius: 10px;
    margin-top: 14px;
    padding-top: 10px;
    color: {text_muted};
    font-weight: 600;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 4px;
    color: {text_muted};
}}
QProgressBar {{
    background-color: {bg_alt};
    border: 1px solid {border};
    border-radius: 6px;
    text-align: center;
    color: {text};
    height: 14px;
}}
QProgressBar::chunk {{
    background-color: {accent};
    border-radius: 5px;
}}
QMenu {{
    background-color: {surface_alt};
    border: 1px solid {border_strong};
    border-radius: 8px;
    padding: 6px;
}}
QMenu::item {{
    padding: 6px 22px 6px 12px;
    border-radius: 6px;
}}
QMenu::item:selected {{
    background-color: {accent_soft};
}}
QStatusBar {{
    background-color: {bg_alt};
    border-top: 1px solid {border};
    color: {text_dim};
}}
QStatusBar::item {{
    border: none;
}}
QFrame#Separator {{
    background-color: {border};
    max-height: 1px;
}}
QFrame#VDivider {{
    background-color: {border};
    max-width: 1px;
}}
QLabel#Badge {{
    border-radius: 8px;
    padding: 2px 8px;
    font-size: 10px;
    font-weight: 600;
}}
QLabel#Badge[tone="demo"] {{
    background-color: rgba(201, 139, 58, 0.18);
    color: {warning};
    border: 1px solid rgba(201, 139, 58, 0.45);
}}
QLabel#Badge[tone="verified"] {{
    background-color: rgba(47, 191, 113, 0.15);
    color: {success};
    border: 1px solid rgba(47, 191, 113, 0.4);
}}
QLabel#Badge[tone="warning"] {{
    background-color: rgba(240, 163, 94, 0.15);
    color: {warning};
    border: 1px solid rgba(240, 163, 94, 0.4);
}}
QLabel#Badge[tone="danger"] {{
    background-color: rgba(229, 83, 75, 0.15);
    color: {danger};
    border: 1px solid rgba(229, 83, 75, 0.4);
}}
QLabel#Badge[tone="info"] {{
    background-color: rgba(61, 139, 253, 0.15);
    color: {accent};
    border: 1px solid rgba(61, 139, 253, 0.4);
}}
QLabel#Badge[tone="neutral"] {{
    background-color: {surface_alt};
    color: {text_muted};
    border: 1px solid {border};
}}
"""


def apply_theme(app: QApplication) -> None:
    app.setStyle("Fusion")
    palette = QPalette()
    palette.setColor(QPalette.Window, QColor(COLORS["bg"]))
    palette.setColor(QPalette.WindowText, QColor(COLORS["text"]))
    palette.setColor(QPalette.Base, QColor(COLORS["bg_alt"]))
    palette.setColor(QPalette.AlternateBase, QColor(COLORS["surface"]))
    palette.setColor(QPalette.Text, QColor(COLORS["text"]))
    palette.setColor(QPalette.Button, QColor(COLORS["surface_alt"]))
    palette.setColor(QPalette.ButtonText, QColor(COLORS["text"]))
    palette.setColor(QPalette.Highlight, QColor(COLORS["accent"]))
    palette.setColor(QPalette.HighlightedText, QColor("#ffffff"))
    palette.setColor(QPalette.ToolTipBase, QColor(COLORS["surface_alt"]))
    palette.setColor(QPalette.ToolTipText, QColor(COLORS["text"]))
    palette.setColor(QPalette.PlaceholderText, QColor(COLORS["text_dim"]))
    palette.setColor(QPalette.Disabled, QPalette.Text, QColor(COLORS["text_dim"]))
    app.setPalette(palette)

    font = QFont()
    font.setFamilies(FONT_FAMILIES)
    font.setPointSize(9 if app.platformName() == "windows" else 10)
    app.setFont(font)
    app.setStyleSheet(QSS.format(**COLORS))
