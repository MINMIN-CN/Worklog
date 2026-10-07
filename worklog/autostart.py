"""开机自启动管理。

应用内开关使用 HKCU\\...\\Run 注册表项；同时兼容旧版安装器在「启动」文件夹
里创建的快捷方式（安装时勾选「开机自启动」会产生），检测到时会一并处理。
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

try:
    import winreg
except ImportError:  # pragma: no cover - 非 Windows
    winreg = None  # type: ignore[assignment]

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
VALUE_NAME = "WorkLog"
# 旧版安装器创建的启动文件夹快捷方式名
LEGACY_SHORTCUT_NAME = "工作小记.lnk"


def legacy_shortcut_path() -> Path:
    appdata = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
    return (
        Path(appdata)
        / "Microsoft"
        / "Windows"
        / "Start Menu"
        / "Programs"
        / "Startup"
        / LEGACY_SHORTCUT_NAME
    )


def installed_command() -> str:
    """开机启动要执行的命令；源码运行模式返回空字符串。"""
    if not getattr(sys, "frozen", False):
        return ""
    return f'"{Path(sys.executable)}" --minimized'


def is_supported() -> bool:
    """只有打包安装版支持开机自启动。"""
    return sys.platform == "win32" and winreg is not None and bool(installed_command())


def _run_value(value_name: str) -> str:
    if winreg is None:
        return ""
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            value, _ = winreg.QueryValueEx(key, value_name)
        return str(value or "")
    except OSError:
        return ""


def is_enabled(value_name: str = VALUE_NAME) -> bool:
    if _run_value(value_name):
        return True
    if value_name != VALUE_NAME:
        return False
    try:
        return legacy_shortcut_path().exists()
    except OSError:
        return False


def _remove_legacy_shortcut() -> None:
    try:
        legacy_shortcut_path().unlink(missing_ok=True)
    except OSError:
        pass


def set_enabled(
    enabled: bool, value_name: str = VALUE_NAME, command: str | None = None
) -> None:
    """开关开机自启动；command 仅供测试注入。"""
    if winreg is None:
        raise RuntimeError("当前系统不支持开机自启动")
    if enabled:
        resolved = command if command is not None else installed_command()
        if not resolved:
            raise RuntimeError("仅安装版支持开机自启动")
        with winreg.CreateKeyEx(
            winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE
        ) as key:
            winreg.SetValueEx(key, value_name, 0, winreg.REG_SZ, resolved)
        _remove_legacy_shortcut()
    else:
        try:
            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE
            ) as key:
                winreg.DeleteValue(key, value_name)
        except OSError:
            pass
        _remove_legacy_shortcut()
