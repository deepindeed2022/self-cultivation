from __future__ import annotations

import os

from openai import OpenAI

from .base import LLMBackend, Message


class OpenAICompatBackend(LLMBackend):
    """覆盖 OpenAI / DeepSeek / Ollama 等 OpenAI 兼容协议的后端。

    差异仅在 base_url / api_key / 默认模型。
    """

    def __init__(
        self,
        *,
        name: str,
        api_key: str,
        base_url: str | None,
        model: str,
    ):
        self.name = name
        self.model = model
        self._client = OpenAI(api_key=api_key, base_url=base_url)

    def chat(
        self,
        messages: list[Message],
        *,
        temperature: float = 0.3,
        max_tokens: int = 1500,
        json_mode: bool = False,
    ) -> str:
        kwargs: dict = {
            "model": self.model,
            "messages": [m.to_dict() for m in messages],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        resp = self._client.chat.completions.create(**kwargs)
        return (resp.choices[0].message.content or "").strip()


def make_openai() -> OpenAICompatBackend:
    return OpenAICompatBackend(
        name="openai",
        api_key=os.environ["OPENAI_API_KEY"],
        base_url=os.getenv("OPENAI_BASE_URL"),
        model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
    )


def make_deepseek() -> OpenAICompatBackend:
    return OpenAICompatBackend(
        name="deepseek",
        api_key=os.environ["DEEPSEEK_API_KEY"],
        base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
        model=os.getenv("DEEPSEEK_MODEL", "deepseek-chat"),
    )


def make_ollama() -> OpenAICompatBackend:
    host = os.getenv("OLLAMA_HOST", "http://localhost:11434")
    return OpenAICompatBackend(
        name="ollama",
        api_key=os.getenv("OLLAMA_API_KEY", "ollama"),
        base_url=f"{host.rstrip('/')}/v1",
        model=os.getenv("OLLAMA_MODEL", "qwen2.5:7b"),
    )
