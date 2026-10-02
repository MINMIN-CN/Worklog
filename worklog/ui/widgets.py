"""通用界面组件：卡片、统计数字、条形榜、热力图、记录卡片、后台任务。"""

from __future__ import annotations

import threading
from datetime import datetime

from PySide6.QtCore import QObject, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMenu,
    QProgressBar,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from .. import i18n

WEEKDAYS = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]


def refresh_style(widget: QWidget) -> None:
    widget.style().unpolish(widget)
    widget.style().polish(widget)


def make_icon(size: int = 64) -> QIcon:
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setPen(Qt.NoPen)
    painter.setBrush(QColor("#2f6bff"))
    margin = size * 0.03
    painter.drawRoundedRect(
        QRectF(margin, margin, size - 2 * margin, size - 2 * margin),
        size * 0.22,
        size * 0.22,
    )
    painter.setPen(QColor("#ffffff"))
    font = QFont("Microsoft YaHei", int(size * 0.4), QFont.Bold)
    painter.setFont(font)
    painter.drawText(QRectF(0, 0, size, size), Qt.AlignCenter, "记")
    painter.end()
    return QIcon(pixmap)


def fmt_time(iso: str) -> str:
    try:
        return datetime.fromisoformat(iso).strftime("%H:%M")
    except Exception:
        return "--:--"


class Card(QFrame):
    def __init__(self, title: str = "", parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("card")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(14, 12, 14, 12)
        outer.setSpacing(8)
        self.title_label = QLabel(title)
        self.title_label.setObjectName("cardTitle")
        self.title_label.setVisible(bool(title))
        outer.addWidget(self.title_label)
        self.body = QVBoxLayout()
        self.body.setContentsMargins(0, 0, 0, 0)
        self.body.setSpacing(6)
        outer.addLayout(self.body, 1)

    def set_title(self, text: str) -> None:
        self.title_label.setText(text)
        self.title_label.setVisible(bool(text))

    def add(self, widget: QWidget) -> None:
        self.body.addWidget(widget)

    def add_layout(self, layout) -> None:
        self.body.addLayout(layout)


class StatCard(Card):
    def __init__(self, title: str, parent: QWidget | None = None):
        super().__init__("", parent)
        self.set_title(title)
        self.value_label = QLabel("-")
        self.value_label.setObjectName("cardValue")
        self.sub_label = QLabel("")
        self.sub_label.setObjectName("cardSub")
        self.add(self.value_label)
        self.add(self.sub_label)

    def set_value(self, value: str, sub: str = "") -> None:
        self.value_label.setText(str(value))
        self.sub_label.setText(sub)


class BarListWidget(QWidget):
    """横向条形排行（应用、分类等）。"""

    def __init__(
        self,
        empty_text: str = "暂无数据",
        max_items: int = 8,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self._empty_text = empty_text
        self._max_items = max_items
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(7)

    def _clear(self) -> None:
        while self._layout.count():
            item = self._layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

    def set_items(self, items: list, formatter=None) -> None:
        self._clear()
        formatter = formatter or (lambda value: str(value))
        items = list(items)[: self._max_items]
        if not items:
            empty = QLabel(self._empty_text)
            empty.setObjectName("cardSub")
            self._layout.addWidget(empty)
            return
        max_value = max(value for _, value in items) or 1
        for name, value in items:
            row = QWidget()
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(10)

            label = QLabel(str(name))
            label.setFixedWidth(118)
            label.setToolTip(str(name))
            bar = QProgressBar()
            bar.setRange(0, 1000)
            bar.setValue(int(max(0.0, value) / max_value * 1000))
            bar.setTextVisible(False)
            bar.setFixedHeight(10)
            amount = QLabel(formatter(value))
            amount.setObjectName("cardSub")
            amount.setFixedWidth(92)
            amount.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

            row_layout.addWidget(label)
            row_layout.addWidget(bar, 1)
            row_layout.addWidget(amount)
            self._layout.addWidget(row)


class HeatmapWidget(QWidget):
    """周 × 小时 热力图。数据为 {(weekday, hour): seconds}。"""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._data: dict = {}
        self.setMinimumHeight(210)

    def set_data(self, data: dict) -> None:
        self._data = data or {}
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        left, top, right, bottom = 40, 8, 8, 24
        plot_w = max(1, self.width() - left - right)
        plot_h = max(1, self.height() - top - bottom)
        cell_w = plot_w / 24
        cell_h = plot_h / 7

        max_value = max(self._data.values(), default=0) or 1
        base = QColor("#141a24")
        hot = QColor("#2f6bff")
        for day in range(7):
            for hour in range(24):
                value = self._data.get((day, hour), 0)
                ratio = min(1.0, value / max_value)
                color = QColor(
                    int(base.red() + (hot.red() - base.red()) * ratio),
                    int(base.green() + (hot.green() - base.green()) * ratio),
                    int(base.blue() + (hot.blue() - base.blue()) * ratio),
                )
                painter.fillRect(
                    QRectF(
                        left + hour * cell_w + 1,
                        top + day * cell_h + 1,
                        max(1.0, cell_w - 2),
                        max(1.0, cell_h - 2),
                    ),
                    color,
                )

        painter.setPen(QColor("#6f7890"))
        font = painter.font()
        font.setPointSize(8)
        painter.setFont(font)
        for hour in range(0, 24, 3):
            painter.drawText(
                QRectF(left + hour * cell_w, self.height() - bottom + 4, cell_w * 3, bottom),
                Qt.AlignLeft | Qt.AlignVCenter,
                f"{hour:02d}",
            )
        for day in range(7):
            painter.drawText(
                QRectF(0, top + day * cell_h, left - 8, cell_h),
                Qt.AlignRight | Qt.AlignVCenter,
                i18n.tr(WEEKDAYS[day]),
            )
        painter.end()


class TagCloudWidget(QLabel):
    def __init__(self, empty_text: str = "暂无标签", parent: QWidget | None = None):
        super().__init__(parent)
        self._empty_text = empty_text
        self.setWordWrap(True)
        self.setTextFormat(Qt.RichText)
        self.setText(
            f"<span style='color:#6f7890'>{i18n.tr(empty_text)}</span>"
        )

    def set_tags(self, items: list) -> None:
        items = list(items)[:24]
        if not items:
            self.setText(
                f"<span style='color:#6f7890'>{i18n.tr(self._empty_text)}</span>"
            )
            return
        max_count = max(count for _, count in items) or 1
        min_count = min(count for _, count in items)
        span = max(1, max_count - min_count)
        parts = []
        for name, count in items:
            ratio = (count - min_count) / span
            size = 12 + round(ratio * 7)
            color = "#7fb0ff" if ratio > 0.5 else "#9aa3b5"
            parts.append(
                f"<span style='font-size:{size}px; color:{color}'>{name}</span>"
            )
        self.setText("&nbsp;&nbsp; ".join(parts))


class Task(QObject):
    """在后台线程执行函数，结果通过信号回到主线程。"""

    done = Signal(object)
    fail = Signal(str)

    def __init__(self, fn, parent: QObject | None = None):
        super().__init__(parent)
        self._fn = fn
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self) -> None:
        try:
            result = self._fn()
        except Exception as exc:
            self.fail.emit(str(exc))
            return
        self.done.emit(result)


class ProgressTask(QObject):
    """带进度和取消的后台任务。

    fn(report, cancel) -> result；report(done, total, speed, source) 可在任意线程调用。
    """

    progress = Signal(int, int, float, str)
    done = Signal(object)
    fail = Signal(str)
    cancelled = Signal()

    def __init__(self, fn, parent: QObject | None = None):
        super().__init__(parent)
        self._fn = fn
        self._cancel = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def cancel(self) -> None:
        self._cancel.set()

    def _report(self, done, total, speed, source) -> None:
        self.progress.emit(int(done), int(total), float(speed), str(source))

    def _run(self) -> None:
        from ..updater import DownloadCancelled

        try:
            result = self._fn(self._report, self._cancel)
        except DownloadCancelled:
            self.cancelled.emit()
            return
        except Exception as exc:
            if self._cancel.is_set():
                self.cancelled.emit()
            else:
                self.fail.emit(str(exc))
            return
        self.done.emit(result)


class RecordCard(QFrame):
    edit_requested = Signal(dict)
    delete_requested = Signal(dict)

    def __init__(self, record: dict, parent: QWidget | None = None):
        super().__init__(parent)
        self.record = record
        self.setObjectName("recordCard")
        self.setToolTip(record.get("details") or record.get("title") or "")

        outer = QVBoxLayout(self)
        outer.setContentsMargins(12, 8, 12, 8)
        outer.setSpacing(3)

        top = QHBoxLayout()
        top.setSpacing(8)
        time_label = QLabel(
            f"{fmt_time(record.get('start_ts', ''))} – {fmt_time(record.get('end_ts', ''))}"
        )
        time_label.setObjectName("recordTime")
        time_label.setFixedWidth(104)
        category = QLabel(i18n.category_display(record.get("category") or "未分类"))
        category.setObjectName("chip")
        app_label = QLabel(
            f"{record.get('app') or '未知'} · {record.get('title') or ''}".rstrip(" ·")
        )
        app_label.setObjectName("recordApp")
        hits = int(record.get("hits") or 1)
        hits_label = QLabel(f"×{hits}" if hits > 1 else "")
        hits_label.setObjectName("cardSub")
        pending = int(record.get("pending") or 0)
        pending_label = QLabel(i18n.tr("待分析") if pending else "")
        pending_label.setObjectName("cardSub")

        top.addWidget(time_label)
        top.addWidget(category)
        top.addWidget(app_label, 1)
        top.addWidget(pending_label)
        top.addWidget(hits_label)
        outer.addLayout(top)

        summary = QLabel(record.get("summary") or "")
        summary.setObjectName("recordSummary")
        summary.setWordWrap(True)
        outer.addWidget(summary)

        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_menu)

    def _show_menu(self, pos) -> None:
        menu = QMenu(self)
        edit_action = menu.addAction("编辑")
        delete_action = menu.addAction("删除")
        chosen = menu.exec(self.mapToGlobal(pos))
        if chosen == edit_action:
            self.edit_requested.emit(self.record)
        elif chosen == delete_action:
            self.delete_requested.emit(self.record)

    def mouseDoubleClickEvent(self, event) -> None:
        self.edit_requested.emit(self.record)
        super().mouseDoubleClickEvent(event)


class RecordListWidget(QScrollArea):
    edit_requested = Signal(dict)
    delete_requested = Signal(dict)

    def __init__(self, empty_text: str = "暂无记录", parent: QWidget | None = None):
        super().__init__(parent)
        self._empty_text = empty_text
        self.setWidgetResizable(True)
        container = QWidget()
        container.setObjectName("page")
        self._layout = QVBoxLayout(container)
        self._layout.setContentsMargins(2, 2, 2, 2)
        self._layout.setSpacing(6)
        self._layout.addStretch(1)
        self.setWidget(container)

    def set_records(self, records: list) -> None:
        while self._layout.count() > 1:
            item = self._layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
        if not records:
            empty = QLabel(self._empty_text)
            empty.setObjectName("muted")
            self._layout.insertWidget(0, empty)
            return
        for index, record in enumerate(records):
            card = RecordCard(record)
            card.edit_requested.connect(self.edit_requested)
            card.delete_requested.connect(self.delete_requested)
            self._layout.insertWidget(index, card)
