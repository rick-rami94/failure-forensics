"""Eval cases derived from confirmed failures, and their on-disk dataset.

Every confirmed failure becomes a regression test: the original input, the failing step,
the last (bad) output, an optional corrected output, and the failure category. Case
content is redacted (it originates from documents), so the dataset is safe to persist.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel, Field

from ..rca.taxonomy import Diagnosis
from ..tracing import redaction
from ..tracing.spans import Trace


class EvalCase(BaseModel):
    """One regression case generated from a confirmed failure."""

    case_id: str
    created_at: str
    doc_id: str
    failing_step: str | None
    failure_category: str
    original_input: str
    last_output: str | None = None
    corrected_output: str | None = None


class EvalDataset(BaseModel):
    """A collection of eval cases with JSON persistence."""

    cases: list[EvalCase] = Field(default_factory=list)

    def add(self, case: EvalCase) -> None:
        self.cases.append(case)

    def save(self, path: str | Path) -> None:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_text(self.model_dump_json(indent=2), encoding="utf-8")

    @classmethod
    def load(cls, path: str | Path) -> EvalDataset:
        file = Path(path)
        if not file.exists():
            return cls()
        return cls.model_validate_json(file.read_text(encoding="utf-8"))


def eval_case_from(
    trace: Trace, diagnosis: Diagnosis, corrected_output: str | None = None
) -> EvalCase:
    """Build an eval case from a diagnosed trace. Content is redacted defensively,
    regardless of whether the trace came from the store (already redacted) or memory."""
    intake_span = next((s for s in trace.spans if s.step_name == "intake"), None)
    original_input = intake_span.step_output if intake_span else ""

    failing_step = diagnosis.root_cause_step
    last_span = None
    if failing_step is not None:
        last_span = next((s for s in trace.spans if s.step_name == failing_step), None)
    if last_span is None:
        last_span = next((s for s in reversed(trace.spans) if s.step_output), None)

    return EvalCase(
        case_id=uuid.uuid4().hex,
        created_at=datetime.now(UTC).isoformat(),
        doc_id=trace.doc_id,
        failing_step=failing_step,
        failure_category=diagnosis.category.value,
        original_input=redaction.redact(original_input) or "",
        last_output=redaction.redact(last_span.step_output) if last_span else None,
        corrected_output=corrected_output,
    )
