from __future__ import annotations

from .memory import MemoryStore, utc_now
from .runtimes.base import Runtime
from .types import InvokeRequest, InvokeResult


class ShuFuNode:
    """Compose one model runtime with durable, runtime-agnostic memory."""

    def __init__(self, runtime: Runtime, memory: MemoryStore):
        self.runtime = runtime
        self.memory = memory

    def invoke(self, request: InvokeRequest) -> InvokeResult:
        """Persist a user turn, generate from its memory window, and persist output.

        The user message is stored before generation so a failed runtime call is
        diagnosable and can be retried by the user.  Only the configured recent
        window is sent to the runtime; artifacts never enter prompts implicitly.
        """

        if not request.input.strip():
            raise ValueError("input must not be empty")
        if not request.session_id.strip():
            raise ValueError("session_id must not be empty")
        self.memory.add_message(request.session_id, "user", request.input)
        messages = self.memory.history(request.session_id, request.memory_window)
        output = self.runtime.generate(request.model, messages)
        self.memory.add_message(request.session_id, "assistant", output)
        return InvokeResult(
            model=request.model,
            session_id=request.session_id,
            output=output,
            created_at=utc_now(),
        )
