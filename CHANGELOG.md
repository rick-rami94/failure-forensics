# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] — 2026-06-25

First complete, production-ready release.

### Added
- **Pipeline** — typed 4-step document pipeline (intake → extraction → classification →
  summarization) with injectable failure modes and an injectable LLM interface.
- **Tracing** — per-step spans (input/output/prompt/confidence/latency/tokens), a
  SQLite-indexed JSON trace store, and redaction-before-persistence.
- **Root-cause analysis** — LLM-as-judge backward walk, a 5-class failure taxonomy, and
  an evidence chain.
- **Trace explorer** — Streamlit node graph (health colour-coded) and per-step diff view.
- **Feedback loop** — confirmed failures become eval cases; a runner re-runs the dataset
  to track resolution, with dashboard stats.
- **Production hardening** — env-driven configuration, structured logging that never logs
  secrets, custom exception types, a `forensics` CLI, token-usage capture on the live
  path, type checking (mypy), test coverage, a non-root Dockerfile, and Dependabot.
- **Security** — STRIDE-lite threat model, prompt/data separation, parameterized SQL,
  path-traversal guards, and a CI gate (gitleaks, bandit, pip-audit, ruff, pytest, mypy).
