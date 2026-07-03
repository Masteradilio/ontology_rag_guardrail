# Changelog

All notable changes to Quimera Semantic Trust Guardrail will be documented here.

## [Unreleased]

### Added

- Created the initial product workspace for Quimera Semantic Trust Guardrail.
- Copied current `quimera_guardrails` modules into `src/quimera_semantic_trust_guardrail`.
- Copied the original guardrail README to `docs/README_quimera_guardrail.md`.
- Vendored selected GroundCite-PTEN source, docs, data samples, annotation artifacts, experiment summaries, and reference tests.
- Copied selected Quimera original legacy modules for adaptation under `src/quimera_legacy`.
- Added product README, PRD, master backlog, requirements, gitignore, and packaging metadata.
- Added the missing guardrail adapter package and GroundCite package source under `src`.
- Created `.venv`, installed `requirements.txt`, and installed the project in editable mode.

### Validation

- Smoke imports passed for `quimera_semantic_trust_guardrail`, `groundcite`, and `quimera_legacy.truth_mapping`.
- GroundCite reference subset passed: `9 passed` for schema and claim tests.

### Notes

- The old AGI/quantum product framing is not part of the new product positioning.
- Legacy and GroundCite code is copied for adaptation; not all reference tests are expected to pass before Phase 1/Phase 4 cleanup.
- Quimera original reference tests currently require import-path adaptation from old flat-module imports to the new `quimera_legacy` package.
