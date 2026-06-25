"""Phase 5 tests — the feedback loop (eval dataset + runner), run fully offline."""

from __future__ import annotations

from forensics.eval.dataset import EvalCase, EvalDataset, eval_case_from
from forensics.eval.runner import run_eval, summarize
from forensics.pipeline import steps
from forensics.rca.walk import diagnose
from forensics.tracing.instrument import run_traced

EMAIL = "owner" + "@example.com"  # assembled so no literal lands in the repo


def test_eval_case_from_captures_failure_and_redacts(scripted_llm, make_judge) -> None:
    document = steps.intake(doc_id="d1", source="t", text=f"Policy owned by {EMAIL}.")
    trace, _ = run_traced(document, scripted_llm)
    diag = diagnose(trace, make_judge({"extraction": 2}))

    case = eval_case_from(trace, diag, corrected_output="fixed")

    assert case.failing_step == "extraction"
    assert case.failure_category == "extraction_hallucination"
    assert case.corrected_output == "fixed"
    # PII from the document is redacted in the persisted case.
    assert EMAIL not in case.original_input
    assert "[REDACTED:EMAIL]" in case.original_input


def test_dataset_round_trip(tmp_path) -> None:
    dataset = EvalDataset()
    dataset.add(
        EvalCase(
            case_id="c1", created_at="2026-06-25T00:00:00+00:00", doc_id="d1",
            failing_step="extraction", failure_category="extraction_hallucination",
            original_input="text", last_output="{}",
        )
    )
    path = tmp_path / "eval" / "dataset.json"
    dataset.save(path)

    loaded = EvalDataset.load(path)
    assert len(loaded.cases) == 1
    assert loaded.cases[0].case_id == "c1"


def _dataset_with_failing_extraction() -> EvalDataset:
    return EvalDataset(
        cases=[
            EvalCase(
                case_id="c1", created_at="2026-06-25T00:00:00+00:00", doc_id="d1",
                failing_step="extraction", failure_category="extraction_hallucination",
                original_input="text", last_output="{}",
            )
        ]
    )


def test_run_eval_marks_case_resolved_when_fixed(scripted_llm, make_judge) -> None:
    dataset = _dataset_with_failing_extraction()
    # The judge now scores extraction well → the known failure is resolved.
    report = run_eval(dataset, scripted_llm, make_judge({"extraction": 5}))
    assert report.total == 1
    assert report.resolved == 1
    assert report.unresolved == 0


def test_run_eval_marks_case_unresolved_when_still_failing(scripted_llm, make_judge) -> None:
    dataset = _dataset_with_failing_extraction()
    report = run_eval(dataset, scripted_llm, make_judge({"extraction": 2}))
    assert report.resolved == 0
    assert report.unresolved == 1


def test_summarize_counts_by_category_step_and_date() -> None:
    dataset = EvalDataset(
        cases=[
            EvalCase(
                case_id="c1", created_at="2026-06-25T01:00:00+00:00", doc_id="d1",
                failing_step="extraction", failure_category="extraction_hallucination",
                original_input="x",
            ),
            EvalCase(
                case_id="c2", created_at="2026-06-25T02:00:00+00:00", doc_id="d2",
                failing_step="classification", failure_category="misclassification",
                original_input="y",
            ),
        ]
    )
    stats = summarize(dataset)
    assert stats["total"] == 2
    assert stats["by_category"]["extraction_hallucination"] == 1
    assert stats["by_failing_step"]["classification"] == 1
    assert stats["by_date"]["2026-06-25"] == 2
