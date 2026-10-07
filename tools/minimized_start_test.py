"""静默启动测试：带 --minimized 启动时不显示主窗口（离屏运行，不影响真实数据）。

运行：uv run python tools/minimized_start_test.py
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

os.environ["WORKLOG_DATA_DIR"] = str(tempfile.mkdtemp(prefix="worklog_minimized_"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QTimer  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

import worklog.app as app_module  # noqa: E402

sys.argv = ["worklog", "--minimized"]

captured: list = []
_original_main_window = app_module.MainWindow


class CapturingMainWindow(_original_main_window):  # type: ignore[misc, valid-type]
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        captured.append(self)


app_module.MainWindow = CapturingMainWindow  # type: ignore[assignment]

_original_exec = QApplication.exec


def _auto_quit_exec(self=None):
    QTimer.singleShot(2500, QApplication.instance().quit)
    return _original_exec()


QApplication.exec = _auto_quit_exec  # type: ignore[method-assign]
app_module._single_instance_guard = lambda wait_seconds=0.0: True  # type: ignore[assignment]

code = app_module.main()
assert code == 0, f"异常退出：{code}"
assert captured, "没有创建主窗口"
window = captured[0]
assert not window.isVisible(), "带 --minimized 启动时不应显示主窗口"
window.tray.hide()
print("静默启动测试通过（主窗口隐藏）")
sys.exit(0)
