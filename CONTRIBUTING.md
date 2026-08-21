# Contributing

This repository is maintained as a focused technical portfolio project. Small, reproducible changes are preferred over broad refactors.

## Local Checks

```powershell
python -m pip install -e ".[dev]"
python -m pytest -q
git diff --check
```

For embedding-backed evaluation:

```powershell
python -m pip install -e ".[evaluation]"
python -m quimera_semantic_trust_guardrail rag-benchmark
```

Keep synthetic datasets, expected labels, provider behavior, and known limitations explicit. Do not commit `.env`, API keys, customer data, or generated artifacts.
