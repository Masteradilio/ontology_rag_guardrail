# Evaluation Guide

Ontology RAG Guardrail evaluates a RAG workflow at three distinct points.

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

### Threshold Calibration Benchmark

The expanded `rag_enterprise_v1` package contains 96 balanced, semisynthetic
cases across 24 enterprise policy families. It is deliberately larger than
the four-case regression seed and contains supported, contradicted,
insufficient-evidence, and partial-coverage cases. The package is committed
with a generator, manifest, provenance fields, and no production or personal
records.

Run the threshold sweep with the local Sentence Transformers backend:

```powershell
python -m quimera_semantic_trust_guardrail rag-threshold-benchmark
```

The command performs one embedding pass, reuses the ranking, and evaluates a
0.20-0.80 absolute-threshold grid at 0.01 increments. It writes JSON, CSV,
Markdown, and a dependency-free SVG containing context precision, context
recall, context F1, abstention, useful abstention, harmful abstention, mean
context size, and pre-RAG hit@k/MRR. The recommended threshold maximizes F1 on
this corpus; it is a calibration artifact, not a production default.

In the committed run, threshold `0.55` is the F1 recommendation with context
precision `0.861`, context recall `0.944`, context F1 `0.901`, and harmful
abstention `0.042`. Threshold `0.65` exceeds `0.90` precision but lowers recall
to `0.778`, making the precision/recall/abstention trade-off visible instead
of hiding it behind one headline number. The published snapshot is under
`docs/benchmarks/rag-enterprise-threshold-20260820`.

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

`NVIDIA_URL_REFERENCE_MODEL` must contain the NVIDIA Chat Completions endpoint
(`https://integrate.api.nvidia.com/v1/chat/completions`). For compatibility,
the client also converts a `build.nvidia.com/.../modelcard` reference into that
endpoint; the model-card page itself is documentation, not an inference API.

## Interpretation

The committed datasets are engineering fixtures, not production accuracy
estimates. The 96-case package is template-generated semisynthetic data, not a
real anonymized customer dataset. Any public report must include the dataset
size, provenance, model name, top-k configuration, threshold policy, and known
limitations. Real anonymized records should replace or extend this package
only after privacy review, identifier removal, label adjudication, and a held-
out evaluation split.
