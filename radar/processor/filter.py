from __future__ import annotations

import re
from pathlib import Path

from ..models import Item
from ..utils.cache import SeenCache


KEYWORDS_LINE_RE = re.compile(r"^\s*keywords\s*[:：]\s*(.+)$", re.IGNORECASE | re.MULTILINE)


def extract_profile_keywords(profile_path: str | Path) -> list[str]:
    p = Path(profile_path)
    if not p.exists():
        return []
    text = p.read_text(encoding="utf-8")
    m = KEYWORDS_LINE_RE.search(text)
    if not m:
        return []
    raw = m.group(1)
    parts = re.split(r"[,，、;；]+", raw)
    return [x.strip() for x in parts if x.strip()]


def dedupe(items: list[Item], cache: SeenCache) -> list[Item]:
    """按 fingerprint 去重（同批次 + 跨运行）。"""
    seen_now: set[str] = set()
    out: list[Item] = []
    for it in items:
        fp = it.fingerprint()
        if fp in seen_now:
            continue
        if cache.is_seen(fp):
            continue
        seen_now.add(fp)
        out.append(it)
    return out


def _matches(text: str, keywords: list[str]) -> bool:
    if not keywords:
        return True
    t = text.lower()
    return any(k.lower() in t for k in keywords)


def keyword_filter(items: list[Item], keywords: list[str]) -> list[Item]:
    """按关键词在 title/summary 粗筛。关键词空则不过滤。"""
    if not keywords:
        return items
    kept: list[Item] = []
    for it in items:
        haystack = f"{it.title}\n{it.summary}"
        if _matches(haystack, keywords):
            kept.append(it)
    return kept
