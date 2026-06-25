"""Shared test fixtures: a deterministic, offline LLM client and a sample document.

The scripted client returns canned outputs per schema and records every call, so the
whole pipeline runs with no ANTHROPIC_API_KEY and no network.
"""

from __future__ import annotations

import pytest

from forensics.pipeline import steps
from forensics.pipeline.schemas import (
    ClassificationOutput,
    DocumentType,
    ExtractionOutput,
    RawDocument,
    SummaryOutput,
)
from forensics.rca.judge import JudgeVerdict

_JUDGE_STEPS = ("extraction", "classification", "summarization")

SAMPLE_TEXT = (
    "Document Type: Policy\nNext Review: 2027-01-15\n"
    "Control AC-2 is reviewed quarterly. Residual risk: Low.\n"
)


class ScriptedLLM:
    """Deterministic LLMClient: canned output per schema, records each call."""

    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []
        self._responses = {
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


class ScriptedJudge:
    """A judge LLMClient that scores each step from a configured map (keyed off the
    STEP marker in the payload), so RCA/eval logic runs with no real LLM."""

    def __init__(self, qualities: dict[str, int], issues: dict[str, list[str]] | None = None):
        self._qualities = qualities
        self._issues = issues or {}

    def parse(self, *, model, system, document_text, schema, context=None, max_tokens=4096):
        step = next((s for s in _JUDGE_STEPS if f"STEP: {s}" in str(document_text)), "unknown")
        return JudgeVerdict(
            quality=self._qualities.get(step, 5),
            issues=self._issues.get(step, []),
            rationale=f"scored {step}",
        )


@pytest.fixture
def scripted_llm() -> ScriptedLLM:
    return ScriptedLLM()


@pytest.fixture
def make_judge():
    def _make(qualities, issues=None) -> ScriptedJudge:
        return ScriptedJudge(qualities, issues)

    return _make


@pytest.fixture
def sample_document() -> RawDocument:
    return steps.intake(doc_id="d1", source="test", text=SAMPLE_TEXT)
