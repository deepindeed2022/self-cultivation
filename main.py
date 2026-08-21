from __future__ import annotations

import argparse
import math
import os
from datetime import date
from pathlib import Path

from radar.config import Config
from radar.llm.factory import build_backend
from radar.models import Item, Summarized
from radar.notify.feishu import send_feishu
from radar.processor.advisor import advise
from radar.processor.filter import (
    dedupe,
    extract_profile_keywords,
    keyword_filter,
)
from radar.processor.summarizer import summarize_batch
from radar.render.markdown import render_digest, render_report
from radar.sources.arxiv import fetch_arxiv
from radar.sources.github import fetch_github
from radar.sources.rss import fetch_rss
from radar.sources.wechat import fetch_wechat
from radar.sources.zhihu import fetch_zhihu
from radar.utils.cache import SeenCache
from radar.utils.logging import get_logger


log = get_logger("radar.main")

ROOT = Path(__file__).resolve().parent


def _collect(cfg: Config) -> list[Item]:
    limits = cfg.limits
    items: list[Item] = []
    items.extend(fetch_arxiv(cfg.arxiv, cfg.lookback_hours*7, int(limits.get("arxiv_max", 40))))
    items.extend(
        fetch_github(cfg.github, cfg.lookback_hours, int(limits.get("github_max_per_repo", 20)))
    )
    items.extend(fetch_rss(cfg.rss, cfg.lookback_hours, int(limits.get("rss_max_per_feed", 15))))
    items.extend(
        fetch_wechat(cfg.wechat, cfg.lookback_hours, int(limits.get("wechat_max_per_feed", 10)))
    )
    items.extend(
        fetch_zhihu(cfg.zhihu, cfg.lookback_hours, int(limits.get("zhihu_max_per_blogger", 10)))
    )
    return items


def _rank_and_trim(items: list[Item], top_k: int, non_github_min_ratio: float) -> list[Item]:
    """按时效选取条目，同时为非 GitHub 来源保留最小份额。"""
    if top_k <= 0:
        return []

    # 热门 Issue 是 GitHub 源内已按评论数选出的 TOP N，保留其优先级，避免被时间排序挤掉。
    hot_issues = [it for it in items if it.extra.get("kind") == "issue"]
    github_others = [
        it for it in items if it.source == "github" and it.extra.get("kind") != "issue"
    ]
    non_github = [it for it in items if it.source != "github"]
    github_others.sort(
        key=lambda it: it.published.timestamp() if it.published else 0.0,
        reverse=True,
    )
    non_github.sort(
        key=lambda it: it.published.timestamp() if it.published else 0.0,
        reverse=True,
    )

    # 候选充足时，top_k=25 会保留至少 5 条非 GitHub 内容。
    non_github_quota = math.ceil(top_k * max(0.0, min(1.0, non_github_min_ratio)))
    picked_non_github = non_github[:non_github_quota]
    picked_github = (hot_issues + github_others)[: top_k - len(picked_non_github)]

    # 任一来源候选不足时，以另一来源补齐总条数。
    remaining = top_k - len(picked_github) - len(picked_non_github)
    if remaining > 0:
        picked_non_github.extend(non_github[len(picked_non_github) : len(picked_non_github) + remaining])

    return picked_github + picked_non_github


def _build_report_url(today: date) -> str | None:
    repo = os.getenv("GITHUB_REPOSITORY")  # owner/name, GitHub Actions 自带
    if not repo:
        return None
    branch = os.getenv("GITHUB_REF_NAME", "main")
    return f"https://github.com/{repo}/blob/{branch}/reports/{today.isoformat()}.md"


def run(config_path: Path, profile_path: Path, dry_run: bool) -> int:
    cfg = Config.load(config_path)
    today = date.today()

    log.info("开始采集（lookback=%dh）", cfg.lookback_hours)
    raw = _collect(cfg)
    log.info("原始条目 %d 条", len(raw))

    # 关键词过滤：profile.md keywords ∪ config.keywords
    keywords = sorted(set((cfg.keywords or []) + extract_profile_keywords(profile_path)))
    filtered = keyword_filter(raw, keywords)
    # 热门 Issue 已由订阅仓库和讨论热度筛选；不因正文未命中关键词而漏跟踪。
    hot_issues = [it for it in raw if it.extra.get("kind") == "issue"]
    filtered = filtered + [it for it in hot_issues if it not in filtered]
    log.info("关键词过滤后 %d 条（关键词数=%d）", len(filtered), len(keywords))

    # 指纹去重（跨运行）
    cache_path = ROOT / ".cache" / "seen.json"
    cache = SeenCache(cache_path)
    deduped = dedupe(filtered, cache)
    log.info("去重后 %d 条", len(deduped))

    top_k = int(cfg.limits.get("summarize_top_k", 25))
    non_github_min_ratio = float(cfg.limits.get("non_github_min_ratio", 0.2))
    picked = _rank_and_trim(deduped, top_k, non_github_min_ratio)
    log.info("送入 LLM 摘要 %d 条", len(picked))

    if not picked:
        log.info("今日无新增条目，结束")
        cache.save()
        return 0

    backend = build_backend()
    log.info("LLM backend: %s", backend.name)

    summarized = summarize_batch(backend, picked, batch_size=10)

    advice = advise(
        backend,
        profile_path=profile_path,
        report_dir=cfg.report.get("dir", "reports"),
        recent_days=int(cfg.report.get("advisor_recent_days", 5)),
        today_items=summarized,
    )

    report_md = render_report(summarized, advice, today=today)

    report_dir = ROOT / cfg.report.get("dir", "reports")
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / f"{today.isoformat()}.md"
    report_path.write_text(report_md, encoding="utf-8")
    log.info("报告已写入 %s", report_path)

    # 构造推送内容
    title_tpl = cfg.feishu.get("title_template", "科研雷达 · {date}")
    title = title_tpl.format(date=today.isoformat())
    max_chars = int(cfg.feishu.get("card_max_chars", 3500))
    digest = render_digest(
        summarized,
        advice,
        max_chars=max_chars,
        report_url=_build_report_url(today),
    )

    if dry_run:
        print("=" * 60)
        print(f"[DRY-RUN] title: {title}")
        print("-" * 60)
        print(digest)
        print("=" * 60)
    else:
        send_feishu(title, digest)

    # 标记已见
    cache.mark_many(it.fingerprint() for it in picked)
    cache.save()
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Research Radar")
    parser.add_argument("--config", default=str(ROOT / "config.yaml"))
    parser.add_argument("--profile", default=str(ROOT / "profile.md"))
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="只打印推送内容，不发 webhook",
    )
    args = parser.parse_args()
    return run(Path(args.config), Path(args.profile), args.dry_run)


if __name__ == "__main__":
    raise SystemExit(main())
