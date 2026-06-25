"""End-to-end demo — runs fully offline, no API key required.

Takes a real sample security/compliance document, seeds a realistic failure (its
type-identifying header is stripped, so the pipeline misclassifies it), runs it through
the traced pipeline with a deterministic scripted model + judge, diagnoses the root
cause, and turns the confirmed failure into an eval case — printing each stage.

    uv run python -m forensics.demo

The trace is saved to ./traces and can be explored visually with:

    uv run streamlit run src/forensics/app/main.py
"""

from __future__ import annotations

from pathlib import Path

from .eval.dataset import eval_case_from
from .pipeline import steps
from .pipeline.failure_modes import FailureMode, apply_failures
from .pipeline.schemas import (
    ClassificationOutput,
    DocumentType,
    ExtractionOutput,
    SummaryOutput,
)
from .rca.judge import JudgeVerdict
from .rca.walk import diagnose
from .tracing.instrument import run_traced
from .tracing.store import TraceStore

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SAMPLE = _REPO_ROOT / "data" / "documents" / "access_control_policy.txt"


class _DemoLLM:
    """Deterministic pipeline model. Misclassifies the (header-stripped) policy as a
    risk register — a realistic, reproducible failure to diagnose."""

    def parse(self, *, model, system, document_text, schema, context=None, max_tokens=4096):
        if schema is ExtractionOutput:
            return ExtractionOutput(
                control_ids=["AC-2", "AC-3", "AC-6"],
                control_families=["Access Control"],
                owner="J. Okafor",
                review_date="2027-01-15",
                risk_ratings=["Low"],
                organizations=["Northwind Logistics"],
                confidence=4,
            )
        if schema is ClassificationOutput:
            return ClassificationOutput(
                doc_type=DocumentType.RISK_REGISTER,  # wrong: it is a policy
                rationale="Mentions risk ratings, so it looks like a risk register.",
                confidence=3,
            )
        return SummaryOutput(
            summary="A register of access-control risks for Northwind Logistics.",
            tags=["access-control", "risk"],
            confidence=4,
        )


class _DemoJudge:
    """Deterministic judge. Flags the misclassification as the quality drop."""

    def parse(self, *, model, system, document_text, schema, context=None, max_tokens=4096):
        if "STEP: classification" in str(document_text):
            return JudgeVerdict(
                quality=2,
                issues=["Classified risk_register; the content is an access-control policy."],
                rationale="The document states policy requirements; it is not a risk register.",
            )
        if "STEP: summarization" in str(document_text):
            return JudgeVerdict(
                quality=3,
                issues=["Summary inherits the wrong document type from classification."],
                rationale="Summary is reasonable but propagates the misclassification.",
            )
        return JudgeVerdict(quality=5, issues=[], rationale="Extraction is faithful to the input.")


def _rule(title: str) -> None:
    print(f"\n{'=' * 70}\n{title}\n{'=' * 70}")


def main() -> None:
    text = _SAMPLE.read_text(encoding="utf-8")
    document = apply_failures(
        steps.intake(doc_id="access_control_policy", source=str(_SAMPLE.name), text=text),
        [FailureMode.AMBIGUOUS_CATEGORY],  # strip the header → induces misclassification
    )

    _rule("1. Run the pipeline (traced)")
    store = TraceStore(root=_REPO_ROOT / "traces")
    trace, _ = run_traced(document, _DemoLLM(), store=store)
    print(f"trace_id: {trace.trace_id}")
    print(f"seeded failure modes: {trace.injected_failures}")
    for span in trace.spans:
        conf = f"confidence {span.confidence}/5" if span.confidence is not None else "—"
        print(f"  [{span.sequence}] {span.step_name:<14} {conf}")

    _rule("2. Diagnose the root cause (LLM-as-judge, scripted offline)")
    diagnosis = diagnose(trace, _DemoJudge())
    print(diagnosis.summary)
    print(f"category: {diagnosis.category.value}")
    print("evidence chain:")
    for link in diagnosis.evidence:
        print(f"  - {link.step_name} (quality {link.quality}/5): {link.note}")

    _rule("3. Turn the confirmed failure into an eval case")
    corrected = '{"doc_type": "policy"}'
    case = eval_case_from(trace, diagnosis, corrected_output=corrected)
    print(f"case_id: {case.case_id}")
    print(f"failing_step: {case.failing_step}")
    print(f"failure_category: {case.failure_category}")
    print(f"corrected_output: {case.corrected_output}")

    _rule("Done")
    print("Trace saved under ./traces/ — explore it visually with:")
    print("  uv run streamlit run src/forensics/app/main.py")


if __name__ == "__main__":
    main()
