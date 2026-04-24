from __future__ import annotations

from collections import defaultdict
from datetime import date
import re

from ..models import Summarized


SECTION_TITLES = {
    "arxiv": "Arxiv 最新论文",
    "github": "GitHub 仓库动态",
    "rss": "研究者 / 博客",
    "wechat": "微信公众号",
    "zhihu": "知乎博主",
}
SECTION_ORDER = ["arxiv", "github", "rss", "wechat", "zhihu"]
GITHUB_REPO_RE = re.compile(r"github\.com/([^/]+/[^/]+)/")
GITHUB_PR_URL_RE = re.compile(r"github\.com/([^/]+/[^/]+)/pull/(\d+)(?:/|$)")
TITLE_PR_RE = re.compile(r"\(#(\d+)\)")
PR_TEXT_RE = re.compile(r"\bPR\s+#(\d+)\b")


def _group_by_source(items: list[Summarized]) -> dict[str, list[Summarized]]:
    groups: dict[str, list[Summarized]] = defaultdict(list)
    for s in items:
        groups[s.item.source].append(s)
    return groups


def _collect_pr_links(items: list[Summarized]) -> dict[str, str]:
    pr_links: dict[str, str] = {}

    # 优先使用真实 PR 链接
    for s in items:
        if s.item.source != "github":
            continue
        m = GITHUB_PR_URL_RE.search(s.item.url)
        if not m:
            continue
        _, pr_num = m.groups()
        pr_links.setdefault(pr_num, s.item.url)

    # 若只有 commit 但标题带 (#12345)，推断对应 PR 链接
    for s in items:
        if s.item.source != "github":
            continue
        repo_m = GITHUB_REPO_RE.search(s.item.url)
        title_m = TITLE_PR_RE.search(s.item.title)
        if not repo_m or not title_m:
            continue
        repo = repo_m.group(1)
        pr_num = title_m.group(1)
        pr_links.setdefault(pr_num, f"https://github.com/{repo}/pull/{pr_num}")

    return pr_links


def _linkify_pr_mentions(text: str, pr_links: dict[str, str]) -> str:
    def _replace(m: re.Match[str]) -> str:
        pr_num = m.group(1)
        url = pr_links.get(pr_num)
        if not url:
            return m.group(0)
        return f"[PR #{pr_num}]({url})"

    return PR_TEXT_RE.sub(_replace, text)


def render_report(
    items: list[Summarized],
    advice: str,
    *,
    today: date | None = None,
) -> str:
    today = today or date.today()
    pr_links = _collect_pr_links(items)
    lines: list[str] = []
    lines.append(f"# 科研雷达 · {today.isoformat()}")
    lines.append("")
    lines.append(f"今日共聚合 {len(items)} 条动态。")
    lines.append("")

    lines.append("## 今日研究方向建议")
    lines.append("")
    lines.append(_linkify_pr_mentions(advice.strip(), pr_links) or "_（暂无）_")
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
                lines.append(f"**TL;DR**: {_linkify_pr_mentions(s.tldr, pr_links)}")
            if s.why_it_matters:
                lines.append("")
                lines.append(
                    f"**Why it matters**: {_linkify_pr_mentions(s.why_it_matters, pr_links)}"
                )
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
    pr_links = _collect_pr_links(items)
    lines: list[str] = []
    lines.append("**今日建议**")
    short_advice = _linkify_pr_mentions(advice.strip(), pr_links)
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
            tldr = _linkify_pr_mentions(tldr, pr_links)
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
