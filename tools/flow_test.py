"""端到端流程测试：mock 一个 OpenAI 兼容接口，验证记录、报告、待办全链路。

运行：uv run python tools/flow_test.py
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

TEMP_DIR = Path(tempfile.mkdtemp(prefix="worklog_flow_"))
os.environ["WORKLOG_DATA_DIR"] = str(TEMP_DIR)

from PySide6.QtCore import QCoreApplication, QTimer  # noqa: E402

from worklog.ai import AIClient  # noqa: E402
from worklog.analyze import classify_text, extract_todos  # noqa: E402
from worklog.config import Config, ensure_dirs  # noqa: E402
from worklog.db import Database  # noqa: E402
from worklog.recorder import RecorderEngine  # noqa: E402
from worklog.reporting import (  # noqa: E402
    DEFAULT_TEMPLATES,
    build_timeline_text,
    generate_report,
)

VISION_JSON = json.dumps(
    {
        "category": "开发",
        "summary": "模拟分析：写代码",
        "details": "mock 详情",
        "project": "mock 项目",
        "tags": ["mock", "测试"],
        "is_work": True,
        "sensitive": False,
    },
    ensure_ascii=False,
)
REPORT_MD = "# 模拟报告\n\n## 今日工作成果\n- 完成了端到端测试\n\n## 下一步计划\n- 接真实模型"
TODOS_JSON = json.dumps(
    [{"title": "完成真实配置", "detail": "填入 API Key", "due": ""}],
    ensure_ascii=False,
)


def _user_text(payload: dict) -> tuple[str, bool]:
    messages = payload.get("messages") or []
    if not messages:
        return "", False
    content = messages[-1].get("content")
    if isinstance(content, list):
        text = "\n".join(
            str(part.get("text") or "") for part in content if isinstance(part, dict)
        )
        has_image = any(
            isinstance(part, dict) and part.get("type") == "image_url" for part in content
        )
        return text, has_image
    return str(content or ""), False


class MockHandler(BaseHTTPRequestHandler):
    counters: dict = {}
    last_payload: dict = {}

    def log_message(self, fmt, *args):
        return

    def do_POST(self):
        length = int(self.headers.get("Content-Length") or 0)
        payload = json.loads(self.rfile.read(length).decode("utf-8"))
        MockHandler.last_payload = payload
        model = str(payload.get("model") or "")
        text, has_image = _user_text(payload)

        finish_reason = "stop"
        reasoning = ""
        if model == "empty-length-model":
            content = ""
            finish_reason = "length"
            reasoning = "thinking for a very long time"
        elif model == "retry-model":
            count = MockHandler.counters.get("retry", 0) + 1
            MockHandler.counters["retry"] = count
            if count == 1:
                content = ""
                finish_reason = "length"
                reasoning = "first attempt exhausted the budget"
            else:
                content = "OK"
        elif has_image:
            content = VISION_JSON
        elif "待办事项" in text or "提取其中" in text:
            content = TODOS_JSON
        elif "推断用户" in text:
            content = VISION_JSON
        elif "工作日报" in text or "工作周报" in text or "工作时间线" in text:
            content = REPORT_MD
        else:
            content = "OK"

        message: dict = {"role": "assistant", "content": content}
        if reasoning:
            message["reasoning_content"] = reasoning
        body = json.dumps(
            {
                "choices": [
                    {"message": message, "finish_reason": finish_reason}
                ]
            },
            ensure_ascii=False,
        ).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main() -> int:
    server = ThreadingHTTPServer(("127.0.0.1", 18999), MockHandler)
    threading.Thread(target=server.serve_forever, daemon=True).start()

    app = QCoreApplication(sys.argv)
    ensure_dirs()
    cfg = Config()
    cfg.update(
        {
            "api": {
                "base_url": "http://127.0.0.1:18999/v1",
                "api_key": "test-key",
                "vision_model": "mock-vision",
                "text_model": "mock-text",
                "timeout": 30,
            },
            "capture": {"interval_sec": 10},
        }
    )
    db = Database(TEMP_DIR / "worklog.db")
    db.seed_templates(DEFAULT_TEMPLATES)

    engine = RecorderEngine(cfg, db)
    errors: list[str] = []
    added: list[dict] = []
    engine.error.connect(errors.append)
    engine.record_added.connect(added.append)

    engine.start()
    engine.capture_now()
    QTimer.singleShot(6000, app.quit)
    app.exec()
    engine.stop()

    records = db.records_between("0000-01-01", "9999-12-31")
    assert records, f"没有生成记录，errors={errors}"
    analyzed = [r for r in records if r["pending"] == 0]
    assert analyzed, f"记录未被分析：{records}"
    latest = analyzed[-1]
    print("记录:", latest["app"], "|", latest["category"], "|", latest["summary"])
    assert latest["category"] == "开发"
    assert "模拟分析" in latest["summary"]

    client = AIClient("http://127.0.0.1:18999/v1", "test-key", 30)
    template = db.templates()[0]
    content = generate_report(client, records, template, "2026-10-02", cfg)
    assert "模拟报告" in content, content
    print("报告生成: OK")

    todos = extract_todos(client, records, cfg, build_timeline_text(records))
    assert todos and todos[0]["title"] == "完成真实配置", todos
    print("待办提取: OK")

    classified = classify_text(client, "Code.exe", "main.py", "2026-10-02 10:00:00", cfg)
    assert classified["category"] == "开发", classified
    print("文本补分析: OK")

    # 思考模式：空内容要报错，被长度截断要自动翻倍重试
    from worklog.ai import AIError

    try:
        client.chat(
            [{"role": "user", "content": "hi"}],
            model="empty-length-model",
            max_tokens=100,
        )
        raise AssertionError("空内容没有报错")
    except AIError as exc:
        assert "思考" in str(exc) or "空" in str(exc), str(exc)
    print("空内容处理: OK")

    reply = client.chat(
        [{"role": "user", "content": "hi"}], model="retry-model", max_tokens=100
    )
    assert reply == "OK", reply
    print("截断自动重试: OK")

    client_thinking = AIClient(
        "http://127.0.0.1:18999/v1", "test-key", 30, thinking="disabled"
    )
    client_thinking.chat(
        [{"role": "user", "content": "hi"}], model="mock-text", max_tokens=10
    )
    assert MockHandler.last_payload.get("thinking") == {"type": "disabled"}
    client_thinking.close()
    print("思考模式参数透传: OK")

    server.shutdown()
    print("\n全链路测试通过。数据目录:", TEMP_DIR)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
