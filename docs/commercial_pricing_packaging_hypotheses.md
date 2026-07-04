# Commercial Pricing And Packaging Hypotheses

Status: hypotheses for buyer discovery, not validated pricing.

## Package Hypotheses

| Package | Buyer | Value hypothesis | Pricing anchor to test |
| --- | --- | --- | --- |
| SDK/runtime license | AI platform and SaaS engineering teams | Add trivalent trust checks to existing RAG/agent stacks. | Annual platform license by environment or tenant tier. |
| Audit/proof module | Compliance, risk, and governance teams | Reduce audit reconstruction effort with proof metadata. | Add-on module priced by tenant or audit volume. |
| Managed evaluation package | AI governance and evaluation teams | Run reproducible trust evaluations without building the harness. | Fixed-scope evaluation engagement plus renewal option. |
| Per-decision usage tier | Teams with variable workloads | Pay with usage as workflows scale. | Metered decisions after included monthly volume. |

## Buyer Discovery Questions

- Which workflow has urgent budget: RAG approval, agent authorization, or audit review?
- Is self-hosted mandatory?
- Are external LLM calls allowed for evaluation?
- What proof fields are mandatory for risk/compliance?
- What is the current cost of manual review or incident reconstruction?
- Who signs off: platform, security, compliance, legal, or product?

## Enterprise Requirements To Test

- SSO/RBAC.
- Audit export.
- Data residency.
- Tenant isolation.
- SLA and support expectations.
- On-prem/self-hosted deployment.
- Policy version governance.

## Provider Cost Rule

NVIDIA MiniMax M3 remains the primary provider for opt-in LLM evaluation because it is free. OpenRouter MiniMax M3 is paid fallback and must be explicitly modeled in pilot cost estimates.

Do not hide OpenRouter fallback usage inside margins.
