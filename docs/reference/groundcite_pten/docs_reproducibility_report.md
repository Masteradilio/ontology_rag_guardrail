# Reproducibility Report

## Environment

- OS: record at run time.
- Python: 3.10+.
- Package: `groundcite` from local source.
- Lock file: `requirements-lock.txt`.
- Core dependency mode: offline-capable.
- Optional dependencies: `[local]`, `[baselines]`, `[server]`.

## Deterministic Dataset Commands

```powershell
python data/scripts/build_groundcite_bench.py
python data/scripts/summarize_groundcite_bench.py
python experiments/scripts/compute_human_agreement.py
```

## Small Reproduction

```powershell
make run-small
```

Expected behavior:

- Runs a lexical local smoke test.
- Does not require network or paid APIs.
- Produces local result and ROI/report artifacts.

## Paper Reproduction Modes

Local/smoke mode:

```powershell
python experiments/scripts/exp07_meta_evaluation.py --dataset data/samples/groundcite_bench_pt.jsonl --min-samples 80 --groundcite-backends lexical,hybrid
```

Strict baseline mode:

```powershell
python experiments/scripts/exp07_meta_evaluation.py --dataset data/samples/groundcite_bench_pt.jsonl --strict-baselines --min-samples 80
```

Strict mode requires real Ragas/DeepEval dependencies and any model/provider configuration those libraries need. In the current environment, the readiness probe passes using the configured NVIDIA-first provider route with paid fallbacks available. Failures in full benchmark runs must still be reported as operational limitations, not as wins.

Current strict baseline readiness:

```powershell
python experiments/scripts/check_strict_baselines.py
```

The generated report is `experiments/exp07_meta_evaluation/results/strict_baseline_check.json`.

Conformal coverage:

```powershell
python experiments/scripts/run_experiment.py --dataset data/samples/groundcite_bench_pt.jsonl --backend lexical --out experiments/conformal_coverage/results/pt_lexical_eval.jsonl
python experiments/scripts/evaluate_conformal_coverage.py --results-jsonl experiments/conformal_coverage/results/pt_lexical_eval.jsonl --gold-jsonl data/samples/groundcite_bench_pt.jsonl --out experiments/conformal_coverage/results/coverage.json
```

## Required Result Provenance

Each paper result must include:

- dataset file and SHA-256 hash;
- sample count and split;
- seed;
- backend/model name;
- dependency versions;
- cache policy;
- adapter mode;
- total runtime;
- estimated cost;
- raw per-sample/per-claim predictions.

## Cache and Cost Policy

LLM-backed runs should use cache where available and report cache status. Budget limits should be set for API-backed experiments.

## Known Failure Modes

- Optional baselines may fail due to dependency conflicts or missing provider credentials.
- Local NLI may be unavailable without `[local]` dependencies.
- Human agreement is blocked until review labels are filled.
- Conformal coverage is interpretable only under calibration assumptions.
