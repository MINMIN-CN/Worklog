"""统计计算：时长、应用分布、分类分布、时段热力图、标签。"""

from __future__ import annotations

from datetime import datetime, timedelta

from . import i18n

MAX_RECORD_SECONDS = 2 * 60 * 60  # 单条记录最长按 2 小时计


def record_duration(record: dict) -> float:
    try:
        start = datetime.fromisoformat(record["start_ts"])
        end = datetime.fromisoformat(record["end_ts"])
    except Exception:
        return 0.0
    seconds = (end - start).total_seconds()
    if seconds <= 0:
        return 0.0
    return min(seconds, MAX_RECORD_SECONDS)


def format_duration(seconds: float) -> str:
    seconds = int(seconds or 0)
    if seconds <= 0:
        return i18n.tr("{minutes} 分钟").format(minutes=0)
    hours, remainder = divmod(seconds, 3600)
    minutes = remainder // 60
    if hours and minutes:
        return i18n.tr("{hours} 小时 {minutes} 分").format(hours=hours, minutes=minutes)
    if hours:
        return i18n.tr("{hours} 小时").format(hours=hours)
    return i18n.tr("{minutes} 分钟").format(minutes=max(1, minutes))


def format_span(hours: float, minutes: int = 0) -> str:
    return format_duration(hours * 3600 + minutes * 60)


def _add_hour_heat(heat: dict, record: dict) -> None:
    try:
        start = datetime.fromisoformat(record["start_ts"])
        end = datetime.fromisoformat(record["end_ts"])
    except Exception:
        return
    if end <= start:
        return
    if (end - start).total_seconds() > MAX_RECORD_SECONDS:
        end = start + timedelta(seconds=MAX_RECORD_SECONDS)
    cursor = start.replace(minute=0, second=0, microsecond=0)
    while cursor < end:
        nxt = cursor + timedelta(hours=1)
        overlap = (min(end, nxt) - max(start, cursor)).total_seconds()
        if overlap > 0:
            key = (cursor.weekday(), cursor.hour)
            heat[key] = heat.get(key, 0.0) + overlap
        cursor = nxt


def compute_stats(records: list[dict]) -> dict:
    stats: dict = {
        "count": len(records),
        "hits": 0,
        "duration": 0.0,
        "by_app": {},
        "by_category": {},
        "by_hour": {},
        "tags": {},
        "days": set(),
        "first_start": "",
        "last_end": "",
    }

    for record in records:
        duration = record_duration(record)
        stats["duration"] += duration
        stats["hits"] += int(record.get("hits") or 1)

        day = record.get("day") or ""
        if day:
            stats["days"].add(day)

        app = record.get("app") or "未知应用"
        stats["by_app"][app] = stats["by_app"].get(app, 0.0) + duration

        category = record.get("category") or "未分类"
        stats["by_category"][category] = stats["by_category"].get(category, 0.0) + duration

        for tag in record.get("tags") or []:
            stats["tags"][tag] = stats["tags"].get(tag, 0) + 1

        _add_hour_heat(stats["by_hour"], record)

        start_ts = record.get("start_ts") or ""
        end_ts = record.get("end_ts") or ""
        if start_ts and (not stats["first_start"] or start_ts < stats["first_start"]):
            stats["first_start"] = start_ts
        if end_ts and (not stats["last_end"] or end_ts > stats["last_end"]):
            stats["last_end"] = end_ts

    stats["active_days"] = len(stats["days"])
    stats["by_app"] = sorted(stats["by_app"].items(), key=lambda kv: -kv[1])
    stats["by_category"] = sorted(stats["by_category"].items(), key=lambda kv: -kv[1])
    stats["tags"] = sorted(stats["tags"].items(), key=lambda kv: -kv[1])
    stats.pop("days", None)
    return stats
