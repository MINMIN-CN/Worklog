"""更新流程测试：本地 HTTP 模拟更新服务器，验证清单获取与安装包下载。

运行：uv run python tools/updater_flow_test.py
"""

from __future__ import annotations

import json
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from worklog.updater import download_installer, fetch_manifest, is_newer  # noqa: E402

INSTALLER = ROOT / "dist" / "installer" / "WorkLog-Setup-0.3.0.exe"
PORT = 18998


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        return

    def do_GET(self):
        if self.path.startswith("/manifest.json"):
            payload = json.dumps(
                {
                    "version": "9.9.9",
                    "url": f"http://127.0.0.1:{PORT}/WorkLog-Setup-9.9.9.exe",
                    "notes": "更新流程测试",
                },
                ensure_ascii=False,
            ).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
        elif self.path.startswith("/WorkLog-Setup-9.9.9.exe"):
            data = INSTALLER.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "application/octet-stream")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        else:
            self.send_response(404)
            self.end_headers()


def main() -> int:
    assert INSTALLER.exists(), f"缺少安装包：{INSTALLER}"
    server = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()

    manifest = fetch_manifest(f"http://127.0.0.1:{PORT}/manifest.json")
    assert manifest["version"] == "9.9.9"
    assert is_newer(manifest["version"], "0.3.0")

    dest = download_installer(
        manifest["url"], dest_dir=Path(tempfile.mkdtemp(prefix="worklog_update_"))
    )
    assert dest.exists()
    data = dest.read_bytes()
    assert data[:2] == b"MZ", "下载的不是有效的 Windows 可执行文件"
    assert len(data) == INSTALLER.stat().st_size, "下载文件大小不一致"

    server.shutdown()
    print(
        f"更新流程测试通过：{dest.name}（{len(data) / 1024 / 1024:.1f} MB）"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
