from __future__ import annotations

import os

from anthropic import Anthropic

from .base import LLMBackend, Message


class AnthropicBackend(LLMBackend):
    name = "anthropic"

    def __init__(self, *, api_key: str, model: str):
        self.model = model
        self._client = Anthropic(api_key=api_key)

    def chat(
        self,
        messages: list[Message],
        *,
        temperature: float = 0.3,
        max_tokens: int = 1500,
        json_mode: bool = False,
    ) -> str:
        system_parts: list[str] = []
        turns: list[dict] = []
        for m in messages:
            if m.role == "system":
                system_parts.append(m.content)
            else:
                turns.append({"role": m.role, "content": m.content})

        system_prompt = "\n\n".join(system_parts) if system_parts else None
        if json_mode:
            json_hint = "Respond with a single valid JSON object only. No prose, no code fences."
            system_prompt = f"{system_prompt}\n\n{json_hint}" if system_prompt else json_hint

        resp = self._client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            temperature=temperature,
            system=system_prompt or "",
            messages=turns,
        )
        parts = [b.text for b in resp.content if getattr(b, "type", None) == "text"]
        return "".join(parts).strip()


def make_anthropic() -> AnthropicBackend:
    return AnthropicBackend(
        api_key=os.environ["ANTHROPIC_API_KEY"],
        model=os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-latest"),
    )
