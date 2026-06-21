from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from shufu.types import Message
from .base import Runtime


class LlamaCppRuntime(Runtime):
    """Optional desktop GGUF adapter backed by ``llama-cpp-python``."""

    name = "llama.cpp"

    def __init__(self, model_path: str, context_size: int = 4096):
        """Validate the model eagerly so configuration failures surface early."""

        path = Path(model_path).expanduser().resolve()
        if not path.is_file():
            raise FileNotFoundError(f"GGUF model not found: {path}")
        try:
            from llama_cpp import Llama
        except ImportError as exc:
            raise RuntimeError(
                "llama-cpp-python is not installed. Run: pip install -e .[llama]"
            ) from exc
        self._llm = Llama(model_path=str(path), n_ctx=context_size, verbose=False)

    def generate(self, model: str, messages: Sequence[Message]) -> str:
        """Translate ShuFu messages to llama.cpp's chat-completion format."""

        response = self._llm.create_chat_completion(
            messages=[{"role": m.role, "content": m.content} for m in messages]
        )
        return str(response["choices"][0]["message"]["content"] or "")
