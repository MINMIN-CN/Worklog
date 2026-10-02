"""SQLite 数据层。

所有记录、报告、待办、模板都保存在 data/worklog.db。
连接使用 check_same_thread=False + 互斥锁，供多线程安全访问。
"""

from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    day TEXT NOT NULL,
    start_ts TEXT NOT NULL,
    end_ts TEXT NOT NULL,
    app TEXT DEFAULT '',
    title TEXT DEFAULT '',
    category TEXT DEFAULT '未分类',
    summary TEXT DEFAULT '',
    details TEXT DEFAULT '',
    project TEXT DEFAULT '',
    tags TEXT DEFAULT '[]',
    hits INTEGER DEFAULT 1,
    source TEXT DEFAULT 'auto',
    pending INTEGER DEFAULT 0,
    created_at TEXT DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_records_day ON records(day);

CREATE TABLE IF NOT EXISTS reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    kind TEXT DEFAULT 'daily',
    start_day TEXT DEFAULT '',
    end_day TEXT DEFAULT '',
    title TEXT DEFAULT '',
    content TEXT DEFAULT '',
    template TEXT DEFAULT '',
    created_at TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS todos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    detail TEXT DEFAULT '',
    status TEXT DEFAULT 'open',
    due TEXT DEFAULT '',
    source TEXT DEFAULT '',
    day TEXT DEFAULT '',
    created_at TEXT DEFAULT '',
    done_at TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS templates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE,
    kind TEXT DEFAULT 'daily',
    instruction TEXT DEFAULT '',
    builtin INTEGER DEFAULT 0,
    lang TEXT DEFAULT 'zh',
    created_at TEXT DEFAULT ''
);
"""

RECORD_FIELDS = [
    "day",
    "start_ts",
    "end_ts",
    "app",
    "title",
    "category",
    "summary",
    "details",
    "project",
    "tags",
    "hits",
    "source",
    "pending",
    "created_at",
]


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


class Database:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(str(self.path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        with self._lock:
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA synchronous=NORMAL")
            self._conn.executescript(SCHEMA)
            self._conn.commit()
            # 旧库升级：templates 增加 lang 列（中文/英文模板共存）
            columns = [row["name"] for row in self._query("PRAGMA table_info(templates)")]
            if "lang" not in columns:
                self._conn.execute(
                    "ALTER TABLE templates ADD COLUMN lang TEXT DEFAULT 'zh'"
                )
                self._conn.commit()

    # ------------------------------------------------------------------ 基础
    def _execute(self, sql: str, params: tuple = ()) -> sqlite3.Cursor:
        with self._lock:
            cur = self._conn.execute(sql, params)
            self._conn.commit()
            return cur

    def _query(self, sql: str, params: tuple = ()) -> list[dict]:
        with self._lock:
            cur = self._conn.execute(sql, params)
            return [dict(row) for row in cur.fetchall()]

    @staticmethod
    def _record_dict(row: dict) -> dict:
        item = dict(row)
        try:
            item["tags"] = json.loads(item.get("tags") or "[]")
        except Exception:
            item["tags"] = []
        return item

    # ---------------------------------------------------------------- records
    def add_record(self, **fields) -> int:
        data = {name: fields.get(name, "") for name in RECORD_FIELDS}
        data["hits"] = int(fields.get("hits") or 1)
        data["pending"] = int(fields.get("pending") or 0)
        data["created_at"] = fields.get("created_at") or _now()
        if isinstance(data["tags"], (list, tuple)):
            data["tags"] = json.dumps(list(data["tags"]), ensure_ascii=False)
        cols = ", ".join(RECORD_FIELDS)
        marks = ", ".join(["?"] * len(RECORD_FIELDS))
        cur = self._execute(
            f"INSERT INTO records ({cols}) VALUES ({marks})",
            tuple(data[name] for name in RECORD_FIELDS),
        )
        return int(cur.lastrowid)

    def update_record(self, record_id: int, **fields) -> None:
        allowed = {k: v for k, v in fields.items() if k in RECORD_FIELDS}
        if isinstance(allowed.get("tags"), (list, tuple)):
            allowed["tags"] = json.dumps(list(allowed["tags"]), ensure_ascii=False)
        if not allowed:
            return
        sets = ", ".join(f"{key}=?" for key in allowed)
        self._execute(
            f"UPDATE records SET {sets} WHERE id=?",
            (*allowed.values(), record_id),
        )

    def extend_record(self, record_id: int, end_ts: str, hits_delta: int = 1) -> None:
        self._execute(
            "UPDATE records SET end_ts=?, hits=hits+? WHERE id=?",
            (end_ts, hits_delta, record_id),
        )

    def delete_record(self, record_id: int) -> None:
        self._execute("DELETE FROM records WHERE id=?", (record_id,))

    def last_record(self, day: str | None = None) -> dict | None:
        if day:
            rows = self._query(
                "SELECT * FROM records WHERE day=? ORDER BY id DESC LIMIT 1", (day,)
            )
        else:
            rows = self._query("SELECT * FROM records ORDER BY id DESC LIMIT 1")
        return self._record_dict(rows[0]) if rows else None

    def records_between(self, start_day: str, end_day: str) -> list[dict]:
        rows = self._query(
            "SELECT * FROM records WHERE day>=? AND day<=? ORDER BY start_ts ASC",
            (start_day, end_day),
        )
        return [self._record_dict(r) for r in rows]

    def records_for_day(self, day: str) -> list[dict]:
        return self.records_between(day, day)

    def pending_for_day(self, day: str) -> list[dict]:
        rows = self._query(
            "SELECT * FROM records WHERE day=? AND pending=1 ORDER BY start_ts ASC",
            (day,),
        )
        return [self._record_dict(r) for r in rows]

    def record_days(self) -> list[str]:
        rows = self._query("SELECT DISTINCT day FROM records ORDER BY day DESC")
        return [r["day"] for r in rows]

    def clear_records(self) -> None:
        self._execute("DELETE FROM records")

    # ---------------------------------------------------------------- reports
    def add_report(
        self,
        kind: str,
        start_day: str,
        end_day: str,
        title: str,
        content: str,
        template: str = "",
    ) -> int:
        cur = self._execute(
            "INSERT INTO reports (kind, start_day, end_day, title, content, template, created_at)"
            " VALUES (?,?,?,?,?,?,?)",
            (kind, start_day, end_day, title, content, template, _now()),
        )
        return int(cur.lastrowid)

    def reports(self, limit: int = 200) -> list[dict]:
        return self._query(
            "SELECT id, kind, start_day, end_day, title, template, created_at"
            " FROM reports ORDER BY id DESC LIMIT ?",
            (int(limit),),
        )

    def report(self, report_id: int) -> dict | None:
        rows = self._query("SELECT * FROM reports WHERE id=?", (report_id,))
        return rows[0] if rows else None

    def delete_report(self, report_id: int) -> None:
        self._execute("DELETE FROM reports WHERE id=?", (report_id,))

    # ------------------------------------------------------------------ todos
    def add_todo(
        self,
        title: str,
        detail: str = "",
        due: str = "",
        source: str = "",
        day: str = "",
    ) -> int:
        cur = self._execute(
            "INSERT INTO todos (title, detail, status, due, source, day, created_at)"
            " VALUES (?,?,?,?,?,?,?)",
            (title, detail, "open", due, source, day, _now()),
        )
        return int(cur.lastrowid)

    def todos(self, include_done: bool = True) -> list[dict]:
        sql = "SELECT * FROM todos"
        if not include_done:
            sql += " WHERE status='open'"
        sql += " ORDER BY CASE status WHEN 'open' THEN 0 ELSE 1 END, due='', due, id DESC"
        return self._query(sql)

    def set_todo_status(self, todo_id: int, status: str) -> None:
        done_at = _now() if status == "done" else ""
        self._execute(
            "UPDATE todos SET status=?, done_at=? WHERE id=?",
            (status, done_at, todo_id),
        )

    def delete_todo(self, todo_id: int) -> None:
        self._execute("DELETE FROM todos WHERE id=?", (todo_id,))

    def open_todo_count(self) -> int:
        rows = self._query("SELECT COUNT(*) AS n FROM todos WHERE status='open'")
        return int(rows[0]["n"]) if rows else 0

    # -------------------------------------------------------------- templates
    def templates(self, lang: str | None = None) -> list[dict]:
        if lang:
            return self._query(
                "SELECT * FROM templates WHERE lang=? ORDER BY builtin DESC, id ASC",
                (lang,),
            )
        return self._query("SELECT * FROM templates ORDER BY builtin DESC, id ASC")

    def add_template(
        self,
        name: str,
        kind: str,
        instruction: str,
        builtin: int = 0,
        lang: str = "zh",
    ) -> int:
        cur = self._execute(
            "INSERT OR IGNORE INTO templates (name, kind, instruction, builtin, lang, created_at)"
            " VALUES (?,?,?,?,?,?)",
            (name, kind, instruction, builtin, lang, _now()),
        )
        return int(cur.lastrowid or 0)

    def update_template(self, template_id: int, name: str, kind: str, instruction: str) -> None:
        self._execute(
            "UPDATE templates SET name=?, kind=?, instruction=? WHERE id=?",
            (name, kind, instruction, template_id),
        )

    def delete_template(self, template_id: int) -> None:
        self._execute("DELETE FROM templates WHERE id=?", (template_id,))

    def seed_templates(self, items: list[dict]) -> None:
        """按名字补齐缺失的内置模板（支持中英两套并存）。"""
        for item in items:
            self.add_template(
                item["name"],
                item["kind"],
                item["instruction"],
                builtin=1,
                lang=item.get("lang", "zh"),
            )

    def close(self) -> None:
        with self._lock:
            self._conn.close()
