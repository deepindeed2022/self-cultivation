from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Any

from dateutil import parser as dateparser

from ..models import Item
from ..utils.http import build_client, get_json
from ..utils.logging import get_logger


log = get_logger(__name__)

API_ROOT = "https://api.github.com"


def _auth_headers() -> dict[str, str]:
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "research-radar",
    }
    token = os.getenv("GH_PAT") or os.getenv("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _parse_dt(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        dt = dateparser.isoparse(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except (ValueError, TypeError):
        return None


def _fetch_commits(client, repo: str, since: datetime, limit: int) -> list[Item]:
    url = f"{API_ROOT}/repos/{repo}/commits"
    params = {"since": since.isoformat(), "per_page": min(100, limit)}
    try:
        data = get_json(client, url, params=params)
    except Exception as e:  # noqa: BLE001
        log.error("GitHub commits 拉取失败 %s: %s", repo, e)
        return []
    items: list[Item] = []
    for c in data or []:
        commit = c.get("commit", {}) or {}
        message = (commit.get("message") or "").strip()
        title = message.splitlines()[0] if message else c.get("sha", "")[:12]
        author = (commit.get("author") or {}).get("name") or "unknown"
        sha = c.get("sha", "")
        items.append(
            Item(
                source="github",
                source_label=f"{repo} · commit",
                title=f"[{repo}] {title}",
                url=c.get("html_url") or f"https://github.com/{repo}/commit/{sha}",
                published=_parse_dt((commit.get("author") or {}).get("date")),
                summary=message[:1000],
                extra={"repo": repo, "kind": "commit", "author": author, "sha": sha},
            )
        )
        if len(items) >= limit:
            break
    return items


def _fetch_releases(client, repo: str, since: datetime, limit: int) -> list[Item]:
    url = f"{API_ROOT}/repos/{repo}/releases"
    try:
        data = get_json(client, url, params={"per_page": min(20, limit)})
    except Exception as e:  # noqa: BLE001
        log.error("GitHub releases 拉取失败 %s: %s", repo, e)
        return []
    items: list[Item] = []
    for rel in data or []:
        published = _parse_dt(rel.get("published_at") or rel.get("created_at"))
        if published and published < since:
            continue
        tag = rel.get("tag_name", "")
        name = rel.get("name") or tag
        items.append(
            Item(
                source="github",
                source_label=f"{repo} · release",
                title=f"[{repo}] Release {name}",
                url=rel.get("html_url") or f"https://github.com/{repo}/releases/tag/{tag}",
                published=published,
                summary=(rel.get("body") or "")[:2000],
                extra={"repo": repo, "kind": "release", "tag": tag},
            )
        )
        if len(items) >= limit:
            break
    return items


def _fetch_merged_pulls(client, repo: str, since: datetime, limit: int) -> list[Item]:
    # GitHub search API 可按 merged 时间过滤
    url = f"{API_ROOT}/search/issues"
    q = f"repo:{repo} is:pr is:merged merged:>={since.date().isoformat()}"
    try:
        data = get_json(
            client,
            url,
            params={"q": q, "sort": "updated", "order": "desc", "per_page": min(50, limit)},
        )
    except Exception as e:  # noqa: BLE001
        log.error("GitHub pulls 拉取失败 %s: %s", repo, e)
        return []
    items: list[Item] = []
    for pr in (data or {}).get("items", []) or []:
        merged_at = _parse_dt(pr.get("closed_at"))
        if merged_at and merged_at < since:
            continue
        items.append(
            Item(
                source="github",
                source_label=f"{repo} · PR",
                title=f"[{repo}] #{pr.get('number')} {pr.get('title','')}",
                url=pr.get("html_url", ""),
                published=merged_at,
                summary=(pr.get("body") or "")[:1500],
                extra={"repo": repo, "kind": "pull", "number": pr.get("number")},
            )
        )
        if len(items) >= limit:
            break
    return items


def fetch_github(github_cfg: dict[str, Any], lookback_hours: int, limit_per_repo: int) -> list[Item]:
    repos: list[str] = list(github_cfg.get("repos", []) or [])
    include = github_cfg.get("include", {}) or {}
    if not repos:
        return []

    since = datetime.now(timezone.utc) - timedelta(hours=lookback_hours)
    out: list[Item] = []
    with build_client(_auth_headers()) as client:
        for repo in repos:
            # 三类事件各给 limit_per_repo 的 1/3 ~ 1/2
            commit_n = max(5, limit_per_repo // 2) if include.get("commits", True) else 0
            release_n = max(2, limit_per_repo // 4) if include.get("releases", True) else 0
            pr_n = max(3, limit_per_repo // 3) if include.get("pulls", True) else 0

            if commit_n:
                out.extend(_fetch_commits(client, repo, since, commit_n))
            if release_n:
                out.extend(_fetch_releases(client, repo, since, release_n))
            if pr_n:
                out.extend(_fetch_merged_pulls(client, repo, since, pr_n))
    log.info("github: 拉到 %d 条（共 %d 仓库）", len(out), len(repos))
    return out
