"""开机自启动开关测试（使用独立的测试注册表值，不影响真实配置）。

运行：uv run python tools/autostart_test.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from worklog import autostart  # noqa: E402

TEST_VALUE = "WorkLogAutostartTest"


def main() -> int:
    if sys.platform != "win32":
        print("非 Windows 平台，跳过开机自启动测试")
        return 0

    # 源码运行模式：界面会禁用开关，也不应生成启动命令
    assert not autostart.is_supported(), "源码模式不应报告支持开机自启动"
    assert autostart.installed_command() == "", "源码模式不应生成启动命令"

    command = '"C:\\fake\\WorkLog.exe" --minimized'
    try:
        autostart.set_enabled(True, value_name=TEST_VALUE, command=command)
        assert autostart.is_enabled(value_name=TEST_VALUE), "写入测试注册表值失败"
        assert autostart._run_value(TEST_VALUE) == command, "注册表值内容不正确"
    finally:
        autostart.set_enabled(False, value_name=TEST_VALUE)
    assert not autostart.is_enabled(value_name=TEST_VALUE), "删除测试注册表值失败"

    shortcut = autostart.legacy_shortcut_path()
    assert shortcut.name == autostart.LEGACY_SHORTCUT_NAME
    print("开机自启动测试通过")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
