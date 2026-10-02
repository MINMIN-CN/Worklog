"""记录编辑对话框。"""

from __future__ import annotations

from PySide6.QtCore import QDateTime, Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDateTimeEdit,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLineEdit,
    QPlainTextEdit,
    QVBoxLayout,
    QWidget,
)

from ..analyze import CATEGORIES


def _parse_dt(value: str) -> QDateTime:
    dt = QDateTime.fromString(value, Qt.ISODate)
    if not dt.isValid():
        dt = QDateTime.currentDateTime()
    return dt


class RecordEditDialog(QDialog):
    def __init__(self, record: dict | None = None, parent: QWidget | None = None):
        super().__init__(parent)
        record = record or {}
        self.setWindowTitle("编辑记录" if record.get("id") else "手动添加记录")
        self.setMinimumWidth(480)

        layout = QVBoxLayout(self)
        form = QFormLayout()
        form.setSpacing(9)

        start_value = record.get("start_ts") or ""
        self.start_edit = QDateTimeEdit(_parse_dt(start_value))
        self.start_edit.setDisplayFormat("yyyy-MM-dd HH:mm:ss")
        self.start_edit.setCalendarPopup(True)

        self.end_edit = QDateTimeEdit(_parse_dt(record.get("end_ts") or start_value))
        self.end_edit.setDisplayFormat("yyyy-MM-dd HH:mm:ss")
        self.end_edit.setCalendarPopup(True)

        self.category_edit = QComboBox()
        self.category_edit.setEditable(True)
        self.category_edit.addItems(CATEGORIES)
        self.category_edit.setCurrentText(record.get("category") or "其他")

        self.summary_edit = QLineEdit(record.get("summary") or "")
        self.summary_edit.setPlaceholderText("一句话说明做了什么")
        self.details_edit = QPlainTextEdit(record.get("details") or "")
        self.details_edit.setFixedHeight(84)
        self.project_edit = QLineEdit(record.get("project") or "")
        self.tags_edit = QLineEdit("，".join(record.get("tags") or []))
        self.tags_edit.setPlaceholderText("用逗号分隔，最多 3 个")

        form.addRow("开始时间", self.start_edit)
        form.addRow("结束时间", self.end_edit)
        form.addRow("分类", self.category_edit)
        form.addRow("摘要", self.summary_edit)
        form.addRow("详情", self.details_edit)
        form.addRow("项目", self.project_edit)
        form.addRow("标签", self.tags_edit)
        layout.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Ok).setText("保存")
        buttons.button(QDialogButtonBox.Cancel).setText("取消")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def values(self) -> dict:
        start = self.start_edit.dateTime().toString(Qt.ISODate)
        end = self.end_edit.dateTime().toString(Qt.ISODate)
        if end < start:
            end = start
        tags = [
            part.strip()
            for part in self.tags_edit.text().replace("，", ",").split(",")
            if part.strip()
        ][:3]
        return {
            "day": start[:10],
            "start_ts": start,
            "end_ts": end,
            "category": self.category_edit.currentText().strip() or "其他",
            "summary": self.summary_edit.text().strip(),
            "details": self.details_edit.toPlainText().strip(),
            "project": self.project_edit.text().strip(),
            "tags": tags,
        }
