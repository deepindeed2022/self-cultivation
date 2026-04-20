from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Literal


Role = Literal["system", "user", "assistant"]


@dataclass
class Message:
    role: Role
    content: str

    def to_dict(self) -> dict[str, str]:
        return {"role": self.role, "content": self.content}


class LLMBackend(ABC):
    """LLM 后端统一接口。"""

    name: str = "base"

    @abstractmethod
    def chat(
        self,
        messages: list[Message],
        *,
        temperature: float = 0.3,
        max_tokens: int = 1500,
        json_mode: bool = False,
    ) -> str:
        """返回 assistant 文本内容。若 json_mode=True，实现应尽力让输出为合法 JSON。"""
        raise NotImplementedError
