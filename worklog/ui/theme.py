"""界面主题（深色）。"""

QSS = """
* {
    font-family: "Microsoft YaHei UI", "Microsoft YaHei", "Segoe UI", sans-serif;
}
QMainWindow, QWidget#root, QWidget#page {
    background: #101216;
}
QWidget {
    color: #d8dde6;
    font-size: 13px;
}
QLabel#pageTitle {
    font-size: 18px;
    font-weight: 600;
    color: #f2f5fa;
}
QLabel#muted {
    color: #6f7890;
    font-size: 12px;
}

QFrame#card {
    background: #181b22;
    border: 1px solid #232833;
    border-radius: 10px;
}
QLabel#cardTitle {
    color: #8b94a7;
    font-size: 12px;
}
QLabel#cardValue {
    color: #f2f5fa;
    font-size: 24px;
    font-weight: 600;
}
QLabel#cardSub {
    color: #6f7890;
    font-size: 12px;
}

QFrame#recordCard {
    background: #181b22;
    border: 1px solid #232833;
    border-radius: 8px;
}
QFrame#recordCard:hover {
    border: 1px solid #33405a;
}
QLabel#recordTime {
    color: #7fb0ff;
    font-family: "Consolas", "Microsoft YaHei UI", monospace;
    font-size: 12px;
}
QLabel#recordApp {
    color: #9aa3b5;
    font-size: 12px;
}
QLabel#recordSummary {
    color: #e8ecf3;
    font-size: 13px;
}
QLabel#chip {
    background: #1d2534;
    color: #7fb0ff;
    border-radius: 8px;
    padding: 1px 8px;
    font-size: 11px;
}

QListWidget#nav {
    background: #0c0e12;
    border: none;
    outline: 0;
    padding: 10px 6px;
    font-size: 13px;
}
QListWidget#nav::item {
    color: #9aa3b5;
    padding: 10px 14px;
    border-radius: 8px;
    margin: 2px 4px;
}
QListWidget#nav::item:selected {
    background: #1d2534;
    color: #7fb0ff;
}
QListWidget#nav::item:hover {
    background: #171c26;
}

QListWidget#reportList {
    background: #12151b;
    border: 1px solid #232833;
    border-radius: 8px;
    outline: 0;
    padding: 4px;
}
QListWidget#reportList::item {
    padding: 8px 10px;
    border-radius: 6px;
    color: #c4cbd8;
}
QListWidget#reportList::item:selected {
    background: #1d2534;
    color: #7fb0ff;
}
QListWidget#reportList::item:hover {
    background: #171c26;
}

QPushButton {
    background: #212734;
    border: 1px solid #2c3444;
    border-radius: 8px;
    padding: 6px 14px;
    color: #d8dde6;
}
QPushButton:hover {
    background: #28303f;
}
QPushButton:pressed {
    background: #1b212c;
}
QPushButton:disabled {
    color: #5a6272;
    background: #181c24;
    border-color: #222833;
}
QPushButton#primary {
    background: #2f6bff;
    border: none;
    color: #ffffff;
    font-weight: 600;
}
QPushButton#primary:hover {
    background: #3d78ff;
}
QPushButton#primary:disabled {
    background: #24304a;
    color: #77839c;
}
QPushButton#danger {
    background: #3a1f26;
    border: 1px solid #5c2b36;
    color: #ff8c9e;
}
QPushButton#danger:hover {
    background: #47262f;
}
QPushButton#ghost {
    background: transparent;
    border: 1px solid #2c3444;
}

QToolButton {
    background: transparent;
    border: none;
    color: #7fb0ff;
    padding: 4px 2px;
    font-size: 12px;
}
QToolButton:hover {
    color: #a8c8ff;
}

QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QDateEdit, QDateTimeEdit,
QPlainTextEdit, QTextEdit, QTextBrowser {
    background: #0f1218;
    border: 1px solid #2a3140;
    border-radius: 8px;
    padding: 5px 8px;
    selection-background-color: #2f6bff;
}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDateEdit:focus,
QDateTimeEdit:focus, QPlainTextEdit:focus, QTextEdit:focus {
    border: 1px solid #3a4a6b;
}
QComboBox::drop-down, QDateEdit::drop-down, QDateTimeEdit::drop-down {
    border: none;
    width: 22px;
}
QComboBox QAbstractItemView {
    background: #181b22;
    border: 1px solid #2a3140;
    selection-background-color: #1d2534;
    outline: 0;
}

QCheckBox {
    spacing: 6px;
}
QCheckBox::indicator {
    width: 15px;
    height: 15px;
    border-radius: 4px;
    border: 1px solid #3a4356;
    background: #0f1218;
}
QCheckBox::indicator:checked {
    background: #2f6bff;
    border: 1px solid #2f6bff;
}

QScrollArea {
    border: none;
    background: transparent;
}
QScrollBar:vertical {
    background: transparent;
    width: 10px;
    margin: 2px;
}
QScrollBar::handle:vertical {
    background: #2b3342;
    border-radius: 5px;
    min-height: 30px;
}
QScrollBar::handle:vertical:hover {
    background: #3a455a;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
}
QScrollBar:horizontal {
    background: transparent;
    height: 10px;
    margin: 2px;
}
QScrollBar::handle:horizontal {
    background: #2b3342;
    border-radius: 5px;
    min-width: 30px;
}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0;
}

QLabel#pill {
    padding: 3px 12px;
    border-radius: 10px;
    font-size: 12px;
}
QLabel#pill[state="recording"] {
    background: #123326;
    color: #4ade80;
}
QLabel#pill[state="paused"] {
    background: #3a2f14;
    color: #fbbf24;
}
QLabel#pill[state="idle"] {
    background: #1c2230;
    color: #7c8aa5;
}
QLabel#pill[state="analyzing"] {
    background: #1b2743;
    color: #7fb0ff;
}
QLabel#pill[state="error"] {
    background: #3a1f26;
    color: #ff8c9e;
}
QLabel#pill[state="stopped"] {
    background: #22262e;
    color: #8b94a7;
}

QProgressBar {
    background: #0f1218;
    border: none;
    border-radius: 5px;
}
QProgressBar::chunk {
    background: #2f6bff;
    border-radius: 5px;
}

QMenu {
    background: #181b22;
    border: 1px solid #2a3140;
    padding: 4px;
}
QMenu::item {
    padding: 6px 26px 6px 12px;
    border-radius: 6px;
}
QMenu::item:selected {
    background: #1d2534;
    color: #7fb0ff;
}
QToolTip {
    background: #1c2230;
    color: #d8dde6;
    border: 1px solid #2a3140;
    padding: 4px;
}
QDialog {
    background: #14161c;
}
QSplitter::handle {
    background: transparent;
}
"""
