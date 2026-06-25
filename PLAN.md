# Failure Forensics Tool for AI Pipelines — Implementation Plan

> **Status:** Plan (no code yet). Awaiting approval before building.
> **Author:** Rick Ramirez · **Target:** Public portfolio repo under `rick-rami94`
> **Timeline:** 15 days · **Last updated:** 2026-06-24

---

## 1. What this is

An **observability + root-cause layer for multi-step AI pipelines**. It traces every
intermediate step of an LLM pipeline, pinpoints exactly *where* a failure originated,
explains *how* it propagated, and feeds confirmed failures back into a growing
evaluation dataset.

**The pitch (interview-ready):** *"When a multi-step AI pipeline produces garbage, most
teams have no idea which step broke. This is the tool that answers 'where did this go
wrong?' — and turns each answer into a regression test. It reduces mean-time-to-root-cause
for AI pipeline failures from hours of manual log-spelunking to seconds of automated
diagnosis."*

**Why it lands interviews:** articulating *why* observability matters for AI systems —
and demonstrating a security-aware engineering process around an LLM that ingests
untrusted data — is a senior-level signal. The security process (Section 4) is the
differentiator that plays to Rick's ISRM background.

---

## 2. Decisions locked in

| Decision | Choice | Rationale |
|---|---|---|
| Language | Python 3.11+ | Pydantic, OTel, data ecosystem |
| Visualization | **Streamlit** | Pure Python; spend the 15 days on forensics logic, not frontend plumbing |
| LLM provider | **Claude / Anthropic** | Official `anthropic` SDK; matches existing AI portfolio |
| Models | `claude-opus-4-8` for the LLM-as-judge; `claude-haiku-4-5` for extraction/classification | Demonstrates deliberate cost/quality model selection (a senior signal) |
| Structured output | `client.messages.parse()` + Pydantic | Guarantees typed, schema-valid extraction, classification, and judge verdicts |
| Trace storage | SQLite (index) + JSON files (full spans) | Matches spec; zero-infra; inspectable |
| Tracing | OpenTelemetry spans + a custom span attribute schema | Industry-standard vocabulary; shows transferable skill |
| Dep management | `uv` + `pyproject.toml`, fully pinned lockfile | Reproducible builds; clean `pip-audit` story |

---

## 3. Repository structure

```
failure-forensics/
├── README.md                 # pitch, architecture diagram, demo GIF, security section
├── SECURITY.md               # threat model + disclosure policy (Phase 0)
├── PLAN.md                   # this file
├── pyproject.toml            # deps, tool config (ruff, bandit, pytest)
├── uv.lock                   # pinned, audited dependency graph
├── .pre-commit-config.yaml   # gitleaks, ruff, bandit, end-of-file fixers
├── .env.example              # documents ANTHROPIC_API_KEY (never a real key)
├── .gitignore                # .env, *.db, traces/, __pycache__, .venv
├── .github/workflows/ci.yml  # lint + test + bandit + pip-audit + gitleaks gate
├── src/forensics/
│   ├── pipeline/             # Phase 1: the 4-step instrumented pipeline
│   │   ├── steps.py          #   intake → extract → classify → summarize (typed)
│   │   ├── schemas.py        #   Pydantic I/O contracts per step
│   │   ├── failure_modes.py  #   injectable realistic failures
│   │   └── llm.py            #   Anthropic client wrapper (retry, redaction)
│   ├── tracing/              # Phase 2: span capture + storage
│   │   ├── spans.py          #   Span schema (input/output/prompt/tokens/latency/confidence)
│   │   ├── store.py          #   SQLite index + JSON file writer (parameterized SQL)
│   │   └── redaction.py      #   secret/PII scrubbing BEFORE persistence
│   ├── rca/                  # Phase 3: root-cause analysis
│   │   ├── judge.py          #   LLM-as-judge quality scoring per step
│   │   ├── walk.py           #   backward walk → first significant quality drop
│   │   └── taxonomy.py       #   failure categories + evidence-chain builder
│   ├── eval/                 # Phase 5: feedback loop
│   │   ├── dataset.py        #   confirmed failure → eval case
│   │   └── runner.py         #   re-run eval set, track resolution over time
│   └── app/                  # Phase 4: Streamlit UI
│       ├── main.py           #   trace explorer entrypoint
│       ├── graph.py          #   node graph, health colour-coding
│       └── diff.py           #   received-vs-produced-vs-expected diff view
├── data/
│   ├── documents/            # sample input docs (synthetic, no real PII)
│   └── eval/                 # generated eval dataset (gitignored if it grows)
├── traces/                   # runtime trace JSON (gitignored)
└── tests/
    ├── test_pipeline.py
    ├── test_tracing.py
    ├── test_rca.py
    ├── test_eval.py
    └── test_redaction.py     # security-critical: prove secrets never persist
```

---

## 4. Security process (cross-cutting — the differentiator)

Security is **built into the workflow**, not bolted on. Two layers:

### 4a. Phase 0 — security foundation (set up before any feature code)

| Control | Tool | What it catches |
|---|---|---|
| Secret scanning (pre-commit + CI) | `gitleaks` | API keys committed to git |
| Static analysis (SAST) | `bandit` | Insecure Python patterns (eval, shell=True, weak crypto) |
| Lint / style | `ruff` | Bugs, unused imports, complexity |
| Dependency audit | `pip-audit` (CI) | Known CVEs in dependencies |
| Pinned deps | `uv.lock` | Supply-chain reproducibility |
| Secrets management | `.env` + `.env.example`, never committed | Keys via env var only; `anthropic.Anthropic()` reads `ANTHROPIC_API_KEY` |
| CI security gate | GitHub Actions | All of the above must pass before merge |

**`SECURITY.md`** ships in Phase 0 with: a responsible-disclosure policy and a
**STRIDE-lite threat model** for the pipeline (see 4c).

### 4b. Per-phase security checkpoints (woven into each phase)

This tool is unusual: **it deliberately captures LLM inputs and outputs** (prompts, raw
responses) into a trace store. That trace data is sensitive. Security can't be an
afterthought — it *is* a feature here. Each phase has an explicit checkpoint:

- **Phase 1 (pipeline):** Pydantic validates all step I/O at boundaries. The pipeline
  ingests *untrusted documents* → treat document text as hostile. Note prompt-injection
  surface (a malicious doc trying to steer the extraction LLM); document it, and keep
  system prompts separate from document content.
- **Phase 2 (tracing):** **Redaction before persistence.** Spans capture prompts +
  outputs, which may contain secrets/PII from input docs. `redaction.py` scrubs
  patterns (emails, keys, tokens) *before* anything hits disk. SQL is parameterized
  (no string-built queries). Trace files written to a fixed `traces/` root with
  path-traversal guards on any trace ID used in a filename.
- **Phase 3 (RCA):** The judge LLM also receives step I/O — same redaction path applies.
  No secrets in judge prompts.
- **Phase 4 (UI):** Streamlit renders trace content — escape/contain rendered model
  output; never `unsafe_allow_html` on untrusted strings. Read-only file access scoped
  to `traces/`.
- **Phase 5 (eval):** Eval cases derived from real traces inherit redaction. The eval
  dataset is treated as potentially sensitive and gitignored if it contains anything
  non-synthetic.

### 4c. Threat model (STRIDE-lite, drafted in Phase 0, refined per phase)

| Threat | Vector | Mitigation |
|---|---|---|
| Info disclosure | Secrets/PII captured in trace spans | `redaction.py` scrubs before persist; tested in `test_redaction.py` |
| Injection | Malicious document steers extraction LLM | System/user prompt separation; document treated as data, not instructions |
| Injection | SQL via trace IDs / filters | Parameterized queries only |
| Path traversal | Crafted trace ID → arbitrary file write/read | Canonicalize + assert within `traces/` root |
| Supply chain | Compromised dependency | Pinned `uv.lock` + `pip-audit` in CI |
| Credential leak | API key in code/logs/traces | `.env` only; gitleaks; never log raw key; key never enters spans |

> **Interview talking point:** "The tool captures model I/O for forensic analysis, which
> creates a data-sensitivity problem most observability demos ignore. I treated the trace
> store as a sensitive data sink and built redaction + a threat model around it."

---

## 5. Phased build (15 days)

Day ranges follow the source spec. Each phase ends with: tests green, CI green, an atomic
set of commits, and a one-line demo-able outcome.

### Phase 0 — Security & repo foundation (Day 1)
**Goal:** A secure, reproducible skeleton before any feature code.
- Init repo, `pyproject.toml`, `uv` env, pin deps.
- `.gitignore`, `.env.example`, `.pre-commit-config.yaml` (gitleaks, ruff, bandit).
- `.github/workflows/ci.yml`: lint + bandit + pip-audit + gitleaks + pytest.
- `SECURITY.md` with disclosure policy + initial threat model (4c).
- Anthropic client wrapper stub (`llm.py`) reading `ANTHROPIC_API_KEY` from env.
- **Deliverable:** green CI on an empty-but-secured repo.

### Phase 1 — Build the pipeline (Days 1–3)
**Goal:** A realistic 4-step document pipeline with typed I/O and injectable failures.
- Steps: **Intake** (raw document) → **Extraction** (LLM pulls structured entities,
  `claude-haiku-4-5` + `messages.parse()`) → **Classification** (document type) →
  **Summarization** (key tags/summary).
- Each step is an isolated function with **Pydantic** typed inputs and outputs.
- `failure_modes.py`: inject realistic failures — missing dates, ambiguous categories,
  currency mismatches — toggleable for demos.
- Synthetic sample documents in `data/documents/` (invoices, contracts, reports — no real PII).
- **Security checkpoint:** prompt/data separation; Pydantic boundary validation.
- **Deliverable:** run a document end-to-end; see structured output (and seeded failures).

### Phase 2 — Tracing layer (Days 3–6)
**Goal:** Capture a full, queryable trace for every pipeline run.
- Each run gets a unique **trace ID**; one **span per step**.
- Each span captures: input, output, LLM prompt, raw response, token count, latency,
  errors, and a **self-assigned confidence score (1–5)** the model gives its own output
  (via structured output).
- Store: spans as JSON files indexed in SQLite (parameterized queries).
- **Security checkpoint:** `redaction.py` scrubs secrets/PII before write; path-traversal
  guard on trace-ID filenames; `test_redaction.py` proves no secret reaches disk.
- **Deliverable:** run pipeline → inspect a complete trace with per-step spans + confidence.

### Phase 3 — Root-cause analysis (Days 6–9)
**Goal:** Given a flagged trace, identify and explain the root-cause step.
- Walk **backward** through spans (`walk.py`).
- **LLM-as-judge** (`judge.py`, `claude-opus-4-8` + adaptive thinking) scores each step's
  output quality given its input.
- First step with a **significant quality drop** = root cause.
- Categorize: **Extraction Hallucination, Misclassification, Propagation Error,
  Prompt Failure, Context Loss** (`taxonomy.py`).
- Produce a **structured evidence chain** explaining what broke and how it propagated.
- **Security checkpoint:** judge prompts go through redaction; judge is given data, not
  trusted instructions from documents.
- **Deliverable:** point at a bad trace → get a categorized root cause + evidence chain in seconds.

### Phase 4 — Visual trace explorer (Days 9–11)
**Goal:** A Streamlit UI that makes a trace legible at a glance.
- Pipeline as **nodes**, colour-coded by health: green (healthy), yellow (low confidence),
  red (root cause).
- Click a node → full span details.
- **Diff view:** what the step received vs. produced vs. should have produced.
- Drill-down trigger runs the backward analysis (Phase 3) and shows the diagnosis.
- **Security checkpoint:** no `unsafe_allow_html` on model output; file reads scoped to `traces/`.
- **Deliverable:** browse a trace visually; one click surfaces the diagnosis.

### Phase 5 — Feedback loop (Days 11–13)
**Goal:** Turn every confirmed failure into a regression test, and track resolution.
- Confirmed flag → auto-generates an **eval case**: original input, failing step, last
  output, corrected output, failure category (`dataset.py`).
- Periodically **re-run the full eval dataset** to track whether known failures are
  resolved over time (`runner.py`).
- Dashboard: most common failure types, which steps drop most, failure rate over time.
- **Security checkpoint:** eval cases inherit redaction; sensitive eval data gitignored.
- **Deliverable:** confirm a failure → it becomes an eval case → dashboard tracks the trend.

### Phase 6 — Polish & demo (Days 13–15)
**Goal:** A repo that reads as senior work and demos in under two minutes.
- Curate ~10 annotated failures of different categories.
- README: pitch, architecture diagram, security section, demo GIF.
- **Demo script:** bad output → open trace explorer → root cause diagnosed in seconds →
  show the auto-generated eval case → show the trend dashboard.
- Final CI/security pass; tag a release.
- **Deliverable:** public repo + demo GIF, ready to link from resume/LinkedIn.

---

## 6. Interview talking points (to rehearse)

1. **The "where did it break" problem** — why multi-step LLM pipelines are opaque and why
   step-level tracing is the answer.
2. **LLM-as-judge for RCA** — using a stronger model to grade a weaker pipeline's
   intermediate outputs; how the backward walk localizes the first quality drop.
3. **Self-reported confidence as a signal** — and its limitations (a hallucinating model
   can be confidently wrong → why the judge is the arbiter, not self-confidence).
4. **Security as a first-class concern** — the trace store is a sensitive data sink;
   redaction, threat model, and CI gates were designed in, not added later.
5. **Cost-aware model selection** — Haiku for high-volume extraction, Opus for the
   low-volume, high-stakes judging.
6. **The feedback loop** — observability that improves the system, not just describes it.

---

## 7. Decisions (resolved 2026-06-24)

- **Sample-doc domain:** **Security / compliance documents** — policies, audit findings,
  risk registers. Rick authors the synthetic data (on-brand for ISRM background). Failure
  modes adapted to this domain (e.g. misclassified control families, missing review dates,
  ambiguous risk ratings).
- **Repo visibility:** **Public from day one** — the Phase 0 security gates must be live
  and green before/at first push (they are part of Phase 0).
- **Anthropic API budget:** eval re-runs (Phase 5) make repeated LLM calls; cache + throttle
  to keep cost low. Confirm `ANTHROPIC_API_KEY` is available before Phase 1 LLM steps.
