# Technical Portfolio Backlog

This is the active backlog for Quimera Semantic Trust Guardrail as a technical portfolio project. The former scientific and commercial tracks remain historical context; they are no longer the product objective.

## Status Legend

- `TODO`: not started.
- `IN_PROGRESS`: actively being implemented.
- `DONE`: implemented and validated.
- `DEFERRED`: intentionally outside the portfolio scope.

## Phase P0: Scope And Repository Presentation

### P0-T01: Reframe Project Scope

Status: DONE

Subtasks:

- State the project as an experimental RAG, guardrail, EVAL, observability, SDK, and ontology portfolio.
- Remove commercial and paper-readiness goals from the active roadmap.
- Record conservative claim boundaries and known limitations.

Acceptance: README and scope documentation make the portfolio objective unambiguous.

### P0-T02: Portfolio Repository Hygiene

Status: DONE

Subtasks:

- Add a real MIT `LICENSE` file and `.env.example`.
- Add CI for supported Python versions.
- Add `SECURITY.md`, contribution guidance, and developer quality tooling.
- Link all active portfolio documents from the README.

Acceptance: a reviewer can clone, install, test, and understand the project without private context.

Validation: added `LICENSE`, `.env.example`, `SECURITY.md`, `CONTRIBUTING.md`, and a GitHub Actions matrix for Python 3.10-3.12.

## Phase P1: Semantic Runtime And Ontology Showcase

### P1-T01: Preserve The Trivalent Decision Contract

Status: DONE

The existing `SemanticTrustDecision` contract covers `TRUE`, `FALSE`, `UNDECIDABLE`, recommended action, evidence, contradictions, missing requirements, and proof metadata.

### P1-T02: Preserve The Versioned Ontology Contract

Status: DONE

The existing semantic-fact model, tenant ontology, provenance, snapshot, rollback, and proof linkage remain the foundation of the showcase.

### P1-T03: Explainable Ontology Operations

Status: DONE

Subtasks:

- Add ontology inspection, diff, conflict, and decision-explanation examples.
- Show how an ontology fact changes a runtime decision.
- Add a small Mermaid architecture and evidence-flow diagram.

Acceptance: a reviewer can understand why the ontology is more than a document store.

Validation: added `examples/04_ontology_inspection.py` covering provenance, snapshot/diff, conflicting facts, and a runtime decision linked to the ontology.

## Phase P2: Three-Stage RAG EVALs

### P2-T01: Embedding Backend Contract

Status: DONE

Subtasks:

- Add an injectable embedding interface.
- Use `sentence-transformers` `5.6.1` for the real evaluation backend.
- Use a multilingual default model for Portuguese and English examples.
- Keep model loading lazy and tests network-free.

Acceptance: the benchmark can use real embeddings while unit tests use a deterministic fake backend.

Validation: added lazy `SentenceTransformerEmbedding`, deterministic test backends, and pinned `sentence-transformers==5.6.1` in the evaluation extra.

### P2-T02: Pre-RAG Evaluation

Status: DONE

Subtasks:

- Evaluate query-to-document retrieval readiness.
- Calculate hit@k, MRR, and top-1 similarity.
- Preserve per-query ranking details.

Acceptance: retrieval quality is measured before answer generation.

Validation: implemented hit@k, MRR, top-1 similarity, and explicit exclusion of no-gold queries from retrieval ranking aggregates.

### P2-T03: During-RAG Evaluation

Status: DONE

Subtasks:

- Evaluate the assembled context against relevant document ids.
- Calculate context precision, context recall, duplicate rate, and evidence coverage.
- Preserve the selected context and scores in the report.

Acceptance: context quality is separated from answer quality.

Validation: implemented candidate-vs-final context precision, context recall, duplicate rate, evidence coverage, context size, and abstention rate per case and in the aggregate report. The adaptive seed run reached final-context precision/recall of `1.0` while preserving candidate precision of `0.3333` as the diagnosed baseline.

### P2-T04: Post-RAG Evaluation

Status: DONE

Subtasks:

- Evaluate answer decision against expected `TRUE`, `FALSE`, or `UNDECIDABLE`.
- Record evidence coverage and decision distribution.
- Accept an injected runtime/evaluator without implicit LLM calls.

Acceptance: answer correctness, grounding evidence, and abstention remain separately inspectable.

Validation: implemented explicit answer evaluator injection, trivalent decision distribution, post-RAG accuracy, and no implicit LLM calls.

### P2-T06: Opt-In LLM RAG Benchmark

Status: DONE

Subtasks:

- Generate conservative structured answers and trivalent decisions from the selected context.
- Attempt NVIDIA MiniMax M3 first and use paid OpenRouter only as an explicit fallback.
- Persist provider/model/latency/fallback metadata without prompts, responses, or credentials.
- Treat malformed output and provider exhaustion as `UNDECIDABLE`/partial benchmark outcomes.

Acceptance: an API-key-backed run is reproducible, auditable, and never required by the offline regression suite.

Validation: added `quimera rag-llm-benchmark`, redacted provider traces, fallback ordering tests, malformed-output tests, and failure-safe artifacts.

### P2-T05: Reproducible Benchmark

Status: DONE

Subtasks:

- Commit a small RAG seed with supported, contradicted, and insufficient-evidence cases.
- Add a CLI benchmark command and JSON/Markdown artifacts.
- Run the benchmark with real embeddings and record model/config metadata.

Acceptance: a clean environment can reproduce the benchmark without an LLM API key.

Validation: added `quimera rag-benchmark`, a four-case committed seed, JSON/Markdown artifacts, and a real local embedding run with `llm_api_key_required: false`.

## Phase P3: Observability And Auditability

Status: DONE

Subtasks:

- Define structured events for retrieval, context assembly, validation, policy, and final decision.
- Correlate trace id, decision id, and proof id.
- Add latency, decision-count, abstention, failure, and token/cost metrics.
- Add optional OpenTelemetry export with redaction.
- Add proof replay and human-readable explanation commands.

Validation: trace events now include stage duration, decision/abstention/failure/token metrics, and secret redaction; `otel.json` is a dependency-free OTLP-shaped export; `trace-replay` and `proof-explain` reconstruct human-readable evaluation/proof paths.

Acceptance: a reviewer can reconstruct one decision from request through evidence and proof ledger.

## Phase P4: RAG And Agent Showcase

Status: DONE

Subtasks:

- Add one offline end-to-end RAG example.
- Add one agent tool-call authorization example.
- Add a `showcase` command with `TRUE`, `FALSE`, and `UNDECIDABLE` cases.
- Demonstrate ontology versioning and proof lookup in the same flow.

Validation: `quimera showcase` runs offline runtime decisions, ontology-backed agent authorization, the three-stage RAG EVAL, proof lookup, and observability artifacts. `docs/demo_walkthrough.md` provides the reviewer path.

Acceptance: the project demonstrates RAG, guardrails, agents, ontology, and auditability in under five minutes.

## Phase P5: Engineering Quality

Status: DONE

Subtasks:

- Add coverage thresholds and lint/type checks.
- Test Python 3.10, 3.11, and 3.12 in CI.
- Remove deprecation warnings from the active runtime path.
- Add contract tests for provider, retriever, embedder, and evidence adapters.

Acceptance: the project presents maintainable engineering, not only a working demo.

Validation: CI covers Python 3.10-3.12, enforces 60% product-test coverage, runs focused Ruff correctness checks and mypy evaluation checks, and includes provider/embedder/RAG/replay contract tests. The active runtime path uses timezone-aware UTC timestamps; the remaining FastAPI TestClient warning is an upstream dependency warning.

## Deferred Tracks

- Formal paper submission and scientific novelty claims are deferred to GroundCite-PTEN.
- Commercial pricing, buyer discovery, hosted service, SSO, RBAC, SLA, and paid deployment are outside this project scope.
