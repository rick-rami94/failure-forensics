"""Command-line entrypoint — run a document through the traced pipeline.

    forensics path/to/document.txt --diagnose

Browsing/tracing needs no key; ``--diagnose`` and the pipeline's live LLM calls require
ANTHROPIC_API_KEY. Configuration comes from the environment (see ``config.Settings``).
"""

from __future__ import annotations

import argparse
from pathlib import Path

from .config import load_settings
from .obs import configure_logging
from .pipeline import steps
from .pipeline.llm import get_client
from .rca.walk import diagnose
from .tracing.instrument import run_traced
from .tracing.store import TraceStore


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="forensics",
        description="Trace and diagnose a multi-step AI document pipeline run.",
    )
    parser.add_argument("document", help="Path to a document to run through the pipeline.")
    parser.add_argument(
        "--diagnose", action="store_true", help="Run root-cause analysis on the trace."
    )
    parser.add_argument(
        "--trace-dir", default=None, help="Where to write traces (overrides config)."
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    settings = load_settings()
    configure_logging(settings.log_level)

    path = Path(args.document)
    text = path.read_text(encoding="utf-8")
    document = steps.intake(doc_id=path.stem, source=path.name, text=text)

    store = TraceStore(root=args.trace_dir or settings.trace_dir)
    client = get_client()
    trace, _ = run_traced(document, client, store=store)
    print(f"trace_id: {trace.trace_id}")
    print(f"spans: {[span.step_name for span in trace.spans]}")

    if args.diagnose:
        diagnosis = diagnose(trace, client, threshold=settings.rca_threshold)
        print(f"category: {diagnosis.category.value}")
        print(diagnosis.summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
