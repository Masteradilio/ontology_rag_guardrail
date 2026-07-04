# Architecture Guide

Quimera Semantic Trust Guardrail is organized as a runtime layer that can sit before or after an LLM, RAG pipeline, or agent tool call. Its job is to convert evidence, ontology facts, policy facts, and compliance rules into an auditable trivalent decision.

## Runtime Flow

```text
Application
  -> SemanticTrustRuntime
       -> claim decomposition when needed
       -> knowledge adapter and explicit evidence
       -> tenant semantic ontology
       -> compliance and policy checks
       -> trivalent decision model
       -> proof recorder
  -> allow, warn, retry, abstain, block, or escalate
```

The runtime exposes four primary checks:

- `claim_check`: one claim, one decision.
- `answer_check`: many claims, one aggregate decision plus claim-level decisions.
- `action_check`: agent authorization for actor/action/resource/purpose.
- `policy_check`: compliance and tenant policy evaluation.

## Core Models

`SemanticTrustDecision` is the central output model. It carries:

- `decision`: `TRUE`, `FALSE`, or `UNDECIDABLE`.
- `recommended_action`: `allow`, `warn`, `retry`, `abstain`, `block`, or `escalate`.
- evidence records and contradiction records.
- missing requirements for underdetermined decisions.
- proof metadata including proof id, ontology version, policy version, and decision path.

`SemanticFact` is the shared ontology fact contract. It supports tenant scope, fact type, trivalent state, confidence, validity window, source metadata, document/chunk/span provenance, ontology version, and policy version.

## Storage Boundaries

The local runtime persists proof entries and ontology snapshots under configured storage paths. Tenant id and ontology id are part of the storage boundary. Production deployments should replace the local filesystem stores with controlled storage that preserves the same contracts.

## Optional FastAPI Runtime

`quimera_semantic_trust_guardrail.fastapi_app.create_app()` exposes the SDK through HTTP endpoints. FastAPI is optional, so the SDK can be installed without web dependencies.

The current HTTP authentication model is intentionally only a placeholder: guarded endpoints require `X-Tenant-ID`, but production systems should replace that dependency with API key, mTLS, JWT, or gateway-enforced tenant identity.

## Compatibility Code

The `quimera_legacy` package keeps selected original Quimera modules for technical reference and regression coverage. The `core.*` and top-level shim modules exist only so copied legacy tests can still validate historical behavior after repackaging.
