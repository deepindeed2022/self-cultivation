from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal


SourceKind = Literal["arxiv", "github", "rss"]


@dataclass
class Item:
    """采集到的原始条目（未经 LLM 摘要）。"""

    source: SourceKind
    source_label: str
    title: str
    url: str
    published: datetime | None = None
    summary: str = ""
    extra: dict = field(default_factory=dict)

    def fingerprint(self) -> str:
        return f"{self.source}:{self.url}"


@dataclass
class Summarized:
    """LLM 摘要后的条目。"""

    item: Item
    tldr: str
    why_it_matters: str = ""
