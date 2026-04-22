from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import urljoin

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
        import re

        text = re.sub(r"<[^>]+>", " ", raw)
        text = re.sub(r"\s+", " ", text).strip()
        return text[:max_len]
    return ""


def _normalize_feeds(wechat_cfg: dict[str, Any]) -> list[dict[str, str]]:
    feeds: list[dict[str, str]] = []

    # 1) 直接写 feed URL
    for f in wechat_cfg.get("feeds", []) or []:
        if not isinstance(f, dict):
            continue
        name = (f.get("name") or "微信公众号").strip()
        url = (f.get("url") or "").strip()
        if url:
            feeds.append({"name": name, "url": url})

    # 2) 用 RSSHub base + accounts 组装
    base_url = (wechat_cfg.get("rsshub_base") or "").strip()
    if not base_url:
        return feeds

    for acc in wechat_cfg.get("accounts", []) or []:
        if not isinstance(acc, dict):
            continue
        name = (acc.get("name") or "微信公众号").strip()
        raw_url = (acc.get("url") or "").strip()
        if raw_url:
            feeds.append({"name": name, "url": raw_url})
            continue

        path = (acc.get("path") or "").strip()
        if path:
            url = urljoin(base_url.rstrip("/") + "/", path.lstrip("/"))
            feeds.append({"name": name, "url": url})
            continue

        biz = (acc.get("biz") or "").strip()
        if biz:
            path = f"/wechat/mp/{biz}"
            url = urljoin(base_url.rstrip("/") + "/", path.lstrip("/"))
            feeds.append({"name": name, "url": url})

    return feeds


def fetch_wechat(wechat_cfg: dict[str, Any], lookback_hours: int, limit_per_feed: int) -> list[Item]:
    feeds = _normalize_feeds(wechat_cfg)
    if not feeds:
        return []

    since = datetime.now(timezone.utc) - timedelta(hours=lookback_hours)
    out: list[Item] = []
    for feed in feeds:
        name = feed["name"]
        url = feed["url"]
        try:
            parsed = feedparser.parse(url)
        except Exception as e:  # noqa: BLE001
            log.error("wechat feed 拉取失败 %s: %s", name, e)
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
                    source="wechat",
                    source_label=f"微信公众号 · {name}",
                    title=title.strip(),
                    url=link,
                    published=pub,
                    summary=_clean_summary(entry),
                    extra={"account": name, "feed_url": url},
                )
            )
            count += 1
            if count >= limit_per_feed:
                break

        log.info("wechat %s: %d 条", name, count)

    log.info("wechat: 共 %d 条", len(out))
    return out
