"""完整启动测试：真实走一遍 app.main()，2.5 秒后自动退出。

使用临时数据目录，不会影响真实数据。
运行：uv run python tools/app_start_test.py
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

TEMP_DIR = Path(tempfile.mkdtemp(prefix="worklog_start_"))
os.environ["WORKLOG_DATA_DIR"] = str(TEMP_DIR)
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QTimer  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

import worklog.app as app_module  # noqa: E402

_original_exec = QApplication.exec


def _auto_quit_exec(self=None):
    QTimer.singleShot(2500, QApplication.instance().quit)
    return _original_exec()


QApplication.exec = _auto_quit_exec  # type: ignore[method-assign]

# 本机可能正运行着正式版应用（占用单实例互斥体），测试时跳过该检查
app_module._single_instance_guard = lambda wait_seconds=0.0: True  # type: ignore[assignment]

code = app_module.main()
print(f"应用正常启动并退出，exit code = {code}，数据目录 = {TEMP_DIR}")
sys.exit(code)
