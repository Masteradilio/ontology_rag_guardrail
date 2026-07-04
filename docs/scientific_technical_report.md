# Quimera Scientific Technical Report

Status: internal technical note, draft-ready for engineering review.

## Summary

Quimera Semantic Trust Guardrail implements ontology-grounded trivalent validation for claim, answer, action, and policy checks. The current scientific package validates the runtime contract on a small synthetic seed dataset and records reproducible artifacts for each run.

The current evidence supports a narrow claim: under configured evidence, ontology facts, policy facts, and compliance rules, Quimera can produce auditable `TRUE`, `FALSE`, and `UNDECIDABLE` decisions with proof metadata.

It does not support claims of real-world truth, legal certification, or hallucination elimination.

## Method

The deterministic seed baseline is run with:

```powershell
.\.venv\Scripts\python -m quimera_semantic_trust_guardrail scientific-baseline --output-dir artifacts/evaluation --run-id <run-id>
```

The runner uses:

- `data/evaluation/scientific_seed/manifest.json`
- `data/evaluation/scientific_seed/claim_answer_seed.jsonl`
- `data/evaluation/scientific_seed/agent_action_seed.jsonl`
- `data/evaluation/scientific_seed/policy_seed.jsonl`
- `quimera_semantic_trust_guardrail.evaluation.scientific_baseline.run_scientific_baseline`

The run writes:

- `metadata.json`
- `sample_results.jsonl`
- `summary.json`
- `failure_analysis.json`

Generated artifacts are local and ignored by Git under `artifacts/`.

## Dataset

The seed package contains 12 synthetic samples:

- 4 claim/answer validation samples.
- 4 agent action authorization samples.
- 4 policy/compliance samples.

Labels include:

- supported;
- contradicted;
- unsupported;
- partially unsupported;
- allow;
- deny;
- missing authorization;
- wrong tenant;
- policy allow;
- policy violation;
- policy undecidable.

The seed is intentionally small. It validates runtime behavior and reporting discipline. It does not estimate production RAG accuracy.

## Current Baseline Result

Local S2 documentation run:

- Run id: `s2-doc-baseline`
- Samples: 12
- Correct decisions: 11
- Accuracy on seed: 0.9167
- False allow rate: 0.0833
- False block rate: 0.0
- Useful abstention rate: 0.8
- Harmful abstention rate: 0.0

The result includes all three trivalent states:

- observed `TRUE`: 4
- observed `FALSE`: 4
- observed `UNDECIDABLE`: 4

## Failure Analysis

The current failure is:

| Sample | Expected | Observed | Decision path | Interpretation |
| --- | --- | --- | --- | --- |
| `policy-undecidable-001` | `UNDECIDABLE` | `TRUE` | `policy:allowed` | The current clean-path policy check treats absence of a blocking rule as allow. This is acceptable for some low-risk text checks, but it is too permissive for an intentionally undecidable policy case. |

This is a product-hardening target before stronger scientific or commercial claims about policy uncertainty.

## Proof And Audit Evidence

Each sample result includes:

- sample id;
- expected label;
- observed decision;
- recommended action;
- correctness;
- proof id;
- decision path;
- ontology version where applicable.

The current seed runner uses local proof metadata. Phase 3 tests continue to cover proof recorder chain integrity, ontology snapshots, rollback, and proof lookup behavior.

## Provider Availability

The deterministic seed baseline does not call external LLM providers.

For opt-in LLM-assisted evaluation:

- NVIDIA MiniMax M3 is the primary provider.
- OpenRouter MiniMax M3 is fallback only.
- Tests use fake providers and do not consume API budget.
- Provider outage must be recorded as provider availability, not model quality.

## Limitations

- The seed dataset is synthetic and small.
- The baseline is not a comparative benchmark against other guardrail systems.
- The current policy clean path can false-allow an intentionally undecidable policy case.
- The runner does not yet evaluate broad external corpora or customer workflows.
- The current baseline does not establish legal compliance.
- The current baseline does not establish production hallucination reduction.

## Reproducibility Checklist

- Record code commit.
- Record dataset package id and version.
- Record ontology and policy versions.
- Record provider name and model only for opt-in LLM runs.
- Keep generated artifacts under ignored `artifacts/evaluation/`.
- Promote only sanitized aggregate results into committed documentation.
- Update the claims ledger before using new public claims.

## Next Scientific Work

1. Add policy uncertainty controls so absence of a blocking rule can be configured as `UNDECIDABLE` for high-risk scopes.
2. Expand the seed into a larger benchmark with frozen splits.
3. Run comparative baselines for binary guardrails versus trivalent decisions.
4. Add natural RAG samples beyond synthetic examples.
5. Produce a benchmark card only after the dataset is large enough to support public claims.
