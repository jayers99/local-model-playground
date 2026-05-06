"""Thin OpenAI-SDK wrapper pointed at the local mlx_lm.server."""
from __future__ import annotations

from collections.abc import Iterator

from openai import OpenAI

from .profiles import Profile


class LLMClient:
    def __init__(self, profile: Profile):
        self.profile = profile
        self._client = OpenAI(base_url=profile.base_url, api_key="not-needed")

    def stream_chat(self, messages: list[dict]) -> Iterator[str]:
        stream = self._client.chat.completions.create(
            model=self.profile.model,
            messages=messages,
            temperature=self.profile.temperature,
            max_tokens=self.profile.max_tokens,
            stream=True,
        )
        for chunk in stream:
            delta = chunk.choices[0].delta
            content = getattr(delta, "content", None)
            if content:
                yield content
