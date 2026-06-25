"""Pure graph-layout logic for the trace explorer.

Kept free of Streamlit so it is unit-testable offline. ``main.py`` renders what these
functions return. Typed return shapes keep the UI shell type-safe.
"""

from __future__ import annotations

from typing import TypedDict

from ..rca.taxonomy import Diagnosis
from ..tracing.spans import Span, Trace

HEALTHY = "green"
LOW_CONFIDENCE = "yellow"
ROOT_CAUSE = "red"


class GraphNode(TypedDict):
    step: str
    sequence: int
    health: str
    confidence: int | None
    quality: int | None
    latency_ms: float


class Graph(TypedDict):
    nodes: list[GraphNode]
    edges: list[tuple[str, str]]


def health_for(span: Span, diagnosis: Diagnosis | None = None) -> str:
    """Colour a node: red for the root cause / an errored step, yellow for low
    confidence, green otherwise."""
    if span.error:
        return ROOT_CAUSE
    if diagnosis is not None and span.step_name == diagnosis.root_cause_step:
        return ROOT_CAUSE
    if span.confidence is not None and span.confidence <= 3:
        return LOW_CONFIDENCE
    return HEALTHY


def build_graph(trace: Trace, diagnosis: Diagnosis | None = None) -> Graph:
    """Return nodes (in pipeline order, colour-coded) and the edges connecting them."""
    ordered = sorted(trace.spans, key=lambda span: span.sequence)
    nodes: list[GraphNode] = [
        GraphNode(
            step=span.step_name,
            sequence=span.sequence,
            health=health_for(span, diagnosis),
            confidence=span.confidence,
            quality=(
                diagnosis.step_quality.get(span.step_name) if diagnosis is not None else None
            ),
            latency_ms=round(span.latency_ms, 1),
        )
        for span in ordered
    ]
    edges: list[tuple[str, str]] = [
        (nodes[i]["step"], nodes[i + 1]["step"]) for i in range(len(nodes) - 1)
    ]
    return Graph(nodes=nodes, edges=edges)
