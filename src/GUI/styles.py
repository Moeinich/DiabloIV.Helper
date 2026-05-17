DARK_BASE = """
    QWidget {
        background-color: rgba(15, 15, 20, 230);
        color: #e0e0e0;
        font-family: Segoe UI, Arial;
        font-size: 12px;
    }
"""

DARK_GROUPBOX = """
    QGroupBox {
        background-color: rgba(20, 20, 28, 240);
        border: 1px solid rgba(80, 80, 100, 150);
        border-radius: 6px;
        margin-top: 14px;
        padding: 14px 10px 10px 10px;
        font-weight: bold;
    }
    QGroupBox::title {
        subcontrol-origin: margin;
        left: 12px;
        padding: 0 6px;
        color: #00cc66;
    }
    QGroupBox::indicator {
        width: 18px; height: 18px;
        border: 2px solid rgba(100, 60, 60, 220);
        border-radius: 3px;
        background-color: rgba(20, 20, 25, 255);
    }
    QGroupBox::indicator:checked {
        background-color: rgba(0, 200, 100, 240);
        border: 2px solid rgba(0, 240, 130, 200);
    }
    QGroupBox::indicator:unchecked {
        background-color: rgba(60, 30, 30, 255);
        border: 2px solid rgba(140, 50, 50, 200);
    }
"""

DARK_INPUT = """
    QLineEdit, QSpinBox, QDoubleSpinBox {
        background-color: rgba(40, 40, 55, 230);
        color: #e0e0e0;
        border: 1px solid rgba(80, 80, 100, 150);
        border-radius: 3px;
        padding: 2px 6px;
    }
    QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus {
        border: 1px solid rgba(0, 180, 100, 200);
    }
"""

DARK_COMBO = """
    QComboBox {
        background-color: rgba(40, 40, 55, 230);
        color: #e0e0e0;
        border: 1px solid rgba(80, 80, 100, 150);
        border-radius: 3px;
        padding: 2px 8px;
    }
    QComboBox::drop-down { border: none; width: 20px; }
    QComboBox::down-arrow {
        border-left: 4px solid transparent;
        border-right: 4px solid transparent;
        border-top: 5px solid #808080;
    }
    QComboBox QAbstractItemView {
        background-color: rgba(30, 30, 40, 250);
        color: #e0e0e0;
        selection-background-color: rgba(0, 180, 100, 200);
    }
"""

DARK_CHECKBOX = """
    QCheckBox { color: #e0e0e0; spacing: 8px; font-weight: bold; }
    QCheckBox::indicator {
        width: 18px; height: 18px;
        border: 2px solid rgba(100, 60, 60, 220);
        border-radius: 3px;
        background-color: rgba(20, 20, 25, 255);
    }
    QCheckBox::indicator:checked {
        background-color: rgba(0, 200, 100, 240);
        border: 2px solid rgba(0, 240, 130, 200);
    }
    QCheckBox::indicator:checked:hover {
        background-color: rgba(0, 220, 120, 240);
    }
    QCheckBox::indicator:unchecked {
        background-color: rgba(60, 30, 30, 255);
        border: 2px solid rgba(140, 50, 50, 200);
    }
    QCheckBox::indicator:unchecked:hover {
        background-color: rgba(80, 40, 40, 255);
        border: 2px solid rgba(160, 60, 60, 200);
    }
"""

DARK_BUTTON = """
    QPushButton {
        background-color: rgba(50, 50, 65, 230);
        color: #e0e0e0;
        border: 1px solid rgba(80, 80, 100, 150);
        border-radius: 4px;
        padding: 4px 14px;
        font-weight: bold;
    }
    QPushButton:hover { background-color: rgba(70, 70, 85, 240); }
    QPushButton:pressed { background-color: rgba(35, 35, 45, 230); }
"""

DARK_TAB = """
    QTabWidget::pane {
        border: 1px solid rgba(80, 80, 100, 150);
        background: rgba(15, 15, 20, 230);
    }
    QTabBar::tab {
        background: rgba(30, 30, 40, 230);
        color: #aaa;
        padding: 8px 20px;
        border: 1px solid rgba(80, 80, 100, 100);
        border-bottom: none;
        border-top-left-radius: 4px;
        border-top-right-radius: 4px;
        margin-right: 2px;
    }
    QTabBar::tab:selected {
        background: rgba(40, 40, 55, 240);
        color: #e0e0e0;
        border-bottom: 2px solid #00cc66;
    }
    QTabBar::tab:hover { background: rgba(50, 50, 65, 240); }
"""

DARK_SCROLL = """
    QScrollArea { border: none; background: transparent; }
    QScrollBar:vertical {
        background: rgba(20, 20, 28, 200);
        width: 8px;
        border-radius: 4px;
    }
    QScrollBar::handle:vertical {
        background: rgba(80, 80, 100, 180);
        border-radius: 4px;
        min-height: 20px;
    }
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
"""

TOOLBOX_STYLESHEET = (DARK_BASE + DARK_GROUPBOX + DARK_INPUT + DARK_COMBO +
                      DARK_CHECKBOX + DARK_BUTTON + DARK_TAB + DARK_SCROLL)

OVERLAY_STYLESHEET = (DARK_BASE + DARK_COMBO + DARK_BUTTON)
