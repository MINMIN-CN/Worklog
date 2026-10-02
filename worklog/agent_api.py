"""本地 HTTP API：让外部 Agent / 脚本读取和补充工作记录。

默认监听 127.0.0.1:8765，仅本机可访问。
"""

from __future__ import annotations

import json
import threading
from datetime import date
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from .db import Database
from .stats import compute_stats


def _today() -> str:
    return date.today().isoformat()


class _Handler(BaseHTTPRequestHandler):
    db: Database = None  # type: ignore[assignment]
    server_version = "WorkLog/0.1"

    def log_message(self, fmt, *args):  # 静默
        return

    # ------------------------------------------------------------- 响应工具
    def _send(self, payload, code: int = 200) -> None:
        body = json.dumps(payload, ensure_ascii=False, indent=2, default=str).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PATCH, DELETE, OPTIONS")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _error(self, message: str, code: int = 400) -> None:
        self._send({"ok": False, "error": message}, code)

    def _read_json(self) -> dict:
        try:
            length = int(self.headers.get("Content-Length") or 0)
            raw = self.rfile.read(length) if length else b"{}"
            data = json.loads(raw.decode("utf-8") or "{}")
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    def _query(self) -> dict:
        parsed = urlparse(self.path)
        return {key: values[0] for key, values in parse_qs(parsed.query).items()}

    # ------------------------------------------------------------------ 路由
    def do_OPTIONS(self):
        self._send({})

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"
        query = self._query()

        if path == "/":
            self._send(
                {
                    "name": "工作小记 API",
                    "endpoints": [
                        "GET /api/health",
                        "GET /api/timeline?date=YYYY-MM-DD | ?start=&end=",
                        "GET /api/stats?date= | ?start=&end=",
                        "GET /api/app-usage?date=",
                        "GET /api/todos",
                        "GET /api/reports",
                        "GET /api/reports/{id}",
                        "POST /api/records",
                        "POST /api/todos",
                        "PATCH /api/todos/{id}",
                    ],
                }
            )
            return

        if path == "/api/health":
            self._send({"ok": True, "records_today": len(self.db.records_for_day(_today()))})
            return

        if path == "/api/timeline":
            start = query.get("start") or query.get("date") or _today()
            end = query.get("end") or query.get("date") or start
            self._send({"ok": True, "records": self.db.records_between(start, end)})
            return

        if path == "/api/stats":
            start = query.get("start") or query.get("date") or _today()
            end = query.get("end") or query.get("date") or start
            records = self.db.records_between(start, end)
            stats = compute_stats(records)
            stats["by_app"] = [[name, seconds] for name, seconds in stats["by_app"]]
            stats["by_category"] = [[name, seconds] for name, seconds in stats["by_category"]]
            stats["tags"] = [[name, count] for name, count in stats["tags"]]
            stats["by_hour"] = {f"{day}-{hour}": value for (day, hour), value in stats["by_hour"].items()}
            self._send({"ok": True, "stats": stats})
            return

        if path == "/api/app-usage":
            day = query.get("date") or _today()
            records = self.db.records_for_day(day)
            stats = compute_stats(records)
            self._send({"ok": True, "date": day, "apps": [[name, seconds] for name, seconds in stats["by_app"]]})
            return

        if path == "/api/todos":
            self._send({"ok": True, "todos": self.db.todos()})
            return

        if path == "/api/reports":
            self._send({"ok": True, "reports": self.db.reports()})
            return

        if path.startswith("/api/reports/"):
            try:
                report_id = int(path.split("/")[-1])
            except ValueError:
                self._error("无效的报告 ID")
                return
            report = self.db.report(report_id)
            if not report:
                self._error("报告不存在", 404)
                return
            self._send({"ok": True, "report": report})
            return

        self._error("接口不存在", 404)

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")
        payload = self._read_json()

        if path == "/api/records":
            title = str(payload.get("title") or "").strip()
            app = str(payload.get("app") or "").strip()
            if not title and not app:
                self._error("至少需要提供 title 或 app")
                return
            start_ts = str(payload.get("start_ts") or "")
            if not start_ts:
                from datetime import datetime

                start_ts = datetime.now().isoformat(timespec="seconds")
            end_ts = str(payload.get("end_ts") or start_ts)
            record_id = self.db.add_record(
                day=start_ts[:10],
                start_ts=start_ts,
                end_ts=end_ts,
                app=app or "外部写入",
                title=title,
                category=str(payload.get("category") or "其他"),
                summary=str(payload.get("summary") or title),
                details=str(payload.get("details") or ""),
                project=str(payload.get("project") or ""),
                tags=payload.get("tags") or [],
                hits=1,
                source="api",
                pending=0,
            )
            self._send({"ok": True, "id": record_id})
            return

        if path == "/api/todos":
            title = str(payload.get("title") or "").strip()
            if not title:
                self._error("title 不能为空")
                return
            todo_id = self.db.add_todo(
                title=title,
                detail=str(payload.get("detail") or ""),
                due=str(payload.get("due") or ""),
                source="api",
            )
            self._send({"ok": True, "id": todo_id})
            return

        self._error("接口不存在", 404)

    def do_PATCH(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")
        payload = self._read_json()

        if path.startswith("/api/todos/"):
            try:
                todo_id = int(path.split("/")[-1])
            except ValueError:
                self._error("无效的待办 ID")
                return
            status = str(payload.get("status") or "")
            if status in ("open", "done"):
                self.db.set_todo_status(todo_id, status)
            self._send({"ok": True})
            return

        self._error("接口不存在", 404)


class AgentAPI:
    def __init__(self, db: Database, port: int = 8765):
        self.db = db
        self.port = int(port)
        self._server: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None

    def start(self) -> bool:
        if self._server:
            return True
        handler = type("WorkLogHandler", (_Handler,), {"db": self.db})
        try:
            self._server = ThreadingHTTPServer(("127.0.0.1", self.port), handler)
        except OSError:
            return False
        self._thread = threading.Thread(
            target=self._server.serve_forever, name="worklog-api", daemon=True
        )
        self._thread.start()
        return True

    def stop(self) -> None:
        if self._server:
            try:
                self._server.shutdown()
                self._server.server_close()
            except Exception:
                pass
        self._server = None
        self._thread = None
