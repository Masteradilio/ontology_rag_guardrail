# Ontology RAG Guardrail Scientific Claims Ledger

This ledger controls scientific and technical claims for Ontology RAG Guardrail. Public material should use only claims marked `supported` or carefully framed `preliminary`.

## Claim Status Legend

- `supported`: backed by committed code, tests, docs, or reproducible local artifacts.
- `preliminary`: plausible but needs broader datasets, external validation, or customer evidence.
- `blocked`: not currently supported and should not be used until evidence changes.
- `engineering_only`: useful implementation work, but not a scientific contribution by itself.
- `remove`: unsafe or misleading claim.

## Claims

| Claim | Status | Evidence | Source file/script | Public? | Required wording |
| --- | --- | --- | --- | --- | --- |
| Ontology RAG Guardrail returns auditable trivalent runtime decisions for claim, answer, action, and policy checks. | supported | Runtime APIs, decision model tests, proof metadata, full regression suite. | `src/quimera_semantic_trust_guardrail/runtime.py`, `tests/product/`, `docs/MASTER_BACKLOG.md` | yes | Say "runtime decisions under configured evidence, ontology, and policy." |
| Ontology RAG Guardrail distinguishes unsupported claims from contradicted claims in controlled cases. | supported | GroundCite mapping, Phase 2 tests, scientific seed baseline. | `src/quimera_semantic_trust_guardrail/decision_model.py`, `tests/product/test_phase_s1_scientific_baseline.py` | yes | Say "controlled cases"; do not generalize to all RAG corpora. |
| Ontology RAG Guardrail can default missing action authorization to `UNDECIDABLE` with escalation. | supported | Phase 2 action tests and scientific seed action cases. | `tests/product/test_phase2_runtime_api.py`, `data/evaluation/scientific_seed/agent_action_seed.jsonl` | yes | Say "when no explicit matching policy is configured." |
| Ontology RAG Guardrail records proof metadata and decision paths for runtime checks. | supported | Proof recorder, runtime proof metadata, Phase 3 tests, S1 sample artifacts. | `src/quimera_semantic_trust_guardrail/proof_recorder.py`, `tests/product/test_phase3_proof_and_ontology_versioning.py` | yes | Say "audit metadata"; not "independent truth proof." |
| The deterministic seed baseline produced 11 correct decisions over 12 synthetic samples. | supported | S1 runner and local artifact summary from `quimera scientific-baseline`. | `src/quimera_semantic_trust_guardrail/evaluation/scientific_baseline.py`, `data/evaluation/scientific_seed/` | yes, cautiously | Always state the sample count and synthetic nature. |
| The current seed baseline exposes one policy false allow on an intentionally undecidable policy case. | supported | `policy-undecidable-001` expected `UNDECIDABLE`, observed `TRUE`. | `data/evaluation/scientific_seed/policy_seed.jsonl`, `failure_analysis.json` from local S1 run | yes | Report as a limitation and product-hardening target. |
| NVIDIA MiniMax M3 is the primary LLM provider and OpenRouter MiniMax M3 is fallback for opt-in evaluation runs. | supported | Provider fallback contract and tests. | `src/quimera_semantic_trust_guardrail/evaluation/llm_providers.py`, `tests/product/test_phase_s0_evaluation_infrastructure.py` | yes | Say "provider policy for opt-in evaluation"; not product dependency. |
| Ontology RAG Guardrail improves enterprise AI auditability in production. | preliminary | Architecture and proof ledger support the hypothesis; needs buyer workflow pilots. | `docs/proof_audit.md`, `docs/comercial_cientific_backlog.md` | yes, cautiously | Say "designed to improve" until pilot evidence exists. |
| Ontology RAG Guardrail reduces unsupported answer exposure compared with binary guardrails. | preliminary | Trivalent abstention design and seed behavior support a research hypothesis; comparative benchmark is not done. | `docs/evaluation_plan.md`, S1 seed baseline | no for strong claims | Phrase as a research question until comparative runs exist. |
| Ontology RAG Guardrail proves real-world truth. | remove | The system validates support under configured evidence, not truth in the world. | `docs/research_positioning.md` | no | Do not use. |
| Ontology RAG Guardrail eliminates hallucinations. | remove | No evidence supports elimination; unsupported cases still depend on corpus and policy coverage. | S1 baseline limitations | no | Do not use. |
| Ontology RAG Guardrail provides legal compliance certification. | remove | Compliance rules are runtime checks, not legal review. | `docs/policy_ontology_modeling.md`, `docs/scientific_technical_report.md` | no | Do not use. |
| The seed baseline is evidence of production accuracy. | blocked | Dataset is synthetic and intentionally small. | `data/evaluation/scientific_seed/README.md` | no | Use only as engineering/scientific seed evidence. |

## Forbidden Public Claims

Do not claim that Ontology RAG Guardrail:

- proves real-world truth;
- eliminates hallucinations;
- certifies legal compliance;
- makes autonomous agents safe by itself;
- replaces human review in high-risk workflows;
- has production accuracy based only on the seed dataset.

## Review Checklist

Before publishing a paper, blog post, sales deck, README change, or benchmark card:

- Every claim maps to a row in this ledger.
- Unsupported and contradicted are kept separate.
- `UNDECIDABLE` is described as a useful operational state, not as a failure.
- Dataset size, synthetic/natural status, and limitations are explicit.
- Provider outages are reported as provider availability, not model quality.
- Proof metadata is described as audit evidence, not proof of global truth.
