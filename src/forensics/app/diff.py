"""Pure diff logic for a single step: what it received, produced, and what the judge
says it should have produced.

Kept free of Streamlit so it is unit-testable offline.
"""

from __future__ import annotations

from typing import TypedDict

from ..rca.taxonomy import Diagnosis
from ..tracing.spans import Trace


class StepDiff(TypedDict):
    step: str
    received: str | None
    produced: str | None
    issues: list[str]
    quality: int | None
    confidence: int | None


def step_diff(
    trace: Trace, step_name: str, diagnosis: Diagnosis | None = None
) -> StepDiff:
    """Return the received/produced content for ``step_name`` plus, if a diagnosis is
    given, the judge's issues (the "should have produced" signal) and quality."""
    span = next((s for s in trace.spans if s.step_name == step_name), None)
    if span is None:
        raise KeyError(step_name)

    issues: list[str] = []
    quality: int | None = None
    if diagnosis is not None:
        quality = diagnosis.step_quality.get(step_name)
        issues = [link.note for link in diagnosis.evidence if link.step_name == step_name]

    return StepDiff(
        step=step_name,
        received=span.step_input,
        produced=span.step_output,
        issues=issues,
        quality=quality,
        confidence=span.confidence,
    )
