"""Span and Trace schemas — the structured record of one pipeline run.

A Trace is a unique run; it holds one Span per step. Each span captures the step's
input, output, the LLM prompt and self-reported confidence, latency, and any error.
String content in a span is redacted before it is persisted (see ``store.TraceStore``).
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class Span(BaseModel):
    """One step of one pipeline run."""

    span_id: str
    trace_id: str
    sequence: int
    step_name: str
    model: str | None = None
    prompt: str | None = None
    step_input: str | None = None
    step_output: str | None = None
    confidence: int | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    latency_ms: float = 0.0
    error: str | None = None
    started_at: str
    ended_at: str


class Trace(BaseModel):
    """A full pipeline run: ordered spans plus run-level metadata."""

    trace_id: str
    created_at: str
    doc_id: str
    source: str
    injected_failures: list[str] = Field(default_factory=list)
    spans: list[Span] = Field(default_factory=list)

    @property
    def has_error(self) -> bool:
        return any(span.error for span in self.spans)
