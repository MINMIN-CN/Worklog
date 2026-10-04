"""生成 README 用的界面截图（中文 / English 两套）。

运行：
    uv run python tools/readme_screenshots.py zh
    uv run python tools/readme_screenshots.py en

输出：docs/images/{lang}_{today,stats,reports,todos,settings}.png
"""

from __future__ import annotations

import datetime as dt
import os
import sys
import tempfile
from pathlib import Path

LANG = (sys.argv[1] if len(sys.argv) > 1 else "zh").lower()
if LANG not in ("zh", "en"):
    raise SystemExit("用法：uv run python tools/readme_screenshots.py [zh|en]")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

TEMP_DIR = Path(tempfile.mkdtemp(prefix=f"worklog_shot_{LANG}_"))
os.environ["WORKLOG_DATA_DIR"] = str(TEMP_DIR)

from PIL import Image  # noqa: E402
from PySide6.QtCore import QCoreApplication, QEvent, Qt  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from worklog import i18n  # noqa: E402
from worklog.config import Config, ensure_dirs  # noqa: E402
from worklog.context import AppContext  # noqa: E402
from worklog.db import Database  # noqa: E402
from worklog.recorder import RecorderEngine  # noqa: E402
from worklog.reporting import all_default_templates  # noqa: E402
from worklog.ui.main_window import MainWindow  # noqa: E402
from worklog.ui.theme import QSS  # noqa: E402

OUT_DIR = ROOT / "docs" / "images"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# (days_ago, start, end, app, title, category, summary, details, project, tags)
TODAY_ZH = [
    ("09:05", "09:48", "Visual Studio Code", "实现截图去重逻辑", "开发",
     "为截图增加指纹去重，避免重复调用 AI", "对比相邻帧哈希，相同画面自动合并", "worklog", ["python"]),
    ("09:48", "10:26", "chrome.exe", "Pull requests · Worklog", "开发",
     "评审更新模块的 PR", "阅读并行下载实现并留下评论", "updater", ["review"]),
    ("10:40", "11:35", "WINWORD.EXE", "Q4 规划.docx", "文档",
     "撰写 Q4 产品规划", "整理里程碑、负责人和排期", "planning", ["规划"]),
    ("13:40", "14:20", "Teams.exe", "周会：进度同步", "会议",
     "参加周会同步项目进度", "确认本周交付范围与风险", "", ["会议"]),
    ("14:20", "15:10", "Windows Terminal", "pytest -q", "测试",
     "运行测试套件并修复失败用例", "修复报告生成相关失败用例", "worklog", ["pytest"]),
    ("15:30", "16:15", "Figma.exe", "工作小记 UI", "设计",
     "调整设置页的信息层级", "优化高级设置分组与间距", "worklog", ["ui"]),
]

PAST_ZH = [
    (1, "09:20", "10:10", "Visual Studio Code", "数据库迁移脚本", "开发",
     "编写旧版本数据迁移脚本", "处理目录不可写时的回退逻辑", "worklog", ["sqlite"]),
    (1, "10:30", "11:20", "MSedge.exe", "Python 打包文档", "学习",
     "查阅 PyInstaller 打包文档", "确认 onedir 模式的资源路径", "worklog", ["docs"]),
    (1, "14:00", "14:50", "WeChat.exe", "与设计沟通改版", "沟通",
     "沟通首页改版的交互细节", "确认快捷键与托盘行为", "官网改版", ["沟通"]),
    (2, "09:40", "11:00", "Visual Studio Code", "自动更新模块", "开发",
     "实现更新清单解析与版本比较", "补齐断网场景的容错处理", "updater", ["python"]),
    (2, "14:10", "15:20", "Windows Terminal", "构建安装包", "运维",
     "构建 0.5.x 安装包并验证升级", "验证原地升级与数据保留", "worklog", ["release"]),
    (3, "10:00", "11:30", "Visual Studio Code", "报告模板参数化", "开发",
     "重构报告模板参数透传", "支持自定义补充指令", "worklog", ["refactor"]),
    (3, "15:00", "15:40", "Teams.exe", "需求评审会", "会议",
     "评审下一迭代需求", "确认优先级与验收标准", "", ["会议"]),
    (4, "09:30", "10:20", "Excel.exe", "工时统计表.xlsx", "文档",
     "整理本周工时统计", "汇总分类占比与专注时长", "planning", ["表格"]),
    (4, "14:30", "16:00", "Visual Studio Code", "多语言词条校对", "开发",
     "校对英文界面词条", "补齐遗漏翻译并回归检查", "worklog", ["i18n"]),
    (6, "10:10", "11:00", "chrome.exe", "GitHub Actions 文档", "学习",
     "学习 GitHub Actions 工作流", "梳理自动发布流程", "worklog", ["ci"]),
    (6, "15:10", "16:00", "PowerPoint.exe", "季度汇报.pptx", "文档",
     "制作季度汇报材料", "整理数据图表与结论", "planning", ["汇报"]),
    (8, "09:50", "11:10", "Visual Studio Code", "下载加速模块", "开发",
     "实现镜像测速与多线程下载", "失败自动切换线路", "updater", ["python"]),
]

TODAY_EN = [
    ("09:05", "09:48", "Visual Studio Code", "Screenshot dedup logic", "开发",
     "Added fingerprint dedup to skip unchanged screenshots", "Compared frame hashes and merged identical frames", "worklog", ["python"]),
    ("09:48", "10:26", "chrome.exe", "Pull requests · Worklog", "开发",
     "Reviewed the updater PR", "Read the parallel download code and left comments", "updater", ["review"]),
    ("10:40", "11:35", "WINWORD.EXE", "Q4 planning.docx", "文档",
     "Drafted the Q4 product plan", "Collected milestones, owners and dates", "planning", ["planning"]),
    ("13:40", "14:20", "Teams.exe", "Weekly sync", "会议",
     "Joined the weekly project sync", "Confirmed scope and risks for the week", "", ["meeting"]),
    ("14:20", "15:10", "Windows Terminal", "pytest -q", "测试",
     "Ran the test suite and fixed failures", "Fixed failing report generation tests", "worklog", ["pytest"]),
    ("15:30", "16:15", "Figma.exe", "WorkLog UI", "设计",
     "Tuned the settings page hierarchy", "Grouped advanced settings and fixed spacing", "worklog", ["ui"]),
]

PAST_EN = [
    (1, "09:20", "10:10", "Visual Studio Code", "Database migration script", "开发",
     "Wrote the legacy data migration script", "Handled the read-only install directory", "worklog", ["sqlite"]),
    (1, "10:30", "11:20", "MSedge.exe", "PyInstaller docs", "学习",
     "Read the PyInstaller packaging docs", "Confirmed resource paths in onedir mode", "worklog", ["docs"]),
    (1, "14:00", "14:50", "WeChat.exe", "Design review chat", "沟通",
     "Discussed the redesigned home page", "Aligned on shortcuts and tray behaviour", "Redesign", ["chat"]),
    (2, "09:40", "11:00", "Visual Studio Code", "Auto-update module", "开发",
     "Implemented manifest parsing and version compare", "Added network failure handling", "updater", ["python"]),
    (2, "14:10", "15:20", "Windows Terminal", "Build installer", "运维",
     "Built 0.5.x installers and verified upgrade", "Verified in-place upgrade keeps data", "worklog", ["release"]),
    (3, "10:00", "11:30", "Visual Studio Code", "Report template params", "开发",
     "Refactored report template arguments", "Supported custom instructions", "worklog", ["refactor"]),
    (3, "15:00", "15:40", "Teams.exe", "Backlog review", "会议",
     "Reviewed the next iteration backlog", "Confirmed priorities and acceptance criteria", "", ["meeting"]),
    (4, "09:30", "10:20", "Excel.exe", "Timesheet.xlsx", "文档",
     "Compiled the weekly timesheet", "Summarised focus time and categories", "planning", ["sheet"]),
    (4, "14:30", "16:00", "Visual Studio Code", "i18n proofreading", "开发",
     "Proofread the English UI strings", "Filled missing translations and re-checked", "worklog", ["i18n"]),
    (6, "10:10", "11:00", "chrome.exe", "GitHub Actions docs", "学习",
     "Studied GitHub Actions workflows", "Sketched the automated release flow", "worklog", ["ci"]),
    (6, "15:10", "16:00", "PowerPoint.exe", "Quarterly review.pptx", "文档",
     "Prepared the quarterly review deck", "Collected charts and conclusions", "planning", ["slides"]),
    (8, "09:50", "11:10", "Visual Studio Code", "Download accelerator", "开发",
     "Added mirror speed-test and parallel download", "Automatic failover between mirrors", "updater", ["python"]),
]

REPORT_ZH = """# {day} 日报

## 今日完成
- 实现截图指纹去重，重复画面不再触发 AI 分析（预计节省约 30% 调用）
- 评审并行下载 PR 并合并到 main
- 完成 Q4 规划初稿（里程碑 / 负责人 / 排期）

## 进行中
- 报告模板参数透传重构，已完成一半

## 待办
- 补充取消下载的边界测试
- 周五前确认设计评审时间

## 数据概览
- 有效记录 6 条，专注约 5.2 小时
- 主要分类：开发 2.6h、文档 0.9h、会议 0.7h
"""

REPORT_EN = """# Daily report — {day}

## Done today
- Added screenshot fingerprint dedup, unchanged frames no longer trigger AI analysis (~30% fewer calls)
- Reviewed and merged the parallel download PR
- Drafted the Q4 plan (milestones / owners / timeline)

## In progress
- Refactoring report template arguments (halfway)

## To-do
- Add boundary tests for cancelling a download
- Confirm the design review slot before Friday

## At a glance
- 6 tracked records, ~5.2 focused hours
- Top categories: Development 2.6h, Documents 0.9h, Meetings 0.7h
"""


def add_record(db: Database, day: dt.date, item: tuple) -> None:
    start, end, app, title, category, summary, details, project, tags = item
    db.add_record(
        day=day.isoformat(),
        start_ts=f"{day.isoformat()}T{start}:00",
        end_ts=f"{day.isoformat()}T{end}:00",
        app=app,
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


def seed(db: Database) -> None:
    today = dt.date.today()
    today_samples = TODAY_ZH if LANG == "zh" else TODAY_EN
    past_samples = PAST_ZH if LANG == "zh" else PAST_EN
    for item in today_samples:
        add_record(db, today, item)
    for days_ago, *item in past_samples:
        add_record(db, today - dt.timedelta(days=days_ago), tuple(item))

    if LANG == "zh":
        db.add_todo("完成 Q4 规划评审", due=(today + dt.timedelta(days=2)).isoformat(), source="手动")
        db.add_todo("补充更新下载的边界测试", due=(today + dt.timedelta(days=1)).isoformat(), source="AI提取")
        db.add_todo("回复设计评审意见", source="AI提取")
        done_id = db.add_todo("整理本周工作记录", source="手动")
        db.set_todo_status(done_id, "done")
        title = f"{today.isoformat()} 日报"
        content = REPORT_ZH.format(day=today.isoformat())
        template = "成果导向日报"
    else:
        db.add_todo("Finish the Q4 plan review", due=(today + dt.timedelta(days=2)).isoformat(), source="手动")
        db.add_todo("Add boundary tests for downloads", due=(today + dt.timedelta(days=1)).isoformat(), source="AI提取")
        db.add_todo("Reply to design review comments", source="AI提取")
        done_id = db.add_todo("Sort this week's records", source="手动")
        db.set_todo_status(done_id, "done")
        title = f"Daily report — {today.isoformat()}"
        content = REPORT_EN.format(day=today.isoformat())
        template = "成果导向日报"

    db.add_report("daily", today.isoformat(), today.isoformat(), title, content, template)


def main() -> int:
    app = QApplication.instance() or QApplication(sys.argv)
    app.setStyleSheet(QSS)
    ensure_dirs()
    cfg = Config()
    db = Database(TEMP_DIR / "worklog.db")
    db.seed_templates(all_default_templates())
    seed(db)

    i18n.set_language(LANG)
    engine = RecorderEngine(cfg, db)
    ctx = AppContext(cfg=cfg, db=db, engine=engine, api=None)

    window = MainWindow(ctx)
    window.resize(1240, 820)
    window.setAttribute(Qt.WA_DontShowOnScreen, True)
    window.show()

    def flush() -> None:
        # 处理延迟删除，避免重建列表时留下旧卡片残影
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        app.processEvents()

    flush()
    for index, name in ((0, "today"), (2, "stats"), (3, "reports"), (4, "todos"), (5, "settings")):
        window.nav.setCurrentRow(index)
        if name == "stats":
            window.stats_page.range_combo.setCurrentIndex(1)  # 最近 7 天
        flush()
        path = OUT_DIR / f"{LANG}_{name}.png"
        window.grab().save(str(path))
        Image.open(path).save(path, optimize=True)
        print("saved", path)

    window._really_quit = True
    window.tray.hide()
    window.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
