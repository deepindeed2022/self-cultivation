from __future__ import annotations

import os

from .base import LLMBackend


def build_backend(provider: str | None = None) -> LLMBackend:
    p = (provider or os.getenv("LLM_PROVIDER", "openai")).strip().lower()
    if p == "openai":
        from .openai_compat import make_openai
        return make_openai()
    if p == "deepseek":
        from .openai_compat import make_deepseek
        return make_deepseek()
    if p == "ollama":
        from .openai_compat import make_ollama
        return make_ollama()
    if p in ("anthropic", "claude"):
        from .anthropic_backend import make_anthropic
        return make_anthropic()
    raise ValueError(
        f"未知 LLM_PROVIDER: {p!r}，支持 openai / deepseek / ollama / anthropic"
    )
