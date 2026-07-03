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
- Quimera original reference tests are copied but still need import-path adaptation; current legacy test collection fails on direct old import `from truth_mapping import ...`.

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

Status: TODO

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

### P1-T02: Unify Semantic Fact And Ontology Model

Status: TODO

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

### P1-T03: Fix Knowledge Adapter Contract

Status: TODO

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

### P1-T04: Fix OntologySync Integration

Status: TODO

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

## Phase 2: Runtime APIs

### P2-T01: Implement `claim_check`

Status: TODO

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

### P2-T02: Implement `answer_check`

Status: TODO

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

### P2-T03: Implement `action_check`

Status: TODO

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

### P2-T04: Implement `policy_check`

Status: TODO

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

## Phase 3: Proof And Audit Hardening

### P3-T01: Enrich Proof Ledger Schema

Status: TODO

Goal: record enough metadata to reproduce semantic decisions.

Subtasks:

- Add ontology version, adapter source, evidence ids, policy ids, and decision path.
- Preserve hash chain verification.
- Add proof lookup API.
- Add chain integrity tests.
- Run regression tests for proof ledger.
- Update this backlog.
- Update `CHANGELOG.md`.

### P3-T02: Add Ontology Versioning

Status: TODO

Goal: support snapshots, diffs, and rollback for semantic knowledge.

Subtasks:

- Adapt legacy snapshot/diff ideas.
- Track tenant ontology versions.
- Add migration records.
- Add tests for snapshot, diff, rollback, and proof linkage.
- Run regression tests for versioning.
- Update this backlog.
- Update `CHANGELOG.md`.

## Phase 4: Evaluation And Regression Harness

### P4-T01: Adapt GroundCite Regression Suite

Status: TODO

Goal: convert selected GroundCite tests into product regression tests.

Subtasks:

- Move useful reference tests from `tests/reference_groundcite`.
- Adapt imports and fixtures.
- Keep research-only tests separated.
- Add product-level quality gates for claim support and abstention.
- Run regression tests.
- Update this backlog.
- Update `CHANGELOG.md`.

### P4-T02: Add Product Smoke Tests

Status: TODO

Goal: verify the product package works from a clean install.

Subtasks:

- Test import of main package.
- Test import of vendored GroundCite package.
- Test import of selected legacy modules.
- Test a minimal `claim_check` once implemented.
- Run regression tests.
- Update this backlog.
- Update `CHANGELOG.md`.

## Phase 5: Packaging And Deployment

### P5-T01: Package The SDK

Status: TODO

Goal: make the project installable as an SDK.

Subtasks:

- Finalize package metadata.
- Add console scripts if needed.
- Add examples.
- Add installation tests in venv.
- Run regression tests.
- Update this backlog.
- Update `CHANGELOG.md`.

### P5-T02: Add Optional FastAPI Runtime

Status: TODO

Goal: expose runtime checks as HTTP endpoints.

Subtasks:

- Add `/claim-check`.
- Add `/answer-check`.
- Add `/action-check`.
- Add `/proofs/{proof_id}`.
- Add tenant authentication placeholders.
- Add integration tests.
- Run regression tests.
- Update this backlog.
- Update `CHANGELOG.md`.

## Phase 6: Documentation And Commercial Readiness

### P6-T01: Product Documentation

Status: TODO

Goal: document the product as a semantic trust guardrail.

Subtasks:

- Write architecture guide.
- Write integration guide for RAG.
- Write integration guide for agents.
- Write policy and ontology modeling guide.
- Write proof/audit guide.
- Run documentation link checks where possible.
- Update this backlog.
- Update `CHANGELOG.md`.

### P6-T02: Research Positioning

Status: TODO

Goal: preserve scientific defensibility.

Subtasks:

- Draft a research note on ontology-grounded trivalent validation.
- Reuse GroundCite claims ledger discipline.
- Define what the product does not prove.
- Create evaluation plan and benchmark protocol.
- Run regression tests for evaluation scripts.
- Update this backlog.
- Update `CHANGELOG.md`.

## Current Immediate Next Tasks

1. Finish Phase 0 setup.
2. Run import smoke tests in the new venv.
3. Commit and push the prepared repository.
4. Start Phase 1 by defining the unified decision model.
