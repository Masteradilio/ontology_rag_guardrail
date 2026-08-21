# Evaluation Guide

Quimera evaluates a RAG workflow at three distinct points.

## Pre-RAG

The query is embedded against candidate documents before answer generation. The report records:

- hit@k;
- mean reciprocal rank;
- top-1 cosine similarity;
- ranked document ids;
- the number of queries with at least one gold relevant document.

Queries with no relevant gold document are not included in hit@k or MRR aggregates. They remain visible in per-case results as insufficient-evidence cases.

## During RAG

The assembled context is evaluated independently of the answer. The report records:

- context precision;
- context recall;
- duplicate rate;
- evidence coverage;
- retrieved document ids.

This stage exposes retrieval noise and duplicate context even when an answer happens to look plausible.

## Post-RAG

The answer is passed to an explicit evaluator. The evaluator may be deterministic, runtime-backed, or LLM-assisted, but no provider is called implicitly. The report records:

- expected and observed trivalent decision;
- decision accuracy when both are available;
- `TRUE`, `FALSE`, and `UNDECIDABLE` distribution;
- evidence coverage inherited from the assembled context.

The committed benchmark uses a controlled deterministic evaluator. This keeps the base benchmark reproducible without an LLM API key. An LLM key is only needed for a separate judge-assisted or generation-based experiment.

## Interpretation

The seed is an engineering regression fixture, not a production accuracy estimate. Any public report must include the dataset size, synthetic nature, model name, top-k configuration, and known limitations.
