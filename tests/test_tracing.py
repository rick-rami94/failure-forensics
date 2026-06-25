"""Phase 2 tests — tracing assembly and the trace store, run fully offline.

Covers: a trace captures one span per step with confidence + latency; the store
round-trips a trace; and the path-traversal guard rejects unsafe trace ids.
"""

from __future__ import annotations

import pytest

from forensics.tracing.instrument import run_traced
from forensics.tracing.store import TraceStore


def test_trace_has_one_span_per_step(scripted_llm, sample_document) -> None:
    trace, result = run_traced(sample_document, scripted_llm)

    assert result is not None
    step_names = [span.step_name for span in trace.spans]
    assert step_names == ["intake", "extraction", "classification", "summarization"]
    assert not trace.has_error

    # LLM steps carry the model, a prompt, and a self-reported confidence (1-5).
    extraction_span = trace.spans[1]
    assert extraction_span.model is not None
    assert extraction_span.prompt is not None
    assert extraction_span.confidence == 4


def test_store_round_trip(scripted_llm, sample_document, tmp_path) -> None:
    store = TraceStore(root=tmp_path)
    trace, _ = run_traced(sample_document, scripted_llm, store=store)

    loaded = store.get(trace.trace_id)
    assert loaded.trace_id == trace.trace_id
    assert len(loaded.spans) == len(trace.spans)

    listed = store.list_traces()
    assert any(row["trace_id"] == trace.trace_id for row in listed)


def test_store_rejects_path_traversal(tmp_path) -> None:
    store = TraceStore(root=tmp_path)
    for bad_id in ["../etc/passwd", "a/b", "..", "with space"]:
        with pytest.raises(ValueError):
            store.get(bad_id)
