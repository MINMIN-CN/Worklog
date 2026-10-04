"""校验仓库内各处的版本号是否一致。

用法：
    uv run python tools/check_version.py          # 检查各文件互相一致
    uv run python tools/check_version.py v0.5.3   # 同时校验与预期版本一致
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

PATTERNS = [
    ("pyproject.toml", r'^version = "([^"]+)"'),
    ("worklog/__init__.py", r'__version__ = "([^"]+)"'),
    ("packaging/installer.iss", r'#define MyAppVersion "([^"]+)"'),
    ("packaging/build.bat", r"WorkLog-Setup-([\d.]+)\.exe"),
    ("README.md", r"产物：`dist\\installer\\WorkLog-Setup-([\d.]+)\.exe`"),
    ("README.en.md", r"Output: `dist\\installer\\WorkLog-Setup-([\d.]+)\.exe`"),
]


def main() -> int:
    expected = sys.argv[1].lstrip("vV") if len(sys.argv) > 1 else ""

    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    match = re.search(r'^version = "([^"]+)"', pyproject, re.M)
    if not match:
        print("FAIL pyproject.toml：找不到 version")
        return 1
    version = match.group(1)
    if expected and version != expected:
        print(f"FAIL pyproject.toml：{version} != 预期 {expected}")
        return 1

    problems: list[str] = []
    for relative, pattern in PATTERNS:
        text = (ROOT / relative).read_text(encoding="utf-8")
        found = re.findall(pattern, text, re.M)
        if not found:
            problems.append(f"{relative}: 找不到版本号")
        elif any(value != version for value in found):
            problems.append(f"{relative}: {found} != {version}")

    info = (ROOT / "packaging/version_info.txt").read_text(encoding="utf-8")
    parts = version.split(".")
    if not re.search(rf"filevers=\({parts[0]}, {parts[1]}, {parts[2]}, ", info):
        problems.append(f"packaging/version_info.txt: filevers 与 {version} 不一致")
    if f"u'{version}'" not in info:
        problems.append(f"packaging/version_info.txt: FileVersion 与 {version} 不一致")

    manifest = json.loads((ROOT / "update/manifest.json").read_text(encoding="utf-8"))
    if manifest.get("version") != version:
        problems.append(f"update/manifest.json: {manifest.get('version')} != {version}")
    if f"/v{version}/" not in str(manifest.get("url", "")):
        problems.append(f"update/manifest.json: url 与 {version} 不一致")

    if problems:
        print("版本号不一致：")
        for item in problems:
            print("  -", item)
        return 1

    print(f"版本号一致：{version}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
