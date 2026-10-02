"""复现：报告列表点击不响应的问题。"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

TEMP_DIR = Path(tempfile.mkdtemp(prefix="worklog_click_"))
os.environ["WORKLOG_DATA_DIR"] = str(TEMP_DIR)

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from worklog import i18n  # noqa: E402
from worklog.config import Config, ensure_dirs  # noqa: E402
from worklog.context import AppContext  # noqa: E402
from worklog.db import Database  # noqa: E402
from worklog.recorder import RecorderEngine  # noqa: E402
from worklog.reporting import all_default_templates  # noqa: E402
from worklog.ui.main_window import MainWindow  # noqa: E402
from worklog.ui.theme import QSS  # noqa: E402

app = QApplication.instance() or QApplication(sys.argv)
app.setStyleSheet(QSS)
ensure_dirs()
cfg = Config()
db = Database(TEMP_DIR / "worklog.db")
db.seed_templates(all_default_templates())

for index in (1, 2, 3):
    db.add_report(
        "daily",
        f"2026-10-0{index}",
        f"2026-10-0{index}",
        f"2026-10-0{index} 日报",
        f"# Report {index}\n\ncontent-{index}",
        "成果导向日报",
    )

i18n.set_language("zh")
engine = RecorderEngine(cfg, db)
ctx = AppContext(cfg=cfg, db=db, engine=engine, api=None)
window = MainWindow(ctx)
window.resize(1240, 820)
window.setAttribute(Qt.WA_DontShowOnScreen, True)
window.show()
app.processEvents()

window.nav.setCurrentRow(3)
app.processEvents()
page = window.reports_page
print("history count:", page.history.count())
print("current row:", page.history.currentRow())
print("item0 data:", page.history.item(0).data(Qt.UserRole))
print("preview after refresh:", repr(page.preview.toPlainText()[:40]))

# 模拟点击第 2 项（索引 1）
item = page.history.item(1)
rect = page.history.visualItemRect(item)
center = rect.center()
print("clicking item1 at:", center.x(), center.y(), "text:", repr(item.text()[:30]))
QTest.mouseClick(page.history.viewport(), Qt.LeftButton, Qt.NoModifier, center)
app.processEvents()
print("current row after click:", page.history.currentRow())
print("preview after click:", repr(page.preview.toPlainText()[:40]))
print("status:", repr(page.status_label.text()))

# 再点第 3 项
item = page.history.item(2)
QTest.mouseClick(page.history.viewport(), Qt.LeftButton, Qt.NoModifier,
                 page.history.visualItemRect(item).center())
app.processEvents()
print("current row after click2:", page.history.currentRow())
print("preview after click2:", repr(page.preview.toPlainText()[:40]))

window._really_quit = True
window.tray.hide()
window.close()
