"""PyInstaller 入口脚本（打包用）。

直接用 `worklog/__main__.py` 会因为没有包上下文而无法相对导入，
所以用这个脚本从包外调用；同时把未捕获异常写入数据目录，方便排查。
"""

from __future__ import annotations

import traceback


def _run() -> int:
    from worklog.app import main

    return main()


def _write_error_log() -> None:
    try:
        from worklog.config import DATA_DIR

        DATA_DIR.mkdir(parents=True, exist_ok=True)
        (DATA_DIR / "worklog_error.log").write_text(
            traceback.format_exc(), encoding="utf-8"
        )
    except Exception:
        pass


if __name__ == "__main__":
    try:
        exit_code = _run()
    except SystemExit:
        raise
    except BaseException:
        _write_error_log()
        raise
    raise SystemExit(exit_code)
