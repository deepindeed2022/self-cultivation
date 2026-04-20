from __future__ import annotations

import argparse
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
    return items


def _rank_and_trim(items: list[Item], top_k: int) -> list[Item]:
    # 最新的排前面（若无时间则置尾）
    items.sort(
        key=lambda it: it.published.timestamp() if it.published else 0.0,
        reverse=True,
    )
    return items[:top_k]


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
    log.info("关键词过滤后 %d 条（关键词数=%d）", len(filtered), len(keywords))

    # 指纹去重（跨运行）
    cache_path = ROOT / ".cache" / "seen.json"
    cache = SeenCache(cache_path)
    deduped = dedupe(filtered, cache)
    log.info("去重后 %d 条", len(deduped))

    top_k = int(cfg.limits.get("summarize_top_k", 25))
    picked = _rank_and_trim(deduped, top_k)
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
