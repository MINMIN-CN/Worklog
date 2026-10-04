"""一键同步版本号到所有需要修改的文件。

用法：
    uv run python tools/bump_version.py 0.5.3

会同步：pyproject.toml、worklog/__init__.py、packaging/installer.iss、
packaging/version_info.txt、packaging/build.bat、update/manifest.json、README.md、README.en.md。
之后记得：更新 manifest 的 notes、补充 CHANGELOG.md、运行测试，然后提交并打标签。
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main() -> int:
    if len(sys.argv) != 2:
        print("用法：uv run python tools/bump_version.py <新版本号>，例如 0.5.3")
        return 1
    new_version = sys.argv[1].lstrip("vV")
    if not re.fullmatch(r"\d+\.\d+\.\d+", new_version):
        print(f"版本号格式应为 X.Y.Z：{new_version}")
        return 1

    pyproject_path = ROOT / "pyproject.toml"
    match = re.search(
        r'^version = "([^"]+)"', pyproject_path.read_text(encoding="utf-8"), re.M
    )
    if not match:
        print("pyproject.toml 中找不到 version")
        return 1
    old_version = match.group(1)

    if old_version == new_version:
        print(f"版本号已经是 {new_version}，无需修改")
        return 0

    old_parts = old_version.split(".")
    new_parts = new_version.split(".")

    replacements: dict[str, list[tuple[str, str]]] = {
        relative: [(old_version, new_version)]
        for relative in (
            "pyproject.toml",
            "worklog/__init__.py",
            "packaging/installer.iss",
            "packaging/build.bat",
            "update/manifest.json",
            "README.md",
            "README.en.md",
        )
    }
    replacements["packaging/version_info.txt"] = [
        (
            f"({old_parts[0]}, {old_parts[1]}, {old_parts[2]}, 0)",
            f"({new_parts[0]}, {new_parts[1]}, {new_parts[2]}, 0)",
        ),
        (f"'{old_version}'", f"'{new_version}'"),
    ]

    print(f"版本号：{old_version} -> {new_version}")
    for relative, pairs in replacements.items():
        path = ROOT / relative
        text = path.read_text(encoding="utf-8")
        changed = 0
        for old_text, new_text in pairs:
            count = text.count(old_text)
            if count:
                text = text.replace(old_text, new_text)
                changed += count
        if changed:
            path.write_text(text, encoding="utf-8")
            print(f"  已更新 {relative}（{changed} 处）")

    print("\n接下来请手动完成：")
    print("  1. 更新 update/manifest.json 的 notes 更新说明")
    print("  2. 在 CHANGELOG.md 顶部补充本版本条目")
    print("  3. 运行测试：uv run python tools/check_version.py && uv run python tools/smoke_test.py")
    print(f"  4. 提交并打标签：git commit -am \"v{new_version}：更新说明\" && git tag v{new_version} && git push origin main --tags")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
