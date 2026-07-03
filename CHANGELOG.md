# Changelog

All notable changes to Quimera Semantic Trust Guardrail will be documented here.

## [Unreleased]

### Added

- Added the Phase 1 runtime decision model with trivalent decisions, recommended actions, decision statuses, evidence records, contradiction records, missing requirements, proof metadata, serialization support, and GroundCite label mapping.
- Added the Phase 1 semantic fact model with tenant-scoped facts, ontology/policy version fields, provenance metadata, validity windows, and migration helpers for `OntologyEntry`, adapter `KnowledgeFact`, and legacy graph `Fact` records.
- Added Phase 1 runtime integration for `knowledge_adapter` and `OntologySync`, including adapter-backed output validation, unified ontology fact writes, duplicate skipping, and conflict metadata.
- Added the Phase 2 `SemanticTrustRuntime` SDK surface with `claim_check`, `answer_check`, `action_check`, and `policy_check`.
- Exposed Phase 2 runtime methods through `QuimeraGuardrails` while keeping the existing input/output guardrail API.
- Created the initial product workspace for Quimera Semantic Trust Guardrail.
- Copied current `quimera_guardrails` modules into `src/quimera_semantic_trust_guardrail`.
- Copied the original guardrail README to `docs/README_quimera_guardrail.md`.
- Vendored selected GroundCite-PTEN source, docs, data samples, annotation artifacts, experiment summaries, and reference tests.
- Copied selected Quimera original legacy modules for adaptation under `src/quimera_legacy`.
- Added product README, PRD, master backlog, requirements, gitignore, and packaging metadata.
- Added the missing guardrail adapter package and GroundCite package source under `src`.
- Created `.venv`, installed `requirements.txt`, and installed the project in editable mode.
- Initialized the Git repository, configured `origin`, committed the prepared workspace, and pushed `main` to GitHub.

### Validation

- Product decision model tests passed: `8 passed` for `tests/product/test_decision_model.py`.
- Product decision and semantic fact model tests passed together: `13 passed`.
- Phase 1 product and GroundCite schema/claim regression passed: `28 passed`.
- Phase 2 runtime API tests passed: `10 passed` for `tests/product/test_phase2_runtime_api.py`.
- Phase 2 product and GroundCite schema/claim regression passed: `38 passed`.
- Smoke imports passed for `quimera_semantic_trust_guardrail`, `groundcite`, and `quimera_legacy.truth_mapping`.
- GroundCite reference subset passed: `9 passed` for schema and claim tests.

### Notes

- The old AGI/quantum product framing is not part of the new product positioning.
- GroundCite `unsupported` labels now map to `UNDECIDABLE`, preserving the distinction between absent support and direct contradiction.
- Legacy and GroundCite code is copied for adaptation; not all reference tests are expected to pass before Phase 1/Phase 4 cleanup.
- Quimera original reference tests currently require import-path adaptation from old flat-module imports to the new `quimera_legacy` package.
