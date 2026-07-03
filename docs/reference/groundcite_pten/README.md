# GroundCite-PTEN

[![Python Version](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

GroundCite-PTEN (`groundcite`) is an experimental open-source toolkit for claim- and span-level evaluation of evidence grounding in RAG answers, with first-class Portuguese and English examples.

It estimates whether an answer is supported by the retrieved context. It does not prove that an answer is true in the real world, does not replace human review in high-stakes domains, and does not claim general state-of-the-art performance.

## Scientific Status

GroundCite-PTEN is currently a research toolkit and benchmark seed. The deterministic PT-BR/EN seed benchmark is useful for regression tests, smoke experiments, and reproducible method development. Only human-reviewed subsets should be described as human-validated.

Results against Ragas and DeepEval must be generated with strict real-baseline execution before they can support paper claims. Mock adapters are allowed only for CI and local smoke tests.

## Core Contributions

- Claim-level support labels: `supported`, `unsupported`, and `contradicted`.
- Span attribution for evidence and unsupported answer regions.
- Abstention-oriented risk scores and optional conformal prediction metadata.
- Controlled PT-BR/EN benchmark seed with dataset and benchmark cards.
- Reproducibility utilities for dataset hashes, experiment summaries, and reporting guardrails.

## Additional Tooling

The repository also contains engineering and usability features: CLI commands, pytest quality gates, optional FastAPI serving, optional Streamlit dashboard, optional PDF reports, Hugging Face export helpers, and baseline adapters. These are useful community features, but they are not the main scientific claim of the project.

## Installation

```bash
pip install -e .
pip install -e ".[dev]"
pip install -e ".[local]"      # optional local NLI dependencies
pip install -e ".[server]"     # optional FastAPI server
pip install -e ".[baselines]"  # optional Ragas/DeepEval experiment dependencies
```

## Quickstart

```python
from groundcite import Context, Sample
from groundcite.evaluator import Evaluator

sample = Sample(
    id="demo_pt_001",
    lang="pt-BR",
    question="O que o contexto informa?",
    contexts=[
        Context(
            doc_id="ctx_1",
            text="Machado de Assis foi o primeiro presidente da Academia Brasileira de Letras.",
        )
    ],
    answer="Machado de Assis foi o primeiro presidente da Academia Brasileira de Letras.",
)

result = Evaluator().evaluate(sample)
print(result.scores)
print(result.claims)
```

## CLI

```bash
groundcite validate data/samples/groundcite_bench_pt.jsonl
groundcite eval data/samples/groundcite_bench_pt.jsonl --backend lexical --out results.jsonl
groundcite gate results.jsonl --min-claim-support 0.60
groundcite report results.jsonl --out report.md
```

## Reproducibility

```bash
python data/scripts/build_groundcite_bench.py
python data/scripts/summarize_groundcite_bench.py
python experiments/scripts/compute_human_agreement.py
pytest tests/test_groundcite_bench_dataset.py tests/test_scientific_reporting_guardrails.py -q
```

For the full paper workflow, see:

- `docs/scientific_claims_ledger.md`
- `docs/reproducibility_report.md`
- `docs/paper_readiness_checklist.md`
- `docs/dataset_card.md`
- `docs/benchmark_card.md`
- `docs/gold_label_audit.md`

## What GroundCite Does Not Do

- It does not guarantee factual truth.
- It does not solve hallucination generally.
- It does not replace domain expert review.
- It does not make broad claims about all Portuguese usage.
- It does not treat mock Ragas/DeepEval adapters as paper baselines.
- It does not require one proprietary LLM provider.

## License

MIT. See [LICENSE](LICENSE).
