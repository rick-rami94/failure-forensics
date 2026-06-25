"""Run the pipeline with full tracing.

``run_traced`` wraps the LLM client in a ``RecordingLLM`` that times each call and
captures its prompt, output, and self-reported confidence, then assembles one
``Span`` per step into a ``Trace``. If a step raises, the failure is recorded as an
error span rather than silently swallowed — the whole point of the tool is to capture
failures, not hide them.
"""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from ..pipeline.llm import DEFAULT_MAX_TOKENS, LLMClient
from ..pipeline.schemas import (
    ClassificationOutput,
    ExtractionOutput,
    PipelineResult,
    RawDocument,
)
from ..pipeline.steps import classify, extract, summarize
from .spans import Span, Trace
from .store import TraceStore


def _now() -> str:
    return datetime.now(UTC).isoformat()


@dataclass
class _Record:
    model: str
    prompt: str
    output_json: str
    confidence: int | None
    latency_ms: float
    input_tokens: int | None = None
    output_tokens: int | None = None


class RecordingLLM:
    """Wraps an ``LLMClient``, recording each call for trace assembly."""

    def __init__(self, inner: LLMClient) -> None:
        self._inner = inner
        self.records: list[_Record] = []

    def parse(
        self, *, model, system, document_text, schema, context=None, max_tokens=DEFAULT_MAX_TOKENS
    ):
        # The recorded prompt is instructions + trusted upstream context only; the
        # untrusted document travels separately and is redacted at persistence time.
        prompt = system if context is None else f"{system}\n\n[upstream context]\n{context}"
        start = time.perf_counter()
        result = self._inner.parse(
            model=model,
            system=system,
            document_text=document_text,
            schema=schema,
            context=context,
            max_tokens=max_tokens,
        )
        latency_ms = (time.perf_counter() - start) * 1000.0
        # Token usage is available on the live client; the offline mock has none.
        usage = getattr(self._inner, "last_usage", None)
        self.records.append(
            _Record(
                model=model,
                prompt=prompt,
                output_json=result.model_dump_json(),
                confidence=getattr(result, "confidence", None),
                latency_ms=latency_ms,
                input_tokens=getattr(usage, "input_tokens", None),
                output_tokens=getattr(usage, "output_tokens", None),
            )
        )
        return result


def _span(
    trace_id: str,
    sequence: int,
    step_name: str,
    *,
    step_input: str | None,
    step_output: str | None,
    latency_ms: float,
    model: str | None = None,
    prompt: str | None = None,
    confidence: int | None = None,
    input_tokens: int | None = None,
    output_tokens: int | None = None,
    error: str | None = None,
) -> Span:
    timestamp = _now()
    return Span(
        span_id=uuid.uuid4().hex,
        trace_id=trace_id,
        sequence=sequence,
        step_name=step_name,
        model=model,
        prompt=prompt,
        step_input=step_input,
        step_output=step_output,
        confidence=confidence,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        latency_ms=latency_ms,
        error=error,
        started_at=timestamp,
        ended_at=timestamp,
    )


def run_traced(
    document: RawDocument,
    llm: LLMClient,
    store: TraceStore | None = None,
    trace_id: str | None = None,
) -> tuple[Trace, PipelineResult | None]:
    """Run the pipeline, building a Trace. Persists it if a store is given."""
    recorder = RecordingLLM(llm)
    trace_id = trace_id or uuid.uuid4().hex
    spans: list[Span] = [
        _span(
            trace_id, 0, "intake",
            step_input=document.source, step_output=document.text, latency_ms=0.0,
        )
    ]

    extraction: ExtractionOutput | None = None
    classification: ClassificationOutput | None = None
    summary = None
    try:
        extraction = extract(document, recorder)
        rec = recorder.records[-1]
        spans.append(
            _span(
                trace_id, 1, "extraction",
                step_input=document.text, step_output=rec.output_json,
                latency_ms=rec.latency_ms, model=rec.model, prompt=rec.prompt,
                confidence=rec.confidence,
                input_tokens=rec.input_tokens, output_tokens=rec.output_tokens,
            )
        )

        classification = classify(document, extraction, recorder)
        rec = recorder.records[-1]
        spans.append(
            _span(
                trace_id, 2, "classification",
                step_input=json.dumps(
                    {"document": document.text, "extraction": extraction.model_dump()}
                ),
                step_output=rec.output_json, latency_ms=rec.latency_ms,
                model=rec.model, prompt=rec.prompt, confidence=rec.confidence,
            )
        )

        summary = summarize(document, extraction, classification, recorder)
        rec = recorder.records[-1]
        spans.append(
            _span(
                trace_id, 3, "summarization",
                step_input=json.dumps(
                    {
                        "document": document.text,
                        "extraction": extraction.model_dump(),
                        "classification": classification.model_dump(),
                    }
                ),
                step_output=rec.output_json, latency_ms=rec.latency_ms,
                model=rec.model, prompt=rec.prompt, confidence=rec.confidence,
            )
        )
    except Exception as exc:  # tracing records failures rather than swallowing them
        spans.append(
            _span(
                trace_id, len(spans), "error",
                step_input=None, step_output=None, latency_ms=0.0,
                error=f"{type(exc).__name__}: {exc}",
            )
        )

    trace = Trace(
        trace_id=trace_id,
        created_at=_now(),
        doc_id=document.doc_id,
        source=document.source,
        injected_failures=list(document.injected_failures),
        spans=spans,
    )
    if store is not None:
        store.save(trace)

    result: PipelineResult | None = None
    if extraction is not None and classification is not None and summary is not None:
        result = PipelineResult(
            document=document,
            extraction=extraction,
            classification=classification,
            summary=summary,
        )
    return trace, result
