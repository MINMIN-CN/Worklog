"""更新流程测试：清单获取、测速选线、多连接下载、故障切换与取消。

运行：uv run python tools/updater_flow_test.py
"""

from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from worklog.updater import (  # noqa: E402
    GITHUB_MIRROR_PREFIXES,
    DownloadCancelled,
    build_download_candidates,
    download_installer,
    fetch_manifest,
    is_newer,
)

INSTALLER = ROOT / "dist" / "installer" / "WorkLog-Setup-0.5.0.exe"
PORT = 18998
PAYLOAD = bytes(range(256)) * (6 * 1024 * 1024 // 256)  # 6 MB，用于并行下载测试


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        return

    def _send_bytes(self, data: bytes, content_type: str) -> None:
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Accept-Ranges", "bytes")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/manifest.json":
            payload = json.dumps(
                {
                    "version": "9.9.9",
                    "url": f"http://127.0.0.1:{PORT}/WorkLog-Setup-9.9.9.exe",
                    "notes": "更新流程测试",
                },
                ensure_ascii=False,
            ).encode("utf-8")
            self._send_bytes(payload, "application/json; charset=utf-8")
            return
        if path == "/WorkLog-Setup-9.9.9.exe":
            data = INSTALLER.read_bytes() if INSTALLER.exists() else b"MZ" + b"\0" * 1024
            self._send_bytes(data, "application/octet-stream")
            return
        if path == "/bigfile.bin":
            # 支持 Range，用于多连接分段下载
            range_header = self.headers.get("Range")
            if range_header and range_header.startswith("bytes="):
                start_text, _, end_text = range_header[6:].partition("-")
                start = int(start_text)
                end = int(end_text) if end_text else len(PAYLOAD) - 1
                chunk = PAYLOAD[start : end + 1]
                self.send_response(206)
                self.send_header("Content-Type", "application/octet-stream")
                self.send_header(
                    "Content-Range", f"bytes {start}-{end}/{len(PAYLOAD)}"
                )
                self.send_header("Content-Length", str(len(chunk)))
                self.send_header("Accept-Ranges", "bytes")
                self.end_headers()
                self.wfile.write(chunk)
                return
            self._send_bytes(PAYLOAD, "application/octet-stream")
            return
        self.send_response(404)
        self.end_headers()


def _collect_progress():
    events: list[tuple[int, int, float, str]] = []

    def callback(done, total, speed, source):
        events.append((done, total, speed, source))

    return events, callback


def test_manifest() -> None:
    manifest = fetch_manifest(f"http://127.0.0.1:{PORT}/manifest.json")
    assert manifest["version"] == "9.9.9"
    assert is_newer(manifest["version"], "0.5.0")


def test_candidates() -> None:
    url = "https://github.com/MINMIN-CN/Worklog/releases/download/v1/x.exe"
    candidates = build_download_candidates(url, extra=["https://mirror.example/{url}"])
    assert candidates[0] == url
    assert "https://mirror.example/" + url in candidates
    for prefix in GITHUB_MIRROR_PREFIXES:
        assert prefix + url in candidates
    plain = build_download_candidates("https://example.com/a.exe")
    assert plain == ["https://example.com/a.exe"]


def test_download_basic() -> None:
    dest_dir = Path(tempfile.mkdtemp(prefix="worklog_dl_"))
    events, callback = _collect_progress()
    path = download_installer(
        f"http://127.0.0.1:{PORT}/WorkLog-Setup-9.9.9.exe",
        dest_dir=dest_dir,
        progress=callback,
    )
    assert path.exists()
    assert path.read_bytes()[:2] == b"MZ"
    assert events and events[-1][0] > 0


def test_download_failover() -> None:
    """第一条线路不可达时，自动换到可用线路。"""
    dest_dir = Path(tempfile.mkdtemp(prefix="worklog_dl_"))
    path = download_installer(
        "http://127.0.0.1:9/WorkLog-Setup-9.9.9.exe",  # 必然失败
        dest_dir=dest_dir,
        extra_mirrors=[f"http://127.0.0.1:{PORT}/WorkLog-Setup-9.9.9.exe"],
    )
    assert path.exists() and path.stat().st_size > 0


def test_download_parallel() -> None:
    """三个候选都支持 Range 时走多连接分段下载，结果必须完整一致。"""
    dest_dir = Path(tempfile.mkdtemp(prefix="worklog_dl_"))
    mirror = f"http://127.0.0.1:{PORT}/bigfile.bin"
    events, callback = _collect_progress()
    started = time.monotonic()
    path = download_installer(
        mirror + "?a=1",
        dest_dir=dest_dir,
        progress=callback,
        extra_mirrors=[mirror + "?a=2", mirror + "?a=3"],
    )
    elapsed = max(0.001, time.monotonic() - started)
    data = path.read_bytes()
    assert hashlib.sha256(data).digest() == hashlib.sha256(PAYLOAD).digest()
    assert len(data) == len(PAYLOAD)
    assert events[-1][0] == len(PAYLOAD)
    assert not list(dest_dir.glob("*.part*"))
    print(f"    （并行下载 {len(data) / 1024 / 1024:.1f} MB，用时 {elapsed:.1f}s）")


def test_download_cancel() -> None:
    dest_dir = Path(tempfile.mkdtemp(prefix="worklog_dl_"))
    cancel_event = threading.Event()

    def callback(done, total, speed, source):
        # 本地下载很快，第一次进度回调就触发取消
        cancel_event.set()

    try:
        download_installer(
            f"http://127.0.0.1:{PORT}/bigfile.bin",
            dest_dir=dest_dir,
            progress=callback,
            cancel=cancel_event,
        )
    except DownloadCancelled:
        return
    raise AssertionError("取消下载未生效")


def main() -> int:
    if INSTALLER.exists():
        print(f"（使用真实安装包：{INSTALLER.name}）")
    else:
        print("（未找到本地安装包，使用内置模拟数据）")
    server = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()

    test_manifest()
    print("清单获取: OK")
    test_candidates()
    print("候选线路生成: OK")
    test_download_basic()
    print("基础下载（单线）: OK")
    test_download_failover()
    print("故障自动切换: OK")
    test_download_parallel()
    print("多连接分段下载: OK")
    test_download_cancel()
    print("取消下载: OK")

    server.shutdown()
    print("\n更新下载流程测试通过")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
