from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Message:
    """One immutable conversation item passed between memory and runtimes."""

    role: str
    content: str
    id: str | None = None
    created_at: str | None = None


@dataclass(frozen=True)
class InvokeRequest:
    """Runtime-neutral input accepted by a :class:`ShuFuNode`."""

    model: str
    session_id: str
    input: str
    memory_window: int = 20
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class InvokeResult:
    """Stable v0.1 response contract returned by local and HTTP calls."""

    model: str
    session_id: str
    output: str
    created_at: str


@dataclass(frozen=True)
class StreamEvent:
    """One ordered event emitted by the v0.3 NDJSON invocation stream."""

    type: str
    request_id: str
    sequence: int
    data: dict[str, Any] = field(default_factory=dict)
