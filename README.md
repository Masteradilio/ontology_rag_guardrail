# Quimera Semantic Trust Guardrail

Quimera Semantic Trust Guardrail is an experimental Python SDK/runtime for ontology-grounded semantic trust decisions in LLM, RAG, and agent systems.

This repository is a technical portfolio project focused on RAG, guardrails, EVALs, observability, SDK architecture, trivalent validation, and auditability. It is not presented as a production security boundary, commercial service, or scientific paper result.

The core contract is conservative and auditable: every public check returns a trivalent decision, recommended action, evidence, policy/ontology provenance, and proof metadata.

- `TRUE`: the claim, answer, policy outcome, or action is supported by available evidence or authorization.
- `FALSE`: it is contradicted, denied, or violates an applicable rule.
- `UNDECIDABLE`: support or authorization is insufficient, so the caller should retry, abstain, warn, or escalate.

The product adapts three sources:

- `quimera_guardrails`: input shield, output validation, tenant ontology, compliance rules, adapters, and proof ledger.
- `groundcite_pten`: claim/span-level RAG groundedness evaluation, abstention risk, and reproducibility discipline.
- `quimera_original`: selected technical ideas only: ontology graph, trivalent truth mapping, symbolic validation cascade, and proof ledger patterns.

The old AGI/quantum product framing is intentionally excluded from the product positioning.

## Current Runtime Surface

```python
from quimera_semantic_trust_guardrail import SemanticTrustRuntime

runtime = SemanticTrustRuntime(tenant_id="tenant_a")

decision = runtime.claim_check(
    claim="Refunds are available after 30 days.",
    context={"domain": "support"},
)

print(decision.decision.value, decision.recommended_action.value, decision.proof.proof_id)
```

Supported SDK checks:

- `claim_check`: validates one claim against evidence, ontology, adapter output, compliance context, and policy.
- `answer_check`: decomposes an answer into claims, validates them independently, and aggregates the result.
- `action_check`: validates whether an agent action is semantically and policy-authorized.
- `policy_check`: evaluates compliance rules and tenant policy facts.
- `proof_lookup`: retrieves recorded proof metadata.
- `snapshot_ontology` / `rollback_ontology`: version and restore tenant ontology state with proof linkage.

Optional HTTP runtime:

```powershell
.\.venv\Scripts\pip install -e ".[fastapi]"
.\.venv\Scripts\quimera-serve --host 127.0.0.1 --port 8000
```

Endpoints include `/claim-check`, `/answer-check`, `/action-check`, `/policy-check`, `/proofs/{proof_id}`, and ontology snapshot/rollback endpoints. Guarded endpoints require an `X-Tenant-ID` header as an authentication placeholder.

## Local Setup

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install --upgrade pip
.\.venv\Scripts\pip install -r requirements.txt
.\.venv\Scripts\pip install -e ".[dev]"
.\.venv\Scripts\pip install -e ".[evaluation]"  # optional embedding-backed EVALs
```

Run the regression suite:

```powershell
.\.venv\Scripts\python -m pytest -q
```

Run examples:

```powershell
.\.venv\Scripts\python examples\01_claim_check_basic.py
.\.venv\Scripts\python examples\02_ontology_versioning.py
.\.venv\Scripts\python examples\04_ontology_inspection.py
```

Run the offline portfolio showcase:

```powershell
.\.venv\Scripts\python -m quimera_semantic_trust_guardrail showcase
```

Run the real embedding-backed three-stage RAG benchmark:

```powershell
.\.venv\Scripts\python -m quimera_semantic_trust_guardrail rag-benchmark
```

The benchmark uses `sentence-transformers==5.6.1` with a multilingual local model. It does not require an LLM API key. Provider keys are only needed for explicit optional LLM-assisted evaluation runs.

Run the expanded threshold calibration benchmark:

```powershell
.\.venv\Scripts\python -m quimera_semantic_trust_guardrail rag-threshold-benchmark
```

This uses the committed 96-case, 24-family semisynthetic enterprise corpus
and writes a threshold curve for context precision, recall, F1, and
abstention. The benchmark is offline and does not require an LLM API key. A
reviewer-friendly snapshot is committed under
`docs/benchmarks/rag-enterprise-threshold-20260820`.

Run the opt-in LLM-backed benchmark configured by `.env`:

```powershell
.\.venv\Scripts\python -m quimera_semantic_trust_guardrail rag-llm-benchmark
```

NVIDIA MiniMax M3 is attempted first and paid OpenRouter is used only as a
fallback. The benchmark reports raw LLM decisions separately from the final
evidence-consistency-guarded decisions.

Set `NVIDIA_URL_REFERENCE_MODEL` to the NVIDIA Chat Completions endpoint shown
in `.env.example`; a `build.nvidia.com/.../modelcard` reference is also
normalized automatically for compatibility.

## Repository Layout

```text
src/
  quimera_semantic_trust_guardrail/  # product SDK/runtime
  groundcite/                        # vendored evaluation core from GroundCite-PTEN
  quimera_legacy/                    # selected legacy components for adaptation
  core/                              # compatibility shims for copied legacy reference tests
  docs/
  architecture.md
  integration_rag.md
  integration_agents.md
  policy_ontology_modeling.md
  proof_audit.md
  research_positioning.md
  evaluation_plan.md
  evaluation_guide.md
  portfolio_backlog.md
  benchmarks/                       # committed RAG threshold artifacts
  PRD.md
  MASTER_BACKLOG.md
tests/
  product/
  reference_groundcite/
  reference_quimera_original/
examples/
```

## Documentation

- [Product requirements](docs/PRD.md)
- [Architecture guide](docs/architecture.md)
- [RAG integration guide](docs/integration_rag.md)
- [Agent integration guide](docs/integration_agents.md)
- [Policy and ontology modeling guide](docs/policy_ontology_modeling.md)
- [Proof and audit guide](docs/proof_audit.md)
- [Research positioning note](docs/research_positioning.md)
- [Evaluation plan](docs/evaluation_plan.md)
- [Portfolio scope](docs/portfolio_scope.md)
- [Portfolio backlog](docs/portfolio_backlog.md)
- [Known limitations](docs/known_limitations.md)
- [Portfolio demo walkthrough](docs/demo_walkthrough.md)
- [Three-stage EVAL guide](docs/evaluation_guide.md)
- [Published threshold benchmark](docs/benchmarks/rag-enterprise-threshold-20260820/summary.md)
- [Quimera scientific claims ledger](docs/scientific_claims_ledger_quimera.md)
- [Scientific technical report](docs/scientific_technical_report.md)
- [External research decision](docs/scientific_external_research_decision.md)
- [Commercial ICP and use cases](docs/commercial_icp_use_cases.md)
- [Commercial technical one-pager](docs/commercial_one_pager.md)
- [Commercial pilot proposal template](docs/commercial_pilot_proposal_template.md)
- [Commercial pilot design](docs/commercial_pilot_design.md)
- [Commercial pilot metrics protocol](docs/commercial_pilot_metrics_protocol.md)
- [Commercial pricing and packaging hypotheses](docs/commercial_pricing_packaging_hypotheses.md)
- [Commercial security FAQ](docs/commercial_security_compliance_faq.md)
- [Commercial metrics sheet](docs/commercial_metrics_sheet.md)
- [Commercial integration diagram](docs/commercial_integration_diagram.md)
- [Commercial pilot report template](docs/commercial_pilot_report_template.md)
- [Execution backlog](docs/MASTER_BACKLOG.md)
- [Change history](CHANGELOG.md)

## Scientific And Commercial Boundaries

Quimera estimates whether a runtime decision is supported, contradicted, authorized, or underdetermined by configured evidence, ontology, and policy. It does not prove real-world truth, replace legal judgment, or eliminate hallucinations. The defensible value proposition is audit-ready semantic governance for AI systems that need explicit abstention and reproducible proof records.
