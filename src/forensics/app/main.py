"""Streamlit trace explorer — the thin UI shell over the pure logic in graph.py/diff.py.

Launch with:  uv run streamlit run src/forensics/app/main.py
(Generate a trace first with:  uv run python -m forensics.demo)

Root-cause analysis is gated on ANTHROPIC_API_KEY, since the judge makes a live LLM call;
everything else (browsing traces, the node graph, the diff view) works with no key.
"""

from __future__ import annotations

import os

import streamlit as st

from ..pipeline.llm import get_client
from ..rca.walk import diagnose
from ..tracing.store import TraceStore
from .diff import step_diff
from .graph import build_graph

_HEALTH_ICON = {"green": "🟢", "yellow": "🟡", "red": "🔴"}


def main() -> None:
    st.set_page_config(page_title="Failure Forensics", layout="wide")
    st.title("Failure Forensics — AI pipeline trace explorer")

    store = TraceStore()
    traces = store.list_traces()
    if not traces:
        st.info("No traces yet. Run `uv run python -m forensics.demo`, then reload.")
        return

    labels = {
        f"{row['trace_id'][:8]} · {row['doc_id']} · "
        f"{'error' if row['has_error'] else 'ok'}": row["trace_id"]
        for row in traces
    }
    choice = st.sidebar.selectbox("Trace", list(labels))
    trace = store.get(labels[choice])

    diagnosis = st.session_state.get(f"diag_{trace.trace_id}")
    has_key = bool(os.environ.get("ANTHROPIC_API_KEY"))
    if st.sidebar.button("Run root-cause analysis", disabled=not has_key):
        diagnosis = diagnose(trace, get_client())
        st.session_state[f"diag_{trace.trace_id}"] = diagnosis
    if not has_key:
        st.sidebar.caption("Set ANTHROPIC_API_KEY to enable live root-cause analysis.")

    graph = build_graph(trace, diagnosis)

    st.subheader("Pipeline")
    columns = st.columns(len(graph["nodes"]))
    for column, node in zip(columns, graph["nodes"], strict=False):
        with column:
            st.markdown(f"### {_HEALTH_ICON[node['health']]} {node['step']}")
            if node["confidence"] is not None:
                st.caption(f"confidence {node['confidence']}/5")
            if node["quality"] is not None:
                st.caption(f"judge quality {node['quality']}/5")
            st.caption(f"{node['latency_ms']} ms")

    if diagnosis is not None:
        st.subheader("Diagnosis")
        st.write(diagnosis.summary)
        st.write(f"Category: **{diagnosis.category.value}**")
        for link in diagnosis.evidence:
            st.write(f"- {link.step_name} (quality {link.quality}): {link.note}")

    st.subheader("Step detail")
    step = st.selectbox("Step", [node["step"] for node in graph["nodes"]])
    detail = step_diff(trace, step, diagnosis)
    left, right = st.columns(2)
    with left:
        st.caption("Received")
        st.code(detail["received"] or "")
    with right:
        st.caption("Produced")
        st.code(detail["produced"] or "")
    if detail["issues"]:
        st.caption("Judge issues (what it should have produced)")
        for issue in detail["issues"]:
            st.write(f"- {issue}")


if __name__ == "__main__":
    main()
