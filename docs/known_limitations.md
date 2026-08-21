# Known Limitations

This document keeps known weaknesses visible instead of allowing a successful demo to imply production guarantees.

## Runtime Decision Limitation

The current deterministic seed includes `policy-undecidable-001`, where the expected state is `UNDECIDABLE` but the observed runtime state is `TRUE`. The failure is preserved in evaluation artifacts and should remain part of regression review until a future design explicitly changes the policy path.

## Evaluation Limitations

- The committed datasets are small and synthetic.
- Embedding retrieval quality depends on the selected model, corpus, language, and threshold configuration.
- The offline benchmark evaluates deterministic answer fixtures; it does not measure an LLM's generation quality.
- The LLM benchmark is a four-case provider-backed smoke evaluation; provider output can vary between runs and the raw LLM accuracy must be reported separately from the guardrailed decision accuracy.
- The evidence-consistency guardrail is intentionally narrow and seed-oriented. It demonstrates a validation stage; it is not a general natural-language contradiction solver.
- The adaptive similarity floor improves precision by abstaining on weak context. Thresholds must be calibrated on a larger, independently labeled corpus before comparing systems.
- No metric in this repository proves real-world truth or production RAG accuracy.
- Optional provider runs can fail because of network, quota, model availability, or provider configuration.

## Deployment Limitations

- The optional HTTP runtime uses `X-Tenant-ID` as a local testing identity placeholder.
- Local filesystem proof and ontology stores are suitable for examples and regression tests, not a production deployment boundary.
- No SSO, RBAC, mTLS, data residency, SLA, or managed retention controls are included.

## Claim Boundary

Use the language "experimental runtime", "ontology-grounded validation", "trivalent decision contract", and "replayable evaluation". Avoid claims that the system eliminates hallucinations, proves truth, certifies compliance, or guarantees autonomous-agent safety.
