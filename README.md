# Failure Forensics Tool for AI Pipelines

**An observability + root-cause layer for multi-step AI pipelines.** It traces every
intermediate step of an LLM pipeline, pinpoints exactly *where* a failure originated,
explains *how* it propagated, and turns each confirmed failure into a regression test.

> When a multi-step AI pipeline produces garbage, most teams have no idea which step broke.
> This is the tool that answers **"where did this go wrong?"** — reducing mean-time-to-root-cause
> for AI pipeline failures from hours of manual log-spelunking to seconds of automated diagnosis.

## Status

🚧 **In active development** — building in public. See [`PLAN.md`](./PLAN.md) for the full
15-day, phased implementation plan.

- [x] **Phase 0** — Secure repo foundation (CI gates, threat model, pinned deps)
- [x] **Phase 1** — Typed 4-step pipeline with injectable failures (mock-tested offline; live run needs `ANTHROPIC_API_KEY`)
- [x] **Phase 2** — Tracing layer: per-step spans (input/output/prompt/confidence/latency), SQLite+JSON store, **redaction-before-persistence** (tested: no secret reaches disk), path-traversal guard
- [x] **Phase 3** — Root-cause analysis: backward walk + LLM-as-judge (`claude-opus-4-8`) localizes the earliest quality drop, categorizes it (5-class taxonomy), and emits an evidence chain
- [ ] **Phase 4** — Visual trace explorer (Streamlit node graph + diff view)
- [ ] **Phase 5** — Feedback loop (confirmed failure → eval case → trend dashboard)
- [ ] **Phase 6** — Polish + demo

## Architecture (target)

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

## Tech stack

Python · [Streamlit](https://streamlit.io) · [Anthropic Claude](https://www.anthropic.com)
(official SDK, structured outputs) · [Pydantic](https://docs.pydantic.dev) · SQLite + JSON
traces · OpenTelemetry span vocabulary.

Models are chosen deliberately for cost/quality: `claude-haiku-4-5` for high-volume
extraction/classification, `claude-opus-4-8` for the low-volume, high-stakes LLM-as-judge.

## Security

This tool captures LLM prompts and outputs into a trace store — a sensitive data sink. Security
is designed in, not bolted on: redaction-before-persistence, a documented threat model, and a CI
gate (gitleaks, bandit, pip-audit, ruff) that every change must pass. See
[`SECURITY.md`](./SECURITY.md).

## Development

```bash
uv sync --extra dev          # install deps (pinned via uv.lock)
uvx pre-commit install       # enable local security/lint gate
uv run pytest                # run tests
uv run ruff check .          # lint
uv run bandit -c pyproject.toml -r src   # SAST
```

Copy `.env.example` to `.env` and set `ANTHROPIC_API_KEY` before running any LLM steps.

## License

MIT
