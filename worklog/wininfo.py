"""Windows 前台窗口、空闲与锁屏检测。

非 Windows 平台或调用失败时返回安全的兜底值。
"""

from __future__ import annotations

import ctypes
import ctypes.wintypes as wt
import sys


class _LASTINPUTINFO(ctypes.Structure):
    _fields_ = [("cbSize", wt.UINT), ("dwTime", wt.DWORD)]


_IS_WINDOWS = sys.platform == "win32"

if _IS_WINDOWS:
    _user32 = ctypes.windll.user32
    _kernel32 = ctypes.windll.kernel32


def get_idle_seconds() -> float:
    """距离上一次键鼠输入经过的秒数。"""
    if not _IS_WINDOWS:
        return 0.0
    try:
        info = _LASTINPUTINFO()
        info.cbSize = ctypes.sizeof(info)
        if not _user32.GetLastInputInfo(ctypes.byref(info)):
            return 0.0
        tick = _kernel32.GetTickCount()
        return max(0.0, (tick - info.dwTime) / 1000.0)
    except Exception:
        return 0.0


def is_locked() -> bool:
    """当前是否处于锁屏 / 未登录状态。"""
    if not _IS_WINDOWS:
        return False
    try:
        # DESKTOP_READOBJECTS = 0x0001
        desktop = _user32.OpenInputDesktop(0, False, 0x0001)
        if not desktop:
            return True
        _user32.CloseDesktop(desktop)
        return False
    except Exception:
        return False


def get_foreground() -> tuple[str, str, int] | None:
    """返回 (进程名, 窗口标题, PID)；失败返回 None。"""
    if not _IS_WINDOWS:
        return None
    try:
        hwnd = _user32.GetForegroundWindow()
        if not hwnd:
            return None
        length = _user32.GetWindowTextLengthW(hwnd)
        buffer = ctypes.create_unicode_buffer(length + 1)
        _user32.GetWindowTextW(hwnd, buffer, length + 1)
        title = buffer.value or ""

        pid = wt.DWORD()
        _user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        pid_value = int(pid.value)

        app = ""
        try:
            import psutil

            app = psutil.Process(pid_value).name() or ""
        except Exception:
            app = ""

        return app, title, pid_value
    except Exception:
        return None


def monitor_count() -> int:
    """物理显示器数量（mss.monitors[0] 是所有屏幕的合成）。"""
    try:
        import mss

        factory = getattr(mss, "MSS", None) or mss.mss
        with factory() as sct:
            return max(1, len(sct.monitors) - 1)
    except Exception:
        return 1
