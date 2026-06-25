"""Phase 4 tests — the trace-explorer's pure logic (graph + diff), offline.

Streamlit itself is not imported here; only the testable functions are.
"""

from __future__ import annotations

import pytest

from forensics.app.diff import step_diff
from forensics.app.graph import HEALTHY, LOW_CONFIDENCE, ROOT_CAUSE, build_graph, health_for
from forensics.rca.taxonomy import Diagnosis, EvidenceLink, FailureCategory
from forensics.tracing.instrument import run_traced
from forensics.tracing.spans import Span


def _span(step: str, *, confidence=None, error=None) -> Span:
    return Span(
        span_id="x", trace_id="t", sequence=0, step_name=step,
        confidence=confidence, error=error, started_at="t", ended_at="t",
    )


def test_health_colour_rules() -> None:
    assert health_for(_span("extraction", confidence=5)) == HEALTHY
    assert health_for(_span("extraction", confidence=2)) == LOW_CONFIDENCE
    assert health_for(_span("extraction", error="boom")) == ROOT_CAUSE


def test_build_graph_orders_and_marks_root_cause(scripted_llm, sample_document) -> None:
    trace, _ = run_traced(sample_document, scripted_llm)
    diag = Diagnosis(
        trace_id=trace.trace_id,
        root_cause_step="classification",
        category=FailureCategory.MISCLASSIFICATION,
        summary="misclassified",
        step_quality={"extraction": 5, "classification": 2, "summarization": 4},
        evidence=[EvidenceLink(step_name="classification", quality=2, note="wrong type")],
    )

    graph = build_graph(trace, diag)

    assert [n["step"] for n in graph["nodes"]] == [
        "intake", "extraction", "classification", "summarization",
    ]
    health = {n["step"]: n["health"] for n in graph["nodes"]}
    assert health["classification"] == ROOT_CAUSE
    assert graph["edges"][0] == ("intake", "extraction")


def test_step_diff_exposes_received_produced_and_issues(scripted_llm, sample_document) -> None:
    trace, _ = run_traced(sample_document, scripted_llm)
    diag = Diagnosis(
        trace_id=trace.trace_id,
        root_cause_step="extraction",
        category=FailureCategory.EXTRACTION_HALLUCINATION,
        summary="hallucinated",
        step_quality={"extraction": 2},
        evidence=[EvidenceLink(step_name="extraction", quality=2, note="hallucinated control")],
    )

    detail = step_diff(trace, "extraction", diag)

    assert detail["received"] is not None
    assert detail["produced"] is not None
    assert "hallucinated control" in detail["issues"]
    assert detail["quality"] == 2


def test_step_diff_unknown_step_raises(scripted_llm, sample_document) -> None:
    trace, _ = run_traced(sample_document, scripted_llm)
    with pytest.raises(KeyError):
        step_diff(trace, "does-not-exist")
