"""报告生成：把工作时间线交给文本模型，生成日报 / 周报 / 月报。"""

from __future__ import annotations

import calendar
from datetime import date, datetime, timedelta

from . import i18n
from .ai import AIClient
from .prompts_en import REPORT_SYSTEM_PROMPT as REPORT_SYSTEM_PROMPT_EN
from .templates_en import EN_TEMPLATES

KIND_LABELS = {"daily": "日报", "weekly": "周报", "monthly": "月报", "custom": "报告"}


def kind_label(kind: str) -> str:
    return i18n.tr(KIND_LABELS.get(kind, "报告"))


def all_default_templates() -> list[dict]:
    """中英两套内置模板（英文模板带 lang=en）。"""
    return [*DEFAULT_TEMPLATES, *EN_TEMPLATES]

DEFAULT_TEMPLATES: list[dict] = [
    {
        "name": "成果导向日报",
        "kind": "daily",
        "instruction": """请根据下面的工作时间线，生成一份中文工作日报（Markdown）。
第一行是一级标题，格式：`# YYYY-MM-DD 工作日报`。
正文使用以下结构：
## 今日工作成果
（把当天的工作归纳成 3-6 条有结果的条目，突出「完成了什么」而不是「做了什么动作」）
## 关键进展
（1-3 条，说明推进了哪些事情、解决了什么问题）
## 下一步计划
（2-4 条，结合当天记录推测接下来要做什么）
要求：只依据记录内容，不编造；语言简洁、书面化；每条不超过 40 字。

工作时间线：
{timeline}""",
    },
    {
        "name": "简洁流水日报",
        "kind": "daily",
        "instruction": """请根据下面的工作时间线，生成一份简洁的中文日报（Markdown）。
第一行是一级标题：`# YYYY-MM-DD 工作日报`。
正文按时间顺序列出主要工作段落，每条格式：`- HH:MM-HH:MM 做了什么事情（一句话）`，只保留有意义的工作，忽略切换窗口之类的噪音。
最后加一行 `## 明日计划`，写 2-3 条。
要求：只依据记录内容，不编造。

工作时间线：
{timeline}""",
    },
    {
        "name": "标准周报",
        "kind": "weekly",
        "instruction": """请根据下面的工作时间线，生成一份中文周报（Markdown）。
第一行是一级标题：`# {range_label} 周报`。
正文使用以下结构：
## 本周进展
（按项目或主题分组，列出完成的事情，3-8 条）
## 数据与产出
（工作时长、主要投入方向、可量化的产出）
## 问题与风险
（记录中体现出的阻塞、延期风险；没有就写「暂无」）
## 下周计划
（3-5 条）
要求：只依据记录内容，不编造；语言简洁、书面化。

工作时间线：
{timeline}""",
    },
    {
        "name": "月度总结",
        "kind": "monthly",
        "instruction": """请根据下面的工作时间线，生成一份中文月度工作总结（Markdown）。
第一行是一级标题：`# {range_label} 月度总结`。
正文使用以下结构：
## 主要成果
## 投入分布
（按分类/项目概括时间投入）
## 遇到的问题
## 下月计划
要求：只依据记录内容，不编造；语言简洁、书面化；适当归纳，避免流水账。

工作时间线：
{timeline}""",
    },
]

REPORT_SYSTEM_PROMPT = (
    "你是一位资深职场写作助理。你只依据用户提供的工作记录撰写报告，"
    "不编造不存在的工作内容。语言简洁、专业、书面化。直接输出 Markdown 正文。"
)


def build_timeline_text(records: list[dict], max_chars: int = 12000) -> str:
    lines: list[str] = []
    for record in records:
        try:
            start = datetime.fromisoformat(record["start_ts"]).strftime("%H:%M")
            end = datetime.fromisoformat(record["end_ts"]).strftime("%H:%M")
        except Exception:
            start, end = "", ""
        category = i18n.category_display(record.get("category") or "未分类")
        head = f"[{start}-{end}] [{category}] {record.get('app') or ''}".rstrip()
        if record.get("title"):
            head += f" · {record['title']}"
        line = head + "\n  " + (record.get("summary") or "")
        if record.get("details"):
            line += f"（{str(record['details'])[:120]}）"
        if record.get("project"):
            project_prefix = "Project" if i18n.is_english() else "项目"
            line += f" [{project_prefix}:{record['project']}]"
        lines.append(line)
    text = "\n".join(lines)
    if len(text) > max_chars:
        text = text[:max_chars] + "\n...(内容过长已截断)"
    return text


def range_for(kind: str, ref: date) -> tuple[str, str, str]:
    """返回 (起始日, 结束日, 范围标签)。"""
    if kind == "daily":
        return ref.isoformat(), ref.isoformat(), ref.strftime("%Y-%m-%d")
    if kind == "weekly":
        start = ref - timedelta(days=ref.weekday())
        end = start + timedelta(days=6)
        return start.isoformat(), end.isoformat(), f"{start.isoformat()} ~ {end.isoformat()}"
    if kind == "monthly":
        first = ref.replace(day=1)
        last = ref.replace(day=calendar.monthrange(ref.year, ref.month)[1])
        if i18n.is_english():
            label = f"{calendar.month_name[ref.month]} {ref.year}"
        else:
            label = f"{ref.year}年{ref.month}月"
        return first.isoformat(), last.isoformat(), label
    # custom
    return ref.isoformat(), ref.isoformat(), ref.isoformat()


def build_prompt(template: dict, records: list[dict], range_label: str) -> str:
    timeline = build_timeline_text(records)
    instruction = template.get("instruction") or ""
    try:
        return instruction.format(timeline=timeline, range_label=range_label)
    except Exception:
        return f"{instruction}\n\n工作时间线：\n{timeline}"


def generate_report(
    client: AIClient,
    records: list[dict],
    template: dict,
    range_label: str,
    cfg,
    extra: str = "",
    model: str | None = None,
) -> str:
    if not records:
        raise ValueError("所选时间段内没有任何工作记录，无法生成报告。")
    prompt = build_prompt(template, records, range_label)
    if extra.strip():
        prompt += (
            f"\n\nAdditional instructions: {extra.strip()}"
            if i18n.is_english()
            else f"\n\n补充要求：{extra.strip()}"
        )
    system_prompt = REPORT_SYSTEM_PROMPT_EN if i18n.is_english() else REPORT_SYSTEM_PROMPT
    content = client.chat(
        [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ],
        model=model or cfg.get("api", "text_model", default="gpt-4o-mini"),
        max_tokens=3000,
        temperature=0.4,
    )
    return content.strip()
