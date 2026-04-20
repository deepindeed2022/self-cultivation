from __future__ import annotations

import json
import re

from ..llm.base import LLMBackend, Message
from ..models import Item, Summarized
from ..utils.logging import get_logger


log = get_logger(__name__)

SYS_PROMPT = """你是一名资深的 LLM 系统/算法研究助理。
给定一批科研与工程动态条目，用简洁的中文产出结构化摘要。
要求：
1. 每条 TL;DR 不超过 2 句话，突出"做了什么 / 为什么重要"。
2. why_it_matters 一句话，点明与大模型推理 / 系统优化 / 研究前沿的关系；不相关就直说"关联较弱"。
3. 不要编造数字或链接，不要复述标题。
只输出 JSON 对象：{"items": [{"idx": int, "tldr": str, "why_it_matters": str}, ...]}，不要输出其他文字或代码围栏。"""


def _truncate(s: str, n: int = 800) -> str:
    s = (s or "").strip()
    return s if len(s) <= n else s[: n - 1] + "…"


def _build_user_prompt(batch: list[Item]) -> str:
    lines = ["以下是需要摘要的条目，按 idx 回填：", ""]
    for i, it in enumerate(batch):
        lines.append(f"[{i}] source={it.source_label}")
        lines.append(f"    title: {it.title}")
        if it.summary:
            lines.append(f"    abstract: {_truncate(it.summary)}")
        lines.append(f"    url: {it.url}")
        lines.append("")
    return "\n".join(lines)


def _parse_json(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.IGNORECASE)
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError(f"无法从 LLM 输出中解析 JSON: {text[:200]}")
    return json.loads(text[start : end + 1])


def summarize_batch(
    backend: LLMBackend,
    items: list[Item],
    *,
    batch_size: int = 10,
) -> list[Summarized]:
    if not items:
        return []
    out: list[Summarized] = []
    for start in range(0, len(items), batch_size):
        batch = items[start : start + batch_size]
        messages = [
            Message(role="system", content=SYS_PROMPT),
            Message(role="user", content=_build_user_prompt(batch)),
        ]
        try:
            raw = backend.chat(
                messages,
                temperature=0.2,
                max_tokens=1800,
                json_mode=True,
            )
            parsed = _parse_json(raw)
        except Exception as e:  # noqa: BLE001
            log.error("LLM 摘要失败，使用原始摘要回退: %s", e)
            for it in batch:
                out.append(
                    Summarized(
                        item=it,
                        tldr=_truncate(it.summary or it.title, 200),
                        why_it_matters="",
                    )
                )
            continue

        by_idx = {int(r.get("idx", -1)): r for r in parsed.get("items", []) or []}
        for i, it in enumerate(batch):
            r = by_idx.get(i, {})
            out.append(
                Summarized(
                    item=it,
                    tldr=(r.get("tldr") or _truncate(it.summary, 200)).strip(),
                    why_it_matters=(r.get("why_it_matters") or "").strip(),
                )
            )
    return out
