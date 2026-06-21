from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator, Protocol, Sequence

from .memory import utc_now


class RawMessageSource(Protocol):
    """Exact-ID lookup implemented by ``MemoryStore``."""

    def message(self, message_id: str) -> dict[str, Any]: ...


@dataclass(frozen=True)
class SummaryPolicy:
    """Host policy for derived memory.

    Long-term facts are off by default.  This prevents an uncertain model
    summary from quietly becoming durable truth.
    """

    max_summary_chars: int = 4096
    max_sources: int = 100
    max_facts: int = 32
    max_fact_chars: int = 512
    allow_long_term_facts: bool = False

    def __post_init__(self) -> None:
        if not 1 <= self.max_summary_chars <= 65536:
            raise ValueError("max_summary_chars must be between 1 and 65536")
        if not 1 <= self.max_sources <= 1000:
            raise ValueError("max_sources must be between 1 and 1000")
        if not 1 <= self.max_facts <= 256:
            raise ValueError("max_facts must be between 1 and 256")
        if not 1 <= self.max_fact_chars <= 4096:
            raise ValueError("max_fact_chars must be between 1 and 4096")


@dataclass(frozen=True)
class SummarySource:
    """Trace from a derived summary back to one immutable raw message."""

    message_id: str
    role: str
    created_at: str | None
    content_sha256: str


@dataclass(frozen=True)
class SummaryRecord:
    """Summary memory stored independently from the raw message log."""

    id: str
    session_id: str
    content: str
    sources: tuple[SummarySource, ...]
    long_term_facts: tuple[str, ...]
    created_at: str

    def as_context_summary(self):
        """Convert to the read-only form accepted by ``ContextBuilder``."""

        # Local import keeps persistence independent from prompt rendering.
        from .context import ContextSummary

        return ContextSummary(
            id=self.id,
            session_id=self.session_id,
            content=self.content,
            source_message_ids=tuple(source.message_id for source in self.sources),
        )


class SummaryStore:
    """Separate SQLite store for summaries and their provenance.

    The raw ``MemoryStore`` database is never modified.  A source snapshot keeps
    role, timestamp, and content hash so callers can detect missing or altered
    source messages during export or inspection.
    """

    def __init__(
        self,
        home: str | Path,
        raw_memory: RawMessageSource,
        policy: SummaryPolicy | None = None,
    ):
        root = Path(home).expanduser().resolve()
        root.mkdir(parents=True, exist_ok=True)
        self.db_path = root / "summaries.sqlite3"
        self.raw_memory = raw_memory
        self.policy = policy or SummaryPolicy()
        self._init_db()

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def _init_db(self) -> None:
        with self._connect() as db:
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS summaries (
                    id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    content TEXT NOT NULL,
                    long_term_facts_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_summaries_session_time
                    ON summaries(session_id, created_at);
                CREATE TABLE IF NOT EXISTS summary_sources (
                    summary_id TEXT NOT NULL,
                    position INTEGER NOT NULL,
                    message_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    created_at TEXT,
                    content_sha256 TEXT NOT NULL,
                    PRIMARY KEY(summary_id, position),
                    FOREIGN KEY(summary_id) REFERENCES summaries(id) ON DELETE CASCADE
                );
                """
            )

    def add(
        self,
        session_id: str,
        content: str,
        source_message_ids: Sequence[str],
        *,
        long_term_facts: Sequence[str] = (),
        summary_id: str | None = None,
        created_at: str | None = None,
    ) -> SummaryRecord:
        """Persist an explicit summary with immutable source fingerprints."""

        if not session_id.strip():
            raise ValueError("session_id must not be empty")
        if not content.strip():
            raise ValueError("summary content must not be empty")
        if len(content) > self.policy.max_summary_chars:
            raise ValueError("summary content exceeds policy limit")
        if not source_message_ids:
            raise ValueError("a summary must reference at least one raw message")
        if len(source_message_ids) > self.policy.max_sources:
            raise ValueError("summary source count exceeds policy limit")

        facts = tuple(str(fact).strip() for fact in long_term_facts if str(fact).strip())
        if facts and not self.policy.allow_long_term_facts:
            raise PermissionError("long-term fact generation is disabled by default")
        if len(facts) > self.policy.max_facts:
            raise ValueError("long-term fact count exceeds policy limit")
        if any(len(fact) > self.policy.max_fact_chars for fact in facts):
            raise ValueError("long-term fact content exceeds policy limit")

        sources: list[SummarySource] = []
        seen_ids: set[str] = set()
        for message_id in source_message_ids:
            if not message_id:
                raise ValueError("every summary source must have an immutable message ID")
            if message_id in seen_ids:
                raise ValueError("summary source message IDs must be unique")
            seen_ids.add(message_id)
            try:
                message = self.raw_memory.message(message_id)
            except KeyError as exc:
                raise ValueError(f"summary source does not exist: {message_id}") from exc
            if str(message["session_id"]) != session_id:
                raise PermissionError("summary source belongs to another session")
            raw_content = str(message["content"])
            sources.append(
                SummarySource(
                    message_id=message_id,
                    role=str(message["role"]),
                    created_at=str(message["created_at"]),
                    content_sha256=hashlib.sha256(raw_content.encode("utf-8")).hexdigest(),
                )
            )

        identifier = summary_id or str(uuid.uuid4())
        timestamp = created_at or utc_now()
        with self._connect() as db:
            db.execute(
                "INSERT INTO summaries(id, session_id, content, long_term_facts_json, created_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (identifier, session_id, content, json.dumps(facts, ensure_ascii=False), timestamp),
            )
            db.executemany(
                "INSERT INTO summary_sources(summary_id, position, message_id, role, created_at, content_sha256) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                [
                    (
                        identifier,
                        position,
                        source.message_id,
                        source.role,
                        source.created_at,
                        source.content_sha256,
                    )
                    for position, source in enumerate(sources)
                ],
            )
        return SummaryRecord(identifier, session_id, content, tuple(sources), facts, timestamp)

    def get(self, summary_id: str, *, verify_sources: bool = True) -> SummaryRecord:
        with self._connect() as db:
            row = db.execute(
                "SELECT id, session_id, content, long_term_facts_json, created_at "
                "FROM summaries WHERE id = ?",
                (summary_id,),
            ).fetchone()
            if row is None:
                raise KeyError(summary_id)
            source_rows = db.execute(
                "SELECT message_id, role, created_at, content_sha256 FROM summary_sources "
                "WHERE summary_id = ? ORDER BY position",
                (summary_id,),
            ).fetchall()
        record = SummaryRecord(
            id=str(row["id"]),
            session_id=str(row["session_id"]),
            content=str(row["content"]),
            sources=tuple(SummarySource(**dict(source)) for source in source_rows),
            long_term_facts=tuple(json.loads(str(row["long_term_facts_json"]))),
            created_at=str(row["created_at"]),
        )
        if verify_sources:
            self._verify_sources(record)
        return record

    def list(self, session_id: str) -> list[SummaryRecord]:
        with self._connect() as db:
            rows = db.execute(
                "SELECT id FROM summaries WHERE session_id = ? ORDER BY created_at, rowid",
                (session_id,),
            ).fetchall()
        return [self.get(str(row["id"])) for row in rows]

    def context_summary(self, summary_id: str):
        """Return a provenance-verified summary safe for explicit context use."""

        return self.get(summary_id, verify_sources=True).as_context_summary()

    def _verify_sources(self, record: SummaryRecord) -> None:
        """Reject missing, moved, or altered raw sources before reuse."""

        seen: set[str] = set()
        for source in record.sources:
            if source.message_id in seen:
                raise ValueError("summary contains duplicate source IDs")
            seen.add(source.message_id)
            try:
                message = self.raw_memory.message(source.message_id)
            except KeyError as exc:
                raise ValueError(
                    f"summary source no longer exists: {source.message_id}"
                ) from exc
            if str(message["session_id"]) != record.session_id:
                raise PermissionError("summary source belongs to another session")
            content_hash = hashlib.sha256(
                str(message["content"]).encode("utf-8")
            ).hexdigest()
            if content_hash != source.content_sha256:
                raise ValueError("summary source content hash no longer matches")
            if str(message["role"]) != source.role:
                raise ValueError("summary source role no longer matches")
