# GroundCite-Bench Benchmark Card

## Goal

GroundCite-Bench measures whether RAG evaluators identify support, missing support, and contradiction relative to provided evidence at claim and span level.

## Evaluation Units

- Sample-level RAG answer.
- Claim-level labels.
- Character-level evidence spans.
- Character-level unsupported answer spans.

## Required Dataset Provenance

Every result table must report:

- dataset file;
- SHA-256 hash;
- sample count;
- claim count;
- split;
- language distribution;
- annotation status;
- generation/import script;
- dependency versions;
- adapter mode for external baselines.

The canonical summary file is:

```text
data/samples/groundcite_bench_summary.json
```

## Metrics

- Macro-F1 over `supported`, `unsupported`, and `contradicted`.
- Precision/recall by class.
- AUPRC/AUROC for unsupported or failure detection when confidence scores are defined.
- Evidence span overlap where spans exist.
- Abstention risk.
- Expected Calibration Error when confidence semantics and bins are documented.
- Conformal empirical coverage when prediction sets are generated.
- Cost and latency.

Kappa between model predictions and gold labels must be described as model-gold agreement, not IAA. IAA requires independent human labels.

## Required Baselines

Final paper experiments should include:

- Lexical baseline.
- Local NLI baseline.
- Judge-only baseline.
- GroundCite hybrid backend.
- Ragas with real dependency execution.
- DeepEval with real dependency execution.

Mock/fallback baselines are allowed only for local smoke tests and CI. They must not appear in main paper tables.

The strict baseline readiness report is:

```text
experiments/exp07_meta_evaluation/results/strict_baseline_check.json
```

If `paper_table_eligible` is `false`, final comparison tables must not include Ragas/DeepEval as completed strict baselines. If it is `true`, it only confirms readiness of the strict adapters/provider route; final paper tables still require a full strict run on the selected benchmark split.

## Current Scope

The seed benchmark contains 180 deterministic samples:

- 80 PT-BR samples.
- 100 English samples.
- Balanced failure types.
- Fixed dev/test splits.

This satisfies the minimum seed size for reproducible development. It does not by itself make the benchmark paper-ready.

## Reporting Rules

Allowed:

- "GroundCite-Bench Seed provides a deterministic PT-BR/EN benchmark seed."
- "In a controlled seed setting, method X produced metric Y under protocol Z."
- "The PT-BR claim set has human-human IAA results" only if the full agreement report exists and has reviewed rows for both annotators.

Not allowed:

- "Benchmark definitivo."
- "Fully human-validated PT-BR benchmark" without completed review/adjudication.
- "GroundCite is generally state of the art."
- "Ragas/DeepEval were beaten" when adapter mode is `mock`.

## Known Risks

- Synthetic samples may overestimate evaluator performance.
- Natural RAG errors may differ from template-generated errors.
- PT-BR linguistic coverage is incomplete.
- Baseline versions and provider behavior can change.
- Small sample sizes limit statistical power.
