# Quimera Semantic Trust Guardrail

Quimera Semantic Trust Guardrail is a Python SDK/runtime for enterprise semantic trust decisions in LLM, RAG, and agent systems.

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
.\.venv\Scripts\pip install -e .
```

Run the regression suite:

```powershell
.\.venv\Scripts\python -m pytest -q
```

Run examples:

```powershell
.\.venv\Scripts\python examples\01_claim_check_basic.py
.\.venv\Scripts\python examples\02_ontology_versioning.py
```

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
- [Quimera scientific claims ledger](docs/scientific_claims_ledger_quimera.md)
- [Scientific technical report](docs/scientific_technical_report.md)
- [External research decision](docs/scientific_external_research_decision.md)
- [Commercial ICP and use cases](docs/commercial_icp_use_cases.md)
- [Commercial technical one-pager](docs/commercial_one_pager.md)
- [Commercial pilot proposal template](docs/commercial_pilot_proposal_template.md)
- [Execution backlog](docs/MASTER_BACKLOG.md)
- [Change history](CHANGELOG.md)

## Scientific And Commercial Boundaries

Quimera estimates whether a runtime decision is supported, contradicted, authorized, or underdetermined by configured evidence, ontology, and policy. It does not prove real-world truth, replace legal judgment, or eliminate hallucinations. The defensible value proposition is audit-ready semantic governance for AI systems that need explicit abstention and reproducible proof records.
