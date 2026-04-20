from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Iterable


def _hash(value: str) -> str:
    return hashlib.sha1(value.encode("utf-8")).hexdigest()


class SeenCache:
    """基于文件的已见条目指纹缓存，用于跨运行去重。"""

    def __init__(self, path: str | os.PathLike[str]):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._seen: set[str] = set()
        if self.path.exists():
            try:
                data = json.loads(self.path.read_text(encoding="utf-8"))
                self._seen = set(data.get("seen", []))
            except (json.JSONDecodeError, OSError):
                self._seen = set()

    def is_seen(self, key: str) -> bool:
        return _hash(key) in self._seen

    def mark(self, key: str) -> None:
        self._seen.add(_hash(key))

    def mark_many(self, keys: Iterable[str]) -> None:
        for k in keys:
            self.mark(k)

    def save(self, max_items: int = 20000) -> None:
        items = list(self._seen)
        if len(items) > max_items:
            items = items[-max_items:]
        self.path.write_text(
            json.dumps({"seen": items}, ensure_ascii=False),
            encoding="utf-8",
        )
