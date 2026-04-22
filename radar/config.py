from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass
class Config:
    raw: dict[str, Any]
    lookback_hours: int = 24
    limits: dict[str, int] = field(default_factory=dict)
    keywords: list[str] = field(default_factory=list)
    arxiv: dict[str, Any] = field(default_factory=dict)
    github: dict[str, Any] = field(default_factory=dict)
    rss: dict[str, Any] = field(default_factory=dict)
    wechat: dict[str, Any] = field(default_factory=dict)
    zhihu: dict[str, Any] = field(default_factory=dict)
    report: dict[str, Any] = field(default_factory=dict)
    feishu: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def load(cls, path: str | Path) -> "Config":
        data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
        return cls(
            raw=data,
            lookback_hours=int(data.get("lookback_hours", 24)),
            limits=data.get("limits", {}) or {},
            keywords=list(data.get("keywords", []) or []),
            arxiv=data.get("arxiv", {}) or {},
            github=data.get("github", {}) or {},
            rss=data.get("rss", {}) or {},
            wechat=data.get("wechat", {}) or {},
            zhihu=data.get("zhihu", {}) or {},
            report=data.get("report", {}) or {},
            feishu=data.get("feishu", {}) or {},
        )
