from __future__ import annotations

import base64
import hashlib
import json
import mimetypes
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from collections.abc import Callable
from typing import Any

from .types import Message


# Keep the public ``export_bundle()`` default at Schema 2 for source/API
# compatibility.  v0.3 call sites opt into Schema 3 explicitly.
SCHEMA_VERSION = 2
LATEST_SCHEMA_VERSION = 3

DEFAULT_ARTIFACT_CHUNK_SIZE = 64 * 1024
DEFAULT_ARTIFACT_INLINE_LIMIT = 256 * 1024


def utc_now() -> str:
    """Return a portable UTC timestamp in the protocol's ISO-8601 form."""

    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class MemoryStore:
    """SQLite metadata store plus content-addressed artifact storage.

    Messages and artifact records have immutable IDs so importing the same
    bundle more than once is safe.  Artifact bytes live outside SQLite under
    their SHA-256 name, allowing identical content to be reused by many records.
    """

    def __init__(self, home: str | Path):
        self.home = Path(home).expanduser().resolve()
        self.home.mkdir(parents=True, exist_ok=True)
        self.artifact_dir = self.home / "artifacts"
        self.artifact_dir.mkdir(exist_ok=True)
        self.db_path = self.home / "memory.sqlite3"
        self._init_db()

    @contextmanager
    def _connect(self):
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def _init_db(self) -> None:
        """Create the latest schema without requiring a separate migration tool."""

        with self._connect() as db:
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS sessions (
                    id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    title TEXT
                );
                CREATE TABLE IF NOT EXISTS messages (
                    id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(session_id) REFERENCES sessions(id)
                );
                CREATE INDEX IF NOT EXISTS idx_messages_session_time
                    ON messages(session_id, created_at);
                CREATE TABLE IF NOT EXISTS artifacts (
                    id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    mime_type TEXT NOT NULL,
                    sha256 TEXT NOT NULL,
                    size INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(session_id) REFERENCES sessions(id)
                );
                CREATE INDEX IF NOT EXISTS idx_artifacts_session
                    ON artifacts(session_id, created_at);
                CREATE TABLE IF NOT EXISTS meta (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS changes (
                    seq INTEGER PRIMARY KEY AUTOINCREMENT,
                    entity_type TEXT NOT NULL,
                    entity_id TEXT NOT NULL,
                    session_id TEXT,
                    origin_node_id TEXT,
                    changed_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_changes_session_seq
                    ON changes(session_id, seq);
                CREATE TABLE IF NOT EXISTS sync_peers (
                    remote_node_id TEXT PRIMARY KEY,
                    pushed_cursor INTEGER NOT NULL DEFAULT 0,
                    pulled_cursor INTEGER NOT NULL DEFAULT 0,
                    updated_at TEXT NOT NULL
                );
                """
            )
            change_columns = {
                str(row["name"]) for row in db.execute("PRAGMA table_info(changes)").fetchall()
            }
            if "origin_node_id" not in change_columns:
                db.execute("ALTER TABLE changes ADD COLUMN origin_node_id TEXT")
            existing = db.execute("SELECT value FROM meta WHERE key = 'node_id'").fetchone()
            if existing is None:
                db.execute(
                    "INSERT INTO meta(key, value) VALUES ('node_id', ?)",
                    (str(uuid.uuid4()),),
                )

    @property
    def node_id(self) -> str:
        """Return the stable identity used to scope remote synchronization cursors."""

        with self._connect() as db:
            row = db.execute("SELECT value FROM meta WHERE key = 'node_id'").fetchone()
        assert row is not None
        return str(row["value"])

    @staticmethod
    def _record_change(
        db: sqlite3.Connection,
        entity_type: str,
        entity_id: str,
        session_id: str | None,
        changed_at: str,
        origin_node_id: str | None = None,
    ) -> None:
        db.execute(
            "INSERT INTO changes(entity_type, entity_id, session_id, origin_node_id, changed_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (entity_type, entity_id, session_id, origin_node_id, changed_at),
        )

    def ensure_session(
        self,
        session_id: str,
        title: str | None = None,
        *,
        origin_node_id: str | None = None,
    ) -> None:
        """Create a session once and refresh its modification timestamp."""

        now = utc_now()
        with self._connect() as db:
            inserted = db.execute(
                "INSERT OR IGNORE INTO sessions(id, created_at, updated_at, title) VALUES (?, ?, ?, ?)",
                (session_id, now, now, title),
            )
            db.execute("UPDATE sessions SET updated_at = ? WHERE id = ?", (now, session_id))
            if inserted.rowcount:
                self._record_change(
                    db, "session", session_id, session_id, now, origin_node_id
                )

    def add_message(
        self,
        session_id: str,
        role: str,
        content: str,
        *,
        message_id: str | None = None,
        created_at: str | None = None,
        origin_node_id: str | None = None,
    ) -> str:
        """Append a validated immutable message and record a sync change."""

        if role not in {"system", "user", "assistant", "tool"}:
            raise ValueError(f"Unsupported message role: {role}")
        self.ensure_session(session_id, origin_node_id=origin_node_id)
        identifier = message_id or str(uuid.uuid4())
        timestamp = created_at or utc_now()
        with self._connect() as db:
            inserted = db.execute(
                "INSERT OR IGNORE INTO messages(id, session_id, role, content, created_at) VALUES (?, ?, ?, ?, ?)",
                (identifier, session_id, role, content, timestamp),
            )
            db.execute("UPDATE sessions SET updated_at = ? WHERE id = ?", (timestamp, session_id))
            if inserted.rowcount:
                self._record_change(
                    db, "message", identifier, session_id, timestamp, origin_node_id
                )
        return identifier

    def history(self, session_id: str, limit: int = 20) -> list[Message]:
        """Return the newest ``limit`` messages in chronological prompt order."""

        if limit <= 0:
            return []
        with self._connect() as db:
            rows = db.execute(
                """
                SELECT id, role, content, created_at FROM (
                    SELECT id, role, content, created_at
                    FROM messages WHERE session_id = ?
                    ORDER BY created_at DESC, rowid DESC LIMIT ?
                ) ORDER BY created_at ASC
                """,
                (session_id, limit),
            ).fetchall()
        return [Message(**dict(row)) for row in rows]

    def message(self, message_id: str) -> dict[str, Any]:
        """Return one immutable raw message with its owning session.

        Summary provenance uses this exact-ID lookup instead of trusting a
        caller-supplied ``Message`` object that could name a different session or
        content.  It is intentionally read-only and does not create changes.
        """

        with self._connect() as db:
            row = db.execute(
                "SELECT id, session_id, role, content, created_at FROM messages WHERE id = ?",
                (message_id,),
            ).fetchone()
        if row is None:
            raise KeyError(message_id)
        return dict(row)

    def sessions(self) -> list[dict[str, Any]]:
        """List sessions from most recently updated to least recent."""

        with self._connect() as db:
            rows = db.execute(
                "SELECT id, created_at, updated_at, title FROM sessions ORDER BY updated_at DESC"
            ).fetchall()
        return [dict(row) for row in rows]

    def add_artifact_bytes(
        self,
        session_id: str,
        name: str,
        content: bytes,
        mime_type: str = "application/octet-stream",
        *,
        artifact_id: str | None = None,
        created_at: str | None = None,
        origin_node_id: str | None = None,
    ) -> dict[str, Any]:
        """Store artifact bytes by hash and create a session-scoped record."""

        self.ensure_session(session_id, origin_node_id=origin_node_id)
        digest = hashlib.sha256(content).hexdigest()
        # Blob storage is content-addressed, while records remain session-addressable.
        # The same bytes can therefore appear in multiple sessions without losing context.
        identifier = artifact_id or str(uuid.uuid4())
        timestamp = created_at or utc_now()
        target = self.artifact_dir / digest
        if not target.exists():
            target.write_bytes(content)
        with self._connect() as db:
            inserted = db.execute(
                """
                INSERT OR IGNORE INTO artifacts
                    (id, session_id, name, mime_type, sha256, size, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (identifier, session_id, Path(name).name, mime_type, digest, len(content), timestamp),
            )
            if inserted.rowcount:
                self._record_change(
                    db, "artifact", identifier, session_id, timestamp, origin_node_id
                )
        return {
            "id": identifier,
            "session_id": session_id,
            "name": Path(name).name,
            "mime_type": mime_type,
            "sha256": digest,
            "size": len(content),
            "created_at": timestamp,
        }

    def add_artifact_file(self, session_id: str, path: str | Path) -> dict[str, Any]:
        """Import a local file as an artifact after resolving it to an absolute path."""

        source = Path(path).expanduser().resolve()
        if not source.is_file():
            raise FileNotFoundError(source)
        mime_type = mimetypes.guess_type(source.name)[0] or "application/octet-stream"
        return self.add_artifact_bytes(session_id, source.name, source.read_bytes(), mime_type)

    def artifacts(self, session_id: str | None = None) -> list[dict[str, Any]]:
        """List artifact metadata, optionally restricted to one session."""

        query = "SELECT id, session_id, name, mime_type, sha256, size, created_at FROM artifacts"
        params: tuple[Any, ...] = ()
        if session_id:
            query += " WHERE session_id = ?"
            params = (session_id,)
        query += " ORDER BY created_at DESC"
        with self._connect() as db:
            rows = db.execute(query, params).fetchall()
        return [dict(row) for row in rows]

    def artifact(self, artifact_id: str) -> dict[str, Any]:
        """Load artifact metadata and verified-on-import content bytes by record ID."""

        with self._connect() as db:
            row = db.execute(
                "SELECT id, session_id, name, mime_type, sha256, size, created_at FROM artifacts WHERE id = ?",
                (artifact_id,),
            ).fetchone()
        if row is None:
            raise KeyError(artifact_id)
        record = dict(row)
        record["content"] = (self.artifact_dir / record["sha256"]).read_bytes()
        return record

    def _current_cursor(self, session_id: str | None = None) -> int:
        """Return the latest local change sequence for the requested scope."""

        query = "SELECT COALESCE(MAX(seq), 0) AS cursor FROM changes"
        params: tuple[Any, ...] = ()
        if session_id:
            query += " WHERE session_id = ?"
            params = (session_id,)
        with self._connect() as db:
            row = db.execute(query, params).fetchone()
        return int(row["cursor"] if row else 0)

    def current_cursor(self, session_id: str | None = None) -> int:
        """Return the public v0.3 change cursor for a store or session."""

        return self._current_cursor(session_id)

    def sync_state(self, remote_node_id: str) -> dict[str, Any]:
        """Read the independent push and pull cursors for one remote node."""

        with self._connect() as db:
            row = db.execute(
                "SELECT remote_node_id, pushed_cursor, pulled_cursor, updated_at "
                "FROM sync_peers WHERE remote_node_id = ?",
                (remote_node_id,),
            ).fetchone()
        if row is not None:
            return dict(row)
        return {
            "remote_node_id": remote_node_id,
            "pushed_cursor": 0,
            "pulled_cursor": 0,
            "updated_at": None,
        }

    def update_sync_state(
        self,
        remote_node_id: str,
        *,
        pushed_cursor: int | None = None,
        pulled_cursor: int | None = None,
    ) -> dict[str, Any]:
        """Advance peer cursors monotonically so an old response cannot rewind sync."""

        if not remote_node_id.strip():
            raise ValueError("remote_node_id must not be empty")
        if pushed_cursor is not None and pushed_cursor < 0:
            raise ValueError("pushed_cursor must be non-negative")
        if pulled_cursor is not None and pulled_cursor < 0:
            raise ValueError("pulled_cursor must be non-negative")
        current = self.sync_state(remote_node_id)
        pushed = max(int(current["pushed_cursor"]), pushed_cursor or 0)
        pulled = max(int(current["pulled_cursor"]), pulled_cursor or 0)
        now = utc_now()
        with self._connect() as db:
            db.execute(
                """
                INSERT INTO sync_peers(remote_node_id, pushed_cursor, pulled_cursor, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(remote_node_id) DO UPDATE SET
                    pushed_cursor = excluded.pushed_cursor,
                    pulled_cursor = excluded.pulled_cursor,
                    updated_at = excluded.updated_at
                """,
                (remote_node_id, pushed, pulled, now),
            )
        return self.sync_state(remote_node_id)

    def _encode_artifact(
        self,
        metadata: dict[str, Any],
        *,
        target_schema: int,
        artifact_mode: str,
        chunk_size: int,
        inline_limit: int,
    ) -> dict[str, Any]:
        """Encode artifact bytes using the representation selected by Schema 3."""

        content = (self.artifact_dir / metadata["sha256"]).read_bytes()
        if target_schema <= 2:
            return {**metadata, "content_base64": base64.b64encode(content).decode("ascii")}

        selected = artifact_mode
        if selected == "auto":
            selected = "inline" if len(content) <= inline_limit else "chunks"
        if selected == "inline":
            return {
                **metadata,
                "content_encoding": "base64",
                "content_base64": base64.b64encode(content).decode("ascii"),
            }
        if selected == "external":
            # Relative references bind resolution to the authenticated Node that
            # produced the bundle and avoid trusting a Host header supplied by a client.
            return {
                **metadata,
                "content_encoding": "external",
                "content_ref": {
                    "url": f"/shufu/v3/artifacts/{metadata['id']}/content",
                    "sha256": metadata["sha256"],
                    "size": metadata["size"],
                },
            }
        chunks = []
        for index, offset in enumerate(range(0, len(content), chunk_size)):
            part = content[offset : offset + chunk_size]
            chunks.append(
                {
                    "index": index,
                    "offset": offset,
                    "size": len(part),
                    "sha256": hashlib.sha256(part).hexdigest(),
                    "content_base64": base64.b64encode(part).decode("ascii"),
                }
            )
        return {
            **metadata,
            "content_encoding": "chunked-base64",
            "chunk_size": chunk_size,
            "content_chunks": chunks,
        }

    def export_bundle(
        self,
        session_id: str | None = None,
        *,
        after: int = 0,
        target_schema: int = SCHEMA_VERSION,
        artifact_mode: str = "auto",
        artifact_chunk_size: int = DEFAULT_ARTIFACT_CHUNK_SIZE,
        artifact_inline_limit: int = DEFAULT_ARTIFACT_INLINE_LIMIT,
        exclude_source_node_id: str | None = None,
    ) -> dict[str, Any]:
        """Export a full or incremental, protocol-versioned memory bundle.

        ``after=0`` creates a complete snapshot.  A positive cursor exports only
        entities referenced by newer change records.  Schema 1 intentionally
        omits v0.2 cursor metadata for old clients.
        """

        if target_schema not in {1, 2, 3}:
            raise ValueError("Unsupported target memory schema")
        if artifact_mode not in {"auto", "inline", "chunks", "external"}:
            raise ValueError("Unsupported artifact mode")
        if artifact_chunk_size <= 0 or artifact_chunk_size > 1024 * 1024:
            raise ValueError("artifact_chunk_size must be between 1 and 1048576")
        if artifact_inline_limit < 0:
            raise ValueError("artifact_inline_limit must be non-negative")
        with self._connect() as db:
            cursor_query = "SELECT COALESCE(MAX(seq), 0) AS cursor FROM changes"
            cursor_params: tuple[Any, ...] = ()
            if session_id:
                cursor_query += " WHERE session_id = ?"
                cursor_params = (session_id,)
            cursor_row = db.execute(cursor_query, cursor_params).fetchone()
            # Bind the exported records and cursor to one database snapshot. A
            # later concurrent write must remain eligible for the next exchange.
            scope_cursor = int(cursor_row["cursor"] if cursor_row else 0)
            if after > 0 or exclude_source_node_id:
                # Resolve changed IDs back to full immutable records.  Sending
                # records instead of patches keeps receivers simple and idempotent.
                change_query = (
                    "SELECT seq, entity_type, entity_id, session_id "
                    "FROM changes WHERE seq > ? AND seq <= ?"
                )
                change_params: list[Any] = [after, scope_cursor]
                if exclude_source_node_id:
                    change_query += " AND (origin_node_id IS NULL OR origin_node_id != ?)"
                    change_params.append(exclude_source_node_id)
                if session_id:
                    change_query += " AND session_id = ?"
                    change_params.append(session_id)
                change_query += " ORDER BY seq"
                changes = db.execute(change_query, tuple(change_params)).fetchall()
                session_ids = {str(row["session_id"]) for row in changes if row["session_id"]}
                message_ids = [str(row["entity_id"]) for row in changes if row["entity_type"] == "message"]
                artifact_ids = [str(row["entity_id"]) for row in changes if row["entity_type"] == "artifact"]
                sessions = []
                messages = []
                artifact_metadata: list[dict[str, Any]] = []
                if session_ids:
                    marks = ",".join("?" for _ in session_ids)
                    sessions = db.execute(
                        f"SELECT id, created_at, updated_at, title FROM sessions WHERE id IN ({marks})",
                        tuple(session_ids),
                    ).fetchall()
                if message_ids:
                    marks = ",".join("?" for _ in message_ids)
                    messages = db.execute(
                        f"SELECT id, session_id, role, content, created_at FROM messages WHERE id IN ({marks}) ORDER BY created_at",
                        tuple(message_ids),
                    ).fetchall()
                if artifact_ids:
                    marks = ",".join("?" for _ in artifact_ids)
                    artifact_metadata = [
                        dict(row)
                        for row in db.execute(
                            f"SELECT id, session_id, name, mime_type, sha256, size, created_at FROM artifacts WHERE id IN ({marks}) ORDER BY created_at",
                            tuple(artifact_ids),
                        ).fetchall()
                    ]
            elif session_id:
                sessions = db.execute(
                    "SELECT id, created_at, updated_at, title FROM sessions WHERE id = ?", (session_id,)
                ).fetchall()
                messages = db.execute(
                    "SELECT id, session_id, role, content, created_at FROM messages WHERE session_id = ? ORDER BY created_at",
                    (session_id,),
                ).fetchall()
                artifact_metadata = self.artifacts(session_id)
            else:
                sessions = db.execute(
                    "SELECT id, created_at, updated_at, title FROM sessions ORDER BY updated_at"
                ).fetchall()
                messages = db.execute(
                    "SELECT id, session_id, role, content, created_at FROM messages ORDER BY created_at"
                ).fetchall()
                artifact_metadata = self.artifacts()
        artifact_records = [
            self._encode_artifact(
                metadata,
                target_schema=target_schema,
                artifact_mode=artifact_mode,
                chunk_size=artifact_chunk_size,
                inline_limit=artifact_inline_limit,
            )
            for metadata in artifact_metadata
        ]
        bundle = {
            "schema_version": target_schema,
            "exported_at": utc_now(),
            "sessions": [dict(row) for row in sessions],
            "messages": [dict(row) for row in messages],
            "artifacts": artifact_records,
        }
        if target_schema >= 2:
            bundle.update(
                {
                    "bundle_id": str(uuid.uuid4()),
                    "source_node_id": self.node_id,
                    "after": after,
                    "cursor": scope_cursor,
                }
            )
        return bundle

    def export_for_peer(
        self,
        remote_node_id: str,
        session_id: str | None = None,
        *,
        artifact_mode: str = "chunks",
    ) -> dict[str, Any]:
        """Export only unsent local changes, excluding objects learned from that peer."""

        state = self.sync_state(remote_node_id)
        return self.export_bundle(
            session_id,
            after=int(state["pushed_cursor"]),
            target_schema=3,
            artifact_mode=artifact_mode,
            exclude_source_node_id=remote_node_id,
        )

    def import_bundle(
        self,
        bundle: dict[str, Any],
        *,
        external_resolver: Callable[[dict[str, Any]], bytes] | None = None,
    ) -> dict[str, int]:
        """Idempotently import Schema 1/2/3 objects and validate artifact hashes.

        Existing IDs win.  The store deliberately avoids silent conflict merges;
        a future conflict UI can make that policy explicit without changing the
        portable bundle format.
        """

        if bundle.get("schema_version") not in {1, 2, 3}:
            raise ValueError("Unsupported memory bundle schema_version")
        counts = {"sessions": 0, "messages": 0, "artifacts": 0}
        source_node_id = (
            str(bundle["source_node_id"]) if bundle.get("source_node_id") else None
        )
        for session in bundle.get("sessions", []):
            session_id = str(session["id"])
            with self._connect() as db:
                inserted = db.execute(
                    "INSERT OR IGNORE INTO sessions(id, created_at, updated_at, title) VALUES (?, ?, ?, ?)",
                    (
                        session_id,
                        str(session.get("created_at") or utc_now()),
                        str(session.get("updated_at") or utc_now()),
                        session.get("title"),
                    ),
                )
                if inserted.rowcount:
                    self._record_change(
                        db,
                        "session",
                        session_id,
                        session_id,
                        str(session.get("updated_at") or utc_now()),
                        source_node_id,
                    )
            counts["sessions"] += int(inserted.rowcount > 0)
        for message in bundle.get("messages", []):
            with self._connect() as db:
                exists = db.execute("SELECT 1 FROM messages WHERE id = ?", (message["id"],)).fetchone()
            self.add_message(
                str(message["session_id"]),
                str(message["role"]),
                str(message["content"]),
                message_id=str(message["id"]),
                created_at=str(message["created_at"]),
                origin_node_id=source_node_id,
            )
            counts["messages"] += int(exists is None)
        for artifact in bundle.get("artifacts", []):
            if "content_base64" in artifact:
                content = base64.b64decode(artifact["content_base64"], validate=True)
            elif "content_chunks" in artifact:
                chunks = sorted(artifact["content_chunks"], key=lambda item: int(item["index"]))
                parts: list[bytes] = []
                expected_offset = 0
                for expected_index, chunk in enumerate(chunks):
                    if int(chunk["index"]) != expected_index:
                        raise ValueError(f"Artifact chunk index gap: {artifact['id']}")
                    if int(chunk.get("offset", expected_offset)) != expected_offset:
                        raise ValueError(f"Artifact chunk offset mismatch: {artifact['id']}")
                    part = base64.b64decode(chunk["content_base64"], validate=True)
                    if len(part) != int(chunk["size"]):
                        raise ValueError(f"Artifact chunk size mismatch: {artifact['id']}")
                    if hashlib.sha256(part).hexdigest() != chunk["sha256"]:
                        raise ValueError(f"Artifact chunk hash mismatch: {artifact['id']}")
                    parts.append(part)
                    expected_offset += len(part)
                content = b"".join(parts)
            elif "content_ref" in artifact:
                if external_resolver is None:
                    raise ValueError(
                        f"External artifact requires an explicit resolver: {artifact['id']}"
                    )
                content = external_resolver(dict(artifact["content_ref"]))
            else:
                raise ValueError(f"Artifact content is missing: {artifact['id']}")
            digest = hashlib.sha256(content).hexdigest()
            if digest != artifact["sha256"]:
                raise ValueError(f"Artifact hash mismatch: {artifact['id']}")
            if len(content) != int(artifact["size"]):
                raise ValueError(f"Artifact size mismatch: {artifact['id']}")
            with self._connect() as db:
                exists = db.execute("SELECT 1 FROM artifacts WHERE id = ?", (artifact["id"],)).fetchone()
            self.add_artifact_bytes(
                str(artifact["session_id"]),
                str(artifact["name"]),
                content,
                str(artifact["mime_type"]),
                artifact_id=str(artifact["id"]),
                created_at=str(artifact["created_at"]),
                origin_node_id=source_node_id,
            )
            counts["artifacts"] += int(exists is None)
        return counts

    def export_to_file(self, path: str | Path, session_id: str | None = None) -> Path:
        """Write a complete portable bundle as human-inspectable UTF-8 JSON."""

        target = Path(path).expanduser().resolve()
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            json.dumps(self.export_bundle(session_id), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return target

    def import_from_file(self, path: str | Path) -> dict[str, int]:
        """Read and import a UTF-8 JSON bundle from disk."""

        source = Path(path).expanduser().resolve()
        return self.import_bundle(json.loads(source.read_text(encoding="utf-8")))
