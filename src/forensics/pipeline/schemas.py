"""Typed I/O contracts for every pipeline step.

Each step is an isolated function with a Pydantic input and output, so a malformed
hand-off between steps fails loudly at the boundary instead of silently propagating.
The LLM-produced schemas carry a self-reported ``confidence`` (1-5) that the tracing
layer (Phase 2) records per span.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class DocumentType(StrEnum):
    """Security/compliance document categories the pipeline classifies into."""

    POLICY = "policy"
    AUDIT_FINDING = "audit_finding"
    RISK_REGISTER = "risk_register"
    CONTROL_ASSESSMENT = "control_assessment"
    INCIDENT_REPORT = "incident_report"
    UNKNOWN = "unknown"


class RawDocument(BaseModel):
    """Output of the Intake step: the raw document plus provenance.

    ``injected_failures`` records any failure modes seeded into this document for
    demos/testing, so a trace can later show the ground-truth fault.
    """

    doc_id: str
    source: str
    text: str
    injected_failures: list[str] = Field(default_factory=list)


class ExtractionOutput(BaseModel):
    """Structured entities pulled from a security/compliance document."""

    control_ids: list[str] = Field(
        default_factory=list,
        description="Control identifiers referenced, e.g. 'AC-2', 'AU-6'.",
    )
    control_families: list[str] = Field(
        default_factory=list,
        description="Control families, e.g. 'Access Control', 'Audit and Accountability'.",
    )
    owner: str | None = Field(
        default=None, description="Named accountable owner, if stated."
    )
    review_date: str | None = Field(
        default=None,
        description="Next review date in ISO-8601 (YYYY-MM-DD) if present, else null.",
    )
    risk_ratings: list[str] = Field(
        default_factory=list,
        description="Risk ratings mentioned, e.g. 'Low', 'High', 'Critical'.",
    )
    organizations: list[str] = Field(
        default_factory=list, description="Organizations or business units named."
    )
    confidence: int = Field(
        ge=1, le=5, description="Self-rated confidence in this extraction (1=low, 5=high)."
    )


class ClassificationOutput(BaseModel):
    """The document type the pipeline assigns, with a brief rationale."""

    doc_type: DocumentType
    rationale: str = Field(description="One sentence justifying the chosen type.")
    confidence: int = Field(
        ge=1, le=5, description="Self-rated confidence in this classification (1=low, 5=high)."
    )


class SummaryOutput(BaseModel):
    """A concise summary plus key tags."""

    summary: str = Field(description="2-3 sentence summary of the document.")
    tags: list[str] = Field(default_factory=list, description="Short topical tags.")
    confidence: int = Field(
        ge=1, le=5, description="Self-rated confidence in this summary (1=low, 5=high)."
    )


class PipelineResult(BaseModel):
    """The full result of running a document through all four steps."""

    document: RawDocument
    extraction: ExtractionOutput
    classification: ClassificationOutput
    summary: SummaryOutput
