"""为安装版测试准备一份"旧版本数据"在 %LOCALAPPDATA%\\WorkLog\\data。

仅用于自动化测试，会在真实旧数据目录写入标记内容，测试结束后请清理。
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from worklog.db import Database  # noqa: E402


def main() -> int:
    base = Path(os.environ.get("LOCALAPPDATA") or Path.home())
    legacy = base / "WorkLog" / "data"
    legacy.mkdir(parents=True, exist_ok=True)

    (legacy / "config.json").write_text(
        json.dumps(
            {
                "api": {
                    "provider": "zhipu",
                    "base_url": "https://open.bigmodel.cn/api/paas/v4",
                    "api_key": "MIGRATION_TEST_KEY",
                    "vision_model": "glm-4.5v",
                    "text_model": "glm-4.5-flash",
                }
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    db = Database(legacy / "worklog.db")
    db.add_record(
        day="2026-10-01",
        start_ts="2026-10-01T09:00:00",
        end_ts="2026-10-01T09:10:00",
        app="legacy.exe",
        title="old record",
        category="开发",
        summary="migration test",
        source="auto",
        pending=0,
        tags=["old"],
    )
    db.close()
    print("legacy data prepared at:", legacy)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
