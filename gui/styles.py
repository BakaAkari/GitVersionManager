"""
Git Version Manager - Dark Theme Styles
Professional neutral gray theme
"""

DARK_THEME = """
/* ============================================
   Git Version Manager - Neutral Gray Theme
   ============================================ */

/* Main Window */
QMainWindow, QDialog {
    background-color: #252525;
    color: #d0d0d0;
}

QWidget {
    background-color: transparent;
    color: #d0d0d0;
    font-family: "Segoe UI", "Microsoft YaHei UI", sans-serif;
    font-size: 13px;
}

/* Central Widget and Frames */
QMainWindow > QWidget {
    background-color: #252525;
}

/* Context Menu */
QMenu {
    background-color: #2a2a2a;
    color: #d0d0d0;
    border: 1px solid #3a3a3a;
    border-radius: 3px;
    padding: 4px;
}

QMenu::item {
    padding: 6px 24px;
    border-radius: 2px;
}

QMenu::item:selected {
    background-color: #353535;
}

QMenu::separator {
    height: 1px;
    background-color: #3a3a3a;
    margin: 4px 8px;
}

/* Group Boxes */
QGroupBox {
    background-color: #2a2a2a;
    border: 1px solid #3a3a3a;
    border-radius: 4px;
    margin-top: 8px;
    padding: 12px;
    padding-top: 16px;
    font-weight: bold;
}

QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 0 8px;
    color: #e0e0e0;
    background-color: #2a2a2a;
    left: 10px;
    top: 0px;
}

/* Labels */
QLabel {
    color: #d0d0d0;
    background: transparent;
}

/* Push Buttons */
QPushButton {
    background-color: #2a2a2a;
    color: #d0d0d0;
    border: 1px solid #3a3a3a;
    border-radius: 3px;
    padding: 8px 16px;
    font-weight: 500;
    min-height: 20px;
}

QPushButton:hover {
    background-color: #353535;
    border-color: #454545;
}

QPushButton:pressed {
    background-color: #404040;
}

QPushButton:disabled {
    background-color: #1e1e1e;
    color: #606060;
    border-color: #2a2a2a;
}

/* List Widget */
QListWidget {
    background-color: #222222;
    border: 1px solid #3a3a3a;
    border-radius: 3px;
    padding: 4px;
    outline: none;
}

QListWidget::item {
    padding: 8px 12px;
    border-radius: 2px;
    margin: 2px 0;
}

QListWidget::item:hover {
    background-color: #2a2a2a;
}

QListWidget::item:selected {
    background-color: #353535;
    color: #ffffff;
}

/* Text Edit (Log area) */
QTextEdit {
    background-color: #1a1a1a;
    color: #b0b0b0;
    border: 1px solid #3a3a3a;
    border-radius: 3px;
    padding: 8px;
    font-family: "Consolas", "Cascadia Code", monospace;
    font-size: 12px;
}

/* Line Edit */
QLineEdit {
    background-color: #222222;
    color: #d0d0d0;
    border: 1px solid #3a3a3a;
    border-radius: 3px;
    padding: 8px 12px;
}

QLineEdit:focus {
    border-color: #505050;
}

/* Combo Box */
QComboBox {
    background-color: #222222;
    color: #d0d0d0;
    border: 1px solid #3a3a3a;
    border-radius: 3px;
    padding: 6px 12px;
    min-width: 100px;
}

QComboBox:hover {
    border-color: #454545;
}

QComboBox::drop-down {
    border: none;
    width: 20px;
}

QComboBox::down-arrow {
    image: none;
    border: none;
    width: 0;
    height: 0;
}

QComboBox QAbstractItemView {
    background-color: #222222;
    border: 1px solid #3a3a3a;
    border-radius: 3px;
    selection-background-color: #353535;
    selection-color: #ffffff;
}

/* Tab Widget */
QTabWidget::pane {
    background-color: #222222;
    border: 1px solid #3a3a3a;
    border-radius: 4px;
    border-top-left-radius: 0;
}

QTabBar::tab {
    background-color: #1a1a1a;
    color: #909090;
    border: 1px solid #3a3a3a;
    border-bottom: none;
    padding: 10px 20px;
    margin-right: 2px;
    border-top-left-radius: 3px;
    border-top-right-radius: 3px;
}

QTabBar::tab:hover {
    background-color: #252525;
    color: #d0d0d0;
}

QTabBar::tab:selected {
    background-color: #222222;
    color: #ffffff;
    border-bottom: 2px solid #606060;
}

/* Splitter */
QSplitter::handle {
    background-color: #3a3a3a;
    width: 2px;
}

QSplitter::handle:hover {
    background-color: #505050;
}

/* Scroll Bars */
QScrollBar:vertical {
    background-color: #1a1a1a;
    width: 10px;
    border: none;
    border-radius: 5px;
}

QScrollBar::handle:vertical {
    background-color: #3a3a3a;
    min-height: 30px;
    border-radius: 5px;
    margin: 2px;
}

QScrollBar::handle:vertical:hover {
    background-color: #454545;
}

QScrollBar::add-line:vertical, 
QScrollBar::sub-line:vertical {
    height: 0;
}

QScrollBar:horizontal {
    background-color: #1a1a1a;
    height: 10px;
    border: none;
    border-radius: 5px;
}

QScrollBar::handle:horizontal {
    background-color: #3a3a3a;
    min-width: 30px;
    border-radius: 5px;
    margin: 2px;
}

QScrollBar::handle:horizontal:hover {
    background-color: #454545;
}

QScrollBar::add-line:horizontal, 
QScrollBar::sub-line:horizontal {
    width: 0;
}

/* Check Box */
QCheckBox {
    spacing: 8px;
    color: #d0d0d0;
}

QCheckBox::indicator {
    width: 16px;
    height: 16px;
    border: 1px solid #3a3a3a;
    border-radius: 2px;
    background-color: #222222;
}

QCheckBox::indicator:hover {
    border-color: #505050;
}

QCheckBox::indicator:checked {
    background-color: #505050;
    border-color: #606060;
}

/* Message Box */
QMessageBox {
    background-color: #1a1a1a;
}

QMessageBox QLabel {
    color: #d0d0d0;
}

/* Form Layout Labels */
QFormLayout QLabel {
    color: #b0b0b0;
}
"""


def apply_dark_theme(app):
    """Apply dark theme to the application."""
    app.setStyleSheet(DARK_THEME)
