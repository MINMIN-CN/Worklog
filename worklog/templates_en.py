"""English report templates (used when the UI language is English)."""

EN_TEMPLATES: list[dict] = [
    {
        "name": "Outcome-focused Daily Report",
        "kind": "daily",
        "lang": "en",
        "instruction": """Write an English daily work report (Markdown) based on the timeline below.
The first line is a level-1 heading in the form `# YYYY-MM-DD Daily Report`.
Use this structure:
## Achievements today
(3-6 bullet points describing results achieved, not just actions taken)
## Key progress
(1-3 points on what moved forward and what problems were solved)
## Next steps
(2-4 points inferred from the records)
Rules: use only the given records, never invent; concise professional language; each bullet under 25 words.

Work timeline:
{timeline}""",
    },
    {
        "name": "Concise Daily Log",
        "kind": "daily",
        "lang": "en",
        "instruction": """Write a concise English daily log (Markdown) based on the timeline below.
First line: `# YYYY-MM-DD Daily Log`.
List the main work blocks in chronological order, one per line:
`- HH:MM-HH:MM what was done (one sentence)`.
Keep only meaningful work; ignore noise such as switching windows.
Finish with `## Plan for tomorrow` and 2-3 bullets.
Rules: use only the given records, never invent.

Work timeline:
{timeline}""",
    },
    {
        "name": "Weekly Report",
        "kind": "weekly",
        "lang": "en",
        "instruction": """Write an English weekly report (Markdown) based on the timeline below.
First line: `# {range_label} Weekly Report`.
Use this structure:
## Progress this week
(group by project or topic, 3-8 bullet points)
## Numbers and output
(hours worked, main areas of effort, measurable output)
## Issues and risks
(blockers or delay risks found in the records; write "None" if there are none)
## Plan for next week
(3-5 bullet points)
Rules: use only the given records, never invent; concise professional language.

Work timeline:
{timeline}""",
    },
    {
        "name": "Monthly Summary",
        "kind": "monthly",
        "lang": "en",
        "instruction": """Write an English monthly summary (Markdown) based on the timeline below.
First line: `# {range_label} Monthly Summary`.
Use this structure:
## Highlights
## Effort distribution
(by category/project in general terms)
## Problems encountered
## Plan for next month
Rules: use only the given records, never invent; concise professional language; summarize rather than list everything.

Work timeline:
{timeline}""",
    },
]
