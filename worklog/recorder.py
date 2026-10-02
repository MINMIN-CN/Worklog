"""后台记录引擎：截图采集线程 + AI 分析线程。

两个线程通过有界队列衔接，互不阻塞：
- 采集线程按间隔截屏，画面静止时只延长上一条记录，不调用 AI；
- 分析线程逐条调用视觉模型，写入数据库并通知界面。
"""

from __future__ import annotations

import queue
import threading
import time
from datetime import datetime, timedelta

from PySide6.QtCore import QObject, Signal

from .ai import AIError, has_api_key, make_client
from .analyze import analyze_capture, classify_text
from .capture import Capture, average_hash, encode_jpeg, grab_screen, hamming
from .db import Database
from .wininfo import get_foreground, get_idle_seconds, is_locked

MAX_MERGE_GAP = 10 * 60  # 超过 10 分钟不再合并
MAX_END_COVER = 120  # 初始/延长时长最多按 2 分钟计


class RecorderEngine(QObject):
    record_added = Signal(dict)
    record_updated = Signal(dict)
    status_changed = Signal(str)
    error = Signal(str)

    def __init__(self, cfg, db: Database, parent=None):
        super().__init__(parent)
        self.cfg = cfg
        self.db = db
        self._queue: queue.Queue[Capture] = queue.Queue(maxsize=3)
        self._stop = threading.Event()
        self._pause = threading.Event()
        self._force = threading.Event()
        self._threads: list[threading.Thread] = []
        self._state_lock = threading.Lock()
        self._force_lock = threading.Lock()
        self._last_hash: int | None = None
        self._last_app = ""
        self._last_record: dict | None = None
        self._status = "stopped"

    # ------------------------------------------------------------- 生命周期
    def start(self) -> None:
        if self._threads:
            return
        self._stop.clear()
        self._threads = [
            threading.Thread(target=self._capture_loop, name="worklog-capture", daemon=True),
            threading.Thread(target=self._analyze_loop, name="worklog-analyze", daemon=True),
        ]
        for thread in self._threads:
            thread.start()
        self._set_status("paused" if self._pause.is_set() else "recording")

    def stop(self) -> None:
        self._stop.set()
        for thread in self._threads:
            thread.join(timeout=4)
        self._threads = []
        self._set_status("stopped")

    @property
    def running(self) -> bool:
        return bool(self._threads)

    @property
    def paused(self) -> bool:
        return self._pause.is_set()

    def pause(self) -> None:
        self._pause.set()
        self._set_status("paused")

    def resume(self) -> None:
        self._pause.clear()
        with self._state_lock:
            self._last_hash = None
            self._last_app = ""
        self._set_status("recording")

    def toggle_pause(self) -> None:
        if self._pause.is_set():
            self.resume()
        else:
            self.pause()

    def capture_now(self) -> None:
        self._force.set()

    # ---------------------------------------------------------------- 内部
    def _set_status(self, status: str) -> None:
        self._status = status
        self.status_changed.emit(status)

    def _sleep(self, seconds: float) -> bool:
        """可被打断的等待。返回 True 表示应退出循环。"""
        deadline = time.monotonic() + max(0.0, seconds)
        while time.monotonic() < deadline:
            if self._stop.is_set():
                return True
            with self._force_lock:
                if self._force.is_set():
                    return False
            time.sleep(0.5)
        return False

    def _capture_loop(self) -> None:
        try:
            import mss

            factory = getattr(mss, "MSS", None) or mss.mss
        except Exception as exc:  # pragma: no cover
            self.error.emit(f"无法加载截图模块：{exc}")
            return
        with factory() as sct:
            while not self._stop.is_set():
                interval = max(10, int(self.cfg.get("capture", "interval_sec", default=120) or 120))
                if self._sleep(interval):
                    break
                with self._force_lock:
                    forced = self._force.is_set()
                    self._force.clear()
                try:
                    self._capture_once(sct, forced)
                except Exception as exc:
                    self.error.emit(f"截图失败：{exc}")
                    time.sleep(2)

    def _capture_once(self, sct, forced: bool = False) -> None:
        if self._pause.is_set() and not forced:
            self._set_status("paused")
            return
        if is_locked():
            self._set_status("idle")
            return
        idle_limit = float(self.cfg.get("capture", "idle_seconds", default=300) or 300)
        if not forced and get_idle_seconds() > idle_limit:
            self._set_status("idle")
            return

        foreground = get_foreground()
        if not foreground:
            return
        app, title, _pid = foreground

        excluded = [
            str(item).strip().lower()
            for item in (self.cfg.get("capture", "excluded_apps", default=[]) or [])
            if str(item).strip()
        ]
        if app.lower() in excluded:
            self._set_status("recording")
            return

        monitor = int(self.cfg.get("capture", "monitor", default=1) or 1)
        image, used_monitor = grab_screen(sct, monitor)

        ahash = average_hash(image)
        now = datetime.now()
        threshold = int(self.cfg.get("capture", "dedup_hamming", default=5) or 5)

        with self._state_lock:
            same_view = (
                self._last_hash is not None
                and app == self._last_app
                and hamming(self._last_hash, ahash) <= threshold
            )
            if same_view and self._queue.empty():
                if self._extend_last(now):
                    self._last_hash = ahash
                    self._set_status("recording")
                    return
            self._last_hash = ahash
            self._last_app = app

        max_width = int(self.cfg.get("api", "max_image_width", default=1280) or 1280)
        quality = int(self.cfg.get("api", "jpeg_quality", default=70) or 70)
        jpeg = encode_jpeg(image, max_width, quality)
        capture = Capture(
            ts=now,
            app=app,
            title=title,
            jpeg=jpeg,
            ahash=ahash,
            monitor=used_monitor,
        )
        self._enqueue(capture)
        self._set_status("analyzing")

    def _extend_last(self, now: datetime) -> bool:
        record = self._last_record
        if not record:
            return False
        try:
            end = datetime.fromisoformat(record["end_ts"])
            start = datetime.fromisoformat(record["start_ts"])
        except Exception:
            return False
        if (now - end).total_seconds() > MAX_MERGE_GAP:
            return False
        new_end = now + timedelta(seconds=MAX_END_COVER)
        if new_end <= end:
            new_end = end
        max_end = start + timedelta(seconds=2 * 60 * 60)
        if new_end > max_end:
            new_end = max_end
        if new_end <= end:
            return True
        self.db.extend_record(record["id"], new_end.isoformat(timespec="seconds"), 1)
        record["end_ts"] = new_end.isoformat(timespec="seconds")
        record["hits"] = int(record.get("hits") or 1) + 1
        self.record_updated.emit(
            {
                "id": record["id"],
                "end_ts": record["end_ts"],
                "hits": record["hits"],
            }
        )
        return True

    def _enqueue(self, capture: Capture) -> None:
        try:
            self._queue.put_nowait(capture)
            return
        except queue.Full:
            pass
        try:
            self._queue.get_nowait()  # 丢弃最旧的，保留最新画面
        except queue.Empty:
            pass
        try:
            self._queue.put_nowait(capture)
        except queue.Full:
            pass

    def _analyze_loop(self) -> None:
        while not self._stop.is_set():
            try:
                capture = self._queue.get(timeout=0.5)
            except queue.Empty:
                continue
            try:
                self._analyze_capture(capture)
            except AIError as exc:
                self.error.emit(f"AI 分析失败：{exc}")
                self._save_raw(capture, error=str(exc))
            except Exception as exc:  # pragma: no cover
                self.error.emit(f"AI 分析异常：{exc}")
                self._save_raw(capture, error=str(exc))
            self._set_status("analyzing" if not self._queue.empty() else ("paused" if self._pause.is_set() else "recording"))

    def _analyze_capture(self, capture: Capture) -> None:
        interval = max(10, int(self.cfg.get("capture", "interval_sec", default=120) or 120))
        end_ts = capture.ts + timedelta(seconds=min(interval, MAX_END_COVER))
        record = {
            "day": capture.ts.strftime("%Y-%m-%d"),
            "start_ts": capture.ts.isoformat(timespec="seconds"),
            "end_ts": end_ts.isoformat(timespec="seconds"),
            "app": capture.app,
            "title": capture.title,
            "category": "未分类",
            "summary": "",
            "details": "",
            "project": "",
            "tags": [],
            "hits": 1,
            "source": "auto",
            "pending": 1,
            "created_at": datetime.now().isoformat(timespec="seconds"),
        }

        if not has_api_key(self.cfg):
            record["summary"] = capture.title or capture.app or "屏幕活动"
            record["details"] = "未配置 AI 模型，可在设置中配置后重新分析。"
            self._store(record)
            return

        client = make_client(self.cfg)
        try:
            result = analyze_capture(client, capture, self.cfg)
        finally:
            # 截图只用于分析，立即随引用释放（不落盘）
            capture.jpeg = b""

        record["category"] = result.get("category") or "未分类"
        record["summary"] = result.get("summary") or capture.title or ""
        record["details"] = result.get("details") or ""
        record["project"] = result.get("project") or ""
        record["tags"] = result.get("tags") or []
        record["pending"] = 0
        self._store(record)

    def _save_raw(self, capture: Capture, error: str = "") -> None:
        interval = max(10, int(self.cfg.get("capture", "interval_sec", default=120) or 120))
        end_ts = capture.ts + timedelta(seconds=min(interval, MAX_END_COVER))
        record = {
            "day": capture.ts.strftime("%Y-%m-%d"),
            "start_ts": capture.ts.isoformat(timespec="seconds"),
            "end_ts": end_ts.isoformat(timespec="seconds"),
            "app": capture.app,
            "title": capture.title,
            "category": "未分类",
            "summary": capture.title or capture.app or "屏幕活动",
            "details": f"AI 分析失败：{error}" if error else "",
            "project": "",
            "tags": [],
            "hits": 1,
            "source": "auto",
            "pending": 1,
            "created_at": datetime.now().isoformat(timespec="seconds"),
        }
        capture.jpeg = b""
        self._store(record)

    def _store(self, record: dict) -> None:
        with self._state_lock:
            last = self._last_record
            merge = False
            if last and last.get("day") == record["day"] and last.get("app") == record["app"]:
                try:
                    gap = (
                        datetime.fromisoformat(record["start_ts"])
                        - datetime.fromisoformat(last["end_ts"])
                    ).total_seconds()
                except Exception:
                    gap = 999
                if (
                    gap <= MAX_MERGE_GAP
                    and last.get("category") == record.get("category")
                    and last.get("summary") == record.get("summary")
                ):
                    merge = True

            if merge and last is not None:
                new_end = record["end_ts"]
                old_end = last["end_ts"]
                if new_end < old_end:
                    new_end = old_end
                self.db.extend_record(last["id"], new_end, 1)
                last["end_ts"] = new_end
                last["hits"] = int(last.get("hits") or 1) + 1
                last["pending"] = max(int(last.get("pending") or 0), int(record.get("pending") or 0))
                self.record_updated.emit(
                    {"id": last["id"], "end_ts": new_end, "hits": last["hits"]}
                )
                return

            record_id = self.db.add_record(**record)
            record["id"] = record_id
            self._last_record = record
            self.record_added.emit(record)


def reanalyze_pending(db: Database, cfg, day: str, progress=None) -> tuple[int, int]:
    """对某天未成功分析的记录做文本补分析。返回 (成功数, 总数)。"""
    records = db.pending_for_day(day)
    total = len(records)
    if not has_api_key(cfg) or not records:
        return 0, total

    client = make_client(cfg)
    done = 0
    for record in records:
        try:
            result = classify_text(
                client,
                record.get("app") or "",
                record.get("title") or "",
                record.get("start_ts") or "",
                cfg,
            )
            db.update_record(
                record["id"],
                category=result.get("category") or "未分类",
                summary=result.get("summary") or record.get("summary") or "",
                details=result.get("details") or "",
                project=result.get("project") or "",
                tags=result.get("tags") or [],
                pending=0,
            )
            done += 1
        except Exception:
            continue
        if progress:
            progress(done, total)
    return done, total
