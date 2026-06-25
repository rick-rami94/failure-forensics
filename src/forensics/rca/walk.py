"""Backward-walk root-cause analysis.

Starting from a flagged trace, grade each LLM step with the judge and find the *first*
step whose quality drops below the threshold — that earliest drop is the root cause,
since later steps consume its (already-wrong) output. The result is a structured
``Diagnosis`` with a per-step quality map and an evidence chain from the root cause
forward, showing how the fault propagated.
"""

from __future__ import annotations

from ..pipeline.llm import LLMClient
from ..tracing.spans import Trace
from .judge import JudgeVerdict, judge_step
from .taxonomy import Diagnosis, EvidenceLink, FailureCategory

# The LLM-backed steps, in pipeline order. The backward walk localizes the earliest of
# these whose quality drops.
_LLM_STEPS = ("extraction", "classification", "summarization")

_STEP_CATEGORY = {
    "extraction": FailureCategory.EXTRACTION_HALLUCINATION,
    "classification": FailureCategory.MISCLASSIFICATION,
    "summarization": FailureCategory.PROPAGATION_ERROR,
}


def _category_for(step_name: str, verdict: JudgeVerdict) -> FailureCategory:
    """Refine the category using the step and the judge's stated issues."""
    issues_text = " ".join(verdict.issues).lower()
    if any(word in issues_text for word in ("inject", "ignore instruction", "instructions")):
        return FailureCategory.PROMPT_FAILURE
    if step_name != "extraction" and any(
        word in issues_text for word in ("missing context", "lost", "dropped", "context")
    ):
        return FailureCategory.CONTEXT_LOSS
    return _STEP_CATEGORY.get(step_name, FailureCategory.PROPAGATION_ERROR)


def diagnose(trace: Trace, llm: LLMClient, threshold: int = 3) -> Diagnosis:
    """Localize and categorize the root cause of a trace's failure."""
    # A step that raised is itself the root cause — no judging needed.
    error_span = next((span for span in trace.spans if span.error), None)
    if error_span is not None:
        return Diagnosis(
            trace_id=trace.trace_id,
            root_cause_step=error_span.step_name,
            category=FailureCategory.PROMPT_FAILURE,
            summary=f"Step '{error_span.step_name}' raised an error: {error_span.error}",
            step_quality={},
            evidence=[
                EvidenceLink(
                    step_name=error_span.step_name,
                    quality=None,
                    note=error_span.error or "error",
                )
            ],
        )

    spans_by_step = {span.step_name: span for span in trace.spans}
    quality: dict[str, int] = {}
    verdicts: dict[str, JudgeVerdict] = {}
    for step in _LLM_STEPS:
        span = spans_by_step.get(step)
        if span is None:
            continue
        verdict = judge_step(step, span.step_input, span.step_output, llm)
        quality[step] = verdict.quality
        verdicts[step] = verdict

    root = next((s for s in _LLM_STEPS if s in quality and quality[s] < threshold), None)
    if root is None:
        return Diagnosis(
            trace_id=trace.trace_id,
            root_cause_step=None,
            category=FailureCategory.NONE,
            summary="No significant quality drop detected across pipeline steps.",
            step_quality=quality,
            evidence=[
                EvidenceLink(step_name=s, quality=quality[s], note="within threshold")
                for s in quality
            ],
        )

    category = _category_for(root, verdicts[root])
    evidence: list[EvidenceLink] = []
    started = False
    for step in _LLM_STEPS:
        if step == root:
            started = True
        if started and step in verdicts:
            verdict = verdicts[step]
            note = verdict.issues[0] if verdict.issues else verdict.rationale
            evidence.append(EvidenceLink(step_name=step, quality=verdict.quality, note=note))

    summary = (
        f"Root cause: '{root}' (quality {quality[root]}/5, {category.value}) — "
        f"{verdicts[root].rationale}"
    )
    return Diagnosis(
        trace_id=trace.trace_id,
        root_cause_step=root,
        category=category,
        summary=summary,
        step_quality=quality,
        evidence=evidence,
    )
