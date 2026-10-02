"""应用内更新：检查更新清单、下载安装包、退出后静默升级并自动重启。

更新清单（JSON）示例：
{
  "version": "0.3.0",
  "url": "https://example.com/WorkLog-Setup-0.3.0.exe",
  "notes": "更新说明（可选）"
}
清单地址可以是 http(s) 链接，也可以是本机文件路径。
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import httpx

from . import __version__, i18n
from .net import default_verify

# 内置更新源：GitHub Releases 的 manifest.json 资源，始终指向最新版本
DEFAULT_MANIFEST_URL = (
    "https://github.com/MINMIN-CN/Worklog/releases/latest/download/manifest.json"
)


def resolve_manifest_url(cfg=None, override: str = "") -> str:
    """更新地址的取值顺序：显式指定 > 配置 > 内置默认地址。

    普通用户无需配置；高级用户可在 config.json 的 update.manifest_url 中自定义。
    """
    if (override or "").strip():
        return override.strip()
    if cfg is not None:
        configured = (cfg.get("update", "manifest_url", default="") or "").strip()
        if configured:
            return configured
    return DEFAULT_MANIFEST_URL


def current_version() -> str:
    return __version__


def parse_version(text: str) -> tuple[int, ...]:
    parts: list[int] = []
    for chunk in str(text).strip().lstrip("vV").split("."):
        digits = "".join(character for character in chunk if character.isdigit())
        parts.append(int(digits) if digits else 0)
    return tuple(parts) or (0,)


def is_newer(remote: str, current: str = __version__) -> bool:
    return parse_version(remote) > parse_version(current)


def fetch_manifest(source: str) -> dict:
    """读取更新清单，支持 http(s) 链接和本地文件路径。"""
    source = (source or "").strip()
    if not source:
        raise ValueError(i18n.tr("未配置更新地址"))
    if source.startswith(("http://", "https://")):
        response = httpx.get(
            source,
            timeout=20,
            follow_redirects=True,
            verify=default_verify(),
        )
        response.raise_for_status()
        data = response.json()
    else:
        data = json.loads(Path(source).expanduser().read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not data.get("version"):
        raise ValueError(i18n.tr("更新清单格式不正确，需要包含 version 和 url 字段"))
    return data


import threading
import time
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlparse

# GitHub 加速前缀：下载前自动并发测速，选最快线路；如有失败自动切换。
# 可在 config.json 的 update.mirror_prefixes 或更新清单的 mirror_prefixes 中覆盖/补充。
GITHUB_MIRROR_PREFIXES = [
    "https://gh-proxy.com/",
    "https://ghfast.top/",
    "https://ghproxy.net/",
]

PROBE_BYTES = 256 * 1024
PROBE_TIMEOUT = 6.0
STALL_TIMEOUT = 20.0
MAX_CONNECTIONS = 3
MIN_PARALLEL_SIZE = 4 * 1024 * 1024


class DownloadCancelled(RuntimeError):
    """用户取消下载。"""


def _normalize_mirror(entry: str, url: str) -> str:
    entry = (entry or "").strip()
    if not entry:
        return ""
    if "{url}" in entry:
        return entry.replace("{url}", url)
    if entry.endswith("/"):
        return entry + url
    return entry


def build_download_candidates(
    url: str, extra: list | None = None, cfg=None
) -> list[str]:
    """生成候选下载地址：原始地址 + 更新清单/配置/内置的加速线路。"""
    url = (url or "").strip()
    candidates = [url]
    extras: list = []
    if extra:
        extras.extend(extra)
    if cfg is not None:
        extras.extend(cfg.get("update", "mirror_prefixes", default=[]) or [])
    if "github.com/" in url and "/releases/" in url:
        extras.extend(GITHUB_MIRROR_PREFIXES)
    for entry in extras:
        candidate = _normalize_mirror(str(entry or ""), url)
        if candidate and candidate not in candidates:
            candidates.append(candidate)
    return candidates


def _source_name(url: str) -> str:
    try:
        return urlparse(url).netloc or url
    except Exception:
        return url


def _probe_candidate(url: str, verify) -> dict | None:
    """读取一小段数据测速，返回 {url, speed, total, supports_ranges}。"""
    started = time.monotonic()
    received = 0
    try:
        with httpx.stream(
            "GET",
            url,
            timeout=httpx.Timeout(
                connect=5.0, read=PROBE_TIMEOUT, write=5.0, pool=5.0
            ),
            follow_redirects=True,
            verify=verify,
            headers={"Range": f"bytes=0-{PROBE_BYTES - 1}"},
        ) as response:
            response.raise_for_status()
            total = 0
            content_range = response.headers.get("Content-Range") or ""
            if "/" in content_range:
                try:
                    total = int(content_range.rsplit("/", 1)[-1])
                except ValueError:
                    total = 0
            if not total and response.status_code == 200:
                total = int(response.headers.get("Content-Length") or 0)
            supports_ranges = (
                response.status_code == 206
                or response.headers.get("Accept-Ranges", "").lower() == "bytes"
            )
            for chunk in response.iter_bytes(32 * 1024):
                received += len(chunk)
                if received >= PROBE_BYTES:
                    break
    except Exception:
        return None
    if received <= 0:
        return None
    elapsed = max(0.001, time.monotonic() - started)
    return {
        "url": url,
        "speed": received / elapsed,
        "total": total,
        "supports_ranges": supports_ranges,
    }


class _Progress:
    """聚合多连接进度，节流上报（done, total, speed, source）。"""

    def __init__(self, total: int, callback, source: str = ""):
        self.total = total
        self.done = 0
        self.callback = callback
        self.source = source
        self._lock = threading.Lock()
        self._window: deque = deque()
        self._last_emit = 0.0

    def set_source(self, source: str) -> None:
        self.source = source

    def add(self, count: int) -> None:
        with self._lock:
            self.done = max(0, self.done + count)
            now = time.monotonic()
            self._window.append((now, self.done))
            while self._window and now - self._window[0][0] > 3:
                self._window.popleft()
            if self.callback and now - self._last_emit >= 0.25:
                self._last_emit = now
                speed = 0.0
                if len(self._window) >= 2:
                    first_time, first_done = self._window[0]
                    elapsed = max(0.001, now - first_time)
                    speed = max(0.0, (self.done - first_done) / elapsed)
                self.callback(self.done, self.total, speed, self.source)


def _download_single(
    dest: Path,
    ranked: list[dict],
    total: int,
    progress,
    cancel,
    verify,
) -> None:
    last_error: Exception | None = None
    for candidate in ranked:
        if cancel and cancel.is_set():
            raise DownloadCancelled()
        tracker = _Progress(total, progress, _source_name(candidate["url"]))
        tracker.total = total
        attempt_written = 0
        try:
            with httpx.stream(
                "GET",
                candidate["url"],
                timeout=httpx.Timeout(
                    connect=8.0, read=STALL_TIMEOUT, write=8.0, pool=8.0
                ),
                follow_redirects=True,
                verify=verify,
            ) as response:
                response.raise_for_status()
                with open(dest, "wb") as handle:
                    for chunk in response.iter_bytes(64 * 1024):
                        if cancel and cancel.is_set():
                            raise DownloadCancelled()
                        handle.write(chunk)
                        attempt_written += len(chunk)
                        tracker.add(len(chunk))
            if total and dest.stat().st_size not in (0, total):
                raise IOError("incomplete download")
            if tracker.callback:
                tracker.callback(tracker.done, total, 0.0, tracker.source)
            return
        except DownloadCancelled:
            raise
        except Exception as exc:  # 换下一条线路
            last_error = exc
            if attempt_written:
                tracker.add(-attempt_written)  # 回退未完成部分，避免进度虚高
            continue
    raise RuntimeError(
        i18n.tr("无法连接任何下载线路，请检查网络后重试")
    ) from last_error


def _download_parallel(
    dest: Path,
    range_capable: list[dict],
    total: int,
    progress,
    cancel,
    verify,
) -> None:
    count = min(MAX_CONNECTIONS, len(range_capable), max(1, total // (2 * 1024 * 1024)))
    part_size = total // count
    tracker = _Progress(total, progress, _source_name(range_capable[0]["url"]))

    def fetch(segment_index: int) -> Path:
        start = segment_index * part_size
        end = total - 1 if segment_index == count - 1 else start + part_size - 1
        part_path = dest.with_suffix(dest.suffix + f".part{segment_index}")
        errors: list[Exception] = []
        order = range_capable[segment_index % len(range_capable):] + range_capable[: segment_index % len(range_capable)]
        for candidate in order:
            if cancel and cancel.is_set():
                raise DownloadCancelled()
            attempt_written = 0
            try:
                with httpx.stream(
                    "GET",
                    candidate["url"],
                    headers={"Range": f"bytes={start}-{end}"},
                    timeout=httpx.Timeout(
                        connect=8.0, read=STALL_TIMEOUT, write=8.0, pool=8.0
                    ),
                    follow_redirects=True,
                    verify=verify,
                ) as response:
                    response.raise_for_status()
                    written = 0
                    with open(part_path, "wb") as handle:
                        for chunk in response.iter_bytes(64 * 1024):
                            if cancel and cancel.is_set():
                                raise DownloadCancelled()
                            handle.write(chunk)
                            written += len(chunk)
                            attempt_written += len(chunk)
                            tracker.add(len(chunk))
                if written != end - start + 1:
                    raise IOError("incomplete segment")
                return part_path
            except DownloadCancelled:
                raise
            except Exception as exc:
                errors.append(exc)
                if attempt_written:
                    tracker.add(-attempt_written)  # 回退本次尝试的进度
                continue
        raise RuntimeError(
            i18n.tr("无法连接任何下载线路，请检查网络后重试")
        ) from (errors[-1] if errors else None)

    try:
        with ThreadPoolExecutor(max_workers=count) as pool:
            parts = list(pool.map(fetch, range(count)))
        with open(dest, "wb") as output:
            for part in parts:
                with open(part, "rb") as handle:
                    while True:
                        chunk = handle.read(1024 * 1024)
                        if not chunk:
                            break
                        output.write(chunk)
        for part in parts:
            part.unlink(missing_ok=True)
        if dest.stat().st_size != total:
            raise IOError("incomplete merge")
        if tracker.callback:
            tracker.callback(total, total, 0.0, tracker.source)
    except DownloadCancelled:
        for part in dest.parent.glob(dest.name + ".part*"):
            part.unlink(missing_ok=True)
        dest.unlink(missing_ok=True)
        raise
    except Exception:
        for part in dest.parent.glob(dest.name + ".part*"):
            part.unlink(missing_ok=True)
        dest.unlink(missing_ok=True)
        raise


def download_installer(
    url: str,
    dest_dir: str | Path | None = None,
    progress=None,
    cancel=None,
    extra_mirrors: list | None = None,
    cfg=None,
) -> Path:
    """下载安装包，自动测速选择最快的加速线路。

    progress(done, total, speed, source)：total 为 0 表示正在测速阶段。
    cancel：threading.Event，用于取消下载。
    extra_mirrors：更新清单里的加速线路（前缀或包含 {url} 的模板）。
    """
    url = (url or "").strip()
    if not url:
        raise ValueError(i18n.tr("更新清单里缺少下载地址 url"))
    target_dir = Path(dest_dir or (Path(tempfile.gettempdir()) / "worklog_update"))
    target_dir.mkdir(parents=True, exist_ok=True)
    name = os.path.basename(url.split("?", 1)[0]) or "WorkLog-Setup.exe"
    if not name.lower().endswith(".exe"):
        name += ".exe"
    dest = target_dir / name

    candidates = build_download_candidates(url, extra_mirrors, cfg)
    if progress:
        progress(0, 0, 0.0, "")
    verify = default_verify()
    with ThreadPoolExecutor(max_workers=min(4, len(candidates))) as pool:
        probes = list(pool.map(lambda candidate: _probe_candidate(candidate, verify), candidates))
    ranked = sorted(
        (item for item in probes if item), key=lambda item: -item["speed"]
    )
    if not ranked:
        raise RuntimeError(i18n.tr("无法连接任何下载线路，请检查网络后重试"))
    if cancel and cancel.is_set():
        raise DownloadCancelled()

    total = next((item["total"] for item in ranked if item["total"]), 0)
    range_capable = [
        item
        for item in ranked
        if item["supports_ranges"] and total and item["total"] == total
    ]
    if total >= MIN_PARALLEL_SIZE and range_capable:
        try:
            _download_parallel(dest, range_capable, total, progress, cancel, verify)
            return dest
        except DownloadCancelled:
            raise
        except Exception:
            # 并行失败时回退到单线下载
            pass
    _download_single(dest, ranked, total, progress, cancel, verify)
    return dest


def launch_update(installer: str | Path, restart: bool = True) -> Path:
    """退出当前程序后静默运行安装包升级，完成后重新启动应用。

    通过一个带 BOM 的 UTF-8 PowerShell 脚本完成：等待本进程退出 →
    运行安装包（/SILENT）→ 重新启动应用。
    使用 PowerShell 而不是 cmd 批处理，避免中文/非 ASCII 安装路径乱码。
    返回脚本路径。
    """
    installer = Path(installer)
    if not installer.exists():
        raise FileNotFoundError(
            i18n.tr("安装包不存在：{path}").format(path=installer)
        )

    pid = os.getpid()
    script = Path(tempfile.gettempdir()) / "worklog_update.ps1"

    def quote(path: str | Path) -> str:
        return str(path).replace("'", "''")

    lines = [
        "$ErrorActionPreference = 'SilentlyContinue'",
        f"try {{ Wait-Process -Id {pid} -Timeout 120 -ErrorAction Stop }} catch {{}}",
        f"& '{quote(installer)}' /SILENT /SUPPRESSMSGBOXES /NORESTART",
    ]
    if restart and getattr(sys, "frozen", False):
        lines.append(
            f"Start-Process -FilePath '{quote(Path(sys.executable))}' "
            "-ArgumentList '--wait-instance'"
        )
    lines.append("Remove-Item -LiteralPath $PSCommandPath -Force")
    # UTF-8 BOM：Windows PowerShell 5.1 才能正确解析中文路径
    script.write_text("\r\n".join(lines) + "\r\n", encoding="utf-8-sig")

    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
    flags |= getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    subprocess.Popen(
        [
            "powershell.exe",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(script),
        ],
        creationflags=flags,
        close_fds=True,
    )
    return script
