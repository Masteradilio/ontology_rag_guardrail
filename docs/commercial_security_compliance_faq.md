# Commercial Security And Compliance FAQ

## Does Ontology RAG Guardrail send customer data to external LLMs?

The deterministic runtime and demo paths do not require external LLM calls. Optional LLM-assisted evaluation is explicit and uses NVIDIA MiniMax M3 first, with OpenRouter MiniMax M3 as fallback only.

## Are API keys stored in the repository?

No. `.env` is ignored. Provider tests use mocks and secret redaction is tested.

## Does Ontology RAG Guardrail certify legal compliance?

No. Ontology RAG Guardrail can run compliance-style runtime checks and record proof metadata. It does not replace legal review or certify compliance.

## What audit data is recorded?

Runtime decisions include proof id, decision path, evidence ids where available, ontology version where available, policy version where available, and recommended action.

## Can the system run offline?

Yes for deterministic runtime checks and demos. LLM provider use is optional for evaluation support.

## What should be reviewed before a customer pilot?

- Customer data handling policy.
- Whether external LLM calls are allowed.
- Tenant isolation expectations.
- Proof log retention and deletion policy.
- Human review path for `UNDECIDABLE`.
- Legal review boundaries.
