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

from . import __version__


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
        raise ValueError("未配置更新地址")
    if source.startswith(("http://", "https://")):
        response = httpx.get(source, timeout=20, follow_redirects=True)
        response.raise_for_status()
        data = response.json()
    else:
        data = json.loads(Path(source).expanduser().read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not data.get("version"):
        raise ValueError("更新清单格式不正确，需要包含 version 和 url 字段")
    return data


def download_installer(
    url: str,
    dest_dir: str | Path | None = None,
    progress=None,
) -> Path:
    """下载安装包到临时目录，返回文件路径。"""
    url = (url or "").strip()
    if not url:
        raise ValueError("更新清单里缺少下载地址 url")
    target_dir = Path(dest_dir or (Path(tempfile.gettempdir()) / "worklog_update"))
    target_dir.mkdir(parents=True, exist_ok=True)
    name = os.path.basename(url.split("?", 1)[0]) or "WorkLog-Setup.exe"
    if not name.lower().endswith(".exe"):
        name += ".exe"
    dest = target_dir / name
    with httpx.stream("GET", url, timeout=300, follow_redirects=True) as response:
        response.raise_for_status()
        total = int(response.headers.get("Content-Length") or 0)
        done = 0
        with open(dest, "wb") as handle:
            for chunk in response.iter_bytes(64 * 1024):
                handle.write(chunk)
                done += len(chunk)
                if progress and total:
                    progress(done / total)
    return dest


def launch_update(installer: str | Path, restart: bool = True) -> Path:
    """退出当前程序后静默运行安装包升级，完成后重新启动应用。

    通过一个临时 cmd 脚本等待本进程退出，再执行安装包（/SILENT），
    最后重新启动应用。返回脚本路径。
    """
    installer = Path(installer)
    if not installer.exists():
        raise FileNotFoundError(f"安装包不存在：{installer}")

    exe = Path(sys.executable)
    pid = os.getpid()
    script = Path(tempfile.gettempdir()) / "worklog_update.cmd"
    lines = [
        "@echo off",
        "chcp 65001 >nul",
        f'powershell -NoProfile -ExecutionPolicy Bypass -Command "try {{ Wait-Process -Id {pid} -Timeout 120 -ErrorAction Stop }} catch {{}}"',
        f'"{installer}" /SILENT /SUPPRESSMSGBOXES /NORESTART',
    ]
    if restart and getattr(sys, "frozen", False):
        lines.append(f'start "" "{exe}" --wait-instance')
    lines.append('del "%~f0"')
    script.write_text("\r\n".join(lines) + "\r\n", encoding="utf-8")

    flags = 0
    flags |= getattr(subprocess, "DETACHED_PROCESS", 0)
    flags |= getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    subprocess.Popen(
        ["cmd", "/c", str(script)],
        creationflags=flags,
        close_fds=True,
    )
    return script
