# Portfolio Demo Walkthrough

The shortest reproducible portfolio path is offline and does not require an LLM API key.

## 1. Install

```powershell
python -m pip install -e ".[dev]"
```

The showcase uses a deterministic local embedding baseline and does not download a model.

## 2. Run The Showcase

```powershell
python -m quimera_semantic_trust_guardrail showcase --run-id portfolio-showcase
```

Inspect `artifacts/showcase/portfolio-showcase/showcase.json` for claim decisions including `TRUE`, `FALSE`, and `UNDECIDABLE`, agent authorization decisions, an ontology snapshot, RAG evaluation results, proof ids, and observability events.

## 3. Run The Real Embedding Benchmark

```powershell
python -m pip install -e ".[evaluation]"
python -m quimera_semantic_trust_guardrail rag-benchmark --run-id rag-seed-benchmark
```

The benchmark uses `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` through `sentence-transformers==5.6.1`. It may download the model from Hugging Face on first use, but it does not call an LLM provider and does not require an API key.

For the expanded threshold calibration benchmark:

```powershell
python -m quimera_semantic_trust_guardrail rag-threshold-benchmark --run-id rag-enterprise-threshold-benchmark
```

This evaluates 96 semisynthetic cases from 24 enterprise policy families and
writes a precision/recall/F1/abstention curve over thresholds from 0.20 to
0.80. The committed, reviewer-friendly snapshot is
`docs/benchmarks/rag-enterprise-threshold-20260820`.

For the opt-in provider-backed benchmark configured by `.env`:

```powershell
python -m quimera_semantic_trust_guardrail rag-llm-benchmark --run-id rag-llm-benchmark
```

NVIDIA MiniMax M3 is attempted first; paid OpenRouter is used only when the
primary provider fails. The run records redacted provider traces and maps
malformed or unavailable model output to `UNDECIDABLE`.

## 4. Inspect Artifacts

- `metadata.json`: commit, dataset, model, and API-key requirement.
- `report.json`: per-case and aggregate pre-RAG, during-RAG, and post-RAG results.
- `summary.md`: reviewer-friendly metrics and limitations.
- `trace.jsonl`: stage-level retrieval, context, and decision events.
- `observability.json`: event and decision summaries.
- `otel.json`: dependency-free OTLP-shaped spans for collector integration.
- `threshold_curve.csv`: threshold-level metrics for plotting or analysis.
- `threshold_curve.svg`: dependency-free chart suitable for GitHub review.

To inspect a trace as a reviewer:

```powershell
python -m quimera_semantic_trust_guardrail trace-replay artifacts/evaluation/rag-seed-benchmark/trace.jsonl
```

## What This Demonstrates

The demo makes the architecture inspectable: retrieval quality is not conflated with context quality, context quality is not conflated with answer generation, and the final trivalent decision remains linked to evidence and proof metadata.
