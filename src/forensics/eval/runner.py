"""Re-run the eval dataset and summarize it for the dashboard.

Re-running periodically tracks whether known failures are now resolved by the current
pipeline + judge. ``summarize`` powers the dashboard: most common failure types, which
steps drop most, and failure rate over time.
"""

from __future__ import annotations

from collections import Counter

from pydantic import BaseModel, Field

from ..pipeline.llm import LLMClient
from ..pipeline.steps import intake
from ..rca.walk import diagnose
from ..tracing.instrument import run_traced
from .dataset import EvalDataset


class EvalResult(BaseModel):
    case_id: str
    resolved: bool
    detail: str


class EvalReport(BaseModel):
    total: int
    resolved: int
    unresolved: int
    results: list[EvalResult] = Field(default_factory=list)


def run_eval(
    dataset: EvalDataset,
    pipeline_llm: LLMClient,
    judge_llm: LLMClient,
    threshold: int = 3,
) -> EvalReport:
    """Re-run every case through the pipeline and re-diagnose; a case is resolved when
    its previously-failing step no longer falls below the quality threshold."""
    results: list[EvalResult] = []
    for case in dataset.cases:
        document = intake(doc_id=case.doc_id, source="eval", text=case.original_input)
        trace, _ = run_traced(document, pipeline_llm)
        diag = diagnose(trace, judge_llm, threshold=threshold)

        if case.failing_step is None:
            is_resolved = diag.category.value == "none"
        else:
            quality = diag.step_quality.get(case.failing_step)
            is_resolved = diag.root_cause_step != case.failing_step and (
                quality is None or quality >= threshold
            )
        results.append(
            EvalResult(case_id=case.case_id, resolved=is_resolved, detail=diag.summary)
        )

    resolved_count = sum(1 for result in results if result.resolved)
    return EvalReport(
        total=len(results),
        resolved=resolved_count,
        unresolved=len(results) - resolved_count,
        results=results,
    )


def summarize(dataset: EvalDataset) -> dict[str, object]:
    """Dashboard stats: counts by failure category, by failing step, and by date."""
    by_category = Counter(case.failure_category for case in dataset.cases)
    by_failing_step = Counter(case.failing_step or "none" for case in dataset.cases)
    by_date = Counter(case.created_at[:10] for case in dataset.cases if case.created_at)
    return {
        "total": len(dataset.cases),
        "by_category": dict(by_category),
        "by_failing_step": dict(by_failing_step),
        "by_date": dict(by_date),
    }
