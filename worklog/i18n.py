"""轻量国际化：以中文原文为 key 的运行时翻译 + Qt 界面树翻译。

用法：
- 启动时 `set_language(resolve_language(cfg.get("ui", "language")))`
- 动态文案用 `tr("中文原文")` 或 `tr("带 {n} 的文案").format(n=...)`
- 静态界面在 refresh/构造后调用 `translate_widget_tree(widget)` 自动替换
"""

from __future__ import annotations

import ctypes
import os
import sys

from ._catalog_en import CATEGORY_EN, EN

# 语言设置选项（与 config.json 的 ui.language 取值对应）
LANGUAGES: dict[str, str] = {
    "auto": "自动 / Auto",
    "zh": "简体中文",
    "en": "English",
}

_language = "zh"


# ------------------------------------------------------------------ 语言设置
def detect_system_language() -> str:
    """跟随系统定位：Windows 看 UI 语言，其他平台看环境变量。"""
    if sys.platform == "win32":
        try:
            lang_id = ctypes.windll.kernel32.GetUserDefaultUILanguage()
            return "zh" if (lang_id & 0xFF) == 0x04 else "en"
        except Exception:
            pass
    locale = (os.environ.get("LC_ALL") or os.environ.get("LANG") or "").lower()
    if locale.startswith("zh"):
        return "zh"
    if locale:
        return "en"
    return "zh"


def resolve_language(setting: str | None) -> str:
    setting = (setting or "auto").strip().lower()
    if setting in ("zh", "en"):
        return setting
    return detect_system_language()


def set_language(language: str) -> None:
    global _language
    _language = language if language in ("zh", "en") else "zh"


def get_language() -> str:
    return _language


def is_english() -> bool:
    return _language == "en"


# -------------------------------------------------------------------- 翻译
def tr(text: str) -> str:
    """中文原文 -> 当前语言文案；没有英文条目时原样返回。"""
    if _language == "en":
        return EN.get(text, text)
    return text


def category_display(category: str) -> str:
    """数据库中的分类值（中文）转显示名。"""
    if _language == "en":
        return CATEGORY_EN.get(category, category)
    return category


def category_key(display: str) -> str:
    """界面上的分类名反查为数据库规范值（中文）。"""
    if _language == "en":
        for key, value in CATEGORY_EN.items():
            if value == display:
                return key
    return display


# ---------------------------------------------------------------- 界面树翻译
def translate_widget_tree(root) -> None:
    """把界面树上精确命中的中文文案替换成当前语言（幂等、只替换已知文案）。"""
    if not is_english() or root is None:
        return
    from PySide6.QtWidgets import QWidget

    objects = [root]
    try:
        objects.extend(root.findChildren(QWidget))
    except Exception:
        pass
    for widget in objects:
        try:
            _translate_widget(widget)
        except Exception:
            continue


def translate_menu(menu) -> None:
    """翻译 QMenu / 菜单栏（不属于窗口子控件的情况）。"""
    if not is_english() or menu is None:
        return
    for action in menu.actions():
        text = action.text()
        if text in EN:
            action.setText(EN[text])
        submenu = action.menu()
        if submenu is not None:
            translate_menu(submenu)


def _translate_text(text: str) -> str | None:
    return EN.get(text)


def _translate_widget(widget) -> None:
    from PySide6.QtWidgets import (
        QAbstractButton,
        QComboBox,
        QGroupBox,
        QLabel,
        QLineEdit,
        QListWidget,
        QMenu,
        QTabWidget,
        QTextBrowser,
    )

    title = widget.windowTitle()
    if title and title in EN:
        widget.setWindowTitle(EN[title])

    if isinstance(widget, QLabel):
        text = widget.text()
        if text and "<" not in text:
            translated = _translate_text(text)
            if translated:
                widget.setText(translated)
        tooltip = widget.toolTip()
        if tooltip and tooltip in EN:
            widget.setToolTip(EN[tooltip])

    if isinstance(widget, QAbstractButton):
        translated = _translate_text(widget.text())
        if translated:
            widget.setText(translated)

    if isinstance(widget, (QLineEdit, QTextBrowser)):
        translated = _translate_text(widget.placeholderText())
        if translated:
            widget.setPlaceholderText(translated)

    if isinstance(widget, QComboBox):
        for index in range(widget.count()):
            translated = _translate_text(widget.itemText(index))
            if translated:
                widget.setItemText(index, translated)

    if isinstance(widget, QListWidget):
        for row in range(widget.count()):
            item = widget.item(row)
            translated = _translate_text(item.text())
            if translated:
                item.setText(translated)

    if isinstance(widget, QGroupBox):
        translated = _translate_text(widget.title())
        if translated:
            widget.setTitle(translated)

    if isinstance(widget, QTabWidget):
        for index in range(widget.count()):
            translated = _translate_text(widget.tabText(index))
            if translated:
                widget.setTabText(index, translated)

    if isinstance(widget, QMenu):
        translate_menu(widget)
