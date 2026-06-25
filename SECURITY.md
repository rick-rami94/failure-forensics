# Security Policy

## Why this project takes security seriously

Failure Forensics is an observability tool that **deliberately captures the inputs and
outputs of LLM calls** — prompts, raw model responses, and the documents being processed —
and persists them as trace data. That makes the trace store a **sensitive data sink**:
anything sensitive in an input document (PII, secrets, credentials) can flow into a span
unless it is scrubbed first. Security is therefore treated as a core design concern, not an
add-on. This document records the threat model and the controls that mitigate it.

## Responsible disclosure

This is a personal portfolio project, not a production service. If you find a security issue,
please open a GitHub issue describing it (omit any real secret or exploit payload), or contact
the maintainer directly. There is no bounty; thoughtful reports are appreciated.

## Secure development process

Every change passes the same gate locally (pre-commit) and in CI:

| Control | Tool | Catches |
|---|---|---|
| Secret scanning | gitleaks | API keys / credentials committed to git |
| Static analysis (SAST) | bandit | Insecure Python (`eval`, `shell=True`, weak crypto, etc.) |
| Lint | ruff | Bugs, unsafe patterns, dead code |
| Dependency audit | pip-audit | Known CVEs in the dependency graph |
| Pinned dependencies | uv.lock | Supply-chain reproducibility |
| Private-key detection | pre-commit-hooks | Accidentally staged private keys |

Secrets are supplied only via environment variables (`ANTHROPIC_API_KEY`); `.env` is
gitignored and `.env.example` documents the shape without a real value. The API key is never
logged and never written into a trace span.

## Threat model (STRIDE-lite)

| Threat | Vector | Mitigation | Status |
|---|---|---|---|
| Information disclosure | Secrets / PII captured in trace spans | Redaction scrubs prompts & outputs **before** persistence; covered by `test_redaction.py` | Phase 2 |
| Tampering / injection | A malicious input document tries to steer the extraction or judge LLM (prompt injection) | System prompts are kept separate from document content; document text is treated as data, never as instructions | Phase 1/3 |
| Injection | SQL injection via trace IDs or query filters | All SQL is parameterized; no string-built queries | Phase 2 |
| Tampering | Path traversal via a crafted trace ID used in a filename | Trace paths are canonicalized and asserted to remain within the `traces/` root | Phase 2 |
| Supply chain | A compromised or vulnerable dependency | Pinned `uv.lock` + `pip-audit` in CI | Phase 0 |
| Credential leak | API key in code, logs, or trace data | `.env`-only; gitleaks gate; key excluded from all logging and spans | Phase 0 |
| Disclosure (UI) | Rendering untrusted model output in the web UI | No `unsafe_allow_html` on model-derived strings; file access scoped to `traces/` | Phase 4 |

Status reflects the phase in which the mitigation is implemented (see `PLAN.md`). Controls are
verified by tests where feasible — notably `test_redaction.py`, whose job is to prove that no
secret reaches disk.

## Scope and limitations

- Synthetic, non-real sample data only. No production or personal data is committed.
- The redaction layer is pattern-based and best-effort; it is a defense-in-depth control, not
  a guarantee. Do not point this tool at genuinely sensitive corpora without review.
