"""Phase 3 tests — root-cause analysis, run fully offline with a scripted judge.

The scripted judge returns a configured quality per step (keyed off the STEP marker in
the payload), so the backward-walk and taxonomy logic is exercised with no real LLM.
"""

from __future__ import annotations

from forensics.rca.judge import JudgeVerdict
from forensics.rca.taxonomy import FailureCategory
from forensics.rca.walk import diagnose
from forensics.tracing.instrument import run_traced
from forensics.tracing.spans import Span, Trace

_STEPS = ("extraction", "classification", "summarization")


class ScriptedJudge:
    """A judge LLMClient that scores each step from a configured map."""

    def __init__(self, qualities: dict[str, int], issues: dict[str, list[str]] | None = None):
        self._qualities = qualities
        self._issues = issues or {}

    def parse(self, *, model, system, document_text, schema, context=None, max_tokens=4096):
        step = next((s for s in _STEPS if f"STEP: {s}" in str(document_text)), "unknown")
        return JudgeVerdict(
            quality=self._qualities.get(step, 5),
            issues=self._issues.get(step, []),
            rationale=f"scored {step}",
        )


def _trace(scripted_llm, sample_document) -> Trace:
    trace, _ = run_traced(sample_document, scripted_llm)
    return trace


def test_diagnose_finds_earliest_low_quality_step(scripted_llm, sample_document) -> None:
    trace = _trace(scripted_llm, sample_document)
    # Extraction is bad; everything downstream inherits it.
    judge = ScriptedJudge({"extraction": 2, "classification": 2, "summarization": 2})

    diag = diagnose(trace, judge)

    assert diag.root_cause_step == "extraction"
    assert diag.category is FailureCategory.EXTRACTION_HALLUCINATION
    # Evidence chain runs from the root cause forward, showing propagation.
    assert [link.step_name for link in diag.evidence] == list(_STEPS)


def test_diagnose_clean_trace_reports_none(scripted_llm, sample_document) -> None:
    trace = _trace(scripted_llm, sample_document)
    judge = ScriptedJudge({"extraction": 5, "classification": 5, "summarization": 4})

    diag = diagnose(trace, judge)

    assert diag.root_cause_step is None
    assert diag.category is FailureCategory.NONE


def test_diagnose_categorizes_context_loss(scripted_llm, sample_document) -> None:
    trace = _trace(scripted_llm, sample_document)
    # Extraction is fine; classification drops and the judge says context was lost.
    judge = ScriptedJudge(
        {"extraction": 5, "classification": 2, "summarization": 5},
        issues={"classification": ["missing context from extraction"]},
    )

    diag = diagnose(trace, judge)

    assert diag.root_cause_step == "classification"
    assert diag.category is FailureCategory.CONTEXT_LOSS


def test_diagnose_error_span_is_prompt_failure() -> None:
    # A trace whose step raised: diagnosis should flag it without invoking the judge.
    spans = [
        Span(
            span_id="s0", trace_id="t1", sequence=0, step_name="extraction",
            error="ValueError: boom", started_at="t", ended_at="t",
        )
    ]
    trace = Trace(trace_id="t1", created_at="t", doc_id="d", source="s", spans=spans)

    class Boom:
        def parse(self, **kwargs):  # must never be called
            raise AssertionError("judge should not run when a step errored")

    diag = diagnose(trace, Boom())

    assert diag.root_cause_step == "extraction"
    assert diag.category is FailureCategory.PROMPT_FAILURE
