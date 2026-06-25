"""Failure taxonomy and the diagnosis structure produced by root-cause analysis."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class FailureCategory(StrEnum):
    """How a pipeline failure is categorized once localized."""

    NONE = "none"
    EXTRACTION_HALLUCINATION = "extraction_hallucination"
    MISCLASSIFICATION = "misclassification"
    PROPAGATION_ERROR = "propagation_error"
    PROMPT_FAILURE = "prompt_failure"
    CONTEXT_LOSS = "context_loss"


class EvidenceLink(BaseModel):
    """One link in the evidence chain explaining how the failure propagated."""

    step_name: str
    quality: int | None
    note: str


class Diagnosis(BaseModel):
    """The result of root-cause analysis over a single trace."""

    trace_id: str
    root_cause_step: str | None
    category: FailureCategory
    summary: str
    step_quality: dict[str, int] = Field(default_factory=dict)
    evidence: list[EvidenceLink] = Field(default_factory=list)
