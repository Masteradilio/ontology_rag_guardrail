# Paper Readiness Checklist

## Go Criteria

- [x] Dataset summary includes SHA-256 hashes, sample counts, claim counts, splits, and annotation status.
- [x] PT-BR human-adjudicated seed is documented with final labels.
- [x] Human-human IAA report exists for the full PT-BR claim set.
- [x] Strict Ragas/DeepEval readiness exists with `adapter_mode = real`; final benchmark-scale paper tables still need a full strict run.
- [x] Main tables exclude mock baseline results.
- [x] Kappa is named correctly as model-gold agreement unless computed from independent human labels.
- [x] Conformal coverage reports empirical coverage and limitations.
- [x] CSA and LIHB are reported as controlled stress tests.
- [x] README and paper outline contain no unsupported claims.
- [x] Claims ledger marks every abstract claim as `supported` or carefully `preliminary`.

## No-Go Criteria

- [ ] Main result table uses mock adapters.
- [ ] PT-BR is called human-validated without completed review/adjudication.
- [ ] Kappa gold-vs-prediction is called IAA.
- [ ] p-values are described as "100% confidence."
- [ ] Conformal prediction is described as a truth guarantee.
- [ ] Dataset lacks hashes or summary.
- [ ] Paper depends on numbers that appear only in the changelog.

## Current Status

Paper drafting can start: yes.

Paper-ready for final comparative empirical tables: no. The full PT-BR strict benchmark run was attempted and is currently blocked by Ragas provider availability at 80-sample scale.

Conservative first draft allowed: yes, if the draft explicitly states:

1. PT-BR has full double-blind human-human IAA over 100 claims, and 11 disagreements have final adjudicated labels.
2. Strict Ragas/DeepEval readiness passes in this environment, but final comparison claims require a full strict benchmark-scale run; the current full run is blocked by Ragas provider failures documented in `experiments/exp07_meta_evaluation/results/pt_human_validated_strict/strict_run_blocker.json`.
3. Conformal prediction undercovered the lexical PT-BR protocol and is reported as a limitation.
4. CSA and LIHB are controlled stress tests, not production guarantees.

Remaining blockers for a stronger paper:

1. Provide a benchmark-scale working Ragas provider and rerun full strict Ragas/DeepEval meta-evaluation on the selected paper benchmark split before using head-to-head tables.
2. Import external natural PT/EN sources from local Pira/FaQuAD/ASSIN2 files if those subsets will be used in the paper.
