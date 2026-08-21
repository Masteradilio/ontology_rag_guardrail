# Changelog

All notable changes to Ontology RAG Guardrail will be documented here.

## [Unreleased]

### Added

- Added the Phase 1 runtime decision model with trivalent decisions, recommended actions, decision statuses, evidence records, contradiction records, missing requirements, proof metadata, serialization support, and GroundCite label mapping.
- Added the Phase 1 semantic fact model with tenant-scoped facts, ontology/policy version fields, provenance metadata, validity windows, and migration helpers for `OntologyEntry`, adapter `KnowledgeFact`, and legacy graph `Fact` records.
- Added Phase 1 runtime integration for `knowledge_adapter` and `OntologySync`, including adapter-backed output validation, unified ontology fact writes, duplicate skipping, and conflict metadata.
- Added the Phase 2 `SemanticTrustRuntime` SDK surface with `claim_check`, `answer_check`, `action_check`, and `policy_check`.
- Exposed Phase 2 runtime methods through `QuimeraGuardrails` while keeping the existing input/output guardrail API.
- Added the Phase 3 enriched proof ledger schema, proof lookup APIs, ontology-scoped proof listing, and proof types for claim, answer, action, policy, snapshot, rollback, and migration records.
- Added the Phase 3 ontology versioning module with snapshot, diff, rollback, migration ledger, and proof-linked ontology operations.
- Added the Phase 4 adapted GroundCite product regression suite and product smoke tests.
- Added the Phase 5 SDK packaging metadata, console scripts, optional FastAPI extra, `py.typed` marker, CLI module, and runnable examples.
- Added the optional FastAPI HTTP runtime with `/health`, `/claim-check`, `/answer-check`, `/action-check`, `/policy-check`, `/proofs/{proof_id}`, and ontology snapshot/rollback endpoints.
- Added Phase 6 product documentation: architecture, RAG integration, agent integration, policy/ontology modeling, and proof/audit guides.
- Added Phase 6 research positioning and evaluation plan documents with conservative scientific claims, explicit non-claims, benchmark protocol, and commercial evaluation axes.
- Added `docs/comercial_cientific_backlog.md` to plan the scientific and commercial validation tracks, including MiniMax M3 provider priority through NVIDIA first and OpenRouter fallback.
- Added Phase S0 scientific evaluation infrastructure with provider fallback clients, evaluation artifact schemas, and a controlled seed dataset package.
- Added a deterministic Phase S1 scientific baseline runner and CLI command that evaluate claim/answer, abstention, agent action, and policy/compliance seed cases and write reproducible artifacts.
- Added Phase S2 scientific reporting package with an Ontology RAG Guardrail claims ledger, technical report, and external research decision.
- Added Phase C0 commercial discovery materials and an offline commercial demo runner/CLI for RAG approval, agent authorization, and policy review workflows.
- Added Phase C1 commercial pilot planning, metrics helpers, pricing hypotheses, and pilot report templates.
- Added packaged compatibility shims for copied legacy Quimera original reference tests: `core.*` modules and legacy flat-module imports now re-export the selected `quimera_legacy` modules.
- Added the active technical portfolio scope and backlog for RAG, guardrails, EVALs, observability, SDK architecture, trivalent validation, and ontology auditability.
- Added three-stage RAG EVAL contracts for pre-RAG retrieval, during-RAG context quality, and post-RAG trivalent answer decisions.
- Added lazy Sentence Transformers embeddings pinned to `5.6.1`, deterministic test/showcase embeddings, a committed RAG seed, and the `quimera rag-benchmark` command.
- Added dependency-free evaluation observability with stage events, decision distributions, JSONL traces, summary artifacts, and secret redaction.
- Added adaptive RAG context assembly with explicit candidate-vs-final precision, recall, duplicate, context-size, and abstention metrics.
- Added the opt-in `quimera rag-llm-benchmark` with NVIDIA-first/OpenRouter-fallback policy, structured-output parsing, evidence-consistency guardrails, redacted provider JSONL, and failure-safe artifacts.
- Added trace metrics, dependency-free OTLP-shaped export, trace replay, proof explanation, coverage/lint/type gates, and provider response error normalization.
- Added the 96-case `rag_enterprise_v1` semisynthetic benchmark package with 24 enterprise policy families, balanced trivalent/evidence scenarios, generator, manifest, and provenance metadata.
- Added `quimera rag-threshold-benchmark` with one-pass Sentence Transformers ranking reuse, threshold-level precision/recall/F1/abstention metrics, recommendation logic, CSV/JSON/Markdown/SVG serialization, and a GitHub-readable benchmark snapshot.
- Added NVIDIA model-card URL normalization so a documentation URL in `NVIDIA_URL_REFERENCE_MODEL` cannot silently force every LLM call into the paid fallback.
- Added the offline `quimera showcase` command, repository license, security/contribution guidance, `.env.example`, and Python 3.10-3.12 CI workflow.
- Added an explicit repository-wide Ruff gate in `pyproject.toml` for `E4`, `E7`, `E9`, and `F` findings, matching the CI quality contract.
- Added the official GNU AGPLv3+ license text and replaced the package's MIT metadata/classifier with AGPLv3+.

### Changed

- Renamed the public project identity from Quimera Semantic Trust Guardrail to Ontology RAG Guardrail while retaining the existing Python package, CLI, and class identifiers for backward compatibility.
- Rewrote the root `README.md` so it reflects the implemented SDK/runtime surface instead of the initial workspace plan.
- Cleaned the changelog to remove duplicated initial workspace and validation entries.
- Updated `docs/MASTER_BACKLOG.md` to restore and close Phase 6 and to reflect that legacy Quimera original reference tests now pass through compatibility shims.
- Updated GroundCite research reference tests to resolve vendored dataset and scientific documentation paths inside the new product repository layout.
- Aligned the runtime-reported version with the experimental package version declared in `pyproject.toml` (`0.1.0.dev0`).
- Changed the default RAG benchmark to adaptive context assembly; the original noisy declared context remains visible as a candidate metric instead of being silently discarded.
- Clarified `.env.example`, README, and evaluation guidance for the NVIDIA inference endpoint versus the NVIDIA model-card URL.
- Made `ruff check .` use the same explicit lint scope as CI so local and hosted validation do not depend on implicit Ruff defaults.
- Made the root README bilingual and documented the AGPLv3+ copyleft, remote-network source requirement, upstream-license boundary, and need for separate written permission for proprietary use outside the license.

### Validation

- Product decision model tests passed: `8 passed` for `tests/product/test_decision_model.py`.
- Product decision and semantic fact model tests passed together: `13 passed`.
- Phase 1 product and GroundCite schema/claim regression passed: `28 passed`.
- Phase 2 runtime API tests passed: `10 passed` for `tests/product/test_phase2_runtime_api.py`.
- Phase 2 product and GroundCite schema/claim regression passed: `38 passed`.
- Phase 3 enriched proof ledger and ontology versioning tests passed: `13 passed` for `tests/product/test_phase3_proof_and_ontology_versioning.py`.
- Phase 3 full product regression passed: `42 passed` without breaking the GroundCite schema/claim reference subset.
- Phase 4 adapted GroundCite regression tests passed: `14 passed` for `tests/product/test_phase4_groundcite_regression.py`.
- Phase 4 product smoke tests passed: `7 passed` for `tests/product/test_phase4_smoke.py`.
- Phase 4 full product + GroundCite schema/claim regression passed: `72 passed`.
- Phase 5 packaging and FastAPI HTTP runtime tests passed: `23 passed` for `tests/product/test_phase5_packaging_and_fastapi.py`.
- Phase 5 full product + GroundCite schema/claim regression passed: `95 passed`.
- legacy Quimera original reference compatibility tests passed: `tests/reference_quimera_original`.
- Full repository regression passed: `217 passed` via `python -m pytest -q`.
- Focused three-stage RAG EVAL, benchmark, observability, replay, and LLM benchmark regression passed: `21 passed`.
- Current full repository regression passed: `240 passed`, with one pre-existing FastAPI/Starlette deprecation warning.
- Real adaptive embedding benchmark completed with `sentence-transformers==5.6.1`, four synthetic cases, `pre_rag.hit_at_k=1.0`, `pre_rag.mrr=1.0`, final `during_rag.context_precision=1.0`, final `during_rag.context_recall=1.0`, `during_rag.duplicate_rate=0.0`, and explicit `context_abstention_rate=0.25`; candidate context precision remains `0.3333` as the diagnosed baseline.
- LLM benchmark completed from `.env` using NVIDIA as primary and OpenRouter as fallback after NVIDIA provider failure: four valid structured decisions, final `post_rag.decision_accuracy=1.0`, `llm_raw_decision_accuracy=1.0`, and `llm_guardrailed_decision_accuracy=1.0`.
- Product coverage measured at `66.13%` with a configured CI threshold of `60%`; focused Ruff and mypy checks pass.
- Enterprise threshold benchmark completed over 96 cases with `pre_rag.hit_at_k=1.0` and `pre_rag.mrr=0.9583`; the F1 recommendation at threshold `0.55` reached context precision `0.861`, recall `0.944`, F1 `0.901`, and harmful abstention `0.042`. A precision-oriented threshold `0.65` reached precision `0.907` with recall `0.778`.
- Recruiter-style reproduction passed for setup, imports, examples, showcase, offline benchmarks, threshold artifacts, trace replay, proof explanation, HTTP endpoints, and optional LLM evaluation. After URL normalization, NVIDIA handled `3/4` cases and OpenRouter handled `1/4` after NVIDIA returned `HTTP 429`; all four structured decisions were valid and both raw/guardrailed accuracy metrics were `1.0`.
- Final regression after the provider configuration fix: `247 passed`, product coverage `67.49%`, focused Ruff/mypy/compileall/pip checks passed.
- Repository-wide lint debt was cleared: `.venv\Scripts\ruff.exe check .` passes with zero `E4`, `E7`, `E9`, or `F` findings; product coverage remains above the `60%` gate at `67.70%`.
- License metadata and README license references now consistently identify GNU AGPLv3+ for original project material.
- Smoke imports passed for `quimera_semantic_trust_guardrail`, `groundcite`, and `quimera_legacy.truth_mapping`.
- GroundCite reference subset passed: `9 passed` for schema and claim tests.

### Notes

- The old AGI/quantum product framing is not part of the new product positioning.
- GroundCite `unsupported` labels map to `UNDECIDABLE`, preserving the distinction between absent support and direct contradiction.
- Research-only GroundCite tests (`test_hybrid.py`, `test_groundcite_bench_dataset.py`, `test_dataset_summary_integrity.py`, `test_scientific_reporting_guardrails.py`) remain under `tests/reference_groundcite/` and are not part of the product regression gate.
- Ontology RAG Guardrail estimates support, contradiction, authorization, and insufficient evidence under configured evidence, ontology, and policy. It does not prove real-world truth, replace legal review, or eliminate hallucinations.
- Commercial and formal-paper validation are historical objectives for this repository; the active portfolio roadmap is `docs/portfolio_backlog.md`.
- The RAG seed benchmark is synthetic and controlled. Its post-RAG evaluator is deterministic, and its metrics do not estimate production RAG quality.
- The expanded enterprise benchmark is template-generated semisynthetic data, not real anonymized customer data. Its published curve demonstrates calibration and trade-off measurement; it is not an out-of-sample or production-quality claim.
- The optional provider benchmark remains network- and quota-dependent. The repository records provider, fallback, parse, latency, and status metadata, but never commits API keys or raw provider responses.

## [0.1.0] - 2026-07-04

### Added

- Created the initial product workspace for Ontology RAG Guardrail.
- Copied current `quimera_guardrails` modules into `src/quimera_semantic_trust_guardrail`.
- Copied the original guardrail README to `docs/README_quimera_guardrail.md`.
- Vendored selected GroundCite-PTEN source, docs, data samples, annotation artifacts, experiment summaries, and reference tests.
- Copied selected legacy Quimera original legacy modules for adaptation under `src/quimera_legacy`.
- Added product README, PRD, master backlog, requirements, gitignore, and packaging metadata.
- Added the missing guardrail adapter package and GroundCite package source under `src`.

### Validation

- Created `.venv`, installed `requirements.txt`, and installed the project in editable mode.
- Smoke imports passed for `quimera_semantic_trust_guardrail`, `groundcite`, and `quimera_legacy.truth_mapping`.
- GroundCite reference subset passed: `9 passed` for schema and claim tests.
- Initialized the Git repository, configured `origin`, committed the prepared workspace, and pushed `main` to GitHub.
