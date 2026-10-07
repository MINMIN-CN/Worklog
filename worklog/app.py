"""应用入口。"""

from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from . import APP_NAME, i18n
from .agent_api import AgentAPI
from .config import DB_PATH, Config, ensure_dirs
from .context import AppContext
from .db import Database
from .recorder import RecorderEngine
from .reporting import all_default_templates
from .ui.main_window import MainWindow
from .ui.theme import QSS
from .ui.widgets import make_icon

_MUTEX_HANDLES: list = []


def _single_instance_guard(wait_seconds: float = 0.0) -> bool:
    """保证只有一个实例在运行。

    升级重启时带 --wait-instance，会等待旧进程退出后再接管（最多 wait_seconds 秒）；
    普通重复启动则直接提示并退出。
    """
    if sys.platform != "win32":
        return True
    try:
        import ctypes
        import time

        kernel32 = ctypes.windll.kernel32
        user32 = ctypes.windll.user32
        SYNCHRONIZE = 0x00100000
        ERROR_ALREADY_EXISTS = 183
        deadline = time.monotonic() + max(0.0, wait_seconds)

        while True:
            existing = kernel32.OpenMutexW(SYNCHRONIZE, False, "WorkLogAppMutex")
            if existing:
                kernel32.CloseHandle(existing)
                if time.monotonic() >= deadline:
                    user32.MessageBoxW(
                        None,
                        i18n.tr("工作小记已经在运行，请在系统托盘查看。"),
                        i18n.tr("工作小记"),
                        0x40,  # MB_ICONINFORMATION
                    )
                    return False
                time.sleep(0.5)
                continue
            handle = kernel32.CreateMutexW(None, False, "WorkLogAppMutex")
            if handle:
                if kernel32.GetLastError() == ERROR_ALREADY_EXISTS:
                    kernel32.CloseHandle(handle)
                    continue
                _MUTEX_HANDLES.append(handle)
                return True
            if time.monotonic() >= deadline:
                return True
            time.sleep(0.5)
    except Exception:
        return True
    return True


def main() -> int:
    # 单实例提示出现在读取配置之前，先按系统语言初始化
    i18n.set_language(i18n.detect_system_language())
    wait_instance = "--wait-instance" in sys.argv
    minimized = "--minimized" in sys.argv
    sys.argv = [
        argument
        for argument in sys.argv
        if argument not in ("--wait-instance", "--minimized")
    ]
    if not _single_instance_guard(20.0 if wait_instance else 0.0):
        return 0

    ensure_dirs()

    cfg = Config()
    i18n.set_language(i18n.resolve_language(cfg.get("ui", "language", default="auto")))
    db = Database(DB_PATH)
    db.seed_templates(all_default_templates())

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationDisplayName(APP_NAME)
    app.setOrganizationName("WorkLog")
    app.setQuitOnLastWindowClosed(False)
    app.setStyleSheet(QSS)
    app.setWindowIcon(make_icon())

    engine = RecorderEngine(cfg, db)
    if cfg.get("recording", "auto_start", default=True):
        engine.start()

    api = None
    if cfg.get("agent_api", "enabled", default=True):
        api = AgentAPI(db, int(cfg.get("agent_api", "port", default=8765) or 8765))
        if not api.start():
            api = None

    ctx = AppContext(cfg=cfg, db=db, engine=engine, api=api)
    window = MainWindow(ctx)
    if minimized:
        # 开机自启：静默进入托盘后台记录，不弹出主窗口
        window.hide()
        window.tray.showMessage(
            APP_NAME,
            i18n.tr("已在后台开始记录，可在系统托盘查看。"),
            make_icon(),
            4000,
        )
    else:
        window.show()

    code = app.exec()

    engine.stop()
    if api:
        api.stop()
    db.close()
    return code
