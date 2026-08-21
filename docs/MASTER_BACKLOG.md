# Master Backlog

This backlog governs the adaptation of `quimera_guardrails`, `groundcite_pten`, and selected `quimera_original` components into Quimera Semantic Trust Guardrail.

Every implementation task must end with:

- regression tests for the changed behavior;
- update to this backlog;
- update to `CHANGELOG.md`;
- `git status --short` review before closeout.

## Status Legend

- `TODO`: not started.
- `IN_PROGRESS`: actively being worked.
- `BLOCKED`: cannot proceed without a decision or dependency.
- `DONE`: implemented and validated.
- `DEFERRED`: intentionally postponed.

## Phase 0: Repository Preparation

### P0-T01: Create New Project Workspace

Status: DONE

Goal: create the independent repository workspace under `C:\Users\adili\projetos_offline\quimera_semantic_trust_guardrail`.

Subtasks:

- Copy current `quimera_guardrails` runtime modules into `src/quimera_semantic_trust_guardrail`.
- Copy `README.md` from the old guardrail into `docs/README_quimera_guardrail.md`.
- Copy selected GroundCite source, docs, samples, annotation artifacts, and tests.
- Copy selected Quimera original source, docs, and tests.
- Create root `README.md`.
- Create `.gitignore`.
- Create `requirements.txt`.
- Create initial `CHANGELOG.md`.
- Run regression/import smoke tests for copied modules.
- Update this backlog.
- Update `CHANGELOG.md`.

Validation:

- Smoke imports passed for `quimera_semantic_trust_guardrail`, `groundcite`, and `quimera_legacy.truth_mapping`.
- GroundCite reference subset passed: `9 passed` for `tests/reference_groundcite/test_schema.py` and `tests/reference_groundcite/test_claims.py`.
- Quimera original reference tests are copied for legacy compatibility coverage. The old flat and `core.*` import paths are now preserved through compatibility shims, and `tests/reference_quimera_original` passes.

### P0-T02: Python Environment Bootstrap

Status: DONE

Goal: create local venv and install project requirements.

Subtasks:

- Create `.venv`.
- Upgrade `pip`.
- Install `requirements.txt`.
- Verify imports for `quimera_semantic_trust_guardrail`, `groundcite`, and selected `quimera_legacy` modules.
- Document install command in `README.md`.
- Run regression/import smoke tests.
- Update this backlog.
- Update `CHANGELOG.md`.

Validation:

- `.venv` created under the new project workspace.
- `pip` upgraded inside `.venv`.
- `requirements.txt` installed successfully.
- Project installed in editable mode with `pip install -e .`.
- Smoke imports passed for the three copied code families.

### P0-T03: Git And Remote Preparation

Status: DONE

Goal: prepare the first synchronization with `https://github.com/Masteradilio/quimera_semantic_trust_guardrail.git`.

Subtasks:

- Initialize git repository if needed.
- Configure default branch.
- Add remote `origin`.
- Confirm `.gitignore` excludes `.venv`, caches, local ledgers, and generated artifacts.
- Stage files for first commit.
- Commit initial project preparation.
- Push to remote when credentials/remote permissions allow.
- Run regression/import smoke tests before commit.
- Update this backlog.
- Update `CHANGELOG.md`.

Validation:

- Git repository initialized with `main` as the default branch.
- Remote configured as `https://github.com/Masteradilio/quimera_semantic_trust_guardrail.git`.
- `.gitignore` verified for `.venv`, `__pycache__`, and `.pyc`.
- Initial project preparation committed and pushed to `origin/main`.

## Phase 1: Contract Consolidation

### P1-T01: Define Runtime Decision Model

Status: DONE

Goal: create a single model for semantic trust decisions.

Subtasks:

- Define decision enum: `TRUE`, `FALSE`, `UNDECIDABLE`.
- Define recommended actions: allow, warn, retry, abstain, block, escalate.
- Define evidence, contradiction, missing requirement, and proof metadata fields.
- Map GroundCite labels to Quimera trivalent states.
- Add serialization and validation tests.
- Run regression tests for model serialization and mapping.
- Update this backlog.
- Update `CHANGELOG.md`.

Validation:

- Added `src/quimera_semantic_trust_guardrail/decision_model.py` with `SemanticTrustDecision`, evidence, contradiction, missing requirement, proof metadata, trivalent decision, status, and recommended action models.
- GroundCite label mapping is conservative: `supported` -> `TRUE`, `contradicted` -> `FALSE`, and `unsupported` / `partially_unsupported` -> `UNDECIDABLE`.
- Product decision model tests passed: `8 passed` for `tests/product/test_decision_model.py`.
- GroundCite reference subset still passed: `9 passed` for `tests/reference_groundcite/test_schema.py` and `tests/reference_groundcite/test_claims.py`.

### P1-T02: Unify Semantic Fact And Ontology Model

Status: DONE

Goal: converge `TenantOntologyManager`, `KnowledgeFact`, and legacy graph facts into one semantic fact contract.

Subtasks:

- Define `SemanticFact` with subject, relation, object, fact type, state, source, confidence, validity period, tenant, and version.
- Preserve support for concepts, definitions, facts, constraints, synonyms, and policies.
- Add provenance fields for document id, chunk id, span, source URI, and extractor.
- Create migration adapters from existing `OntologyEntry` and legacy `Fact`.
- Add tests for fact conversion and tenant isolation.
- Run regression tests for ontology behavior.
- Update this backlog.
- Update `CHANGELOG.md`.

Validation:

- Added `src/quimera_semantic_trust_guardrail/semantic_fact.py` with `SemanticFact`, `SemanticFactProvenance`, `SemanticFactType`, and a tenant-scoped `SemanticOntology`.
- Added migration helpers for current `OntologyEntry`, adapter `KnowledgeFact`, and legacy `quimera_legacy.knowledge_ontology.Fact`.
- Preserved concepts, definitions, facts, constraints, synonyms, policies, trivalent state, confidence, validity windows, tenant id, ontology/policy version, and structured provenance fields.
- Product model tests passed: `13 passed` for `tests/product/test_decision_model.py` and `tests/product/test_semantic_fact.py`.

### P1-T03: Fix Knowledge Adapter Contract

Status: DONE

Goal: make `knowledge_adapter` a real supported constructor/runtime dependency.

Subtasks:

- Add `knowledge_adapter` to runtime initialization.
- Ensure `OutputValidator` can use adapter-backed claim verification.
- Preserve tenant and agent scoping in adapter calls.
- Make adapter failures return `UNDECIDABLE`, not false certainty.
- Add tests using `SimpleKnowledgeAdapter`.
- Run regression tests for adapter-backed validation.
- Update this backlog.
- Update `CHANGELOG.md`.

Validation:

- `QuimeraGuardrails` and `create_guardrails` now accept `knowledge_adapter`.
- `QuimeraOutputValidator` now runs adapter-backed claim verification when a knowledge adapter is configured.
- Adapter `verified` results are accepted, `contradicted` results become false hallucination evidence, and `uncertain` / adapter exceptions become `ClaimVerification(verified=None)`.
- Product integration tests cover supported, uncertain, and failing adapter paths using `SimpleKnowledgeAdapter` and a failing adapter stub.

### P1-T04: Fix OntologySync Integration

Status: DONE

Goal: make automatic fact extraction write into the unified ontology model.

Subtasks:

- Replace incompatible `add_entry` calls in `OntologySync`.
- Add or adapt `add_fact` support in ontology manager.
- Store extracted fact provenance.
- Add duplicate and conflict handling.
- Add tests for pattern extraction and sync.
- Run regression tests for sync and ontology write paths.
- Update this backlog.
- Update `CHANGELOG.md`.

Validation:

- `TenantOntologyManager` now stores unified `semantic_facts` alongside legacy `entries`, exposes `add_fact` / `list_facts`, skips exact duplicates, and marks conflicting same-triple states in fact metadata.
- `OntologySync` now writes extracted facts through `add_fact`, creates or reuses a target ontology, maps extraction fact types to `SemanticFactType`, and stores document/chunk/extractor provenance.
- Product integration tests cover direct sync of extracted facts into the unified ontology model.
- Phase 1 regression passed: `28 passed` for product tests plus GroundCite schema/claim reference tests.

## Phase 2: Runtime APIs

### P2-T01: Implement `claim_check`

Status: DONE

Goal: validate one claim against ontology, adapter evidence, policy, and compliance context.

Subtasks:

- Accept claim, tenant, domain, context, and optional evidence.
- Use GroundCite-style claim support where relevant.
- Return trivalent decision with evidence and proof id.
- Add support for contradicted vs unsupported distinction.
- Add unit and integration tests.
- Run regression tests for claim checking.
- Update this backlog.
- Update `CHANGELOG.md`.

Validation:

- Added `SemanticTrustRuntime.claim_check` with adapter, ontology, explicit evidence, compliance, trivalent decision, evidence, contradiction, missing requirement, and proof metadata paths.
- Tests cover supported adapter evidence, explicit evidence with tenant/domain/context, contradicted adapter output, and unsupported claims that return `UNDECIDABLE` instead of `FALSE`.

### P2-T02: Implement `answer_check`

Status: DONE

Goal: decompose an answer into claims and aggregate a decision.

Subtasks:

- Use GroundCite claim decomposition.
- Validate claims independently.
- Propagate claim dependency graph failures.
- Aggregate into allow/warn/retry/abstain/block/escalate.
- Include unsupported spans when available.
- Add tests with GroundCite reference samples.
- Run regression tests for answer checking.
- Update this backlog.
- Update `CHANGELOG.md`.

Validation:

- Added `SemanticTrustRuntime.answer_check` using GroundCite `RegexClaimDecomposer`, claim-level validation, dependency graph propagation, aggregate trivalent decisions, and unsupported span metadata.
- Tests cover mixed supported/unsupported answers, propagated dependency failures, and a GroundCite `Context` sample-shaped check.

### P2-T03: Implement `action_check`

Status: DONE

Goal: validate whether an agent action is semantically and policy-authorized.

Subtasks:

- Define action schema: actor, action, resource, tenant, purpose, context.
- Model permissions as semantic facts or policy rules.
- Default to `UNDECIDABLE` when authorization is absent.
- Return proof id and missing requirements.
- Add tests for allow, deny, and undecidable paths.
- Run regression tests for action checking.
- Update this backlog.
- Update `CHANGELOG.md`.

Validation:

- Added `SemanticTrustRuntime.action_check` with actor/action/resource/purpose/context inputs and semantic policy fact matching.
- Tests cover allowed policy facts, denied policy facts, and absent authorization returning `UNDECIDABLE` with an escalation recommendation.

### P2-T04: Implement `policy_check`

Status: DONE

Goal: unify compliance rules, internal policies, and constraints.

Subtasks:

- Adapt current `ComplianceEngine`.
- Add tenant policy packs.
- Add input/output/action scopes.
- Add policy provenance.
- Add tests for LGPD/AI Act/custom policies.
- Run regression tests for policy checks.
- Update this backlog.
- Update `CHANGELOG.md`.

Validation:

- Added `SemanticTrustRuntime.policy_check` combining `ComplianceEngine` violations with tenant semantic policy facts and policy provenance in evidence/contradiction records.
- Tests cover LGPD, AI Act, custom compliance rules, tenant policy packs, and input/output/action scope filtering.
- Phase 2 product tests passed: `10 passed` for `tests/product/test_phase2_runtime_api.py`.
- Product plus GroundCite schema/claim regression passed after Phase 2 implementation: `38 passed`.

## Phase 3: Proof And Audit Hardening

### P3-T01: Enrich Proof Ledger Schema

Status: DONE

Goal: record enough metadata to reproduce semantic decisions.

Subtasks:

- Add ontology version, adapter source, evidence ids, policy ids, and decision path.
- Preserve hash chain verification.
- Add proof lookup API.
- Add chain integrity tests.
- Run regression tests for proof ledger.
- Update this backlog.
- Update `CHANGELOG.md`.

Validation:

- `ProofEntry` now stores `ontology_id`, `ontology_version`, `policy_id`, `policy_version`, `ruleset_version`, `adapter_source`, `evidence_ids`, `policy_ids`, `decision_path`, `proof_status`, and `related_proof_id` in addition to the original fields.
- The hash calculation now covers the enriched fields, so `verify_integrity` and `verify_chain` remain valid for new and historical entries.
- `ProofRecorder.lookup_proof(proof_id)` and `list_tenant_proofs_with_provenance(tenant_id, ontology_id=...)` are the new public audit APIs.
- New `ProofType` enum values: `CLAIM_CHECK`, `ANSWER_CHECK`, `ACTION_CHECK`, `POLICY_CHECK`, `ONTOLOGY_SNAPSHOT`, `ONTOLOGY_ROLLBACK`, `ONTOLOGY_MIGRATION`. The runtime now uses the matching `ProofType` per public method instead of the generic `ONTOLOGY_VERIFICATION`.
- `QuimeraGuardrails` exposes `proof_lookup(proof_id)` and `list_proofs_for_ontology(ontology_id)`.
- `get_statistics` now also reports `by_ontology` and `by_adapter` distributions.
- Phase 3 regression tests passed: `13 passed` for `tests/product/test_phase3_proof_and_ontology_versioning.py`.
- Full product regression passed: `42 passed` (29 prior + 13 new) without breaking the GroundCite schema/claim reference subset.

### P3-T02: Add Ontology Versioning

Status: DONE

Goal: support snapshots, diffs, and rollback for semantic knowledge.

Subtasks:

- Adapt legacy snapshot/diff ideas.
- Track tenant ontology versions.
- Add migration records.
- Add tests for snapshot, diff, rollback, and proof linkage.
- Run regression tests for versioning.
- Update this backlog.
- Update `CHANGELOG.md`.

Validation:

- Added `src/quimera_semantic_trust_guardrail/ontology_versioning.py` with `OntologyVersioningStore`, `OntologySnapshot`, `OntologyMigration`, and the `diff_payloads` helper.
- Snapshots are stored under `<storage_path>/<tenant_id>/<ontology_id>/snapshots/<snapshot_id>.json`, and a `migrations.jsonl` ledger records every snapshot, rollback, and `add_fact` event.
- `TenantOntologyManager` now exposes `snapshot_ontology`, `list_ontology_snapshots`, `get_ontology_snapshot`, `diff_ontology`, `rollback_ontology`, and `list_ontology_migrations`.
- `QuimeraGuardrails` wraps `snapshot_ontology` and `rollback_ontology`, recording `ONTOLOGY_SNAPSHOT` and `ONTOLOGY_ROLLBACK` proofs in the chain with `decision_path` and `related_proof_id` linkage.
- `add_fact` now records an `add_fact` migration linked to the optional `proof_id`, preserving the audit trail of ontology writes.
- Phase 3 regression tests passed: `13 passed` for `tests/product/test_phase3_proof_and_ontology_versioning.py`.
- Full product regression passed: `42 passed`.

## Phase 4: Evaluation And Regression Harness

### P4-T01: Adapt GroundCite Regression Suite

Status: DONE

Goal: convert selected GroundCite tests into product regression tests.

Subtasks:

- Move useful reference tests from `tests/reference_groundcite`.
- Adapt imports and fixtures.
- Keep research-only tests separated.
- Add product-level quality gates for claim support and abstention.
- Run regression tests.
- Update this backlog.
- Update `CHANGELOG.md`.

Validation:

- Added `tests/product/test_phase4_groundcite_regression.py` with 14 adapted regression tests:
  - Adapted from `test_claims.py`: sentence splitting, abbreviation preservation, empty/short text, and the runtime `answer_check` decomposition contract.
  - Adapted from `test_schema.py`: `Context` schema minimal/full, `Sample` JSONL payload loading, and the `map_groundcite_label` contract between GroundCite and the trivalent decision model.
  - Product-level **claim support quality gate**: with a fully supported answer the `claim_support_rate` is 1.0 and `AbstentionRisk` recommends NOT abstaining.
  - Product-level **abstention quality gate (contradicted)**: any contradicted claim forces risk to 1.0 and recommends abstention.
  - Product-level **abstention quality gate (unsupported)**: 100% unsupported claims produce risk 0.7 and recommend abstention.
  - Product-level **runtime claim support gate**: with a populated `SimpleKnowledgeAdapter` the runtime returns `ALLOW + TRUE`.
  - Product-level **runtime abstention gate**: with no adapter, no ontology, and no evidence the runtime returns `ABSTAIN + UNDECIDABLE` and records an `evidence` missing requirement.
  - Lightweight integration with the vendored `Evaluator` + `LexicalBackend` so the public GroundCite surface remains import-safe.
  - Dependency graph exposure contract from the product `answer_check` (Mermaid graph with at least two nodes for a multi-claim answer).
- Research-only tests remain in `tests/reference_groundcite/`:
  - `test_hybrid.py` (HybridBackend fast-path contract).
  - `test_groundcite_bench_dataset.py` and `test_dataset_summary_integrity.py` (benchmark dataset integrity for the original research benchmark).
  - `test_scientific_reporting_guardrails.py` (research-doc overclaim guardrails, depends on docs that are not part of the product).
- Phase 4 regression passed: `14 passed` for `tests/product/test_phase4_groundcite_regression.py`.
- Full product + GroundCite schema/claim regression passed: `72 passed` (63 product + 9 GroundCite).

### P4-T02: Add Product Smoke Tests

Status: DONE

Goal: verify the product package works from a clean install.

Subtasks:

- Test import of main package.
- Test import of vendored GroundCite package.
- Test import of selected legacy modules.
- Test a minimal `claim_check` once implemented.
- Run regression tests.
- Update this backlog.
- Update `CHANGELOG.md`.

Validation:

- Added `tests/product/test_phase4_smoke.py` with 7 smoke tests:
  - `test_main_package_imports` verifies all 30 public symbols of `quimera_semantic_trust_guardrail` are importable.
  - `test_groundcite_package_imports` verifies the vendored `groundcite` package, `groundcite.claims`, `groundcite.metrics.claim_support`, and `groundcite.metrics.abstention` all import with their public surface.
  - `test_legacy_truth_mapping_imports` verifies the `quimera_legacy.truth_mapping` module still imports.
  - `test_minimal_claim_check_returns_trivalent_decision` runs a no-frills `claim_check` and asserts the trivalent decision + proof metadata.
  - `test_minimal_guardrails_construct_and_run` constructs `QuimeraGuardrails` with a tempdir-backed `GuardrailsConfig`, runs `shield_input` and `claim_check`, and verifies the public `proof_lookup` API.
  - `test_minimal_claim_check_with_adapter_supported_path` exercises the adapter-backed supported path of the runtime.
  - `test_package_metadata_exposes_versions` verifies both packages expose string `__version__` attributes.
- Phase 4 regression passed: `7 passed` for `tests/product/test_phase4_smoke.py`.
- Full product + GroundCite schema/claim regression passed: `72 passed` (63 product + 9 GroundCite).

## Phase 5: Packaging And Deployment

### P5-T01: Package The SDK

Status: DONE

Goal: make the project installable as an SDK.

Subtasks:

- Finalize package metadata.
- Add console scripts if needed.
- Add examples.
- Add installation tests in venv.
- Run regression tests.
- Update this backlog.
- Update `CHANGELOG.md`.

Validation:

- `pyproject.toml` now declares full PyPI metadata (classifiers, keywords, project URLs, `requires-python`, `License :: MIT`, `Topic :: Scientific/Engineering :: Artificial Intelligence`) and the optional `[fastapi]` and `[dev]` extras.
- Two console scripts are exposed: `quimera` -> `quimera_semantic_trust_guardrail.__main__:main` and `quimera-serve` -> `quimera_semantic_trust_guardrail.__main__:serve_main`.
- `setuptools.packages.find` is scoped to `src/` and explicitly includes `quimera_semantic_trust_guardrail*`, `groundcite*`, and `quimera_legacy*` so the vendored packages are installed alongside the product.
- The package ships a `py.typed` marker (PEP 561).
- New `__main__.py` implements `quimera version`, `quimera claim <text>`, and `quimera serve` (the latter lazily imports FastAPI/uvicorn so the base package can be used without the optional extra).
- Added `examples/01_claim_check_basic.py`, `examples/02_ontology_versioning.py`, and `examples/03_fastapi_server.py` as runnable scripts.
- Phase 5 regression passed: `23 passed` for `tests/product/test_phase5_packaging_and_fastapi.py` (12 packaging tests + 11 FastAPI tests).
- Full product + GroundCite schema/claim regression passed: `95 passed` (86 product + 9 GroundCite).

### P5-T02: Add Optional FastAPI Runtime

Status: DONE

Goal: expose runtime checks as HTTP endpoints.

Subtasks:

- Add `/claim-check`.
- Add `/answer-check`.
- Add `/action-check`.
- Add `/policy-check`.
- Add `/proofs/{proof_id}`.
- Add tenant authentication placeholders.
- Add integration tests.
- Run regression tests.
- Update this backlog.
- Update `CHANGELOG.md`.

Validation:

- Added `src/quimera_semantic_trust_guardrail/fastapi_app.py` exposing `create_app(proof_storage_path, ontology_storage_path)` which returns a configured `FastAPI` instance.
- FastAPI is an optional dependency: the `[fastapi]` extra in `pyproject.toml` pulls in `fastapi>=0.110` and `uvicorn[standard]>=0.27`. The module raises a clear `ImportError` if the user calls `create_app` without the extra installed, and the `quimera-serve` CLI surfaces a friendly message.
- Endpoints: `GET /health`, `POST /claim-check`, `POST /answer-check`, `POST /action-check`, `POST /policy-check`, `GET /proofs/{proof_id}`, `POST /ontologies/snapshots`, `POST /ontologies/rollback`, `GET /ontologies/snapshots`.
- Tenant authentication placeholder: every guarded endpoint requires the `X-Tenant-ID` header (missing/empty -> 401). A real deployment should swap the dependency for JWT/API-key auth.
- Per-tenant `QuimeraGuardrails` instances are cached on the app and lazily created with `compliance_standards=["LGPD"]` so `policy-check` works out of the box.
- Snapshot/rollback endpoints auto-pick the active or first existing ontology (or auto-create a default) when the caller does not pass `ontology_id`.
- `create_fastapi_app` is re-exported from the package top-level when FastAPI is available; `None` otherwise.
- Phase 5 integration tests pass via `fastapi.testclient.TestClient`: supported/unsupported claim paths, LGPD PII policy block, snapshot/rollback success + 404 on unknown snapshot, proof lookup, tenant header enforcement, and lazy import of the FastAPI module.
- Phase 5 regression passed: `23 passed` for `tests/product/test_phase5_packaging_and_fastapi.py`.
- Full product + GroundCite schema/claim regression passed: `95 passed` (86 product + 9 GroundCite).

## Phase 6: Product Documentation And Research Positioning

### P6-T01: Complete Product Documentation

Status: DONE

Goal: document the runtime architecture and integration patterns so the SDK can be evaluated by technical users without relying on backlog notes.

Subtasks:

- Write an architecture guide.
- Write an integration guide for RAG systems.
- Write an integration guide for agent systems.
- Write a policy and ontology modeling guide.
- Write a proof and audit guide.
- Refresh the root README so it reflects the implemented SDK/runtime surface.
- Run documentation link checks where possible.
- Update this backlog.
- Update `CHANGELOG.md`.

Validation:

- Added `docs/architecture.md`, `docs/integration_rag.md`, `docs/integration_agents.md`, `docs/policy_ontology_modeling.md`, and `docs/proof_audit.md`.
- Rewrote the root `README.md` to describe the current SDK methods, optional FastAPI runtime, local setup, examples, documentation index, and scientific/commercial boundaries.
- Documentation uses conservative positioning: the runtime records evidence-grounded decisions and proof metadata; it does not claim to prove real-world truth or eliminate hallucinations.
- Documentation links were checked with a local Markdown link scanner script.

### P6-T02: Complete Research Positioning And Evaluation Plan

Status: DONE

Goal: define a defensible scientific/commercial evaluation path for ontology-grounded trivalent validation.

Subtasks:

- Draft a research positioning note for ontology-grounded trivalent validation.
- Reuse the GroundCite claims-ledger discipline.
- Define what the product does not prove.
- Create an evaluation plan and benchmark protocol.
- Keep research-only tests separated from product regression gates.
- Run regression tests for product and reference compatibility.
- Update this backlog.
- Update `CHANGELOG.md`.

Validation:

- Added `docs/research_positioning.md` with a narrow, defensible claim: given configured evidence, ontology facts, policy facts, and compliance rules, the runtime can produce auditable trivalent decisions that distinguish support, contradiction, and insufficient evidence.
- Added `docs/evaluation_plan.md` with evaluation axes for claim support, abstention quality, action authorization, policy compliance, and auditability.
- The evaluation plan defines baseline reporting fields including dataset version, ontology version, policy version, proof id, and code commit.
- Research boundaries explicitly reject claims of real-world truth proof, legal compliance without review, hallucination elimination, corpus completeness, and autonomous safety without system-level controls.
- GroundCite research reference tests were adjusted to read vendored dataset and scientific documentation from `data/reference/groundcite_pten` and `docs/reference/groundcite_pten`.
- Legacy import compatibility was restored with packaged `core.*` and old flat-module shims so `tests/reference_quimera_original` now passes.
- Full repository regression now passes with `python -m pytest -q`: `240 passed`.

## Active Portfolio Extension

The original product phases in this master backlog are complete. The current
technical-portfolio work is tracked in `docs/portfolio_backlog.md` and keeps
the runtime focused on RAG, guardrails, EVALs, observability, SDK architecture,
trivalent validation, ontology provenance, and proof replay.

Latest portfolio validation includes adaptive candidate-vs-final context
metrics, the opt-in NVIDIA-first/OpenRouter-fallback LLM benchmark, redacted
provider traces, OTLP-shaped observability export, replay commands, a 60%
coverage gate, focused Ruff/mypy checks, the 96-case threshold sweep, and
the recruiter reproduction audit. The real provider-backed rerun used NVIDIA
for three cases and OpenRouter fallback for one rate-limited case; the full
suite now passes with `247 passed` and product coverage at `67.49%` after the
provider configuration fix.
