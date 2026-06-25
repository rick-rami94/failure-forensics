"""Phase 1 tests — the typed pipeline, run fully offline with a scripted LLM.

No ANTHROPIC_API_KEY, no network. The scripted client records every call so we can
assert the security-critical invariant: the untrusted document never enters the system
prompt (prompt/data separation, the prompt-injection mitigation from SECURITY.md).
"""

from __future__ import annotations

from pydantic import BaseModel

from forensics.pipeline import steps
from forensics.pipeline.failure_modes import FailureMode, apply_failures
from forensics.pipeline.schemas import (
    ClassificationOutput,
    DocumentType,
    ExtractionOutput,
    PipelineResult,
    RawDocument,
    SummaryOutput,
)

SAMPLE_TEXT = (
    "Document Type: Policy\nNext Review: 2027-01-15\n"
    "Control AC-2 is reviewed quarterly. Residual risk: Low.\n"
)


class ScriptedLLM:
    """A deterministic LLMClient for tests. Returns a canned output per schema type and
    records each call's arguments for inspection."""

    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []
        self._responses: dict[type[BaseModel], BaseModel] = {
            ExtractionOutput: ExtractionOutput(
                control_ids=["AC-2"],
                control_families=["Access Control"],
                owner="J. Okafor",
                review_date="2027-01-15",
                risk_ratings=["Low"],
                organizations=["Northwind Logistics"],
                confidence=4,
            ),
            ClassificationOutput: ClassificationOutput(
                doc_type=DocumentType.POLICY, rationale="States requirements.", confidence=5
            ),
            SummaryOutput: SummaryOutput(
                summary="An access control policy.", tags=["access-control"], confidence=4
            ),
        }

    def parse(self, *, model, system, document_text, schema, context=None, max_tokens=4096):
        self.calls.append(
            {
                "model": model,
                "system": system,
                "document_text": document_text,
                "schema": schema,
                "context": context,
            }
        )
        return self._responses[schema]


def _doc() -> RawDocument:
    return steps.intake(doc_id="d1", source="test", text=SAMPLE_TEXT)


def test_run_pipeline_returns_typed_result_offline() -> None:
    llm = ScriptedLLM()
    result = steps.run_pipeline(_doc(), llm)

    assert isinstance(result, PipelineResult)
    assert result.classification.doc_type is DocumentType.POLICY
    assert "AC-2" in result.extraction.control_ids
    # One LLM call per LLM-backed step (extract, classify, summarize).
    assert len(llm.calls) == 3


def test_document_text_never_enters_system_prompt() -> None:
    """Security invariant: the untrusted document is data, never instructions."""
    llm = ScriptedLLM()
    steps.run_pipeline(_doc(), llm)

    for call in llm.calls:
        assert call["document_text"] == SAMPLE_TEXT
        assert SAMPLE_TEXT not in str(call["system"])
        # Upstream context (when present) is our own structured output, not the document.
        assert SAMPLE_TEXT not in str(call["context"])


def test_prompt_injection_stays_in_data_channel() -> None:
    """A document that tries to hijack the model must only ever appear as document_text."""
    poisoned = apply_failures(_doc(), [FailureMode.PROMPT_INJECTION])
    llm = ScriptedLLM()
    steps.run_pipeline(poisoned, llm)

    needle = "IGNORE ALL PREVIOUS INSTRUCTIONS"
    assert any(needle in str(c["document_text"]) for c in llm.calls)
    for call in llm.calls:
        assert needle not in str(call["system"])
        assert needle not in str(call["context"])


def test_failure_modes_transform_text_and_record() -> None:
    base = _doc()

    stripped = apply_failures(base, [FailureMode.MISSING_REVIEW_DATE])
    assert "Next Review" not in stripped.text
    assert "missing_review_date" in stripped.injected_failures

    injected = apply_failures(base, [FailureMode.PROMPT_INJECTION])
    assert "IGNORE ALL PREVIOUS INSTRUCTIONS" in injected.text
    assert "prompt_injection" in injected.injected_failures

    # Original document is unchanged (failures return a copy).
    assert "Next Review" in base.text
    assert base.injected_failures == []
