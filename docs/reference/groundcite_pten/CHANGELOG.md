# Changelog

All notable changes to GroundCite-PTEN are documented here.

## [0.9.1.dev0] - 2026-06-02

### Changed

- Repositioned the project as an experimental research toolkit and benchmark seed for claim- and span-level RAG groundedness evaluation.
- Rewrote the README and paper outline to remove unsupported scientific claims and separate scientific, reproducibility, and community tooling contributions.
- Updated dataset, benchmark, annotation, and gold-label audit documentation with explicit reporting boundaries.
- Added a scientific claims ledger that marks claims as `supported`, `preliminary`, `blocked`, `engineering_only`, or `remove`.
- Updated LLM provider handling to support the NVIDIA-first free model configuration with paid fallbacks after a 15s timeout.
- Updated Ragas/DeepEval strict adapters to use real providers and fail honestly in strict mode instead of producing paper-eligible fallback results.

### Added

- `data/scripts/summarize_groundcite_bench.py` for dataset hashes, counts, label distributions, split distributions, annotation status, and length/context statistics.
- `experiments/scripts/compute_human_agreement.py` for PT-BR second-pass agreement reporting.
- `data/scripts/consolidate_human_adjudication.py` for consolidating double-blind human review and adjudication into final PT-BR labels.
- `data/samples/groundcite_bench_pt_human_validated.jsonl` with 80 PT-BR samples and 100 human-adjudicated claim labels.
- `data/annotation/pt_human_full_review_with_context.csv`, `data/annotation/pt_human_full_adjudication.csv`, and `data/annotation/pt_human_full_final_labels.csv` for the full PT-BR human review workflow.
- `experiments/scripts/evaluate_conformal_coverage.py` for empirical conformal coverage reporting.
- `docs/reproducibility_report.md` and `docs/paper_readiness_checklist.md`.
- Scientific reporting guardrails and dataset summary integrity tests.

### Scientific Status

- PT-BR seed labels now have double-blind human-human IAA and final adjudicated labels for 100 claims across 80 samples.
- PT-BR final label distribution is `supported=40`, `unsupported=42`, `contradicted=18`; 89 labels came from human agreement and 11 from adjudication.
- Human-human IAA is percent agreement `0.89` and Cohen's Kappa `0.826169`.
- Strict Ragas/DeepEval readiness passes with real adapters in the current provider environment, but final comparative paper tables still require a full strict benchmark-scale run.
- Full PT-BR strict meta-evaluation was attempted against `data/samples/groundcite_bench_pt_human_validated.jsonl` and is blocked by Ragas provider availability at 80-sample scale; details are recorded in `experiments/exp07_meta_evaluation/results/pt_human_validated_strict/strict_run_blocker.json`.
- Mock Ragas/DeepEval adapters remain smoke-test tooling only and must not be used in paper tables.
- Kappa between model predictions and gold labels is reported as model-gold agreement, not IAA.
- Conformal coverage currently undercovers the lexical PT-BR protocol and must be reported as a limitation, not a guarantee.

## [0.9.0-dev] - 2026-06-02

### Added

- Experimental conflicting-source adjudication metric.
- Experimental conformal prediction metadata for factual labels.
- Experimental language-induced hallucination perturbation.
- Experiment scripts for CSA and LIHB stress tests.

### Note

Results from this development version require provenance checks before being used in paper claims. Numbers in generated reports must be backed by raw result files, dataset hashes, dependency versions, and strict baseline mode where applicable.

## [0.8.0 and earlier]

Earlier development versions added the core schemas, evaluator, lexical/local/hybrid backends, CLI commands, benchmark seed generation, baseline adapters, perturbation utilities, optional dashboard/PDF/server integrations, and reproducibility harness.

Historical descriptions may have used stronger language than the current scientific status allows. The current source of truth for paper claims is `docs/scientific_claims_ledger.md`.
