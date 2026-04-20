from __future__ import annotations

from collections import defaultdict
from datetime import date

from ..models import Summarized


SECTION_TITLES = {
    "arxiv": "Arxiv 最新论文",
    "github": "GitHub 仓库动态",
    "rss": "研究者 / 博客",
}
SECTION_ORDER = ["arxiv", "github", "rss"]


def _group_by_source(items: list[Summarized]) -> dict[str, list[Summarized]]:
    groups: dict[str, list[Summarized]] = defaultdict(list)
    for s in items:
        groups[s.item.source].append(s)
    return groups


def render_report(
    items: list[Summarized],
    advice: str,
    *,
    today: date | None = None,
) -> str:
    today = today or date.today()
    lines: list[str] = []
    lines.append(f"# 科研雷达 · {today.isoformat()}")
    lines.append("")
    lines.append(f"今日共聚合 {len(items)} 条动态。")
    lines.append("")

    lines.append("## 今日研究方向建议")
    lines.append("")
    lines.append(advice.strip() or "_（暂无）_")
    lines.append("")

    groups = _group_by_source(items)
    for src in SECTION_ORDER:
        bucket = groups.get(src) or []
        if not bucket:
            continue
        lines.append(f"## {SECTION_TITLES[src]}（{len(bucket)}）")
        lines.append("")
        for s in bucket:
            it = s.item
            lines.append(f"### [{it.title}]({it.url})")
            meta_bits: list[str] = [it.source_label]
            if it.published:
                meta_bits.append(it.published.strftime("%Y-%m-%d %H:%M UTC"))
            if it.extra.get("authors"):
                meta_bits.append(it.extra["authors"])
            lines.append(f"_{' · '.join(meta_bits)}_")
            lines.append("")
            if s.tldr:
                lines.append(f"**TL;DR**: {s.tldr}")
            if s.why_it_matters:
                lines.append("")
                lines.append(f"**Why it matters**: {s.why_it_matters}")
            lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def render_digest(
    items: list[Summarized],
    advice: str,
    *,
    max_chars: int = 3500,
    report_url: str | None = None,
) -> str:
    """为推送生成的简短摘要版本（飞书卡片用）。"""
    lines: list[str] = []
    lines.append("**今日建议**")
    short_advice = advice.strip()
    if len(short_advice) > 800:
        short_advice = short_advice[:800].rstrip() + "…"
    lines.append(short_advice or "_（暂无）_")
    lines.append("")

    groups = _group_by_source(items)
    for src in SECTION_ORDER:
        bucket = groups.get(src) or []
        if not bucket:
            continue
        lines.append(f"**{SECTION_TITLES[src]}（{len(bucket)}）**")
        for s in bucket[:8]:
            it = s.item
            tldr = s.tldr.strip()
            if len(tldr) > 140:
                tldr = tldr[:140].rstrip() + "…"
            lines.append(f"- [{it.title}]({it.url})")
            if tldr:
                lines.append(f"  {tldr}")
        if len(bucket) > 8:
            lines.append(f"  …另有 {len(bucket) - 8} 条")
        lines.append("")

    text = "\n".join(lines).rstrip()
    if len(text) > max_chars:
        text = text[: max_chars - 1].rstrip() + "…"
        if report_url:
            text += f"\n\n[查看完整报告]({report_url})"
    elif report_url:
        text += f"\n\n[查看完整报告]({report_url})"
    return text
