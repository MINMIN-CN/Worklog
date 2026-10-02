"""冒烟测试：验证核心模块与界面可构造（使用临时数据目录，不触碰真实数据）。

运行：uv run python tools/smoke_test.py
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import urllib.request
from datetime import date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

TEMP_DIR = Path(tempfile.mkdtemp(prefix="worklog_smoke_"))
os.environ["WORKLOG_DATA_DIR"] = str(TEMP_DIR)
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

failures: list[str] = []


def check(name: str, fn) -> None:
    try:
        fn()
        print(f"[OK]   {name}")
    except Exception as exc:  # noqa: BLE001
        failures.append(f"{name}: {exc!r}")
        print(f"[FAIL] {name}: {exc!r}")


# --------------------------------------------------------------- 基础模块
from PySide6.QtWidgets import QApplication  # noqa: E402

from worklog.ai import parse_json_list_loose, parse_json_loose  # noqa: E402
from worklog.analyze import _normalize  # noqa: E402
from worklog.config import Config, ensure_dirs, migrate_legacy_data  # noqa: E402
from worklog.db import Database  # noqa: E402
from worklog.reporting import (  # noqa: E402
    DEFAULT_TEMPLATES,
    build_timeline_text,
    range_for,
)
from worklog.stats import compute_stats, format_duration  # noqa: E402
from worklog.wininfo import (  # noqa: E402
    get_foreground,
    get_idle_seconds,
    is_locked,
    monitor_count,
)

qt_app = QApplication.instance() or QApplication(sys.argv)

ensure_dirs()
cfg = Config()
db = Database(TEMP_DIR / "worklog.db")
db.seed_templates(DEFAULT_TEMPLATES)


def test_windows_info() -> None:
    assert get_idle_seconds() >= 0
    assert isinstance(is_locked(), bool)
    assert monitor_count() >= 1


def test_json_loose() -> None:
    assert parse_json_loose('```json\n{"a": 1}\n```') == {"a": 1}
    assert parse_json_loose('前缀 {"b": 2} 后缀') == {"b": 2}
    assert parse_json_list_loose('好的：[{"title":"x"}]') == [{"title": "x"}]
    assert parse_json_list_loose('{"todos": [{"title": "y"}]}') == [{"title": "y"}]


def test_normalize() -> None:
    result = _normalize(
        {"category": "开发", "summary": "写代码", "tags": "a,b"},
        {"category": "未分类", "summary": "", "details": "", "project": "", "tags": []},
    )
    assert result["category"] == "开发"
    assert result["tags"] == ["a", "b"]


def test_db_records() -> None:
    now = datetime.now().replace(microsecond=0)
    first = db.add_record(
        day=now.strftime("%Y-%m-%d"),
        start_ts=(now - timedelta(hours=2)).isoformat(timespec="seconds"),
        end_ts=(now - timedelta(hours=1, minutes=40)).isoformat(timespec="seconds"),
        app="Code.exe",
        title="main.py",
        category="开发",
        summary="调试冒烟测试",
        project="worklog",
        tags=["python", "测试"],
        hits=3,
        source="auto",
        pending=0,
    )
    second = db.add_record(
        day=now.strftime("%Y-%m-%d"),
        start_ts=(now - timedelta(hours=1)).isoformat(timespec="seconds"),
        end_ts=(now - timedelta(minutes=30)).isoformat(timespec="seconds"),
        app="chrome.exe",
        title="文档",
        category="文档",
        summary="阅读资料",
        tags=["资料"],
        source="auto",
        pending=1,
    )
    assert len(db.records_for_day(now.strftime("%Y-%m-%d"))) == 2
    db.extend_record(first, now.isoformat(timespec="seconds"), 1)
    db.update_record(second, pending=0)
    assert db.pending_for_day(now.strftime("%Y-%m-%d")) == []
    assert db.last_record(now.strftime("%Y-%m-%d"))["id"] == second
    assert db.records_between("0000-01-01", "9999-12-31")


def test_stats() -> None:
    today = datetime.now().strftime("%Y-%m-%d")
    stats = compute_stats(db.records_for_day(today))
    assert stats["count"] >= 2
    assert stats["duration"] > 0
    assert stats["by_app"]
    assert format_duration(3660) == "1 小时 1 分"


def test_ranges() -> None:
    assert range_for("daily", date(2026, 10, 2))[0] == "2026-10-02"
    assert range_for("weekly", date(2026, 10, 2))[0] == "2026-09-28"
    assert range_for("monthly", date(2026, 2, 15))[1] == "2026-02-28"


def test_timeline_and_templates() -> None:
    today = datetime.now().strftime("%Y-%m-%d")
    timeline = build_timeline_text(db.records_for_day(today))
    assert timeline.count("[") >= 2
    assert len(db.templates()) >= 4


def test_todos() -> None:
    todo_id = db.add_todo("写测试", due=datetime.now().strftime("%Y-%m-%d"), source="手动")
    assert db.open_todo_count() == 1
    db.set_todo_status(todo_id, "done")
    assert db.open_todo_count() == 0
    db.delete_todo(todo_id)


def test_reports() -> None:
    today = datetime.now().strftime("%Y-%m-%d")
    report_id = db.add_report("daily", today, today, "测试报告", "# 标题", "测试模板")
    assert db.report(report_id)["title"] == "测试报告"
    assert db.reports()
    db.delete_report(report_id)


def test_providers() -> None:
    from worklog.providers import all_providers, match_provider, provider_by_key

    providers = all_providers()
    assert len(providers) >= 10, len(providers)
    dashscope = provider_by_key("dashscope")
    assert dashscope and dashscope.vision_model and dashscope.base_url
    assert provider_by_key("custom") is not None
    matched = match_provider("https://api.openai.com/v1/")
    assert matched is not None and matched.key == "openai"
    assert match_provider("https://example.com/v1") is None
    deepseek = provider_by_key("deepseek")
    assert deepseek is not None
    assert deepseek.base_url == "https://api.deepseek.com"
    assert deepseek.vision_model == "deepseek-flash"


def test_migration() -> None:
    import tempfile

    legacy = Path(tempfile.mkdtemp(prefix="worklog_legacy_")) / "data"
    legacy.mkdir(parents=True)
    (legacy / "worklog.db").write_text("legacy-db", encoding="utf-8")
    (legacy / "config.json").write_text(
        '{"api": {"api_key": "legacy-key"}}', encoding="utf-8"
    )
    (legacy / "reports").mkdir()
    (legacy / "reports" / "a.md").write_text("# x", encoding="utf-8")
    (legacy / "tmp").mkdir()
    (legacy / "tmp" / "junk.bin").write_bytes(b"x" * 16)

    target = Path(tempfile.mkdtemp(prefix="worklog_new_")) / "data"
    migrated = migrate_legacy_data(target, candidates=[legacy])
    assert migrated == legacy
    assert (target / "worklog.db").read_text(encoding="utf-8") == "legacy-db"
    assert "legacy-key" in (target / "config.json").read_text(encoding="utf-8")
    assert (target / "reports" / "a.md").exists()
    assert not (target / "tmp").exists()
    assert not legacy.exists()
    backup = legacy.with_name(legacy.name + "_已迁移_可删除")
    assert backup.exists()
    # 目标已有数据时不再迁移
    assert migrate_legacy_data(target, candidates=[backup]) is None


def test_updater() -> None:
    import tempfile

    from worklog.updater import (
        DEFAULT_MANIFEST_URL,
        fetch_manifest,
        is_newer,
        parse_version,
        resolve_manifest_url,
    )

    assert parse_version("v0.3.0") == (0, 3, 0)
    assert parse_version("0.3") == (0, 3)
    assert is_newer("0.3.0", "0.2.1")
    assert is_newer("1.0.0", "0.9.9")
    assert not is_newer("0.2.1", "0.2.1")
    assert not is_newer("0.2.0", "0.2.1")

    # 内置更新源：无需用户配置
    assert DEFAULT_MANIFEST_URL.startswith("https://github.com/")
    assert resolve_manifest_url(cfg) == DEFAULT_MANIFEST_URL
    assert (
        resolve_manifest_url(cfg, "https://example.com/a.json")
        == "https://example.com/a.json"
    )
    cfg.update({"update": {"manifest_url": "https://example.com/custom.json"}})
    try:
        assert resolve_manifest_url(cfg) == "https://example.com/custom.json"
    finally:
        cfg.update({"update": {"manifest_url": ""}})
    assert resolve_manifest_url(cfg) == DEFAULT_MANIFEST_URL

    # 本地清单元数据
    manifest_path = Path(tempfile.mkdtemp(prefix="worklog_manifest_")) / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {"version": "9.9.9", "url": "http://example.com/x.exe", "notes": "test"}
        ),
        encoding="utf-8",
    )
    manifest = fetch_manifest(str(manifest_path))
    assert manifest["version"] == "9.9.9"


def test_config_migration() -> None:
    """0.3.0 的配置（auto_check=false、无 config_version）应迁移为启用内置更新。"""
    import tempfile

    path = Path(tempfile.mkdtemp(prefix="worklog_cfg_")) / "config.json"
    path.write_text(
        json.dumps({"update": {"manifest_url": "", "auto_check": False}}),
        encoding="utf-8",
    )
    migrated = Config(path)
    assert migrated.get("update", "auto_check", default=False) is True
    assert migrated.get("config_version", default=0) == 2
    # 用户手动关闭后保持不变
    migrated.update({"update": {"auto_check": False}})
    reloaded = Config(path)
    assert reloaded.get("update", "auto_check", default=True) is False
    # 用户自定义地址时不覆盖 auto_check
    path2 = Path(tempfile.mkdtemp(prefix="worklog_cfg2_")) / "config.json"
    path2.write_text(
        json.dumps(
            {"update": {"manifest_url": "https://example.com/m.json", "auto_check": False}}
        ),
        encoding="utf-8",
    )
    custom = Config(path2)
    assert custom.get("update", "auto_check", default=True) is False
    assert custom.get("update", "manifest_url", default="") == "https://example.com/m.json"


def test_repo_manifest() -> None:
    """仓库里的 update/manifest.json 必须是合法清单且地址可用。"""
    manifest_path = Path(__file__).resolve().parent.parent / "update" / "manifest.json"
    assert manifest_path.exists(), "缺少 update/manifest.json"
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert data.get("version")
    assert str(data.get("url", "")).startswith("https://github.com/")
    assert data["url"].endswith(".exe")


def test_capture() -> None:
    import mss

    from worklog.capture import (
        Capture,
        average_hash,
        encode_jpeg,
        grab_screen,
        hamming,
        to_data_url,
    )

    factory = getattr(mss, "MSS", None) or mss.mss
    with factory() as sct:
        image, index = grab_screen(sct, 1)
        assert image.width > 0 and image.height > 0
        fingerprint = average_hash(image)
        jpeg = encode_jpeg(image, 1280, 70)
        assert len(jpeg) > 1000, len(jpeg)
        assert to_data_url(jpeg).startswith("data:image/jpeg;base64,")
        capture = Capture(datetime.now(), "test.exe", "测试", jpeg, fingerprint, index)
        assert hamming(capture.ahash, fingerprint) == 0


from worklog.recorder import RecorderEngine  # noqa: E402

engine = RecorderEngine(cfg, db)


def test_engine_store() -> None:
    base = datetime.now().replace(microsecond=0)
    record = {
        "day": base.strftime("%Y-%m-%d"),
        "start_ts": base.isoformat(timespec="seconds"),
        "end_ts": (base + timedelta(minutes=2)).isoformat(timespec="seconds"),
        "app": "merge.exe",
        "title": "窗口",
        "category": "开发",
        "summary": "合并测试",
        "details": "",
        "project": "",
        "tags": [],
        "hits": 1,
        "source": "auto",
        "pending": 0,
    }
    engine._store(dict(record))
    second = dict(record)
    second["start_ts"] = (base + timedelta(minutes=2)).isoformat(timespec="seconds")
    second["end_ts"] = (base + timedelta(minutes=4)).isoformat(timespec="seconds")
    engine._store(second)
    latest = db.last_record(record["day"])
    assert latest["app"] == "merge.exe"
    assert latest["hits"] >= 2, latest


from worklog.agent_api import AgentAPI  # noqa: E402

api = AgentAPI(db, 18765)


def test_api_start() -> None:
    assert api.start(), "API 启动失败"


def test_api_endpoints() -> None:
    with urllib.request.urlopen("http://127.0.0.1:18765/api/health", timeout=5) as response:
        payload = json.loads(response.read().decode("utf-8"))
        assert payload["ok"] is True
    with urllib.request.urlopen("http://127.0.0.1:18765/api/timeline", timeout=5) as response:
        payload = json.loads(response.read().decode("utf-8"))
        assert payload["ok"] is True and isinstance(payload["records"], list)
    with urllib.request.urlopen("http://127.0.0.1:18765/api/stats", timeout=5) as response:
        payload = json.loads(response.read().decode("utf-8"))
        assert payload["ok"] is True and "stats" in payload
    request = urllib.request.Request(
        "http://127.0.0.1:18765/api/todos",
        data=json.dumps({"title": "来自 API 的待办"}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=5) as response:
        assert json.loads(response.read().decode("utf-8"))["ok"] is True
    request = urllib.request.Request(
        "http://127.0.0.1:18765/api/records",
        data=json.dumps({"title": "外部写入记录", "app": "agent.exe", "category": "其他"}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=5) as response:
        assert json.loads(response.read().decode("utf-8"))["ok"] is True


from worklog.context import AppContext  # noqa: E402
from worklog.ui.main_window import MainWindow  # noqa: E402
from worklog.ui.theme import QSS  # noqa: E402
from worklog.ui.widgets import make_icon  # noqa: E402

qt_app.setStyleSheet(QSS)
qt_app.setWindowIcon(make_icon())
ctx = AppContext(cfg=cfg, db=db, engine=engine, api=None)


def test_window() -> None:
    window = MainWindow(ctx)
    try:
        assert window.stack.count() == 6
        for index in range(6):
            window.nav.setCurrentRow(index)
            page = window.stack.currentWidget()
            if hasattr(page, "refresh"):
                page.refresh()
        window.stats_page.refresh()
        window.today_page.refresh()
    finally:
        window._really_quit = True
        window.tray.hide()
        window.close()
        window.deleteLater()


# -------------------------------------------------------------------- 执行
check("windows info", test_windows_info)
check("foreground info", lambda: get_foreground())
check("json loose parse", test_json_loose)
check("normalize result", test_normalize)
check("db records", test_db_records)
check("db stats", test_stats)
check("report ranges", test_ranges)
check("timeline & templates", test_timeline_and_templates)
check("todos crud", test_todos)
check("reports crud", test_reports)
check("provider presets", test_providers)
check("legacy data migration", test_migration)
check("updater", test_updater)
check("config migration", test_config_migration)
check("repo manifest", test_repo_manifest)
check("screen capture", test_capture)
check("engine store merge", test_engine_store)
check("agent api start", test_api_start)
check("agent api endpoints", test_api_endpoints)
api.stop()
check("main window build", test_window)

print()
if failures:
    print(f"共 {len(failures)} 项失败：")
    for item in failures:
        print(" -", item)
    sys.exit(1)
print("全部通过。临时目录：", TEMP_DIR)
