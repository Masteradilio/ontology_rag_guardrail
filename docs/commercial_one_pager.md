# Quimera Semantic Trust Guardrail: Technical One-Pager

## What It Is

Quimera is an experimental Python SDK/runtime for audit-ready trivalent semantic trust decisions in RAG and agent workflows.

It returns:

- `TRUE`: supported or authorized under configured evidence, ontology, and policy.
- `FALSE`: contradicted, denied, or policy-violating.
- `UNDECIDABLE`: insufficient evidence or authorization.

## Where It Fits

```text
RAG or Agent System
  -> Quimera claim_check / answer_check / action_check / policy_check
  -> allow, retry, abstain, block, or escalate
  -> proof metadata for audit
```

## Current Evidence

- Deterministic seed baseline: 12 synthetic samples, 11 correct decisions.
- Known limitation: one intentionally undecidable policy case currently false-allows.
- Regression suite: 209 tests passing.
- Scientific claims ledger controls public claims and explicitly blocks truth-proof, hallucination-elimination, and legal-certification claims.

## Buyer Hypothesis

Enterprise teams may value Quimera when they need:

- claim-level RAG answer approval;
- agent tool-call authorization;
- proof records for AI governance and incident review.

## What It Does Not Claim

Quimera does not prove real-world truth, certify legal compliance, or eliminate hallucinations. It validates decisions under configured evidence, ontology, and policy.
