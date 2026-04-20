from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import feedparser

from ..models import Item
from ..utils.logging import get_logger


log = get_logger(__name__)


def _entry_time(entry: Any) -> datetime | None:
    for key in ("published_parsed", "updated_parsed", "created_parsed"):
        val = getattr(entry, key, None) or (entry.get(key) if isinstance(entry, dict) else None)
        if val:
            try:
                return datetime(*val[:6], tzinfo=timezone.utc)
            except (TypeError, ValueError):
                continue
    return None


def _clean_summary(entry: Any, max_len: int = 1200) -> str:
    raw = ""
    if hasattr(entry, "summary"):
        raw = entry.summary or ""
    elif isinstance(entry, dict):
        raw = entry.get("summary", "") or ""
    if isinstance(raw, str):
        # 粗暴去 HTML 标签，避免额外依赖
        import re
        text = re.sub(r"<[^>]+>", " ", raw)
        text = re.sub(r"\s+", " ", text).strip()
        return text[:max_len]
    return ""


def fetch_rss(rss_cfg: dict[str, Any], lookback_hours: int, limit_per_feed: int) -> list[Item]:
    feeds = rss_cfg.get("feeds", []) or []
    if not feeds:
        return []

    since = datetime.now(timezone.utc) - timedelta(hours=lookback_hours)
    out: list[Item] = []
    for feed in feeds:
        name = feed.get("name") or feed.get("url", "rss")
        url = feed.get("url")
        if not url:
            continue
        try:
            parsed = feedparser.parse(url)
        except Exception as e:  # noqa: BLE001
            log.error("RSS 拉取失败 %s: %s", name, e)
            continue
        count = 0
        for entry in parsed.entries or []:
            pub = _entry_time(entry)
            if pub and pub < since:
                continue
            title = (entry.get("title") if isinstance(entry, dict) else getattr(entry, "title", "")) or ""
            link = (entry.get("link") if isinstance(entry, dict) else getattr(entry, "link", "")) or ""
            if not title or not link:
                continue
            out.append(
                Item(
                    source="rss",
                    source_label=name,
                    title=title.strip(),
                    url=link,
                    published=pub,
                    summary=_clean_summary(entry),
                    extra={"feed": name},
                )
            )
            count += 1
            if count >= limit_per_feed:
                break
        log.info("rss %s: %d 条", name, count)
    log.info("rss: 共 %d 条", len(out))
    return out
