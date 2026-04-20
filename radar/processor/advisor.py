from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

from ..llm.base import LLMBackend, Message
from ..models import Summarized
from ..utils.logging import get_logger


log = get_logger(__name__)

SYS_PROMPT = """你是一名博士生的研究导师。
结合用户的研究方向 profile 与今日聚合到的 Arxiv / GitHub / RSS 动态，
以及最近几天已推送的报告，给出 3~5 条"今日与用户最相关的研究方向建议或跟进动作"。
要求：
- 建议必须与今日条目挂钩，引用相应的标题（1~2 个即可）。
- 避免空洞口号，给出可执行的下一步（例如：阅读 X 的 section 3；在 Y 仓库验证某 commit；对比 Z 的 benchmark）。
- 输出为 Markdown 有序列表，中文。
- 不要复述 profile 本身，不要客套。"""


def _load_recent_reports(report_dir: str | Path, days: int) -> str:
    p = Path(report_dir)
    if not p.exists() or days <= 0:
        return ""
    today = date.today()
    chunks: list[str] = []
    for i in range(1, days + 1):
        d = today - timedelta(days=i)
        f = p / f"{d.isoformat()}.md"
        if f.exists():
            text = f.read_text(encoding="utf-8")
            # 只取前 1500 字，避免上下文过长
            chunks.append(f"# {d.isoformat()}\n{text[:1500]}")
    return "\n\n---\n\n".join(chunks)


def _format_today_brief(summarized: list[Summarized], limit: int = 30) -> str:
    lines: list[str] = []
    for s in summarized[:limit]:
        lines.append(f"- [{s.item.source_label}] {s.item.title}")
        if s.tldr:
            lines.append(f"  TL;DR: {s.tldr}")
    return "\n".join(lines)


def advise(
    backend: LLMBackend,
    *,
    profile_path: str | Path,
    report_dir: str | Path,
    recent_days: int,
    today_items: list[Summarized],
) -> str:
    profile_text = ""
    p = Path(profile_path)
    if p.exists():
        profile_text = p.read_text(encoding="utf-8")

    recent = _load_recent_reports(report_dir, recent_days)
    today_brief = _format_today_brief(today_items)

    user_prompt_parts = [
        "## 我的研究方向 profile",
        profile_text or "(未提供)",
        "",
        "## 今日动态（摘要）",
        today_brief or "(无)",
    ]
    if recent:
        user_prompt_parts.extend(["", "## 最近几天的已推送报告（参考，避免重复）", recent])

    messages = [
        Message(role="system", content=SYS_PROMPT),
        Message(role="user", content="\n".join(user_prompt_parts)),
    ]
    try:
        return backend.chat(messages, temperature=0.4, max_tokens=900).strip()
    except Exception as e:  # noqa: BLE001
        log.error("advisor 失败: %s", e)
        return "_（今日研究方向建议生成失败，见日志）_"
