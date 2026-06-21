from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any

from .agent_lite import AuditEvent


SENSITIVE_MARKERS = (
    "token",
    "password",
    "secret",
    "api_key",
    "authorization",
    "content",
    "output",
    "prompt",
    "input",
)


def redact_audit_value(value: Any) -> Any:
    """Return a JSON-safe copy with conventionally sensitive fields removed."""

    if isinstance(value, dict):
        redacted: dict[str, Any] = {}
        for key, item in value.items():
            normalized = str(key).lower()
            redacted[str(key)] = (
                "[REDACTED]"
                if any(marker in normalized for marker in SENSITIVE_MARKERS)
                else redact_audit_value(item)
            )
        return redacted
    if isinstance(value, (list, tuple)):
        return [redact_audit_value(item) for item in value]
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


class JsonlAuditSink:
    """Append redacted Agent Lite events to a host-owned JSONL file."""

    def __init__(self, path: str | Path):
        self.path = Path(path).expanduser().resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def __call__(self, event: AuditEvent) -> None:
        payload = redact_audit_value(event.as_dict())
        line = json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n"
        with self._lock:
            with self.path.open("a", encoding="utf-8", newline="") as output:
                output.write(line)
