from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import urljoin

import feedparser

from ..models import Item
from ..utils.http import NonRetryableHTTPError, build_client, get_json
from ..utils.logging import get_logger


log = get_logger(__name__)

API_ROOT = "https://www.zhihu.com/api/v4"


def _ts_to_dt(ts: Any) -> datetime | None:
    if ts is None:
        return None
    try:
        val = int(ts)
        return datetime.fromtimestamp(val, tz=timezone.utc)
    except (TypeError, ValueError, OSError):
        return None


def _extract_token(raw: str) -> str:
    token = (raw or "").strip().strip("/")
    if not token:
        return ""
    if "/people/" in token:
        token = token.split("/people/", 1)[1]
    return token.split("/", 1)[0]


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


def _normalize_bloggers(zhihu_cfg: dict[str, Any]) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for blogger in zhihu_cfg.get("bloggers", []) or []:
        if isinstance(blogger, str):
            token = _extract_token(blogger)
            if token:
                out.append({"name": token, "url_token": token})
            continue

        if not isinstance(blogger, dict):
            continue
        token = _extract_token(blogger.get("url_token") or blogger.get("url") or "")
        if not token:
            continue

        row = {"name": (blogger.get("name") or token).strip(), "url_token": token}
        rss_url = (blogger.get("rss_url") or "").strip()
        if rss_url:
            row["rss_url"] = rss_url
        path = (blogger.get("path") or "").strip()
        if path:
            row["path"] = path
        out.append(row)
    return out


def _normalize_feeds(zhihu_cfg: dict[str, Any]) -> list[dict[str, str]]:
    feeds: list[dict[str, str]] = []

    for f in zhihu_cfg.get("feeds", []) or []:
        if not isinstance(f, dict):
            continue
        name = (f.get("name") or "知乎博主").strip()
        url = (f.get("url") or "").strip()
        if url:
            feeds.append({"name": name, "url": url})

    base = (zhihu_cfg.get("rsshub_base") or "").strip()
    for b in _normalize_bloggers(zhihu_cfg):
        name = b["name"]
        rss_url = (b.get("rss_url") or "").strip()
        if rss_url:
            feeds.append({"name": name, "url": rss_url})
            continue
        path = (b.get("path") or "").strip()
        if path and base:
            feeds.append({"name": name, "url": urljoin(base.rstrip("/") + "/", path.lstrip("/"))})

    return feeds


def _fetch_from_rss(feeds: list[dict[str, str]], since: datetime, limit: int) -> list[Item]:
    out: list[Item] = []
    for feed in feeds:
        name = feed["name"]
        url = feed["url"]
        try:
            parsed = feedparser.parse(url)
        except Exception as e:  # noqa: BLE001
            log.error("zhihu rss 拉取失败 %s: %s", name, e)
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
                    source="zhihu",
                    source_label=f"知乎 · {name}",
                    title=title.strip(),
                    url=link,
                    published=pub,
                    summary=_clean_summary(entry),
                    extra={"author": name, "feed_url": url, "kind": "rss"},
                )
            )
            count += 1
            if count >= limit:
                break

        log.info("zhihu rss %s: %d 条", name, count)

    return out


def _fetch_articles(
    client,
    *,
    name: str,
    url_token: str,
    since: datetime,
    limit: int,
) -> list[Item]:
    out: list[Item] = []
    offset = 0

    while len(out) < limit:
        url = f"{API_ROOT}/members/{url_token}/articles"
        remaining = limit - len(out)
        params = {
            "limit": min(20, remaining),
            "offset": offset,
            "sort_by": "created",
        }
        data = get_json(client, url, params=params)
        articles = (data or {}).get("data", []) or []
        if not articles:
            break

        should_stop = False
        for a in articles:
            created = _ts_to_dt(a.get("created"))
            updated = _ts_to_dt(a.get("updated"))
            published = created or updated
            if published and published < since:
                should_stop = True
                continue

            article_id = a.get("id")
            title = (a.get("title") or "").strip()
            url = (
                (a.get("url") or "").strip()
                or (a.get("share_url") or "").strip()
                or (f"https://zhuanlan.zhihu.com/p/{article_id}" if article_id else "")
            )
            if not title or not url:
                continue

            out.append(
                Item(
                    source="zhihu",
                    source_label=f"知乎 · {name}",
                    title=title,
                    url=url,
                    published=published,
                    summary=((a.get("excerpt") or "").strip())[:1200],
                    extra={
                        "author": name,
                        "url_token": url_token,
                        "article_id": article_id,
                        "voteup_count": a.get("voteup_count", 0),
                        "comment_count": a.get("comment_count", 0),
                        "kind": "api",
                    },
                )
            )
            if len(out) >= limit:
                break

        if should_stop:
            break

        paging = (data or {}).get("paging", {}) or {}
        if paging.get("is_end", False):
            break
        offset += len(articles)

    return out


def _fetch_from_api(zhihu_cfg: dict[str, Any], since: datetime, limit: int) -> list[Item]:
    if not bool(zhihu_cfg.get("use_official_api", False)):
        return []

    bloggers = _normalize_bloggers(zhihu_cfg)
    if not bloggers:
        return []

    out: list[Item] = []
    headers = {
        "Accept": "application/json",
        "User-Agent": "research-radar",
        "Referer": "https://www.zhihu.com/",
    }
    with build_client(headers) as client:
        for blogger in bloggers:
            try:
                items = _fetch_articles(
                    client,
                    name=blogger["name"],
                    url_token=blogger["url_token"],
                    since=since,
                    limit=limit,
                )
                out.extend(items)
                log.info("zhihu api %s: %d 条", blogger["name"], len(items))
            except NonRetryableHTTPError as e:
                if e.status == 401:
                    log.warning(
                        "知乎 API 401（%s）。请改用 zhihu.feeds 或 zhihu.bloggers[].rss_url/path（配合 rsshub_base）。",
                        blogger["name"],
                    )
                else:
                    log.error("知乎 API 拉取失败 %s: %s", blogger["name"], e)
            except Exception as e:  # noqa: BLE001
                log.error("知乎 API 拉取失败 %s: %s", blogger["name"], e)

    return out


def fetch_zhihu(zhihu_cfg: dict[str, Any], lookback_hours: int, limit_per_blogger: int) -> list[Item]:
    since = datetime.now(timezone.utc) - timedelta(hours=lookback_hours)

    feeds = _normalize_feeds(zhihu_cfg)
    bloggers = _normalize_bloggers(zhihu_cfg)
    use_api = bool(zhihu_cfg.get("use_official_api", False))

    if bloggers and not feeds and not use_api:
        log.warning(
            "zhihu 配置了 bloggers 但未配置可用 RSS（feeds/rss_url/path），且 use_official_api=false，当前会得到 0 条。",
        )

    rss_items = _fetch_from_rss(feeds, since, limit_per_blogger)
    api_items = _fetch_from_api(zhihu_cfg, since, limit_per_blogger)

    out = rss_items + api_items
    log.info("zhihu: 共 %d 条", len(out))
    return out
