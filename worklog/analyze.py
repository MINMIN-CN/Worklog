"""把截图交给多模态模型理解，并整理成结构化工作记录。"""

from __future__ import annotations

import json
from datetime import datetime

from .ai import AIClient, AIError, parse_json_list_loose, parse_json_loose
from .capture import Capture, to_data_url

CATEGORIES = [
    "开发",
    "会议",
    "沟通",
    "文档",
    "设计",
    "测试",
    "运维",
    "数据分析",
    "学习",
    "管理",
    "产品",
    "写作",
    "研究",
    "生活",
    "其他",
]

VISION_SYSTEM_PROMPT = (
    "你是一个严谨的工作记录分析助手。你只根据截图内容判断用户正在做什么，"
    "不猜测、不编造。输出必须是一个 JSON 对象，不要输出其他内容。"
)

VISION_USER_PROMPT = """当前时间：{ts}
前台应用：{app}
窗口标题：{title}

请观察截图，判断用户当前的工作内容，并严格输出如下 JSON：
{{
  "category": "从以下选一个：开发、会议、沟通、文档、设计、测试、运维、数据分析、学习、管理、产品、写作、研究、生活、其他",
  "summary": "一句话说明正在做什么，不超过 20 字",
  "details": "更具体的描述，例如正在处理的任务、文件、页面，不超过 100 字",
  "project": "如果明显属于某个项目则写项目名，否则为空字符串",
  "tags": ["最多 3 个关键词"],
  "is_work": true,
  "sensitive": false
}}

隐私要求：
- 不要记录任何人名、账号、密码、密钥、手机号、地址等个人信息，用「同事」「客户」等泛称替代。
- 不要摘抄聊天记录原文、邮件正文或文档大段内容，只概括正在做什么。
- 如果画面是密码管理器、私人聊天、证件、银行等明显私密内容，返回 "sensitive": true，summary 写「私密内容（已跳过细节）」，details 留空。
{extra}"""

TEXT_SYSTEM_PROMPT = (
    "你是一个严谨的工作记录分析助手。根据应用名和窗口标题推断用户的工作内容，"
    "不编造细节。输出必须是一个 JSON 对象，不要输出其他内容。"
)

TEXT_USER_PROMPT = """时间：{ts}
前台应用：{app}
窗口标题：{title}

请推断用户当时的工作内容，并严格输出如下 JSON：
{{
  "category": "从以下选一个：{categories}",
  "summary": "一句话说明正在做什么，不超过 20 字",
  "details": "基于标题的简短推断，不超过 60 字",
  "project": "项目名或空字符串",
  "tags": ["最多 3 个关键词"]
}}"""

TODO_SYSTEM_PROMPT = (
    "你是一个任务整理助手。只从给定的工作记录中提取明确的待办事项，"
    "不要凭空发明。输出必须是一个 JSON 数组，不要输出其他内容。"
)

TODO_USER_PROMPT = """以下是某一天的工作时间线：

{timeline}

请提取其中明确提到、但尚未完成的待办事项，输出 JSON 数组：
[
  {{"title": "待办标题，不超过 30 字", "detail": "补充说明或空字符串", "due": "YYYY-MM-DD 或空字符串"}}
]
如果没有明确的待办，返回空数组 []。最多 8 条。"""


def _clean_text(value, limit: int, fallback: str = "") -> str:
    text = str(value or "").strip().replace("\n", " ")
    if len(text) > limit:
        text = text[:limit]
    return text or fallback


def _normalize(result: dict | None, fallback: dict) -> dict:
    if not isinstance(result, dict):
        return fallback
    category = _clean_text(result.get("category"), 10, fallback["category"])
    if category not in CATEGORIES:
        category = fallback["category"]
    tags = result.get("tags") or []
    if isinstance(tags, str):
        tags = [part.strip() for part in tags.replace("，", ",").split(",") if part.strip()]
    tags = [_clean_text(tag, 12) for tag in list(tags)[:3]]
    tags = [tag for tag in tags if tag]
    return {
        "category": category,
        "summary": _clean_text(result.get("summary"), 30, fallback["summary"]),
        "details": _clean_text(result.get("details"), 120, fallback["details"]),
        "project": _clean_text(result.get("project"), 30),
        "tags": tags,
        "sensitive": bool(result.get("sensitive")),
    }


def analyze_capture(
    client: AIClient,
    capture: Capture,
    cfg,
    model: str | None = None,
) -> dict:
    """调用视觉模型分析截图，返回记录字段（不含时间、ID）。"""
    fallback = {
        "category": "未分类",
        "summary": _clean_text(capture.title, 30, capture.app or "屏幕活动"),
        "details": "",
        "project": "",
        "tags": [],
        "sensitive": False,
    }
    extra = (cfg.get("api", "extra_instruction", default="") or "").strip()
    user_text = VISION_USER_PROMPT.format(
        ts=capture.ts.strftime("%Y-%m-%d %H:%M:%S"),
        app=capture.app or "未知",
        title=capture.title or "(无标题)",
        extra=f"\n补充要求：{extra}" if extra else "",
    )
    messages = [
        {"role": "system", "content": VISION_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": [
                {"type": "text", "text": user_text},
                {
                    "type": "image_url",
                    "image_url": {"url": to_data_url(capture.jpeg), "detail": "low"},
                },
            ],
        },
    ]
    raw = client.chat(
        messages,
        model=model or cfg.get("api", "vision_model", default="gpt-4o-mini"),
        max_tokens=800,
    )
    return _normalize(parse_json_loose(raw), fallback)


def classify_text(
    client: AIClient,
    app: str,
    title: str,
    ts: str,
    cfg,
    model: str | None = None,
) -> dict:
    """仅根据应用名与标题做文本分类（用于补分析无截图的记录）。"""
    fallback = {
        "category": "未分类",
        "summary": _clean_text(title, 30, app or "工作记录"),
        "details": "",
        "project": "",
        "tags": [],
        "sensitive": False,
    }
    user_text = TEXT_USER_PROMPT.format(
        ts=ts,
        app=app or "未知",
        title=title or "(无标题)",
        categories="、".join(CATEGORIES),
    )
    raw = client.chat(
        [{"role": "system", "content": TEXT_SYSTEM_PROMPT},
         {"role": "user", "content": user_text}],
        model=model or cfg.get("api", "text_model", default="gpt-4o-mini"),
        max_tokens=500,
    )
    return _normalize(parse_json_loose(raw), fallback)


def extract_todos(
    client: AIClient,
    records: list[dict],
    cfg,
    timeline_text: str,
    model: str | None = None,
) -> list[dict]:
    """从时间线中提取待办。"""
    raw = client.chat(
        [{"role": "system", "content": TODO_SYSTEM_PROMPT},
         {"role": "user", "content": TODO_USER_PROMPT.format(timeline=timeline_text)}],
        model=model or cfg.get("api", "text_model", default="gpt-4o-mini"),
        max_tokens=900,
    )
    items = parse_json_list_loose(raw) or []
    results: list[dict] = []
    for item in items[:8]:
        if not isinstance(item, dict):
            continue
        title = _clean_text(item.get("title"), 40)
        if not title:
            continue
        due = _clean_text(item.get("due"), 10)
        if due and not _looks_like_date(due):
            due = ""
        results.append(
            {
                "title": title,
                "detail": _clean_text(item.get("detail"), 200),
                "due": due,
            }
        )
    return results


def _looks_like_date(value: str) -> bool:
    try:
        datetime.strptime(value, "%Y-%m-%d")
        return True
    except Exception:
        return False


def apply_analysis(record: dict, result: dict) -> dict:
    """把分析结果合并进记录字段。"""
    record.update(
        {
            "category": result.get("category") or "未分类",
            "summary": result.get("summary") or record.get("summary") or "",
            "details": result.get("details") or record.get("details") or "",
            "project": result.get("project") or record.get("project") or "",
            "tags": json.dumps(result.get("tags") or [], ensure_ascii=False),
            "pending": 0,
        }
    )
    return record
