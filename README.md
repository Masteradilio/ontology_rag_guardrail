# Quimera Semantic Trust Guardrail

Quimera Semantic Trust Guardrail is the new product workspace for an enterprise semantic trust runtime for LLM, RAG, and agentic systems.

The product goal is to provide auditable trivalent validation for semantic decisions:

- `TRUE`: the claim, answer, plan, or action is supported and allowed.
- `FALSE`: it is contradicted, disallowed, or violates policy.
- `UNDECIDABLE`: evidence or authorization is insufficient, so the system should abstain, ask for clarification, retry with guidance, or escalate to human review.

This repository starts from three reference codebases:

- `quimera_guardrails`: input shield, output validator, tenant ontology, compliance checks, adapters, and proof ledger.
- `groundcite_pten`: claim/span-level RAG groundedness evaluation, abstention risk, and reproducibility discipline.
- `quimera_original`: selected legacy ideas only: graph ontology, structured hypothesis parsing, symbolic validation cascade, and proof ledger patterns.

The AGI/quantum framing from the old project is intentionally not part of this product positioning.

## Initial Layout

```text
src/
  quimera_semantic_trust_guardrail/  # current guardrail codebase copied as the first product core
  groundcite/                        # vendored evaluation core from GroundCite-PTEN
  quimera_legacy/                    # selected legacy components for adaptation
docs/
  PRD.md
  MASTER_BACKLOG.md
  README_quimera_guardrail.md
  reference/
data/
  reference/
tests/
  reference_groundcite/
  reference_quimera_original/
```

## Next Product Direction

The first implementation milestone is to converge the copied components into a coherent runtime API:

- `claim_check`
- `answer_check`
- `action_check`
- `plan_check`
- `policy_check`
- `proof_lookup`

Each decision must include evidence, ontology version, policy/rule provenance, and a proof id.

## Local Setup

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install --upgrade pip
.\.venv\Scripts\pip install -r requirements.txt
.\.venv\Scripts\pip install -e .
```

## Source References

- Original guardrail README snapshot: `docs/README_quimera_guardrail.md`
- Product PRD: `docs/PRD.md`
- Execution backlog: `docs/MASTER_BACKLOG.md`
- Change history: `CHANGELOG.md`
