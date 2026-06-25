"""Phase 1 tests — the typed pipeline, run fully offline with a scripted LLM.

No ANTHROPIC_API_KEY, no network. The scripted client records every call so we can
assert the security-critical invariant: the untrusted document never enters the system
prompt (prompt/data separation, the prompt-injection mitigation from SECURITY.md).
"""

from __future__ import annotations

from forensics.pipeline import steps
from forensics.pipeline.failure_modes import FailureMode, apply_failures
from forensics.pipeline.schemas import DocumentType, PipelineResult


def test_run_pipeline_returns_typed_result_offline(scripted_llm, sample_document) -> None:
    result = steps.run_pipeline(sample_document, scripted_llm)

    assert isinstance(result, PipelineResult)
    assert result.classification.doc_type is DocumentType.POLICY
    assert "AC-2" in result.extraction.control_ids
    # One LLM call per LLM-backed step (extract, classify, summarize).
    assert len(scripted_llm.calls) == 3


def test_document_text_never_enters_system_prompt(scripted_llm, sample_document) -> None:
    """Security invariant: the untrusted document is data, never instructions."""
    steps.run_pipeline(sample_document, scripted_llm)

    for call in scripted_llm.calls:
        assert call["document_text"] == sample_document.text
        assert sample_document.text not in str(call["system"])
        # Upstream context (when present) is our own structured output, not the document.
        assert sample_document.text not in str(call["context"])


def test_prompt_injection_stays_in_data_channel(scripted_llm, sample_document) -> None:
    """A document that tries to hijack the model must only ever appear as document_text."""
    poisoned = apply_failures(sample_document, [FailureMode.PROMPT_INJECTION])
    steps.run_pipeline(poisoned, scripted_llm)

    needle = "IGNORE ALL PREVIOUS INSTRUCTIONS"
    assert any(needle in str(c["document_text"]) for c in scripted_llm.calls)
    for call in scripted_llm.calls:
        assert needle not in str(call["system"])
        assert needle not in str(call["context"])


def test_failure_modes_transform_text_and_record(sample_document) -> None:
    stripped = apply_failures(sample_document, [FailureMode.MISSING_REVIEW_DATE])
    assert "Next Review" not in stripped.text
    assert "missing_review_date" in stripped.injected_failures

    injected = apply_failures(sample_document, [FailureMode.PROMPT_INJECTION])
    assert "IGNORE ALL PREVIOUS INSTRUCTIONS" in injected.text
    assert "prompt_injection" in injected.injected_failures

    # Original document is unchanged (failures return a copy).
    assert "Next Review" in sample_document.text
    assert sample_document.injected_failures == []
