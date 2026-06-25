"""Trace persistence: one JSON file per trace, indexed in SQLite.

Security properties enforced here:
- **Redaction before write** — every span's string content is passed through
  ``redaction.redact`` before anything touches disk.
- **Parameterized SQL only** — no query is built by string concatenation.
- **Path-traversal guard** — a trace id must match ``[A-Za-z0-9_-]+`` and the resolved
  file path must stay within the trace root, so a crafted id cannot escape the directory.
"""

from __future__ import annotations

import re
import sqlite3
from contextlib import closing
from pathlib import Path
from typing import TypedDict

from ..errors import TraceNotFoundError, UnsafeTracePathError
from ..obs import get_logger
from . import redaction
from .spans import Trace

_SAFE_ID = re.compile(r"^[A-Za-z0-9_-]+$")
_log = get_logger()


class TraceIndexRow(TypedDict):
    trace_id: str
    created_at: str
    doc_id: str
    source: str
    n_spans: int
    has_error: int


class TraceStore:
    """Stores traces as redacted JSON files with a SQLite index."""

    def __init__(self, root: str | Path = "traces") -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.db_path = self.root / "index.db"
        self._init_db()

    def _init_db(self) -> None:
        with closing(sqlite3.connect(self.db_path)) as conn, conn:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS traces ("
                "trace_id TEXT PRIMARY KEY, created_at TEXT, doc_id TEXT, "
                "source TEXT, n_spans INTEGER, has_error INTEGER, path TEXT)"
            )

    def _safe_path(self, trace_id: str) -> Path:
        if not _SAFE_ID.match(trace_id):
            raise UnsafeTracePathError(f"unsafe trace id: {trace_id!r}")
        path = (self.root / f"{trace_id}.json").resolve()
        if self.root.resolve() not in path.parents:
            raise UnsafeTracePathError("resolved trace path escapes the trace root")
        return path

    def _redact_trace(self, trace: Trace) -> Trace:
        spans = [
            span.model_copy(
                update={
                    "prompt": redaction.redact(span.prompt),
                    "step_input": redaction.redact(span.step_input),
                    "step_output": redaction.redact(span.step_output),
                    "error": redaction.redact(span.error),
                }
            )
            for span in trace.spans
        ]
        return trace.model_copy(update={"spans": spans})

    def save(self, trace: Trace) -> Path:
        """Redact, then write the trace JSON and upsert its index row."""
        redacted = self._redact_trace(trace)
        path = self._safe_path(redacted.trace_id)
        path.write_text(redacted.model_dump_json(indent=2), encoding="utf-8")
        with closing(sqlite3.connect(self.db_path)) as conn, conn:
            conn.execute(
                "INSERT OR REPLACE INTO traces "
                "(trace_id, created_at, doc_id, source, n_spans, has_error, path) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    redacted.trace_id,
                    redacted.created_at,
                    redacted.doc_id,
                    redacted.source,
                    len(redacted.spans),
                    int(redacted.has_error),
                    str(path),
                ),
            )
        # Safe metadata only — never the prompts/outputs (those stay in the redacted file).
        _log.info(
            "trace saved trace_id=%s doc_id=%s spans=%d has_error=%s",
            redacted.trace_id, redacted.doc_id, len(redacted.spans), redacted.has_error,
        )
        return path

    def get(self, trace_id: str) -> Trace:
        path = self._safe_path(trace_id)
        if not path.exists():
            raise TraceNotFoundError(trace_id)
        return Trace.model_validate_json(path.read_text(encoding="utf-8"))

    def list_traces(self) -> list[TraceIndexRow]:
        with closing(sqlite3.connect(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT trace_id, created_at, doc_id, source, n_spans, has_error "
                "FROM traces ORDER BY created_at DESC"
            ).fetchall()
        return [
            TraceIndexRow(
                trace_id=row["trace_id"],
                created_at=row["created_at"],
                doc_id=row["doc_id"],
                source=row["source"],
                n_spans=row["n_spans"],
                has_error=row["has_error"],
            )
            for row in rows
        ]
