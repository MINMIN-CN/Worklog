"""英文模式中文残留检查：以英文构建全部界面，列出仍然是中文的地方。

运行：uv run python tools/i18n_coverage.py
"""

from __future__ import annotations

import os
import re
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

TEMP_DIR = Path(tempfile.mkdtemp(prefix="worklog_i18n_"))
os.environ["WORKLOG_DATA_DIR"] = str(TEMP_DIR)
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication  # noqa: E402

from worklog import i18n  # noqa: E402
from worklog.config import Config, ensure_dirs  # noqa: E402
from worklog.context import AppContext  # noqa: E402
from worklog.db import Database  # noqa: E402
from worklog.recorder import RecorderEngine  # noqa: E402
from worklog.reporting import DEFAULT_TEMPLATES, all_default_templates  # noqa: E402

CJK = re.compile(r"[\u4e00-\u9fff]")

app = QApplication.instance() or QApplication(sys.argv)
ensure_dirs()
cfg = Config()
db = Database(TEMP_DIR / "worklog.db")
db.seed_templates(all_default_templates())

# 放几条记录和待办，覆盖列表/卡片/统计等动态界面
db.add_record(
    day="2026-10-02",
    start_ts="2026-10-02T09:00:00",
    end_ts="2026-10-02T09:30:00",
    app="Code.exe",
    title="main.py",
    category="开发",
    summary="working on the parser",
    details="refactoring",
    project="demo",
    tags=["python"],
    hits=2,
    source="auto",
    pending=0,
)
db.add_todo("write tests", due="2026-10-03", source="手动")
db.add_report("daily", "2026-10-02", "2026-10-02", "2026-10-02 Daily Report", "# done", "Outcome-focused Daily Report")

i18n.set_language("en")
engine = RecorderEngine(cfg, db)
ctx = AppContext(cfg=cfg, db=db, engine=engine, api=None)

from worklog.ui.main_window import MainWindow  # noqa: E402
from worklog.ui.dialogs import RecordEditDialog  # noqa: E402

window = MainWindow(ctx)
window.show()

found: list[tuple[str, str]] = []


def scan(widget, path: str) -> None:
    from PySide6.QtWidgets import (
        QAbstractButton,
        QComboBox,
        QGroupBox,
        QLabel,
        QLineEdit,
        QListWidget,
        QTextBrowser,
    )

    text = ""
    if isinstance(widget, QLabel):
        text = widget.text()
    elif isinstance(widget, QAbstractButton):
        text = widget.text()
    elif isinstance(widget, (QLineEdit, QTextBrowser)):
        text = widget.placeholderText()
    elif isinstance(widget, QGroupBox):
        text = widget.title()
    if text and CJK.search(text) and "<" not in text:
        found.append((path, text[:60]))
    if isinstance(widget, QComboBox):
        for index in range(widget.count()):
            item = widget.itemText(index)
            if CJK.search(item):
                found.append((f"{path}[combo]", item[:60]))
    if isinstance(widget, QListWidget):
        for row in range(widget.count()):
            item = widget.item(row).text()
            if CJK.search(item):
                found.append((f"{path}[list]", item[:60]))


for index in range(window.stack.count()):
    window.nav.setCurrentRow(index)
    page = window.stack.currentWidget()
    if hasattr(page, "refresh"):
        page.refresh()
    scan(page, f"page{index}:{type(page).__name__}")

scan(window, "MainWindow")

dialog = RecordEditDialog(None, window)
scan(dialog, "RecordEditDialog")

dialog_window = window.reports_page
# 报告页状态、待办行、菜单等
i18n.translate_menu(window.tray_menu)
for action in window.tray_menu.actions():
    if CJK.search(action.text()):
        found.append(("tray", action.text()))

for path, text in found:
    print(f"  [{path}] {text}")
print(f"\n共 {len(found)} 处中文残留（英文模式）")
