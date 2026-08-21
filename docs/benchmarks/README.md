# Published Benchmarks

This directory contains small, reproducible benchmark snapshots intended for
technical portfolio review. Each snapshot includes the dataset manifest,
configuration, raw report, tabular curve, readable summary, and chart.

## Enterprise RAG Threshold Sweep

`rag-enterprise-threshold-20260820` evaluates 96 template-generated
semisynthetic cases across 24 enterprise policy families with
`sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`.

The headline result is a trade-off, not a single quality claim:

- F1 recommendation at threshold `0.55`: precision `0.861`, recall `0.944`,
  F1 `0.901`, harmful abstention `0.042`.
- Precision-oriented threshold `0.65`: precision `0.907`, recall `0.778`,
  harmful abstention `0.208`.

The corpus contains no production records or personal data. It is a
reproducible engineering fixture and must not be described as a real customer
dataset. Replace or extend it with privacy-reviewed anonymized records before
making any production-quality claim.
