from __future__ import annotations

import json
import urllib.request
from collections.abc import Sequence

from shufu.types import Message
from .base import Runtime


class OpenAICompatibleRuntime(Runtime):
    """Adapter for services implementing the OpenAI chat-completions shape."""

    name = "openai-compatible"

    def __init__(self, base_url: str, api_key: str | None = None, timeout: float = 120):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout

    def generate(self, model: str, messages: Sequence[Message]) -> str:
        """Perform one non-streaming completion without provider-specific logic."""

        body = json.dumps(
            {
                "model": model,
                "messages": [{"role": m.role, "content": m.content} for m in messages],
                "stream": False,
            }
        ).encode("utf-8")
        request = urllib.request.Request(
            f"{self.base_url}/v1/chat/completions",
            data=body,
            method="POST",
            headers={"Content-Type": "application/json"},
        )
        if self.api_key:
            request.add_header("Authorization", f"Bearer {self.api_key}")
        with urllib.request.urlopen(request, timeout=self.timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
        return str(payload["choices"][0]["message"]["content"] or "")
