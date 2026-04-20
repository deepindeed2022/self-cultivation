from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Iterable

import arxiv

from ..models import Item
from ..utils.logging import get_logger


log = get_logger(__name__)


def fetch_arxiv(arxiv_cfg: dict[str, Any], lookback_hours: int, limit: int) -> list[Item]:
    categories: list[str] = list(arxiv_cfg.get("categories", []) or [])
    extra_queries: list[str] = list(arxiv_cfg.get("extra_queries", []) or [])

    if not categories and not extra_queries:
        log.warning("arxiv 未配置 categories / extra_queries，跳过")
        return []

    parts: list[str] = []
    if categories:
        cat_expr = " OR ".join(f"cat:{c}" for c in categories)
        parts.append(f"({cat_expr})")
    parts.extend(f"({q})" for q in extra_queries)
    query = " OR ".join(parts)

    since = datetime.now(timezone.utc) - timedelta(hours=lookback_hours)

    client = arxiv.Client(page_size=min(100, max(10, limit)), delay_seconds=3, num_retries=3)
    search = arxiv.Search(
        query=query,
        max_results=limit * 3,  # 多取一些，因为后面要按时间窗过滤
        sort_by=arxiv.SortCriterion.SubmittedDate,
        sort_order=arxiv.SortOrder.Descending,
    )

    items: list[Item] = []
    try:
        results: Iterable[arxiv.Result] = client.results(search)
        for r in results:
            published = r.published
            if published and published.tzinfo is None:
                published = published.replace(tzinfo=timezone.utc)
            if published and published < since:
                break
            authors = ", ".join(a.name for a in r.authors[:6])
            if len(r.authors) > 6:
                authors += f" 等 {len(r.authors)} 人"
            items.append(
                Item(
                    source="arxiv",
                    source_label="Arxiv",
                    title=r.title.strip().replace("\n", " "),
                    url=r.entry_id,
                    published=published,
                    summary=(r.summary or "").strip().replace("\n", " "),
                    extra={
                        "authors": authors,
                        "primary_category": r.primary_category,
                        "categories": r.categories,
                    },
                )
            )
            if len(items) >= limit:
                break
    except Exception as e:  # noqa: BLE001
        log.error("arxiv 拉取失败: %s", e)

    log.info("arxiv: 拉到 %d 条", len(items))
    return items
