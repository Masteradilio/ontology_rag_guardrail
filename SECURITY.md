# Security Policy

Ontology RAG Guardrail is an experimental portfolio project. It is not a production security boundary and must not be used as the sole control for legal compliance, financial authorization, privacy protection, or autonomous-agent safety.

## Reporting

For a security concern, open a private report through the repository's GitHub security channel when available. Do not publish credentials, customer data, proof records containing sensitive content, or exploit details in a public issue.

## Current Boundaries

- The optional HTTP runtime uses `X-Tenant-ID` as a local identity placeholder.
- Local proof and ontology storage is intended for examples and tests.
- API keys belong only in local `.env` files and must never appear in logs, artifacts, commits, or issue reports.
- Provider calls are opt-in; the deterministic benchmark does not require an LLM API key.
