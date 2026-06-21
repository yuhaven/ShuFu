from __future__ import annotations

import json
import hashlib
import urllib.request
import urllib.parse
from collections.abc import Iterator
from typing import Any


class ShuFuClient:
    """Small standard-library client for ShuFu's stable HTTP endpoints.

    Transport errors deliberately propagate to the caller.  Retry policy is a
    product decision because an automatic retry could repeat a costly model
    call or a future side effect.
    """

    def __init__(self, base_url: str = "http://127.0.0.1:7878", token: str | None = None):
        self.base_url = base_url.rstrip("/")
        self.token = token

    def _request(self, method: str, path: str, payload: dict[str, Any] | None = None) -> dict:
        """Send one JSON request and decode one JSON object response."""

        data = None if payload is None else json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            f"{self.base_url}{path}",
            data=data,
            method=method,
            headers={"Content-Type": "application/json"},
        )
        if self.token:
            request.add_header("Authorization", f"Bearer {self.token}")
        with urllib.request.urlopen(request, timeout=120) as response:
            return json.loads(response.read().decode("utf-8"))

    def _request_bytes(self, path: str, *, byte_range: tuple[int, int] | None = None) -> bytes:
        """Fetch authenticated bytes from this Node, optionally with one HTTP range."""

        resolved = urllib.parse.urljoin(f"{self.base_url}/", path)
        base = urllib.parse.urlparse(self.base_url)
        target = urllib.parse.urlparse(resolved)
        if (target.scheme, target.netloc) != (base.scheme, base.netloc):
            raise ValueError("external artifact reference must belong to the ShuFu Node")
        request = urllib.request.Request(resolved, method="GET")
        if self.token:
            request.add_header("Authorization", f"Bearer {self.token}")
        if byte_range:
            request.add_header("Range", f"bytes={byte_range[0]}-{byte_range[1]}")
        with urllib.request.urlopen(request, timeout=120) as response:
            return response.read()

    def invoke(
        self,
        input_text: str,
        *,
        model: str = "assistant",
        session_id: str = "default",
        memory_window: int = 20,
    ) -> dict:
        """Invoke a node through the v0.1-compatible endpoint."""

        return self._request(
            "POST",
            "/shufu/v1/invoke",
            {
                "model": model,
                "session_id": session_id,
                "input": input_text,
                "memory_window": memory_window,
            },
        )

    def invoke_stream(
        self,
        input_text: str,
        *,
        model: str = "assistant",
        session_id: str = "default",
        memory_window: int = 20,
        stream_chunk_size: int = 64,
    ) -> Iterator[dict[str, Any]]:
        """Yield ordered v0.3 NDJSON events without buffering the response body."""

        payload = json.dumps(
            {
                "model": model,
                "session_id": session_id,
                "input": input_text,
                "memory_window": memory_window,
                "stream_chunk_size": stream_chunk_size,
            }
        ).encode("utf-8")
        request = urllib.request.Request(
            f"{self.base_url}/shufu/v3/invoke/stream",
            data=payload,
            method="POST",
            headers={"Content-Type": "application/json", "Accept": "application/x-ndjson"},
        )
        if self.token:
            request.add_header("Authorization", f"Bearer {self.token}")

        def events() -> Iterator[dict[str, Any]]:
            request_id: str | None = None
            expected_sequence = 0
            with urllib.request.urlopen(request, timeout=120) as response:
                for raw_line in response:
                    if not raw_line.strip():
                        continue
                    event = json.loads(raw_line.decode("utf-8"))
                    if request_id is None:
                        request_id = str(event["request_id"])
                    if str(event.get("request_id")) != request_id:
                        raise ValueError("stream request_id changed")
                    if int(event.get("sequence", -1)) != expected_sequence:
                        raise ValueError("stream event sequence is not contiguous")
                    event_type = str(event.get("type"))
                    if expected_sequence == 0 and event_type != "start":
                        raise ValueError("stream must begin with a start event")
                    if expected_sequence > 0 and event_type not in {"delta", "done", "error"}:
                        raise ValueError(f"unsupported stream event type: {event_type}")
                    expected_sequence += 1
                    yield event
                    if event_type == "error":
                        raise RuntimeError(str(event.get("detail") or event.get("error")))
                    if event_type == "done":
                        return
            raise ValueError("stream ended without a done or error event")

        return events()

    def capabilities(self) -> dict:
        """Read advertised features instead of inferring them from a version."""

        return self._request("GET", "/shufu/v1/capabilities")

    def sync_pull(self, *, after: int = 0, session_id: str | None = None) -> dict:
        """Pull a Schema 2 bundle containing changes after a node cursor."""

        query = {"after": str(after)}
        if session_id:
            query["session_id"] = session_id
        return self._request("GET", f"/shufu/v2/sync/pull?{urllib.parse.urlencode(query)}")

    def sync_push(self, bundle: dict[str, Any]) -> dict:
        """Idempotently push a portable memory bundle to a v0.2 node."""

        return self._request("POST", "/shufu/v2/sync/push", bundle)

    def sync_pull_v3(
        self,
        *,
        after: int = 0,
        session_id: str | None = None,
        artifact_mode: str = "auto",
    ) -> dict:
        """Pull Schema 3 changes with a bounded artifact representation."""

        query = {"after": str(after), "artifact_mode": artifact_mode}
        if session_id:
            query["session_id"] = session_id
        return self._request("GET", f"/shufu/v3/sync/pull?{urllib.parse.urlencode(query)}")

    def sync_exchange(
        self,
        push_bundle: dict[str, Any],
        *,
        push_after: int,
        pull_after: int,
        session_id: str | None = None,
        artifact_mode: str = "auto",
    ) -> dict:
        """Exchange deltas while keeping local-push and remote-pull cursors separate."""

        return self._request(
            "POST",
            "/shufu/v3/sync/exchange",
            {
                "source_node_id": push_bundle["source_node_id"],
                "push_after": push_after,
                "pull_after": pull_after,
                "session_id": session_id,
                "artifact_mode": artifact_mode,
                "push_bundle": push_bundle,
            },
        )

    def resolve_artifact_ref(self, reference: dict[str, Any]) -> bytes:
        """Explicitly materialize a same-Node external reference and verify it."""

        content = self._request_bytes(str(reference["url"]))
        if len(content) != int(reference["size"]):
            raise ValueError("external artifact size mismatch")
        if hashlib.sha256(content).hexdigest() != str(reference["sha256"]):
            raise ValueError("external artifact hash mismatch")
        return content
