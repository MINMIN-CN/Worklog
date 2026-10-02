"""验证应用内更新的“退出后静默安装”机制。

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

MARKER = Path(tempfile.gettempdir()) / "worklog_update_test_marker.txt"
FAKE = Path(tempfile.gettempdir()) / "worklog_fake_installer.cmd"


def main() -> int:
    if MARKER.exists():
        MARKER.unlink()
    FAKE.write_text(
        "@echo off\r\n" f'echo installed > "{MARKER}"\r\n',
        encoding="utf-8",
    )
    script = launch_update(FAKE, restart=False)
    print("update script created:", script)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
