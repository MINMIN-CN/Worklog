"""各功能页面：今日、时间线、统计、报告、待办、设置。"""

from __future__ import annotations

import json
import os
import sys
import time
from datetime import date, timedelta
from pathlib import Path

from PySide6.QtCore import QDate, Qt, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtCore import QUrl
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDateEdit,
    QDialog,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QTextBrowser,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from .. import APP_NAME, __version__
from ..ai import AIClient, make_client
from ..analyze import CATEGORIES, extract_todos
from ..config import DATA_DIR, REPORTS_DIR
from ..providers import all_providers, match_provider, provider_by_key
from ..reporting import KIND_LABELS, build_timeline_text, generate_report, range_for
from ..stats import compute_stats, format_duration
from ..updater import (
    download_installer,
    fetch_manifest,
    is_newer,
    launch_update,
    resolve_manifest_url,
)
from ..wininfo import monitor_count
from .dialogs import RecordEditDialog
from .widgets import (
    BarListWidget,
    Card,
    HeatmapWidget,
    RecordListWidget,
    StatCard,
    TagCloudWidget,
    Task,
    fmt_time,
    refresh_style,
)


# ---------------------------------------------------------------- 公共小工具
def edit_record_dialog(parent: QWidget, ctx, record: dict) -> bool:
    dialog = RecordEditDialog(record, parent)
    if dialog.exec() != QDialog.Accepted:
        return False
    values = dialog.values()
    ctx.db.update_record(record["id"], **values)
    return True


def delete_record_dialog(parent: QWidget, ctx, record: dict) -> bool:
    answer = QMessageBox.question(
        parent,
        "删除记录",
        f"确定删除 {fmt_time(record.get('start_ts', ''))} 的这条记录吗？",
    )
    if answer != QMessageBox.Yes:
        return False
    ctx.db.delete_record(record["id"])
    return True


def open_path(path: Path) -> None:
    if sys.platform == "win32":
        os.startfile(str(path))  # type: ignore[attr-defined]
    else:
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))


def _make_scroll_page(inner: QWidget) -> QScrollArea:
    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setWidget(inner)
    return scroll


# -------------------------------------------------------------------- 今日页
class TodayPage(QWidget):
    data_changed = Signal()
    open_reports = Signal(str)
    open_settings = Signal()

    def __init__(self, ctx, parent: QWidget | None = None):
        super().__init__(parent)
        self.ctx = ctx
        self.setObjectName("page")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(14)

        header = QHBoxLayout()
        title = QLabel("今日概览")
        title.setObjectName("pageTitle")
        self.range_label = QLabel("")
        self.range_label.setObjectName("muted")
        header.addWidget(title)
        header.addWidget(self.range_label)
        self.setup_notice = QPushButton("尚未配置 AI，点这里选择服务商 →")
        self.setup_notice.setObjectName("ghost")
        self.setup_notice.clicked.connect(self.open_settings)
        header.addWidget(self.setup_notice)
        header.addStretch(1)
        capture_btn = QPushButton("立即记录")
        capture_btn.setObjectName("ghost")
        capture_btn.clicked.connect(self.ctx.engine.capture_now)
        report_btn = QPushButton("生成今日日报")
        report_btn.setObjectName("primary")
        report_btn.clicked.connect(lambda: self.open_reports.emit("daily"))
        header.addWidget(capture_btn)
        header.addWidget(report_btn)
        layout.addLayout(header)

        cards = QHBoxLayout()
        cards.setSpacing(12)
        self.card_records = StatCard("记录条数")
        self.card_duration = StatCard("专注时长")
        self.card_span = StatCard("活跃时段")
        self.card_todos = StatCard("未完成待办")
        for card in (self.card_records, self.card_duration, self.card_span, self.card_todos):
            cards.addWidget(card, 1)
        layout.addLayout(cards)

        timeline_card = Card("今日时间线")
        self.list = RecordListWidget("今天还没有记录。打开记录开关后，它会自动工作。")
        self.list.edit_requested.connect(self._edit)
        self.list.delete_requested.connect(self._delete)
        timeline_card.add(self.list)
        layout.addWidget(timeline_card, 1)

        self.refresh()

    def refresh(self) -> None:
        today = date.today().isoformat()
        self.setup_notice.setVisible(
            not bool(self.ctx.cfg.get("api", "api_key", default=""))
        )
        records = self.ctx.db.records_for_day(today)
        stats = compute_stats(records)
        self.range_label.setText(f"{today} · {len(records)} 个片段")
        self.card_records.set_value(str(len(records)), f"共采集 {stats['hits']} 次")
        self.card_duration.set_value(format_duration(stats["duration"]), "按记录时长估算")
        if stats["first_start"] and stats["last_end"]:
            span = f"{fmt_time(stats['first_start'])}–{fmt_time(stats['last_end'])}"
        else:
            span = "—"
        self.card_span.set_value(span, "首末活动时间")
        self.card_todos.set_value(str(self.ctx.db.open_todo_count()), "在待办页管理")
        self.list.set_records(list(reversed(records)))

    def _edit(self, record: dict) -> None:
        if edit_record_dialog(self, self.ctx, record):
            self.refresh()
            self.data_changed.emit()

    def _delete(self, record: dict) -> None:
        if delete_record_dialog(self, self.ctx, record):
            self.refresh()
            self.data_changed.emit()


# ------------------------------------------------------------------ 时间线页
class TimelinePage(QWidget):
    data_changed = Signal()

    def __init__(self, ctx, parent: QWidget | None = None):
        super().__init__(parent)
        self.ctx = ctx
        self.setObjectName("page")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(12)

        header = QHBoxLayout()
        title = QLabel("时间线")
        title.setObjectName("pageTitle")
        header.addWidget(title)
        header.addSpacing(12)
        prev_btn = QPushButton("‹")
        prev_btn.setFixedWidth(36)
        prev_btn.clicked.connect(lambda: self._shift(-1))
        self.date_edit = QDateEdit(QDate.currentDate())
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDisplayFormat("yyyy-MM-dd")
        self.date_edit.dateChanged.connect(lambda _: self.refresh())
        next_btn = QPushButton("›")
        next_btn.setFixedWidth(36)
        next_btn.clicked.connect(lambda: self._shift(1))
        today_btn = QPushButton("今天")
        today_btn.clicked.connect(lambda: self.date_edit.setDate(QDate.currentDate()))
        self.count_label = QLabel("")
        self.count_label.setObjectName("muted")
        header.addWidget(prev_btn)
        header.addWidget(self.date_edit)
        header.addWidget(next_btn)
        header.addWidget(today_btn)
        header.addWidget(self.count_label)
        header.addStretch(1)
        reanalyze_btn = QPushButton("重新分析未分析")
        reanalyze_btn.clicked.connect(self._reanalyze)
        add_btn = QPushButton("手动添加")
        add_btn.setObjectName("primary")
        add_btn.clicked.connect(self._add)
        header.addWidget(reanalyze_btn)
        header.addWidget(add_btn)
        layout.addLayout(header)

        self.list = RecordListWidget("这一天还没有记录。")
        self.list.edit_requested.connect(self._edit)
        self.list.delete_requested.connect(self._delete)
        layout.addWidget(self.list, 1)

        self.refresh()

    def _day(self) -> str:
        return self.date_edit.date().toString("yyyy-MM-dd")

    def _shift(self, days: int) -> None:
        self.date_edit.setDate(self.date_edit.date().addDays(days))

    def refresh(self) -> None:
        records = self.ctx.db.records_for_day(self._day())
        self.count_label.setText(f"· {len(records)} 个片段")
        self.list.set_records(records)

    def _edit(self, record: dict) -> None:
        if edit_record_dialog(self, self.ctx, record):
            self.refresh()
            self.data_changed.emit()

    def _delete(self, record: dict) -> None:
        if delete_record_dialog(self, self.ctx, record):
            self.refresh()
            self.data_changed.emit()

    def _add(self) -> None:
        dialog = RecordEditDialog(None, self)
        if dialog.exec() == QDialog.Accepted:
            values = dialog.values()
            values.update({"source": "manual", "hits": 1, "pending": 0})
            self.ctx.db.add_record(**values)
            self.refresh()
            self.data_changed.emit()

    def _reanalyze(self) -> None:
        from ..recorder import reanalyze_pending

        day = self._day()
        pending = self.ctx.db.pending_for_day(day)
        if not pending:
            QMessageBox.information(self, "重新分析", "这一天没有待分析的记录。")
            return
        task = Task(lambda: reanalyze_pending(self.ctx.db, self.ctx.cfg, day), self)
        task.done.connect(self._on_reanalyzed)
        task.fail.connect(lambda message: QMessageBox.warning(self, "重新分析失败", message))
        self._task = task
        task.start()

    def _on_reanalyzed(self, result) -> None:
        done, total = result
        QMessageBox.information(self, "重新分析", f"完成：{done}/{total} 条记录已补上分析。")
        self.refresh()
        self.data_changed.emit()


# -------------------------------------------------------------------- 统计页
class StatsPage(QWidget):
    def __init__(self, ctx, parent: QWidget | None = None):
        super().__init__(parent)
        self.ctx = ctx

        inner = QWidget()
        inner.setObjectName("page")
        layout = QVBoxLayout(inner)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(12)

        header = QHBoxLayout()
        title = QLabel("统计")
        title.setObjectName("pageTitle")
        self.range_combo = QComboBox()
        self.range_combo.addItems(["今天", "最近 7 天", "本周", "本月", "自定义"])
        self.range_combo.currentIndexChanged.connect(self._on_range_changed)
        self.date_edit = QDateEdit(QDate.currentDate())
        self.date_edit.setCalendarPopup(True)
        self.date_edit.dateChanged.connect(lambda _: self.refresh())
        self.start_edit = QDateEdit(QDate.currentDate().addDays(-7))
        self.start_edit.setCalendarPopup(True)
        self.start_edit.dateChanged.connect(lambda _: self.refresh())
        self.end_edit = QDateEdit(QDate.currentDate())
        self.end_edit.setCalendarPopup(True)
        self.end_edit.dateChanged.connect(lambda _: self.refresh())
        self.start_label = QLabel("从")
        self.end_label = QLabel("到")
        header.addWidget(title)
        header.addSpacing(12)
        header.addWidget(self.range_combo)
        header.addWidget(self.date_edit)
        header.addWidget(self.start_label)
        header.addWidget(self.start_edit)
        header.addWidget(self.end_label)
        header.addWidget(self.end_edit)
        header.addStretch(1)
        layout.addLayout(header)

        cards = QHBoxLayout()
        cards.setSpacing(12)
        self.card_records = StatCard("记录片段")
        self.card_duration = StatCard("专注时长")
        self.card_days = StatCard("活跃天数")
        self.card_hits = StatCard("采集次数")
        for card in (self.card_records, self.card_duration, self.card_days, self.card_hits):
            cards.addWidget(card, 1)
        layout.addLayout(cards)

        row = QHBoxLayout()
        row.setSpacing(12)
        app_card = Card("应用使用时长")
        self.app_bars = BarListWidget("暂无应用数据")
        app_card.add(self.app_bars)
        category_card = Card("分类分布")
        self.category_bars = BarListWidget("暂无分类数据")
        category_card.add(self.category_bars)
        row.addWidget(app_card, 1)
        row.addWidget(category_card, 1)
        layout.addLayout(row)

        heat_card = Card("时段热力图（周 × 小时）")
        self.heatmap = HeatmapWidget()
        heat_card.add(self.heatmap)
        layout.addWidget(heat_card)

        tag_card = Card("高频标签")
        self.tag_cloud = TagCloudWidget()
        tag_card.add(self.tag_cloud)
        layout.addWidget(tag_card)
        layout.addStretch(1)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(_make_scroll_page(inner))

        self._on_range_changed()

    def _on_range_changed(self) -> None:
        custom = self.range_combo.currentText() == "自定义"
        self.date_edit.setVisible(not custom)
        self.start_edit.setVisible(custom)
        self.end_edit.setVisible(custom)
        self.start_label.setVisible(custom)
        self.end_label.setVisible(custom)
        self.refresh()

    def _range(self) -> tuple[str, str]:
        mode = self.range_combo.currentText()
        ref = self.date_edit.date().toPython()
        if mode == "今天":
            return ref.isoformat(), ref.isoformat()
        if mode == "最近 7 天":
            return (ref - timedelta(days=6)).isoformat(), ref.isoformat()
        if mode == "本周":
            start = ref - timedelta(days=ref.weekday())
            return start.isoformat(), (start + timedelta(days=6)).isoformat()
        if mode == "本月":
            start = ref.replace(day=1)
            last = (start + timedelta(days=40)).replace(day=1) - timedelta(days=1)
            return start.isoformat(), last.isoformat()
        start = self.start_edit.date().toPython()
        end = self.end_edit.date().toPython()
        if end < start:
            start, end = end, start
        return start.isoformat(), end.isoformat()

    def refresh(self) -> None:
        start, end = self._range()
        records = self.ctx.db.records_between(start, end)
        stats = compute_stats(records)
        self.card_records.set_value(str(len(records)), f"{start} ~ {end}")
        self.card_duration.set_value(format_duration(stats["duration"]), "按记录时长估算")
        self.card_days.set_value(str(stats["active_days"]), "有记录的天数")
        self.card_hits.set_value(str(stats["hits"]), "自动采集次数")
        self.app_bars.set_items(stats["by_app"], format_duration)
        self.category_bars.set_items(stats["by_category"], format_duration)
        self.heatmap.set_data(stats["by_hour"])
        self.tag_cloud.set_tags(stats["tags"])


# -------------------------------------------------------------------- 报告页
class ReportsPage(QWidget):
    KIND_LABELS_UI = [("日报", "daily"), ("周报", "weekly"), ("月报", "monthly")]

    def __init__(self, ctx, parent: QWidget | None = None):
        super().__init__(parent)
        self.ctx = ctx
        self.setObjectName("page")
        self._task = None

        layout = QHBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(14)

        left = QVBoxLayout()
        left.setSpacing(8)
        history_title = QLabel("历史报告")
        history_title.setObjectName("muted")
        left.addWidget(history_title)
        self.history = QListWidget()
        self.history.setObjectName("reportList")
        self.history.setFixedWidth(250)
        self.history.currentItemChanged.connect(self._load_selected)
        left.addWidget(self.history, 1)
        layout.addLayout(left)

        right = QVBoxLayout()
        right.setSpacing(10)

        controls = QHBoxLayout()
        controls.setSpacing(8)
        self.kind_combo = QComboBox()
        for label, _key in self.KIND_LABELS_UI:
            self.kind_combo.addItem(label)
        self.kind_combo.currentIndexChanged.connect(lambda _: self._refresh_templates())
        self.date_edit = QDateEdit(QDate.currentDate())
        self.date_edit.setCalendarPopup(True)
        self.template_combo = QComboBox()
        self.template_combo.setMinimumWidth(150)
        self.extra_edit = QLineEdit()
        self.extra_edit.setPlaceholderText("补充要求（可选），例如：语气更简洁")
        self.generate_btn = QPushButton("生成报告")
        self.generate_btn.setObjectName("primary")
        self.generate_btn.clicked.connect(self.generate)
        controls.addWidget(QLabel("类型"))
        controls.addWidget(self.kind_combo)
        controls.addWidget(QLabel("基准日期"))
        controls.addWidget(self.date_edit)
        controls.addWidget(QLabel("模板"))
        controls.addWidget(self.template_combo)
        controls.addWidget(self.extra_edit, 1)
        controls.addWidget(self.generate_btn)
        right.addLayout(controls)

        actions = QHBoxLayout()
        actions.setSpacing(8)
        copy_btn = QPushButton("复制")
        copy_btn.clicked.connect(self._copy)
        save_btn = QPushButton("另存为 Markdown")
        save_btn.clicked.connect(self._save_as)
        delete_btn = QPushButton("删除")
        delete_btn.setObjectName("danger")
        delete_btn.clicked.connect(self._delete)
        open_btn = QPushButton("打开报告目录")
        open_btn.clicked.connect(lambda: open_path(REPORTS_DIR))
        self.status_label = QLabel("")
        self.status_label.setObjectName("muted")
        actions.addWidget(copy_btn)
        actions.addWidget(save_btn)
        actions.addWidget(delete_btn)
        actions.addWidget(open_btn)
        actions.addWidget(self.status_label)
        actions.addStretch(1)
        right.addLayout(actions)

        self.preview = QTextBrowser()
        self.preview.setOpenExternalLinks(True)
        self.preview.setPlaceholderText("选择左侧报告，或点击「生成报告」。")
        right.addWidget(self.preview, 1)
        layout.addLayout(right, 1)

    # ------------------------------------------------------------- 数据加载
    def refresh(self) -> None:
        self._refresh_templates()
        self._refresh_history()

    def prefill(self, kind: str) -> None:
        for index, (_label, key) in enumerate(self.KIND_LABELS_UI):
            if key == kind:
                self.kind_combo.setCurrentIndex(index)
                break
        self._refresh_templates()

    def _kind_key(self) -> str:
        return self.KIND_LABELS_UI[self.kind_combo.currentIndex()][1]

    def _refresh_templates(self) -> None:
        kind = self._kind_key()
        current = self.template_combo.currentText()
        self.template_combo.clear()
        templates = [t for t in self.ctx.db.templates() if t["kind"] == kind]
        if not templates:
            templates = self.ctx.db.templates()
        for template in templates:
            self.template_combo.addItem(template["name"], template["id"])
        default_name = self.ctx.cfg.get("report", "default_template", default="")
        index = self.template_combo.findText(default_name)
        if index >= 0:
            self.template_combo.setCurrentIndex(index)
        elif current:
            index = self.template_combo.findText(current)
            if index >= 0:
                self.template_combo.setCurrentIndex(index)

    def _current_template(self) -> dict | None:
        template_id = self.template_combo.currentData()
        for template in self.ctx.db.templates():
            if template["id"] == template_id:
                return template
        return None

    def _refresh_history(self) -> None:
        self.history.blockSignals(True)
        self.history.clear()
        for report in self.ctx.db.reports():
            item = QListWidgetItem(f"{report['title']}\n{report['created_at'][:16]}")
            item.setData(Qt.UserRole, report["id"])
            self.history.addItem(item)
        self.history.blockSignals(False)
        if self.history.count() and self.history.currentRow() < 0:
            self.history.setCurrentRow(0)

    def _load_selected(self, current, _previous=None) -> None:
        if current is None:
            return
        report_id = current.data(Qt.UserRole)
        report = self.ctx.db.report(int(report_id))
        if report:
            self.preview.setMarkdown(report["content"])
            self.status_label.setText(
                f"{KIND_LABELS.get(report['kind'], '报告')} · {report['start_day']} ~ {report['end_day']}"
            )

    # ------------------------------------------------------------- 生成报告
    def generate(self) -> None:
        kind = self._kind_key()
        ref = self.date_edit.date().toPython()
        start, end, label = range_for(kind, ref)
        records = self.ctx.db.records_between(start, end)
        if not records:
            QMessageBox.information(self, "生成报告", f"{label} 没有任何工作记录。")
            return
        template = self._current_template()
        if template is None:
            QMessageBox.warning(self, "生成报告", "没有可用模板。")
            return

        self.generate_btn.setEnabled(False)
        self.status_label.setText("正在生成，请稍候…")
        extra = self.extra_edit.text()

        def run():
            client = make_client(self.ctx.cfg)
            content = generate_report(client, records, template, label, self.ctx.cfg, extra=extra)
            title = f"{label} {KIND_LABELS.get(kind, '报告')}"
            return kind, start, end, label, title, content, template["name"]

        task = Task(run, self)
        task.done.connect(self._on_generated)
        task.fail.connect(self._on_generate_failed)
        self._task = task
        task.start()

    def _on_generated(self, result) -> None:
        kind, start, end, _label, title, content, template_name = result
        report_id = self.ctx.db.add_report(kind, start, end, title, content, template_name)
        try:
            filename = f"{kind}_{start}_{end}.md"
            (REPORTS_DIR / filename).write_text(content, encoding="utf-8")
        except Exception:
            pass
        self.generate_btn.setEnabled(True)
        self.status_label.setText("已生成并保存")
        self._refresh_history()
        for row in range(self.history.count()):
            item = self.history.item(row)
            if item.data(Qt.UserRole) == report_id:
                self.history.setCurrentRow(row)
                break
        self.preview.setMarkdown(content)

    def _on_generate_failed(self, message: str) -> None:
        self.generate_btn.setEnabled(True)
        self.status_label.setText("生成失败")
        QMessageBox.warning(self, "生成失败", message)

    # ------------------------------------------------------------- 操作按钮
    def _copy(self) -> None:
        text = self.preview.toPlainText().strip()
        if text:
            QApplication.clipboard().setText(text)
            self.status_label.setText("已复制到剪贴板")

    def _save_as(self) -> None:
        text = self.preview.toPlainText().strip()
        if not text:
            return
        default = str(REPORTS_DIR / f"{self.date_edit.date().toString('yyyyMMdd')}_{self._kind_key()}.md")
        filename, _ = QFileDialog.getSaveFileName(self, "另存为", default, "Markdown (*.md)")
        if filename:
            Path(filename).write_text(text, encoding="utf-8")
            self.status_label.setText("已保存")

    def _delete(self) -> None:
        current = self.history.currentItem()
        if current is None:
            return
        report_id = int(current.data(Qt.UserRole))
        if QMessageBox.question(self, "删除报告", "确定删除这份报告吗？") != QMessageBox.Yes:
            return
        self.ctx.db.delete_report(report_id)
        self.preview.clear()
        self._refresh_history()
        self.status_label.setText("已删除")


# -------------------------------------------------------------------- 待办页
class TodoRow(QFrame):
    status_changed = Signal(dict)
    delete_requested = Signal(dict)

    def __init__(self, todo: dict, parent: QWidget | None = None):
        super().__init__(parent)
        self.todo = todo
        self.setObjectName("recordCard")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 6, 10, 6)
        layout.setSpacing(10)

        self.check = QCheckBox()
        self.check.setChecked(todo.get("status") == "done")
        self.check.stateChanged.connect(self._on_check)

        title = QLabel(todo.get("title") or "")
        if todo.get("status") == "done":
            title.setStyleSheet("color:#6f7890; text-decoration: line-through;")
        title.setWordWrap(True)

        due = QLabel(f"截止 {todo['due']}" if todo.get("due") else "")
        due.setObjectName("muted")
        source = QLabel(todo.get("source") or "")
        source.setObjectName("muted")
        source.setFixedWidth(52)

        delete_btn = QPushButton("删除")
        delete_btn.setObjectName("ghost")
        delete_btn.setFixedWidth(56)
        delete_btn.clicked.connect(lambda: self.delete_requested.emit(self.todo))

        layout.addWidget(self.check)
        layout.addWidget(title, 1)
        layout.addWidget(due)
        layout.addWidget(source)
        layout.addWidget(delete_btn)

    def _on_check(self, _state: int) -> None:
        status = "done" if self.check.isChecked() else "open"
        self.status_changed.emit({"id": self.todo["id"], "status": status})


class TodosPage(QWidget):
    data_changed = Signal()

    def __init__(self, ctx, parent: QWidget | None = None):
        super().__init__(parent)
        self.ctx = ctx
        self.setObjectName("page")
        self._task = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(12)

        header = QHBoxLayout()
        title = QLabel("待办")
        title.setObjectName("pageTitle")
        self.count_label = QLabel("")
        self.count_label.setObjectName("muted")
        header.addWidget(title)
        header.addWidget(self.count_label)
        header.addStretch(1)
        layout.addLayout(header)

        add_row = QHBoxLayout()
        add_row.setSpacing(8)
        self.input = QLineEdit()
        self.input.setPlaceholderText("添加待办，回车确认…")
        self.input.returnPressed.connect(self._add)
        self.due_check = QCheckBox("截止")
        self.due_edit = QDateEdit(QDate.currentDate().addDays(1))
        self.due_edit.setCalendarPopup(True)
        self.due_edit.setEnabled(False)
        self.due_check.stateChanged.connect(lambda state: self.due_edit.setEnabled(bool(state)))
        add_btn = QPushButton("添加")
        add_btn.setObjectName("primary")
        add_btn.clicked.connect(self._add)
        add_row.addWidget(self.input, 1)
        add_row.addWidget(self.due_check)
        add_row.addWidget(self.due_edit)
        add_row.addWidget(add_btn)
        layout.addLayout(add_row)

        extract_row = QHBoxLayout()
        extract_row.setSpacing(8)
        extract_label = QLabel("从时间线提取待办：")
        extract_label.setObjectName("muted")
        self.extract_date = QDateEdit(QDate.currentDate())
        self.extract_date.setCalendarPopup(True)
        self.extract_btn = QPushButton("AI 提取")
        self.extract_btn.clicked.connect(self._extract)
        self.status_label = QLabel("")
        self.status_label.setObjectName("muted")
        extract_row.addWidget(extract_label)
        extract_row.addWidget(self.extract_date)
        extract_row.addWidget(self.extract_btn)
        extract_row.addWidget(self.status_label)
        extract_row.addStretch(1)
        layout.addLayout(extract_row)

        self.list_widget = QWidget()
        self.list_widget.setObjectName("page")
        self.list_layout = QVBoxLayout(self.list_widget)
        self.list_layout.setContentsMargins(0, 0, 0, 0)
        self.list_layout.setSpacing(6)
        self.list_layout.addStretch(1)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self.list_widget)
        layout.addWidget(scroll, 1)

        self.refresh()

    def refresh(self) -> None:
        todos = self.ctx.db.todos()
        while self.list_layout.count() > 1:
            item = self.list_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
        if not todos:
            empty = QLabel("还没有待办。可以手动添加，或让 AI 从时间线里提取。")
            empty.setObjectName("muted")
            self.list_layout.insertWidget(0, empty)
        for index, todo in enumerate(todos):
            row = TodoRow(todo)
            row.status_changed.connect(self._on_status_changed)
            row.delete_requested.connect(self._on_delete)
            self.list_layout.insertWidget(index, row)
        open_count = self.ctx.db.open_todo_count()
        self.count_label.setText(f"· {open_count} 项未完成 / 共 {len(todos)} 项")

    def _add(self) -> None:
        title = self.input.text().strip()
        if not title:
            return
        due = self.due_edit.date().toString("yyyy-MM-dd") if self.due_check.isChecked() else ""
        self.ctx.db.add_todo(title=title, due=due, source="手动")
        self.input.clear()
        self.refresh()
        self.data_changed.emit()

    def _on_status_changed(self, payload: dict) -> None:
        self.ctx.db.set_todo_status(int(payload["id"]), payload["status"])
        self.refresh()
        self.data_changed.emit()

    def _on_delete(self, todo: dict) -> None:
        if QMessageBox.question(self, "删除待办", f"删除「{todo['title']}」？") != QMessageBox.Yes:
            return
        self.ctx.db.delete_todo(int(todo["id"]))
        self.refresh()
        self.data_changed.emit()

    def _extract(self) -> None:
        day = self.extract_date.date().toString("yyyy-MM-dd")
        records = self.ctx.db.records_for_day(day)
        if not records:
            QMessageBox.information(self, "提取待办", f"{day} 没有工作记录。")
            return
        if not self.ctx.cfg.get("api", "api_key", default=""):
            QMessageBox.warning(self, "提取待办", "请先在「设置」里配置 AI 接口。")
            return
        self.extract_btn.setEnabled(False)
        self.status_label.setText("正在提取…")
        timeline = build_timeline_text(records)

        def run():
            client = make_client(self.ctx.cfg)
            return extract_todos(client, records, self.ctx.cfg, timeline)

        task = Task(run, self)
        task.done.connect(self._on_extracted)
        task.fail.connect(self._on_extract_failed)
        self._task = task
        task.start()

    def _on_extracted(self, items: list) -> None:
        self.extract_btn.setEnabled(True)
        day = self.extract_date.date().toString("yyyy-MM-dd")
        count = 0
        for item in items:
            self.ctx.db.add_todo(
                title=item.get("title") or "",
                detail=item.get("detail") or "",
                due=item.get("due") or "",
                source="AI提取",
                day=day,
            )
            count += 1
        self.status_label.setText(f"提取到 {count} 条待办" if count else "没有提取到明确的待办")
        self.refresh()
        self.data_changed.emit()

    def _on_extract_failed(self, message: str) -> None:
        self.extract_btn.setEnabled(True)
        self.status_label.setText("提取失败")
        QMessageBox.warning(self, "提取失败", message)


# -------------------------------------------------------------------- 设置页
class SettingsPage(QWidget):
    def __init__(self, ctx, parent: QWidget | None = None):
        super().__init__(parent)
        self.ctx = ctx
        self._task = None

        cfg = self.ctx.cfg
        inner = QWidget()
        inner.setObjectName("page")
        layout = QVBoxLayout(inner)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(12)

        title = QLabel("设置")
        title.setObjectName("pageTitle")
        layout.addWidget(title)

        # ---- API
        api_card = Card("AI 模型接口")
        provider_row = QHBoxLayout()
        provider_label = QLabel("服务商")
        provider_label.setFixedWidth(64)
        self.provider_combo = QComboBox()
        for provider in all_providers():
            self.provider_combo.addItem(provider.name, provider.key)
        self.provider_combo.currentIndexChanged.connect(
            lambda _index: self._on_provider_changed()
        )
        provider_row.addWidget(provider_label)
        provider_row.addWidget(self.provider_combo, 1)
        api_card.add_layout(provider_row)

        key_row = QHBoxLayout()
        key_label = QLabel("API Key")
        key_label.setFixedWidth(64)
        self.api_key = QLineEdit(cfg.get("api", "api_key", default="") or "")
        self.api_key.setEchoMode(QLineEdit.Password)
        self.api_key.setPlaceholderText("粘贴你的 API Key")
        key_row.addWidget(key_label)
        key_row.addWidget(self.api_key, 1)
        api_card.add_layout(key_row)

        self.provider_hint = QLabel("")
        self.provider_hint.setObjectName("muted")
        self.provider_hint.setWordWrap(True)
        api_card.add(self.provider_hint)

        self.advanced_toggle = QToolButton()
        self.advanced_toggle.setText("高级设置（接口地址、模型名等）")
        self.advanced_toggle.setCheckable(True)
        self.advanced_toggle.setArrowType(Qt.RightArrow)
        self.advanced_toggle.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.advanced_toggle.toggled.connect(self._toggle_advanced)
        api_card.add(self.advanced_toggle)

        self.advanced_widget = QWidget()
        advanced_form = QFormLayout(self.advanced_widget)
        advanced_form.setContentsMargins(0, 0, 0, 0)
        advanced_form.setSpacing(9)
        self.base_url = QLineEdit(cfg.get("api", "base_url", default="") or "")
        self.vision_model = QLineEdit(cfg.get("api", "vision_model", default=""))
        self.text_model = QLineEdit(cfg.get("api", "text_model", default=""))
        self.timeout_spin = QSpinBox()
        self.timeout_spin.setRange(10, 600)
        self.timeout_spin.setValue(int(cfg.get("api", "timeout", default=120)))
        self.timeout_spin.setSuffix(" 秒")
        self.max_width_spin = QSpinBox()
        self.max_width_spin.setRange(640, 4096)
        self.max_width_spin.setSingleStep(160)
        self.max_width_spin.setValue(int(cfg.get("api", "max_image_width", default=1280)))
        self.quality_spin = QSpinBox()
        self.quality_spin.setRange(40, 95)
        self.quality_spin.setValue(int(cfg.get("api", "jpeg_quality", default=70)))
        self.extra_edit = QPlainTextEdit(cfg.get("api", "extra_instruction", default="") or "")
        self.extra_edit.setFixedHeight(56)
        self.extra_edit.setPlaceholderText("补充给模型的指令，例如：我在做电商项目，分类时把「直播」归到「运营」")
        advanced_form.addRow("接口地址", self.base_url)
        advanced_form.addRow("视觉模型", self.vision_model)
        advanced_form.addRow("文本模型", self.text_model)
        advanced_form.addRow("请求超时", self.timeout_spin)
        advanced_form.addRow("截图最大宽度", self.max_width_spin)
        advanced_form.addRow("JPEG 质量", self.quality_spin)
        advanced_form.addRow("补充指令", self.extra_edit)
        self.advanced_widget.setVisible(False)
        api_card.add(self.advanced_widget)

        test_row = QHBoxLayout()
        test_btn = QPushButton("测试连接")
        test_btn.setObjectName("primary")
        test_btn.clicked.connect(self._test_connection)
        self.test_status = QLabel("")
        self.test_status.setObjectName("muted")
        self.test_status.setWordWrap(True)
        test_row.addWidget(test_btn)
        test_row.addWidget(self.test_status, 1)
        api_card.add_layout(test_row)
        layout.addWidget(api_card)

        self._init_provider_selection()

        # ---- 记录
        capture_card = Card("记录设置")
        capture_form = QFormLayout()
        capture_form.setSpacing(9)
        self.interval_spin = QSpinBox()
        self.interval_spin.setRange(10, 7200)
        self.interval_spin.setSingleStep(10)
        self.interval_spin.setValue(int(cfg.get("capture", "interval_sec", default=120)))
        self.interval_spin.setSuffix(" 秒")
        self.monitor_combo = QComboBox()
        self.monitor_combo.addItem("所有屏幕（合成）", 0)
        for index in range(1, monitor_count() + 1):
            self.monitor_combo.addItem(f"显示器 {index}", index)
        saved_monitor = int(cfg.get("capture", "monitor", default=1) or 1)
        combo_index = self.monitor_combo.findData(saved_monitor)
        if combo_index >= 0:
            self.monitor_combo.setCurrentIndex(combo_index)
        self.idle_spin = QSpinBox()
        self.idle_spin.setRange(60, 3600)
        self.idle_spin.setSingleStep(60)
        self.idle_spin.setValue(int(cfg.get("capture", "idle_seconds", default=300)))
        self.idle_spin.setSuffix(" 秒")
        self.excluded_edit = QPlainTextEdit(
            "\n".join(cfg.get("capture", "excluded_apps", default=[]) or [])
        )
        self.excluded_edit.setFixedHeight(80)
        self.excluded_edit.setPlaceholderText("每行一个进程名，例如 Chrome.exe")
        self.auto_start_check = QCheckBox("启动应用后自动开始记录")
        self.auto_start_check.setChecked(bool(cfg.get("recording", "auto_start", default=True)))
        capture_form.addRow("截屏间隔", self.interval_spin)
        capture_form.addRow("截屏范围", self.monitor_combo)
        capture_form.addRow("空闲多久后暂停", self.idle_spin)
        capture_form.addRow("排除的应用", self.excluded_edit)
        capture_form.addRow("", self.auto_start_check)
        capture_card.add_layout(capture_form)
        layout.addWidget(capture_card)

        # ---- 隐私
        privacy_card = Card("隐私")
        privacy_note = QLabel(
            "· 截图只在内存中用于一次 AI 分析，分析结束立即销毁，不写入磁盘。\n"
            "· 工作记录、报告和待办保存在程序目录下的 data 文件夹，卸载时可选择保留或删除。\n"
            "· 只有分析请求会发送到你自己配置的模型接口。"
        )
        privacy_note.setObjectName("muted")
        privacy_note.setWordWrap(True)
        privacy_card.add(privacy_note)
        self.scrub_check = QCheckBox("在提示词中要求模型脱敏个人信息（推荐）")
        self.scrub_check.setChecked(bool(cfg.get("privacy", "scrub_personal", default=True)))
        privacy_card.add(self.scrub_check)
        layout.addWidget(privacy_card)

        # ---- 本地 API
        api_server_card = Card("本地 Agent API")
        server_form = QFormLayout()
        server_form.setSpacing(9)
        self.api_enabled_check = QCheckBox("启用本地 API（仅 127.0.0.1 可访问）")
        self.api_enabled_check.setChecked(bool(cfg.get("agent_api", "enabled", default=True)))
        self.api_port_spin = QSpinBox()
        self.api_port_spin.setRange(1024, 65535)
        self.api_port_spin.setValue(int(cfg.get("agent_api", "port", default=8765)))
        self.api_addr_label = QLabel(f"http://127.0.0.1:{self.api_port_spin.value()}/api/timeline")
        self.api_addr_label.setObjectName("muted")
        self.api_port_spin.valueChanged.connect(
            lambda value: self.api_addr_label.setText(f"http://127.0.0.1:{value}/api/timeline")
        )
        server_form.addRow("", self.api_enabled_check)
        server_form.addRow("端口", self.api_port_spin)
        server_form.addRow("", self.api_addr_label)
        api_server_card.add_layout(server_form)
        layout.addWidget(api_server_card)

        # ---- 数据
        data_card = Card("数据")
        data_path_label = QLabel(f"当前数据目录：{DATA_DIR}")
        data_path_label.setObjectName("muted")
        data_path_label.setWordWrap(True)
        data_path_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        data_card.add(data_path_label)
        data_row = QHBoxLayout()
        open_data_btn = QPushButton("打开数据目录")
        open_data_btn.clicked.connect(lambda: open_path(DATA_DIR))
        open_reports_btn = QPushButton("打开报告目录")
        open_reports_btn.clicked.connect(lambda: open_path(REPORTS_DIR))
        export_btn = QPushButton("导出全部数据")
        export_btn.clicked.connect(self._export)
        clear_btn = QPushButton("清空所有记录")
        clear_btn.setObjectName("danger")
        clear_btn.clicked.connect(self._clear)
        for button in (open_data_btn, open_reports_btn, export_btn, clear_btn):
            data_row.addWidget(button)
        data_row.addStretch(1)
        data_card.add_layout(data_row)
        layout.addWidget(data_card)

        # ---- 关于与更新
        update_card = Card("关于与更新")
        version_label = QLabel(f"当前版本：v{__version__}")
        version_label.setObjectName("muted")
        update_card.add(version_label)
        update_row = QHBoxLayout()
        self.check_update_btn = QPushButton("检查更新")
        self.check_update_btn.setObjectName("primary")
        self.check_update_btn.clicked.connect(self._check_update)
        self.pick_installer_btn = QPushButton("选择安装包升级")
        self.pick_installer_btn.clicked.connect(self._pick_installer)
        self.update_status = QLabel("")
        self.update_status.setObjectName("muted")
        self.update_status.setWordWrap(True)
        update_row.addWidget(self.check_update_btn)
        update_row.addWidget(self.pick_installer_btn)
        update_row.addWidget(self.update_status, 1)
        update_card.add_layout(update_row)
        self.auto_update_check = QCheckBox("启动时自动检查更新（推荐）")
        self.auto_update_check.setChecked(bool(cfg.get("update", "auto_check", default=True)))
        update_card.add(self.auto_update_check)
        source_label = QLabel("更新源：GitHub Releases（内置，无需填写任何地址）")
        source_label.setObjectName("muted")
        source_label.setWordWrap(True)
        update_card.add(source_label)
        layout.addWidget(update_card)

        save_row = QHBoxLayout()
        save_btn = QPushButton("保存设置")
        save_btn.setObjectName("primary")
        save_btn.clicked.connect(self._save)
        self.save_status = QLabel("")
        self.save_status.setObjectName("muted")
        save_row.addWidget(save_btn)
        save_row.addWidget(self.save_status, 1)
        layout.addLayout(save_row)
        layout.addStretch(1)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(_make_scroll_page(inner))

    def _init_provider_selection(self) -> None:
        saved_key = self.ctx.cfg.get("api", "provider", default="") or ""
        provider = provider_by_key(saved_key)
        if provider is None:
            provider = match_provider(self.base_url.text().strip())
        if provider is None:
            provider = provider_by_key("custom")
        index = self.provider_combo.findData(provider.key if provider else "custom")
        if index >= 0:
            self.provider_combo.blockSignals(True)
            self.provider_combo.setCurrentIndex(index)
            self.provider_combo.blockSignals(False)
        self._on_provider_changed(initial=True)

    def _toggle_advanced(self, checked: bool) -> None:
        self.advanced_widget.setVisible(checked)
        self.advanced_toggle.setArrowType(Qt.DownArrow if checked else Qt.RightArrow)

    def _on_provider_changed(self, initial: bool = False) -> None:
        provider = provider_by_key(self.provider_combo.currentData())
        if provider is None or provider.key == "custom":
            self.provider_hint.setText(
                "手动填写接口地址（以 /v1 结尾）和模型名，任何 OpenAI 兼容接口都可以。"
            )
            self.api_key.setPlaceholderText("粘贴你的 API Key")
            return
        if not initial:
            self.base_url.setText(provider.base_url)
            if provider.vision_model:
                self.vision_model.setText(provider.vision_model)
            if provider.text_model:
                self.text_model.setText(provider.text_model)
        # 兼容老配置：字段为空时补上预设值
        if not self.base_url.text().strip():
            self.base_url.setText(provider.base_url)
        if not self.vision_model.text().strip() and provider.vision_model:
            self.vision_model.setText(provider.vision_model)
        if not self.text_model.text().strip() and provider.text_model:
            self.text_model.setText(provider.text_model)
        self.provider_hint.setText(provider.hint)
        self.api_key.setPlaceholderText(provider.key_placeholder)
        if provider.key == "ollama" and not self.api_key.text().strip():
            self.api_key.setText("ollama")
        if not self.api_key.text().strip():
            self.api_key.setFocus()

    def _check_update(self) -> None:
        source = resolve_manifest_url(self.ctx.cfg)
        self.update_status.setText("正在检查更新…")
        self.check_update_btn.setEnabled(False)
        task = Task(lambda: fetch_manifest(source), self)
        task.done.connect(self._on_update_manifest)
        task.fail.connect(self._on_update_failed)
        self._update_task = task
        task.start()

    def _on_update_failed(self, message: str) -> None:
        self.check_update_btn.setEnabled(True)
        self.update_status.setText(f"检查失败：{message}")

    def _on_update_manifest(self, manifest: dict) -> None:
        self.check_update_btn.setEnabled(True)
        remote = str(manifest.get("version") or "")
        if not is_newer(remote):
            self.update_status.setText(f"已是最新版本（v{__version__}）")
            return
        notes = str(manifest.get("notes") or "").strip()
        message = f"发现新版本 v{remote}（当前 v{__version__}）"
        if notes:
            message += f"\n\n{notes}"
        message += "\n\n是否立即下载并自动安装？安装完成后程序会自动重新打开。"
        if QMessageBox.question(self, "发现新版本", message) != QMessageBox.Yes:
            self.update_status.setText(f"发现新版本 v{remote}，可稍后再更新")
            return
        url = str(manifest.get("url") or "")
        if not url:
            self.update_status.setText("更新清单缺少下载地址 url")
            return
        self.update_status.setText("正在下载安装包…")
        self.check_update_btn.setEnabled(False)
        task = Task(lambda: download_installer(url), self)
        task.done.connect(self._on_update_downloaded)
        task.fail.connect(self._on_update_failed)
        self._update_task = task
        task.start()

    def _on_update_downloaded(self, path) -> None:
        self.check_update_btn.setEnabled(True)
        self.update_status.setText(f"下载完成：{path}")
        self._run_installer(Path(path))

    def _pick_installer(self) -> None:
        filename, _ = QFileDialog.getOpenFileName(
            self, "选择新版本安装包", "", "安装包 (*.exe)"
        )
        if not filename:
            return
        self._run_installer(Path(filename))

    def _run_installer(self, installer: Path) -> None:
        answer = QMessageBox.question(
            self,
            "自动更新",
            f"即将安装：\n{installer}\n\n"
            "程序会先退出，安装完成后自动重新打开；工作数据会保留。\n\n继续吗？",
        )
        if answer != QMessageBox.Yes:
            return
        try:
            launch_update(installer)
        except Exception as exc:
            QMessageBox.warning(self, "更新失败", str(exc))
            return
        QApplication.quit()

    def _save(self) -> None:
        excluded = [
            line.strip()
            for line in self.excluded_edit.toPlainText().splitlines()
            if line.strip()
        ]
        self.ctx.cfg.update(
            {
                "api": {
                    "provider": self.provider_combo.currentData(),
                    "base_url": self.base_url.text().strip(),
                    "api_key": self.api_key.text().strip(),
                    "vision_model": self.vision_model.text().strip(),
                    "text_model": self.text_model.text().strip(),
                    "timeout": int(self.timeout_spin.value()),
                    "max_image_width": int(self.max_width_spin.value()),
                    "jpeg_quality": int(self.quality_spin.value()),
                    "extra_instruction": self.extra_edit.toPlainText().strip(),
                },
                "capture": {
                    "interval_sec": int(self.interval_spin.value()),
                    "monitor": int(self.monitor_combo.currentData() or 1),
                    "idle_seconds": int(self.idle_spin.value()),
                    "excluded_apps": excluded,
                },
                "recording": {"auto_start": self.auto_start_check.isChecked()},
                "privacy": {"scrub_personal": self.scrub_check.isChecked()},
                "agent_api": {
                    "enabled": self.api_enabled_check.isChecked(),
                    "port": int(self.api_port_spin.value()),
                },
                "update": {
                    "auto_check": self.auto_update_check.isChecked(),
                },
            }
        )
        self.save_status.setText("已保存（API 端口修改需重启应用）")

    def _test_connection(self) -> None:
        base_url = self.base_url.text().strip()
        api_key = self.api_key.text().strip()
        vision_model = self.vision_model.text().strip()
        text_model = self.text_model.text().strip()
        timeout = int(self.timeout_spin.value())
        if not base_url:
            self.test_status.setText("请先选择服务商或填写接口地址")
            return
        if not api_key:
            self.test_status.setText("请先填写 API Key")
            return
        self.test_status.setText("测试中，请稍候…")

        def run():
            import base64
            import io

            from PIL import Image as PILImage

            client = AIClient(base_url, api_key, timeout)
            notes: list[str] = []
            try:
                client.chat(
                    [{"role": "user", "content": "请只回复两个字母：OK"}],
                    model=text_model,
                    max_tokens=10,
                )
                notes.append("文本模型正常")
            except Exception as exc:
                notes.append(f"文本模型失败（{exc}）")
            try:
                buffer = io.BytesIO()
                PILImage.new("RGB", (32, 32), (255, 255, 255)).save(
                    buffer, format="JPEG"
                )
                data_url = "data:image/jpeg;base64," + base64.b64encode(
                    buffer.getvalue()
                ).decode("ascii")
                client.chat(
                    [
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": "请只回复两个字母：OK"},
                                {
                                    "type": "image_url",
                                    "image_url": {"url": data_url},
                                },
                            ],
                        }
                    ],
                    model=vision_model,
                    max_tokens=10,
                )
                notes.append("视觉模型正常")
            except Exception as exc:
                notes.append(f"视觉模型失败（{exc}）")
            client.close()
            return "；".join(notes)

        task = Task(run, self)
        task.done.connect(
            lambda text: self.test_status.setText(text + "。确认无误后点「保存设置」")
        )
        task.fail.connect(lambda message: self.test_status.setText(f"失败：{message}"))
        self._task = task
        task.start()

    def _export(self) -> None:
        default = str(DATA_DIR / "worklog_export.json")
        filename, _ = QFileDialog.getSaveFileName(self, "导出数据", default, "JSON (*.json)")
        if not filename:
            return
        payload = {
            "exported_at": date.today().isoformat(),
            "records": self.ctx.db.records_between("0000-01-01", "9999-12-31"),
            "reports": [
                self.ctx.db.report(report["id"]) for report in self.ctx.db.reports(limit=10000)
            ],
            "todos": self.ctx.db.todos(),
        }
        Path(filename).write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, default=str),
            encoding="utf-8",
        )
        self.save_status.setText("已导出")

    def _clear(self) -> None:
        answer = QMessageBox.warning(
            self,
            "清空所有记录",
            "将删除全部工作记录（报告和待办保留），且不可恢复。确定继续吗？",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return
        self.ctx.db.clear_records()
        self.save_status.setText("已清空所有记录")
