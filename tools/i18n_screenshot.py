"""渲染英文界面截图（今日 / 统计 / 设置），用于人工检查英文效果。

运行：uv run python tools/i18n_screenshot.py
输出：dist/i18n_preview/*.png
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

TEMP_DIR = Path(tempfile.mkdtemp(prefix="worklog_shot_"))
OUT_DIR = ROOT / "dist" / "i18n_preview"
OUT_DIR.mkdir(parents=True, exist_ok=True)
os.environ["WORKLOG_DATA_DIR"] = str(TEMP_DIR)

from PySide6.QtCore import Qt  # noqa: E402
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

samples = [
    ("09:12", "09:41", "Visual Studio Code", "parser.py", "开发", "Refactoring the log parser", "Implementing batch merge", "worklog", ["python"]),
    ("09:41", "10:20", "chrome.exe", "Pull request #42", "开发", "Reviewing a pull request", "Reading comments on pricing sync", "billing", ["review"]),
    ("10:35", "11:30", "WINWORD.EXE", "Q4 planning.docx", "文档", "Writing the Q4 plan", "Drafting milestones and owners", "planning", ["doc"]),
    ("13:30", "14:10", "Teams.exe", "Sprint sync", "会议", "Sprint sync with the team", "Discussed blockers and scope", "", ["meeting"]),
    ("14:10", "15:00", "Terminal", "pytest", "测试", "Running the test suite", "Fixing failing API tests", "worklog", ["pytest"]),
]
for start, end, app_name, title, category, summary, details, project, tags in samples:
    db.add_record(
        day="2026-10-02",
        start_ts=f"2026-10-02T{start}:00",
        end_ts=f"2026-10-02T{end}:00",
        app=app_name,
        title=title,
        category=category,
        summary=summary,
        details=details,
        project=project,
        tags=tags,
        hits=3,
        source="auto",
        pending=0,
    )
db.add_todo("Finish the pricing sync doc", due="2026-10-05", source="手动")
db.add_todo("Reply to the design review", source="AI提取")

i18n.set_language("en")
engine = RecorderEngine(cfg, db)
ctx = AppContext(cfg=cfg, db=db, engine=engine, api=None)

window = MainWindow(ctx)
window.resize(1240, 820)
window.setAttribute(Qt.WA_DontShowOnScreen, True)
window.show()
app.processEvents()

shots = []
for index, name in ((0, "today"), (2, "stats"), (4, "todos"), (5, "settings")):
    window.nav.setCurrentRow(index)
    app.processEvents()
    path = OUT_DIR / f"en_{name}.png"
    window.grab().save(str(path))
    shots.append(path)

window._really_quit = True
window.tray.hide()
window.close()
print("saved:")
for path in shots:
    print(" ", path)
