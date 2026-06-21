from __future__ import annotations

from collections.abc import Sequence

from shufu.types import Message
from .base import Runtime


class EchoRuntime(Runtime):
    """A deterministic, dependency-free runtime for first-run and tests."""

    name = "echo"

    def generate(self, model: str, messages: Sequence[Message]) -> str:
        """Return the last prompt plus a deterministic continuity marker."""

        prompt = next((m.content for m in reversed(messages) if m.role == "user"), "")
        prior_turns = max(0, sum(1 for m in messages if m.role == "user") - 1)
        continuity = f"，已延续 {prior_turns} 轮上下文" if prior_turns else ""
        return f"ShuFu[{model}]{continuity}: {prompt}"
