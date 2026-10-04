"""验证应用内更新的“退出后静默安装”机制（含中文与空格路径）。

用一个假的安装脚本代替真实安装包：launch_update 会先生成更新脚本并返回，
本进程退出后脚本才会执行。运行后由外部命令检查标记文件是否生成。
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from worklog.updater import launch_update  # noqa: E402

# 故意使用带中文和空格的目录，验证脚本编码处理
WORK_DIR = Path(tempfile.gettempdir()) / "工作小记 更新测试"
MARKER = Path(tempfile.gettempdir()) / "worklog_update_test_marker.txt"
FAKE = WORK_DIR / "fake installer.cmd"


def main() -> int:
    WORK_DIR.mkdir(parents=True, exist_ok=True)
    if MARKER.exists():
        MARKER.unlink()
    # 注意：cmd 批处理不能带 BOM，内容保持纯 ASCII
    FAKE.write_text(
        "@echo off\r\necho installed > \"%TEMP%\\worklog_update_test_marker.txt\"\r\n",
        encoding="ascii",
    )
    script = launch_update(FAKE, restart=False)
    print("update script created:", script)
    print("fake installer:", FAKE)
    print("marker expected at:", MARKER)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
