# Commercial And Scientific Validation Backlog

This backlog prepares the next two validation tracks for Quimera Semantic Trust Guardrail:

- scientific validation: evidence that the runtime behaves as claimed under controlled conditions;
- commercial validation: evidence that the product solves urgent enterprise workflows with acceptable integration effort.

## Recommended Order

Start with scientific validation, then run commercial validation on top of the scientific evidence package.

Reasoning:

- The product's main differentiator is trust: ontology-grounded trivalent validation with proof records. Commercial claims will be stronger if the team can first show controlled evidence for `TRUE`, `FALSE`, and `UNDECIDABLE` behavior.
- The GroundCite lineage makes overclaim risk material. A scientific baseline reduces the chance of selling unsupported "hallucination elimination" claims.
- Enterprise buyers will still care about business value, but they will ask for auditability, failure modes, and evidence. The scientific track produces the artifacts needed for those conversations.

The two tracks should not be isolated for months. The sequence should be:

1. Build the scientific evidence harness and baseline.
2. Use its artifacts to run commercial workflow pilots.
3. Feed commercial workflow failures back into the benchmark.
4. Repeat until both evidence and buyer value are clear.

## LLM Provider Policy

Use the `.env` configuration without committing secrets.

Priority order:

1. NVIDIA API for MiniMax M3.
   - Primary provider because it is free.
   - Expected environment variables:
     - `NVIDIA_LLM_MODEL`
     - `NVIDIA_URL_REFERENCE_MODEL`
     - `NVIDIA_API_KEY`
2. OpenRouter API for MiniMax M3.
   - Paid fallback only.
   - Expected environment variables:
     - `OPENROUTER_LLM_MODEL`
     - `OPENROUTER_API_KEY`

Provider behavior rules:

- Never print API keys in logs, reports, tests, or proof records.
- Record provider name, model name, request id when available, latency, and failure mode.
- Do not treat provider outage as model failure; record it as infrastructure/provider unavailable.
- Use deterministic settings where supported: low temperature, fixed seed if available, stable prompts, and pinned model names.
- Cache raw request/response payloads only in local ignored artifacts with redacted secrets and tenant-safe sample data.
- Prefer offline/local deterministic tests for regression gates; use LLM providers for evaluation runs, judge-assisted labeling, and stress tests where explicitly needed.

## Phase S0: Evaluation Infrastructure

Status: DONE

Goal: create a reproducible evaluation harness that can call NVIDIA first and OpenRouter only as fallback.

### S0-T01: Provider Adapter Contract

Subtasks:

- Define a minimal internal LLM client interface: `generate`, `provider_name`, `model_name`, `usage`, `latency_ms`, and `failure`.
- Implement NVIDIA MiniMax M3 provider using `NVIDIA_URL_REFERENCE_MODEL`, `NVIDIA_LLM_MODEL`, and `NVIDIA_API_KEY`.
- Implement OpenRouter MiniMax M3 provider using `OPENROUTER_LLM_MODEL` and `OPENROUTER_API_KEY`.
- Add fallback orchestration: NVIDIA first, OpenRouter second only on configured failures.
- Add timeout, retry, and backoff configuration.
- Add tests with mocked providers for success, NVIDIA failure/OpenRouter fallback, both providers failure, and secret redaction.

Acceptance criteria:

- Provider fallback is deterministic and tested without real API calls.
- Real API calls are behind an explicit opt-in marker or script flag.
- Logs never include API key values.

Validation:

- Added `quimera_semantic_trust_guardrail.evaluation.llm_providers` with `NVIDIAProvider`, `OpenRouterProvider`, `FallbackLLMClient`, secret redaction, and `.env` parsing.
- Tests cover NVIDIA-first success, NVIDIA failure with OpenRouter fallback, all-providers failure, env var mapping, and secret redaction without real API calls.

### S0-T02: Evaluation Artifact Layout

Subtasks:

- Create ignored artifact directories for evaluation outputs, for example `artifacts/evaluation/`.
- Define JSONL schemas for run metadata, per-sample result, provider trace, proof trace, and summary metrics.
- Include commit sha, dataset version, ontology version, policy version, provider, model, and runtime config.
- Add a script that creates a timestamped run directory.
- Add validation tests for artifact schema.

Acceptance criteria:

- A run can be reproduced from committed code plus recorded config metadata.
- Generated artifacts remain out of Git unless intentionally promoted as sanitized examples.

Validation:

- Added `quimera_semantic_trust_guardrail.evaluation.artifacts` with pydantic schemas for run metadata, provider traces, sample results, proof traces, and summary metrics.
- Added `artifacts/` to `.gitignore`.
- Tests cover run directory creation, JSONL artifact writing, and the `quimera scientific-baseline` CLI path.

### S0-T03: Baseline Dataset Selection

Subtasks:

- Select a first controlled dataset from vendored GroundCite samples.
- Define a small product-specific agent-action dataset.
- Define a small policy/compliance dataset with LGPD/custom-policy examples.
- Freeze dataset ids, splits, and expected labels.
- Document what each dataset can and cannot support scientifically.

Acceptance criteria:

- Dataset card exists for the first benchmark package.
- Unsupported, contradicted, and undecidable examples are explicitly represented.

Validation:

- Added `data/evaluation/scientific_seed/README.md`, `manifest.json`, `claim_answer_seed.jsonl`, `agent_action_seed.jsonl`, and `policy_seed.jsonl`.
- Tests verify manifest loading, sample counts, label distributions, and coverage of `TRUE`, `FALSE`, `UNDECIDABLE`, `partially_unsupported`, and `missing_authorization`.

## Phase S1: Scientific Validation Baseline

Status: DONE

Goal: produce a defensible baseline for ontology-grounded trivalent validation.

### S1-T01: Claim And Answer Evaluation

Subtasks:

- Run `claim_check` on controlled supported, contradicted, unsupported, and partially unsupported claims.
- Run `answer_check` on multi-claim RAG answers.
- Measure trivalent confusion matrix, false allow rate, false block rate, unsupported-to-undecidable rate, and contradiction detection rate.
- Compare runtime decisions against GroundCite labels using the conservative mapping.
- Store proof ids and verify proof lookup for sampled cases.

Acceptance criteria:

- Results separate `unsupported` from `contradicted`.
- Every reported metric links to dataset version and code commit.
- At least one failure analysis table is produced.

Validation:

- Added `quimera_semantic_trust_guardrail.evaluation.scientific_baseline.run_scientific_baseline`.
- The deterministic seed baseline writes `metadata.json`, `sample_results.jsonl`, `summary.json`, and `failure_analysis.json`.
- Tests verify reproducible artifacts, task coverage, trivalent output coverage, summary metrics, and explicit failure analysis.

### S1-T02: Abstention Quality Evaluation

Subtasks:

- Define cases where abstention is expected.
- Measure whether `UNDECIDABLE` maps to `abstain`, `retry`, `warn`, or `escalate` as intended.
- Track over-abstention cases where enough evidence existed.
- Track under-abstention cases where unsupported answers were allowed.
- Evaluate behavior with and without retrieved evidence.

Acceptance criteria:

- The report quantifies useful abstention and harmful abstention separately.
- No claim is made that abstention eliminates hallucinations.

Validation:

- The deterministic baseline summary records `useful_abstention_rate` and `harmful_abstention_rate`.
- Seed data includes unsupported, partially unsupported, missing authorization, and wrong-tenant cases.
- The summary limitations explicitly state that the seed does not estimate hallucination elimination.
- Focused S0/S1 regression passed: `14 passed`.
- Full repository regression passed after S0/S1 implementation: `204 passed`.

### S1-T03: Agent Action Authorization Evaluation

Subtasks:

- Build a controlled set of agent tool-call scenarios.
- Include allowed, denied, missing-authorization, wrong-purpose, wrong-tenant, and stale-policy cases.
- Run `action_check` and record proof metadata.
- Measure false allow, false deny, and undecidable authorization rate.
- Verify tenant isolation across action checks.

Acceptance criteria:

- Missing authorization defaults to `UNDECIDABLE` unless an explicit deny policy applies.
- At least one audit trace reconstructs why a tool call was allowed or blocked.

Validation:

- The seed runner creates controlled tenant policy facts for allow and deny cases.
- The action seed covers allowed, denied, missing-authorization, and wrong-tenant scenarios.
- Each sample result includes proof metadata and decision path.

### S1-T04: Policy And Compliance Evaluation

Subtasks:

- Build test cases for LGPD, AI Act-style, and custom tenant policy rules.
- Run `policy_check` for input, output, and action scopes.
- Measure policy violation detection and policy provenance completeness.
- Test conflicting policy facts and ontology version changes.
- Validate proof chain after snapshot and rollback.

Acceptance criteria:

- Reports distinguish compliance-rule evidence from legal conclusions.
- Rollback and snapshot decisions preserve audit linkage.

Validation:

- The policy seed covers LGPD, custom policy violation, allowed text, and an intentionally undecidable policy expectation.
- Baseline artifacts preserve policy/compliance disagreements in `failure_analysis.json` instead of hiding them.
- Snapshot/rollback proof linkage remains covered by Phase 3 product tests; this S1 baseline focuses on policy decision behavior.

## Phase S2: Scientific Reporting Package

Status: DONE

Goal: turn baseline runs into a conservative scientific evidence package.

### S2-T01: Scientific Claims Ledger For Quimera

Subtasks:

- Create a Quimera-specific claims ledger.
- Classify each claim as supported, preliminary, blocked, engineering-only, or remove.
- Link each supported claim to code, tests, datasets, or run artifacts.
- Add a forbidden-claims section: hallucination elimination, legal proof, real-world truth proof, and autonomous safety guarantee.
- Add a test or review checklist to prevent public overclaims.

Acceptance criteria:

- Every public-facing claim has evidence status.
- Unsupported claims are either blocked or removed.

Validation:

- Added `docs/scientific_claims_ledger_quimera.md`.
- Claims are classified as `supported`, `preliminary`, `blocked`, `engineering_only`, or `remove`.
- Forbidden claims include real-world truth proof, hallucination elimination, legal compliance certification, autonomous safety, and production accuracy from the seed dataset.

### S2-T02: Technical Report Draft

Subtasks:

- Write an internal technical report with method, datasets, metrics, results, limitations, and failure analysis.
- Include proof ledger reconstruction examples.
- Include provider availability and fallback behavior.
- Separate deterministic runtime tests from LLM-assisted evaluation runs.
- Include a reproducibility checklist.

Acceptance criteria:

- Report is draft-ready for technical reviewers.
- It clearly states that Quimera validates support under configured evidence/policy, not global truth.

Validation:

- Added `docs/scientific_technical_report.md`.
- The report records the deterministic seed baseline: 12 samples, 11 correct decisions, false allow rate 0.0833, false block rate 0.0, useful abstention rate 0.8, harmful abstention rate 0.0.
- The report explicitly records `policy-undecidable-001` as a false allow and product-hardening target.

### S2-T03: External Research Decision

Subtasks:

- Decide whether the evidence supports a workshop paper, technical blog, whitepaper, or only internal note.
- Identify missing experiments before public submission.
- Define ethical and legal review needs for benchmark publication.
- Define artifact release policy for datasets, prompts, and proof logs.

Acceptance criteria:

- Clear go/no-go decision for public scientific positioning.
- No public claim depends only on anecdotal demos.

Validation:

- Added `docs/scientific_external_research_decision.md`.
- Current decision: do not submit a formal paper yet; prepare an internal technical note and only a conservative technical blog or whitepaper after benchmark expansion.
- Added product tests for the S2 reporting package and conservative-claim guardrails.
- Focused S2 reporting regression passed: `5 passed`.
- Full repository regression passed after S2 implementation: `209 passed`.

## Phase C0: Commercial Discovery Preparation

Status: DONE

Goal: convert the scientific evidence package into buyer-facing hypotheses and pilot workflows.

### C0-T01: ICP And Use Case Selection

Subtasks:

- Select 2-3 initial ideal customer profiles:
  - AI platform teams deploying enterprise RAG.
  - SaaS teams embedding agent tool calls.
  - compliance/risk teams auditing LLM decisions.
- Choose one workflow per ICP.
- Define pain, current workaround, buyer, user, budget owner, and urgency.
- Define what Quimera must prove in a pilot.

Acceptance criteria:

- Each ICP has a concrete workflow and measurable pain.
- No ICP depends on broad "trust AI" messaging.

Validation:

- Added `docs/commercial_icp_use_cases.md` with three ICPs: enterprise RAG platform teams, SaaS agent teams, and compliance/risk teams.
- Each ICP includes buyer, users, pain, current workaround, workflow, and pilot success criteria.

### C0-T02: Demo Dataset And Script

Subtasks:

- Build safe synthetic demo data for support RAG, agent authorization, and compliance review.
- Create a deterministic demo script using local runtime paths.
- Add optional LLM-assisted demo mode using NVIDIA first and OpenRouter fallback.
- Capture proof lookup and ontology versioning in the demo.
- Add a failure-mode demo showing `UNDECIDABLE` as a useful outcome.

Acceptance criteria:

- Demo can run without external APIs.
- LLM mode is optional and records provider fallback transparently.

Validation:

- Added `quimera_semantic_trust_guardrail.evaluation.commercial_demo.run_commercial_demo`.
- Added `quimera commercial-demo` CLI with deterministic offline default and optional `--use-llm`.
- Demo covers RAG answer approval, agent refund authorization, missing authorization, policy/compliance review, proof ids, and ontology snapshot metadata.

### C0-T03: Buyer Evidence Pack

Subtasks:

- Prepare a concise technical one-pager.
- Prepare a security/compliance FAQ.
- Prepare an integration diagram for RAG and agents.
- Prepare a metrics sheet using scientific baseline results.
- Prepare a pilot proposal template with success criteria.

Acceptance criteria:

- Buyer-facing materials use only claims allowed by the scientific claims ledger.
- The value proposition is audit-ready semantic governance, not generic hallucination elimination.

Validation:

- Added `docs/commercial_one_pager.md`, `docs/commercial_security_compliance_faq.md`, `docs/commercial_pilot_proposal_template.md`, `docs/commercial_metrics_sheet.md`, and `docs/commercial_integration_diagram.md`.
- Added product tests that enforce conservative commercial wording and run the offline commercial demo/CLI.
- Focused C0 commercial discovery regression passed: `3 passed`.
- Full repository regression passed after C0 implementation: `212 passed`.

## Phase C1: Commercial Pilot Validation

Status: DONE

Goal: test whether real buyers value the product enough to pilot or pay.

### C1-T01: Workflow Pilot Design

Subtasks:

- Define a 2-week pilot scope for RAG answer approval.
- Define a 2-week pilot scope for agent tool-call authorization.
- Define a 2-week pilot scope for policy/compliance audit.
- For each pilot, define input data, integration points, success metrics, and exit criteria.
- Define legal/security constraints for customer data handling.

Acceptance criteria:

- Each pilot can be run with synthetic data first and customer data only after approval.
- Success metrics are measurable in runtime logs and proof artifacts.

Validation:

- Added `docs/commercial_pilot_design.md` with 2-week pilot scopes for RAG answer approval, agent tool-call authorization, and policy/compliance audit.
- Added `quimera_semantic_trust_guardrail.evaluation.commercial_pilot.default_pilot_scopes`.
- Pilot scopes include input data, integration points, success metrics, exit criteria, and security constraints.

### C1-T02: Pilot Metrics

Subtasks:

- Measure setup time.
- Measure false allow rate and false block rate against customer-reviewed labels.
- Measure useful abstention rate.
- Measure audit reconstruction time before and after Quimera.
- Measure developer integration friction.
- Measure whether proof records satisfy compliance/risk reviewers.

Acceptance criteria:

- Pilot report separates product value from implementation friction.
- Results include both positive outcomes and blockers.

Validation:

- Added `PilotReviewSample`, `PilotMetrics`, `compute_pilot_metrics`, and `write_default_pilot_package`.
- Added `docs/commercial_pilot_metrics_protocol.md` and `docs/commercial_pilot_report_template.md`.
- Tests cover useful abstention, false allow, proof lookup success, setup hours, audit reconstruction delta, reviewer usefulness, and blockers.

### C1-T03: Pricing And Packaging Hypotheses

Subtasks:

- Test pricing anchors:
  - SDK/runtime license.
  - enterprise audit/proof module.
  - managed evaluation package.
  - per-tenant or per-decision usage tier.
- Identify which buyers prefer self-hosted vs managed.
- Identify must-have enterprise requirements: SSO, RBAC, audit export, data residency, and SLA.
- Estimate cost of LLM provider usage for optional evaluation features.

Acceptance criteria:

- At least one pricing/package hypothesis is backed by buyer feedback.
- Paid OpenRouter fallback cost is explicitly modeled and not hidden in margins.

Validation:

- Added `docs/commercial_pricing_packaging_hypotheses.md`.
- Pricing remains explicitly marked as hypotheses, not validated pricing.
- The provider cost rule states NVIDIA first and paid OpenRouter fallback must be explicitly modeled.
- Focused C1 commercial pilot regression passed: `5 passed`.
- Full repository regression passed after C1 implementation: `217 passed`.

## Phase C2: Productization Decision

Status: TODO

Goal: decide whether to invest in a product release, research release, or narrower consulting/evaluation offer.

### C2-T01: Evidence Review

Subtasks:

- Review scientific baseline, commercial pilot outcomes, and integration blockers.
- Identify which claims are supported commercially and scientifically.
- Identify missing features blocking paid deployment.
- Identify which workflows should be cut from the first product offer.

Acceptance criteria:

- Decision memo recommends one path: SDK product, hosted service, evaluation toolkit, consulting pilot, or pause.

### C2-T02: Release Roadmap

Subtasks:

- Convert validated needs into engineering backlog.
- Prioritize only features tied to evidence or buyer pull.
- Define release criteria for version `0.1.0` or `0.2.0`.
- Define documentation, examples, and security review requirements.
- Define support and maintenance expectations.

Acceptance criteria:

- Roadmap is shorter than the discovery backlog and focused on validated demand.
- Public claims remain aligned with the claims ledger and evaluation evidence.

## Global Validation Gates

Before claiming the commercial/scientific phase is complete:

- `python -m pytest -q` passes.
- Provider fallback tests pass without real API calls.
- At least one opt-in real provider smoke run succeeds or records a provider-unavailable artifact.
- Scientific claims ledger is updated.
- Commercial pilot materials cite only supported or preliminary claims.
- `docs/MASTER_BACKLOG.md` and `CHANGELOG.md` are updated when implementation work is completed.
- `git status --short --branch` is reviewed before closeout.
