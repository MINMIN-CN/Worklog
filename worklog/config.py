"""配置与路径管理。

配置保存在 data/config.json，首次运行时自动生成默认配置。
所有路径都相对于项目目录，方便备份和迁移。
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import threading
import time
from copy import deepcopy
from pathlib import Path

APP_NAME = "工作小记"
PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _is_writable(path: Path) -> bool:
    try:
        path.mkdir(parents=True, exist_ok=True)
        probe = path / ".write_test"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
        return True
    except Exception:
        return False


def _fallback_data_dir() -> Path:
    base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    return Path(base) / "WorkLog" / "data"


def _resolve_data_dir() -> Path:
    env = os.environ.get("WORKLOG_DATA_DIR")
    if env:
        return Path(env).expanduser().resolve()
    if getattr(sys, "frozen", False):
        # 安装版：数据默认放在程序安装目录下，方便整体备份、迁移和卸载清理
        exe_dir = Path(sys.executable).resolve().parent
        target = exe_dir / "data"
        # 便携模式：exe 旁的 portable.txt 强制数据跟随程序目录
        if (exe_dir / "portable.txt").exists():
            return target
        if _is_writable(target):
            return target
        # 程序目录不可写（例如装到了 Program Files）时退回用户目录
        return _fallback_data_dir()
    return PROJECT_ROOT / "data"


DATA_DIR = _resolve_data_dir()


def legacy_data_dirs(target: Path | None = None) -> list[Path]:
    """旧版本可能存放数据的位置。"""
    candidates: list[Path] = []
    local = os.environ.get("LOCALAPPDATA")
    if local:
        candidates.append(Path(local) / "WorkLog" / "data")
    roaming = os.environ.get("APPDATA")
    if roaming:
        candidates.append(Path(roaming) / "WorkLog" / "data")
    result: list[Path] = []
    for path in candidates:
        if target is not None and path.resolve() == Path(target).resolve():
            continue
        result.append(path)
    return result


def migrate_legacy_data(
    target: Path | None = None, candidates: list[Path] | None = None
) -> Path | None:
    """把旧版本存放在用户目录的数据迁移到当前数据目录。

    先完整复制并校验，再把旧目录改名为备份（不直接删除），返回迁移来源；无可迁移数据返回 None。
    """
    target = Path(target or DATA_DIR)
    if (target / "worklog.db").exists():
        return None
    if candidates is None:
        if os.environ.get("WORKLOG_DATA_DIR"):
            return None
        if not getattr(sys, "frozen", False):
            return None
        candidates = legacy_data_dirs(target)

    for legacy in candidates:
        legacy = Path(legacy)
        if not (legacy / "worklog.db").exists():
            continue
        try:
            shutil.copytree(
                legacy,
                target,
                dirs_exist_ok=True,
                ignore=shutil.ignore_patterns("tmp"),
            )
        except Exception:
            continue
        if not (target / "worklog.db").exists():
            continue
        backup = legacy.with_name(legacy.name + "_已迁移_可删除")
        if backup.exists():
            backup = legacy.with_name(legacy.name + f"_已迁移_{int(time.time())}")
        try:
            legacy.rename(backup)
        except Exception:
            pass
        return legacy
    return None
CONFIG_PATH = DATA_DIR / "config.json"
DB_PATH = DATA_DIR / "worklog.db"
REPORTS_DIR = DATA_DIR / "reports"
TMP_DIR = DATA_DIR / "tmp"

DEFAULT_CONFIG: dict = {
    "config_version": 2,
    "api": {
        "provider": "deepseek",
        "base_url": "https://api.deepseek.com",
        "api_key": "",
        "vision_model": "deepseek-flash",
        "text_model": "deepseek-flash",
        "timeout": 120,
        "max_image_width": 1280,
        "jpeg_quality": 70,
        "extra_instruction": "",
        "use_json_mode": False,
    },
    "capture": {
        "interval_sec": 120,
        "monitor": 1,
        "excluded_apps": [
            "KeePass.exe",
            "KeePassXC.exe",
            "1Password.exe",
            "Bitwarden.exe",
            "LastPass.exe",
            "Dashlane.exe",
        ],
        "idle_seconds": 300,
        "dedup_hamming": 5,
    },
    "recording": {
        "auto_start": True,
    },
    "agent_api": {
        "enabled": True,
        "port": 8765,
    },
    "report": {
        "default_template": "成果导向日报",
    },
    "privacy": {
        "scrub_personal": True,
    },
    "ui": {
        "close_to_tray": True,
        "language": "auto",
    },
    "update": {
        "manifest_url": "",
        "auto_check": True,
    },
}


def _deep_merge(base: dict, override: dict) -> dict:
    result = deepcopy(base)
    for key, value in (override or {}).items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


class Config:
    """线程安全的配置对象。"""

    def __init__(self, path: Path = CONFIG_PATH):
        self.path = Path(path)
        self._lock = threading.RLock()
        self._data: dict = deepcopy(DEFAULT_CONFIG)
        self.load()

    def load(self) -> None:
        with self._lock:
            existed = self.path.exists()
            raw: dict = {}
            if existed:
                try:
                    raw = json.loads(self.path.read_text(encoding="utf-8"))
                except Exception:
                    raw = {}
            if not isinstance(raw, dict):
                raw = {}
            data = _deep_merge(DEFAULT_CONFIG, raw)

            changed = False
            # v1 -> v2：旧版本默认关闭自动更新且需要手填更新地址；
            # 升级后启用内置更新源，除非用户自己配置过地址。
            try:
                version = int(raw.get("config_version", 1) or 1)
            except Exception:
                version = 1
            if version < 2:
                if not (raw.get("update", {}) or {}).get("manifest_url"):
                    data.setdefault("update", {})["auto_check"] = True
                data["config_version"] = 2
                changed = True

            self._data = data
            if not existed or changed:
                # 首次启动或配置迁移后写出配置，方便用户查看和直接编辑
                self.save()

    def save(self) -> None:
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix(".json.tmp")
            tmp.write_text(
                json.dumps(self._data, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            tmp.replace(self.path)

    @property
    def data(self) -> dict:
        with self._lock:
            return deepcopy(self._data)

    def get(self, *keys, default=None):
        with self._lock:
            node = self._data
            for key in keys:
                if not isinstance(node, dict) or key not in node:
                    return default
                node = node[key]
            return deepcopy(node)

    def update(self, values: dict) -> None:
        with self._lock:
            self._data = _deep_merge(self._data, values)
            self.save()

    def replace_section(self, section: str, values: dict) -> None:
        with self._lock:
            self._data[section] = deepcopy(values)
            self.save()


def ensure_dirs() -> Path:
    for path in (DATA_DIR, REPORTS_DIR, TMP_DIR):
        path.mkdir(parents=True, exist_ok=True)
    # 首次以新路径启动时，把旧版本存在用户目录的数据迁移过来
    migrate_legacy_data(DATA_DIR)
    return DATA_DIR
