# GroundCite-Bench Gold Label Audit

## Current Status

- PT-BR seed labels are deterministic single-pass gold labels generated from templates.
- PT-BR human-human review is complete for the full claim set when `data/annotation/pt_human_full_review_with_context.csv` has filled `annotator_1_label` and `annotator_2_label` values and `experiments/human_agreement/full_pt_results/pt_human_agreement.json` reports reviewed rows.
- English external human span gold can be imported from RAGTruth when upstream files are available.

This status is sufficient for claiming human-adjudicated labels for the synthetic PT-BR benchmark seed. It is not sufficient for broad real-world PT-BR generalization claims.

## Implemented Workflow

- `data/scripts/build_groundcite_bench.py` generates PT-BR/EN seed data.
- `data/scripts/summarize_groundcite_bench.py` generates hashes and dataset statistics.
- `data/scripts/build_human_audit_packet.py` creates a stratified PT-BR review packet.
- `experiments/scripts/compute_human_agreement.py` computes second-pass agreement or human-human IAA depending on the review columns present.
- `data/scripts/consolidate_human_adjudication.py` consolidates human agreement plus adjudication into final labels.
- `data/scripts/import_ragtruth.py` imports external RAGTruth EN human span annotations when upstream files are supplied.

## Human Review Protocol

1. Fill `annotator_1_label` and `annotator_2_label` in `data/annotation/pt_human_full_review_with_context.csv`.
2. Use only `supported`, `unsupported`, or `contradicted`.
3. Avoid exposing seed labels to the reviewer when feasible.
4. Record uncertainty and adjudication decisions in `notes`.
5. Run:

```powershell
python experiments/scripts/compute_human_agreement.py
python data/scripts/consolidate_human_adjudication.py
```

## Reporting Rules

Allowed now:

- "PT-BR deterministic seed labels."
- "PT-BR full claim set with double-blind human-human IAA."
- "Human-human IAA for the PT-BR claim set: 100/100 claims, percent agreement 0.89, Cohen's Kappa 0.826169."
- "PT-BR synthetic seed benchmark with human-adjudicated claim labels: 80 samples, 100 claims."

Blocked or limited:

- Broad claims about real-world PT-BR RAG hallucination behavior.

## Agreement Report

Expected output:

```text
experiments/human_agreement/full_pt_results/pt_human_agreement.json
experiments/human_agreement/full_pt_results/pt_disagreements.csv
experiments/human_agreement/full_pt_results/report.md
```

Current generated report status:

- `status = ready_for_full_iaa_reporting_adjudication_required`
- `reviewed_rows = 100`
- `review_coverage = 1.0`
- `percent_agreement = 0.89`
- `cohen_kappa = 0.826169`
- `disagreement_count = 11`

Adjudication summary:

- `status = human_adjudicated_gold_ready`
- `total_samples = 80`
- `total_claims = 100`
- `adjudicated_disagreement_count = 11`
- `changed_from_seed_count = 8`
- `final_label_distribution = {'contradicted': 18, 'supported': 40, 'unsupported': 42}`

This removes the IAA and adjudication blockers for the synthetic PT-BR benchmark seed.

## EN External Gold

RAGTruth import command:

```powershell
python data/scripts/import_ragtruth.py `
  --response-jsonl path/to/response.jsonl `
  --source-info-jsonl path/to/source_info.jsonl `
  --out data/samples/groundcite_bench_en_ragtruth.jsonl `
  --split test `
  --quality good `
  --max-samples 100
```

Imported records must be reported separately from the deterministic EN seed.
