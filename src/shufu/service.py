from __future__ import annotations

import base64
import json
import uuid
from dataclasses import asdict
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from .node import ShuFuNode
from .types import InvokeRequest


class ShuFuHTTPServer(ThreadingHTTPServer):
    """Thread-per-request HTTP server carrying a shared node and optional token."""

    daemon_threads = True

    def __init__(self, address: tuple[str, int], node: ShuFuNode, token: str | None = None):
        super().__init__(address, ShuFuRequestHandler)
        self.node = node
        self.token = token


class ShuFuRequestHandler(BaseHTTPRequestHandler):
    """Versioned JSON transport for invoke, memory, artifact, and sync operations."""

    server: ShuFuHTTPServer

    def log_message(self, format: str, *args: object) -> None:
        return

    def _authorized(self) -> bool:
        """Apply the deliberately small v0.1 shared-token policy."""

        if not self.server.token:
            return True
        return self.headers.get("Authorization") == f"Bearer {self.server.token}"

    def _json(self, status: int, payload: object) -> None:
        """Serialize one UTF-8 JSON response with an exact content length."""

        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _body(self) -> dict:
        """Decode a bounded JSON object to avoid unbounded in-memory request reads."""

        length = int(self.headers.get("Content-Length", "0"))
        if length > 16 * 1024 * 1024:
            raise ValueError("request body exceeds 16 MiB")
        return json.loads(self.rfile.read(length).decode("utf-8"))

    def _raw_artifact(self, artifact_id: str) -> None:
        """Send artifact bytes, honoring one bounded HTTP byte range for edge clients."""

        try:
            artifact = self.server.node.memory.artifact(artifact_id)
        except KeyError:
            self._json(HTTPStatus.NOT_FOUND, {"error": "ARTIFACT_NOT_FOUND"})
            return
        content = artifact["content"]
        start, end = 0, len(content) - 1
        status = HTTPStatus.OK
        requested_range = self.headers.get("Range")
        if requested_range:
            if not requested_range.startswith("bytes=") or "," in requested_range:
                self._json(HTTPStatus.BAD_REQUEST, {"error": "INVALID_RANGE"})
                return
            bounds = requested_range[6:].split("-", 1)
            try:
                start = int(bounds[0])
                end = int(bounds[1]) if bounds[1] else end
            except ValueError:
                self._json(HTTPStatus.BAD_REQUEST, {"error": "INVALID_RANGE"})
                return
            if start < 0 or end < start or start >= len(content):
                self.send_response(HTTPStatus.REQUESTED_RANGE_NOT_SATISFIABLE)
                self.send_header("Content-Range", f"bytes */{len(content)}")
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            end = min(end, len(content) - 1)
            status = HTTPStatus.PARTIAL_CONTENT
        body = content[start : end + 1]
        self.send_response(status)
        self.send_header("Content-Type", artifact["mime_type"])
        self.send_header("Content-Length", str(len(body)))
        self.send_header("ETag", f'"sha256:{artifact["sha256"]}"')
        self.send_header("Accept-Ranges", "bytes")
        if status == HTTPStatus.PARTIAL_CONTENT:
            self.send_header("Content-Range", f"bytes {start}-{end}/{len(content)}")
        self.end_headers()
        self.wfile.write(body)

    def _stream_invoke(self, payload: dict) -> None:
        """Emit a v0.3 invocation as newline-delimited JSON events.

        The current runtimes expose a blocking ``generate`` method.  The wire
        protocol still streams bounded UTF-8 deltas after generation, allowing
        ESP32 and CLI consumers to use constant-memory parsers.  A future runtime
        adapter can provide token-level deltas without changing this endpoint.
        """

        request = InvokeRequest(
            model=str(payload.get("model", "assistant")),
            session_id=str(payload.get("session_id", "default")),
            input=str(payload.get("input", "")),
            memory_window=int(payload.get("memory_window", 20)),
        )
        if not request.input.strip() or not request.session_id.strip():
            raise ValueError("input and session_id must not be empty")
        chunk_size = int(payload.get("stream_chunk_size", 64))
        if chunk_size < 1 or chunk_size > 4096:
            raise ValueError("stream_chunk_size must be between 1 and 4096")
        request_id = str(uuid.uuid4())
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "application/x-ndjson; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Accel-Buffering", "no")
        self.end_headers()

        def emit(event: dict) -> None:
            self.wfile.write(json.dumps(event, ensure_ascii=False).encode("utf-8") + b"\n")
            self.wfile.flush()

        emit(
            {
                "type": "start",
                "request_id": request_id,
                "sequence": 0,
                "protocol_version": "0.3",
                "model": request.model,
                "session_id": request.session_id,
            }
        )
        try:
            result = self.server.node.invoke(request)
            sequence = 1
            for offset in range(0, len(result.output), chunk_size):
                emit(
                    {
                        "type": "delta",
                        "request_id": request_id,
                        "sequence": sequence,
                        "delta": result.output[offset : offset + chunk_size],
                    }
                )
                sequence += 1
            emit(
                {
                    "type": "done",
                    "request_id": request_id,
                    "sequence": sequence,
                    "created_at": result.created_at,
                    "output_chars": len(result.output),
                }
            )
        except Exception as exc:  # A stream already has HTTP 200; failure is an event.
            emit(
                {
                    "type": "error",
                    "request_id": request_id,
                    "sequence": 1,
                    "error": "INVOKE_FAILED",
                    "detail": str(exc),
                }
            )

    def _guard(self) -> bool:
        """Leave health public and require the configured token everywhere else."""

        if self.path == "/health" or self._authorized():
            return True
        self._json(HTTPStatus.UNAUTHORIZED, {"error": "AUTH_REQUIRED"})
        return False

    def do_GET(self) -> None:
        """Serve health, capabilities, export, incremental pull, and artifacts."""

        if not self._guard():
            return
        parsed = urlparse(self.path)
        if parsed.path == "/health":
            self._json(HTTPStatus.OK, {"status": "ok", "version": "0.4"})
            return
        if parsed.path == "/shufu/v1/capabilities":
            self._json(
                HTTPStatus.OK,
                {
                    # The v1 capabilities route keeps its historical primary
                    # value; new clients negotiate through protocol_versions.
                    "protocol_version": "0.2",
                    "latest_protocol_version": "0.4",
                    "protocol_versions": ["0.1", "0.2", "0.3", "0.4"],
                    "node_id": self.server.node.memory.node_id,
                    "runtime": self.server.node.runtime.name,
                    "memory": {
                        "sessions": True,
                        "artifacts": True,
                        "bundle_schemas": [1, 2, 3],
                        "incremental_sync": True,
                        "dual_cursor_sync": True,
                        "artifact_transfer": ["inline", "chunks", "external"],
                    },
                    "discovery": {"method": "udp-broadcast", "port": 7879},
                    "invoke": {"streaming": "ndjson"},
                    "agent": {
                        "tool_registry": True,
                        "agent_lite": True,
                        "bounded_loop": True,
                        "side_effect_approval": "per_call",
                        "artifact_context": "explicit_selection",
                        "summary_memory": "separate_store",
                        "http_transport": False,
                        "autonomous_loop": False,
                    },
                },
            )
            return
        if parsed.path == "/shufu/v1/memory/export":
            session_id = parse_qs(parsed.query).get("session_id", [None])[0]
            # A v0.1 path must keep returning Schema 1 even though this server
            # also supports v0.2.  Old clients are never forced to parse cursors.
            self._json(
                HTTPStatus.OK,
                self.server.node.memory.export_bundle(session_id, target_schema=1),
            )
            return
        if parsed.path == "/shufu/v2/sync/pull":
            query = parse_qs(parsed.query)
            session_id = query.get("session_id", [None])[0]
            after = int(query.get("after", ["0"])[0])
            self._json(
                HTTPStatus.OK,
                self.server.node.memory.export_bundle(
                    session_id, after=after, target_schema=2, artifact_mode="inline"
                ),
            )
            return
        if parsed.path == "/shufu/v3/sync/pull":
            query = parse_qs(parsed.query)
            session_id = query.get("session_id", [None])[0]
            after = int(query.get("after", ["0"])[0])
            artifact_mode = query.get("artifact_mode", ["auto"])[0]
            self._json(
                HTTPStatus.OK,
                self.server.node.memory.export_bundle(
                    session_id,
                    after=after,
                    target_schema=3,
                    artifact_mode=artifact_mode,
                ),
            )
            return
        v3_artifact_prefix = "/shufu/v3/artifacts/"
        if parsed.path.startswith(v3_artifact_prefix) and parsed.path.endswith("/content"):
            identifier = parsed.path[len(v3_artifact_prefix) : -len("/content")]
            self._raw_artifact(identifier)
            return
        prefix = "/shufu/v1/artifacts/"
        if parsed.path.startswith(prefix):
            identifier = parsed.path[len(prefix) :]
            try:
                artifact = self.server.node.memory.artifact(identifier)
            except KeyError:
                self._json(HTTPStatus.NOT_FOUND, {"error": "ARTIFACT_NOT_FOUND"})
                return
            content = artifact.pop("content")
            self._json(
                HTTPStatus.OK,
                {**artifact, "content_base64": base64.b64encode(content).decode("ascii")},
            )
            return
        self._json(HTTPStatus.NOT_FOUND, {"error": "NOT_FOUND"})

    def do_POST(self) -> None:
        """Serve invocation, imports, sync pushes, and artifact uploads."""

        if not self._guard():
            return
        parsed = urlparse(self.path)
        try:
            payload = self._body()
            if parsed.path == "/shufu/v3/invoke/stream":
                self._stream_invoke(payload)
                return
            if parsed.path == "/shufu/v1/invoke":
                request = InvokeRequest(
                    model=str(payload.get("model", "assistant")),
                    session_id=str(payload.get("session_id", "default")),
                    input=str(payload.get("input", "")),
                    memory_window=int(payload.get("memory_window", 20)),
                )
                self._json(HTTPStatus.OK, asdict(self.server.node.invoke(request)))
                return
            if parsed.path == "/shufu/v1/memory/import":
                self._json(HTTPStatus.OK, self.server.node.memory.import_bundle(payload))
                return
            if parsed.path == "/shufu/v2/sync/push":
                result = self.server.node.memory.import_bundle(payload)
                self._json(
                    HTTPStatus.OK,
                    {**result, "cursor": self.server.node.memory._current_cursor()},
                )
                return
            if parsed.path == "/shufu/v3/sync/exchange":
                source_node_id = str(payload["source_node_id"])
                push_after = int(payload.get("push_after", 0))
                pull_after = int(payload.get("pull_after", 0))
                session_id = payload.get("session_id")
                artifact_mode = str(payload.get("artifact_mode", "auto"))
                push_bundle = payload["push_bundle"]
                if push_bundle.get("schema_version") != 3:
                    raise ValueError("v0.3 exchange requires a Schema 3 push bundle")
                if str(push_bundle.get("source_node_id")) != source_node_id:
                    raise ValueError("source_node_id does not match push bundle")
                if int(push_bundle.get("after", 0)) != push_after:
                    raise ValueError("push_after does not match push bundle")
                # Snapshot remote changes before importing the push.  This avoids
                # immediately reflecting the requester's own objects in one exchange.
                pulled = self.server.node.memory.export_bundle(
                    str(session_id) if session_id else None,
                    after=pull_after,
                    target_schema=3,
                    artifact_mode=artifact_mode,
                    exclude_source_node_id=source_node_id,
                )
                imported = self.server.node.memory.import_bundle(push_bundle)
                self._json(
                    HTTPStatus.OK,
                    {
                        "protocol_version": "0.3",
                        "remote_node_id": self.server.node.memory.node_id,
                        "acknowledged_push_cursor": int(push_bundle.get("cursor", push_after)),
                        "imported": imported,
                        "pull_bundle": pulled,
                    },
                )
                return
            if parsed.path == "/shufu/v1/artifacts":
                content = base64.b64decode(payload["content_base64"], validate=True)
                record = self.server.node.memory.add_artifact_bytes(
                    str(payload.get("session_id", "default")),
                    str(payload["name"]),
                    content,
                    str(payload.get("mime_type", "application/octet-stream")),
                )
                self._json(HTTPStatus.CREATED, record)
                return
        except (ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
            self._json(HTTPStatus.BAD_REQUEST, {"error": "INVALID_REQUEST", "detail": str(exc)})
            return
        self._json(HTTPStatus.NOT_FOUND, {"error": "NOT_FOUND"})


def serve(node: ShuFuNode, host: str, port: int, token: str | None = None) -> None:
    """Run a ShuFu node until interrupted and always close its listening socket."""

    server = ShuFuHTTPServer((host, port), node, token)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
