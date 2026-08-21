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

The pipeline separates the declared candidate context from the final assembled
context. The report records:

- context precision;
- context recall;
- duplicate rate;
- evidence coverage;
- candidate-context metrics, preserving input noise;
- final retrieved document ids;
- context size and explicit abstention rate.

The default benchmark uses adaptive assembly: a document must reach the
configured absolute similarity floor and remain close to the top score. An
empty final context is an abstention, not a fabricated retrieval success. This
stage therefore exposes both the original retrieval noise and the quality of
the policy that turns candidates into model context.

## Post-RAG

The answer is passed to an explicit evaluator. The evaluator may be deterministic, runtime-backed, or LLM-assisted, but no provider is called implicitly. The report records:

- expected and observed trivalent decision;
- decision accuracy when both are available;
- `TRUE`, `FALSE`, and `UNDECIDABLE` distribution;
- evidence coverage inherited from the assembled context.

The committed benchmark uses a controlled deterministic evaluator. This keeps the base benchmark reproducible without an LLM API key. The opt-in
`quimera rag-llm-benchmark` command sends only the selected context to the
NVIDIA MiniMax M3 endpoint first and uses OpenRouter only when the primary
provider fails. Provider traces are redacted and malformed model output maps
to `UNDECIDABLE`.

## Interpretation

The seed is an engineering regression fixture, not a production accuracy estimate. Any public report must include the dataset size, synthetic nature, model name, top-k configuration, and known limitations.
