# Failure Forensics Tool for AI Pipelines

[![CI](https://github.com/rick-rami94/failure-forensics/actions/workflows/ci.yml/badge.svg)](https://github.com/rick-rami94/failure-forensics/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/rick-rami94/failure-forensics/branch/main/graph/badge.svg)](https://codecov.io/gh/rick-rami94/failure-forensics)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](./LICENSE)
![Python](https://img.shields.io/badge/python-3.11%2B-blue)

**An observability + root-cause layer for multi-step AI pipelines.** It traces every
intermediate step of an LLM pipeline, pinpoints exactly *where* a failure originated,
explains *how* it propagated, and turns each confirmed failure into a regression test.

> When a multi-step AI pipeline produces garbage, most teams have no idea which step broke.
> This is the tool that answers **"where did this go wrong?"** — reducing mean-time-to-root-cause
> for AI pipeline failures from hours of manual log-spelunking to seconds of automated diagnosis.

## Status — complete (built in public)

- [x] **Phase 0** — Secure repo foundation (CI gates, threat model, pinned deps)
- [x] **Phase 1** — Typed 4-step pipeline with injectable failures
- [x] **Phase 2** — Tracing layer (per-step spans, self-reported confidence, **redaction**)
- [x] **Phase 3** — Root-cause analysis (backward walk + LLM-as-judge + failure taxonomy)
- [x] **Phase 4** — Visual trace explorer (Streamlit node graph + diff view)
- [x] **Phase 5** — Feedback loop (confirmed failure → eval case → trend dashboard)
- [x] **Phase 6** — Polish + runnable demo

Everything runs and is tested **fully offline** (no API key, no network); a key is only
needed to drive the pipeline and judge against live Claude models.

## Quickstart

```bash
uv sync --extra dev                         # install (deps pinned via uv.lock)
uv run python -m forensics.demo             # offline end-to-end demo — no API key needed
uv run streamlit run src/forensics/app/main.py   # explore traces visually
```

The demo takes a sample security/compliance document, seeds a realistic failure (its
type-identifying header is stripped, inducing a misclassification), traces it, diagnoses
the root cause, and turns the failure into an eval case:

```
2. Diagnose the root cause (LLM-as-judge, scripted offline)
======================================================================
Root cause: 'classification' (quality 2/5, misclassification) — The document
states policy requirements; it is not a risk register.
category: misclassification
evidence chain:
  - classification (quality 2/5): Classified risk_register; the content is an access-control policy.
  - summarization (quality 3/5): Summary inherits the wrong document type from classification.
```

Full output: [`examples/sample_run.txt`](./examples/sample_run.txt).

## How it works

```
documents ─▶ Intake ─▶ Extraction ─▶ Classification ─▶ Summarization ─▶ output
                 │           │              │                │
                 └───────────┴──────────────┴────────────────┘
                           one span per step  →  trace store (SQLite + JSON)
                                                        │
                                       ┌────────────────┴────────────────┐
                                  Root-cause analysis            Visual trace explorer
                                  (backward walk +               (node graph, diff view)
                                   LLM-as-judge)                          │
                                          │                              │
                                          └────────▶ Feedback loop ◀─────┘
                                              (confirmed failure → eval case)
```

1. **Pipeline** — four isolated steps with Pydantic-typed I/O. Each LLM output carries a
   self-reported confidence (1–5). Downstream steps consume upstream *structured* output
   as trusted context, while the raw document is always passed as untrusted data.
2. **Tracing** — every run is a trace of one span per step (input, output, prompt,
   confidence, latency, errors), stored as JSON indexed in SQLite.
3. **Root-cause analysis** — an LLM-as-judge grades each step; the earliest quality drop
   is the root cause, categorized into a 5-class taxonomy with an evidence chain.
4. **Explorer** — a Streamlit node graph colour-codes step health and shows a
   received-vs-produced diff per step.
5. **Feedback loop** — confirmed failures become eval cases; re-running the dataset tracks
   whether known failures get resolved over time.

## Tech stack

Python · [Streamlit](https://streamlit.io) · [Anthropic Claude](https://www.anthropic.com)
(official SDK, structured outputs) · [Pydantic](https://docs.pydantic.dev) · SQLite + JSON
traces · OpenTelemetry span vocabulary.

Models are chosen deliberately for cost/quality: `claude-haiku-4-5` for high-volume
extraction/classification, `claude-opus-4-8` for the low-volume, high-stakes LLM-as-judge.

## Security

This tool captures LLM prompts and outputs into a trace store — a sensitive data sink.
Security is designed in, not bolted on:

- **Redaction before persistence** — secrets/PII are scrubbed from span content before it
  touches disk; `tests/test_redaction.py` proves no planted secret ever reaches a file.
- **Prompt/data separation** — the untrusted document never enters the system prompt
  (prompt-injection mitigation), enforced by the LLM interface and verified in tests.
- **Hardened storage** — parameterized SQL and a path-traversal guard on trace IDs.
- **CI gate** every change must pass — gitleaks, bandit (SAST), pip-audit, ruff, pytest.

See [`SECURITY.md`](./SECURITY.md) for the full STRIDE-lite threat model.

## Project layout

```
src/forensics/
  pipeline/   typed 4-step pipeline, injectable failures, LLM interface
  tracing/    span/trace schemas, redaction, SQLite+JSON store, instrumentation
  rca/        LLM-as-judge, backward-walk diagnosis, failure taxonomy
  eval/       confirmed-failure dataset + regression runner + dashboard stats
  app/        Streamlit trace explorer (pure graph/diff logic + thin shell)
  demo.py     offline end-to-end demo
data/documents/   synthetic security/compliance samples (no real PII)
tests/            offline test suite (no API key required)
```

## Development

```bash
uv run pytest                              # tests (offline, no key)
uv run ruff check .                        # lint
uv run bandit -c pyproject.toml -r src     # SAST
uvx pre-commit install                     # enable the local security/lint gate
```

Copy `.env.example` to `.env` and set `ANTHROPIC_API_KEY` to run against live models.

## License

MIT
