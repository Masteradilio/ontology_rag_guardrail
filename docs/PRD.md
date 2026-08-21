# PRD: Ontology RAG Guardrail

## 1. Product Summary

Ontology RAG Guardrail is an enterprise guardrail and semantic trust runtime for LLM, RAG, and AI agent deployments.

It validates claims, answers, plans, and tool/action requests against tenant-specific knowledge, policies, compliance rules, and evidence sources. The product returns auditable trivalent decisions: `TRUE`, `FALSE`, or `UNDECIDABLE`.

The product is not a general ontology editor, a generic RAG eval framework, or an AGI system. It is a runtime and governance layer that makes semantic decisions operationally enforceable.

## 2. Problem

Enterprise AI projects often pass demos and fail in production because agents operate in semantically unstable environments:

- the same business term has different meanings across systems;
- RAG answers may contain partially unsupported claims;
- agents can attempt actions that are not explicitly authorized;
- compliance rules are scattered across documents, prompts, dashboards, and code;
- audit teams cannot reconstruct why an AI answer or action was allowed.

Binary allow/block guardrails are too coarse. A production agent often needs a third state: not enough evidence or authorization.

## 3. Target Users

- AI platform teams deploying RAG and agents.
- Data and enterprise architects responsible for semantic consistency.
- Security, privacy, compliance, and risk teams.
- SaaS teams embedding LLM agents into regulated customer workflows.
- Research and evaluation teams measuring groundedness and abstention.

## 4. Target Buyers

- CTO, CIO, Head of AI Platform, Head of Data Platform.
- CISO or DPO for regulated deployments.
- Product leaders responsible for enterprise agent products.

## 5. Value Proposition

Ontology RAG Guardrail gives enterprise AI systems a governed semantic decision layer:

- validate claims against evidence and ontology;
- distinguish unsupported from contradicted content;
- require abstention when evidence is insufficient;
- enforce allowed actions before an agent calls a tool;
- produce audit-ready proofs for every decision;
- regression-test semantic trust before production release.

## 6. Core Principles

- Evidence first: never treat model confidence as proof.
- Trivalent decisions: `UNDECIDABLE` is a first-class operational state.
- Tenant isolation: every tenant has isolated knowledge, policy, and proof trails.
- Runtime first: APIs must be easy to attach to existing RAG and agent systems.
- Auditability: every decision must be reproducible from its inputs, evidence, rules, and ontology version.
- Conservative claims: the product estimates support and policy conformance; it does not prove real-world truth.

## 7. Product Scope

### MVP In Scope

- Python package with copied/adapted core components.
- Fast local SDK surface for:
  - `claim_check`
  - `answer_check`
  - `action_check`
  - `policy_check`
- Tenant-scoped semantic facts and ontology records.
- Knowledge adapter integration for RAG/File Search sources.
- Claim decomposition and claim-level support labels from GroundCite.
- Trivalent decision mapping.
- Proof ledger with decision, evidence, and ontology version metadata.
- Basic compliance rules and policy packs.
- Regression test suite for copied modules and new contracts.

### Out Of Scope For MVP

- Full SaaS dashboard.
- Full OWL/RDF editor.
- Marketplace of policy packs.
- Automated legal advice.
- AGI, quantum positioning, or autonomous self-improvement.
- Broad claims of hallucination elimination.

## 8. Differentiators

- Trivalent semantic validation instead of binary guardrail decisions.
- Claim/span-level groundedness from GroundCite, adapted for runtime use.
- Action permission checks as part of ontology, not only text validation.
- Proof ledger designed for audit and incident review.
- Adapter-first architecture for existing enterprise RAG stores.

## 9. Functional Requirements

### FR1: Claim Check

The system must accept a single claim and return:

- decision: `TRUE`, `FALSE`, or `UNDECIDABLE`;
- status mapping: supported, contradicted, unsupported, or error;
- confidence;
- evidence;
- contradictions;
- missing evidence or missing policy requirements;
- proof id.

### FR2: Answer Check

The system must decompose an answer into claims, validate each claim, aggregate the result, and recommend:

- allow;
- allow with warnings;
- retry with guidance;
- abstain;
- block;
- escalate to human review.

### FR3: Action Check

The system must validate whether an agent may execute an action:

- actor;
- tenant;
- resource;
- action;
- purpose;
- context;
- policy and ontology version.

If no explicit permission or valid inference exists, default to `UNDECIDABLE` or `FALSE` depending on policy.

### FR4: Ontology And Policy Store

The system must support tenant-scoped facts, constraints, policies, relation types, sources, and versions.

### FR5: Proof Ledger

The system must record every decision with a stable proof id and enough metadata for reconstruction.

### FR6: Regression Evaluation

The system must support offline evals using copied GroundCite assets and reference test cases.

## 10. Non-Functional Requirements

- Python 3.10+ target, with current local validation on Python 3.13.
- Core runtime should be usable without paid LLM APIs.
- Optional LLM-based extractors or judges must fail honestly when providers are unavailable.
- Tenant data must be isolated in storage and cache keys.
- Default execution must avoid sending sensitive content to external APIs.
- Decisions must be deterministic where possible.

## 11. Initial Architecture

```text
Client RAG/Agent
  -> Input Shield
  -> Agent/RAG System
  -> Semantic Trust Runtime
       -> Claim Decomposer
       -> Knowledge/Ontology Adapter
       -> Policy/Action Engine
       -> Compliance Engine
       -> Trivalent Decision Mapper
       -> Proof Ledger
  -> Response / Retry / Abstain / Escalate
```

## 12. Initial API Sketch

```python
from quimera_semantic_trust_guardrail import SemanticTrustRuntime

runtime = SemanticTrustRuntime(tenant_id="tenant_a")

result = await runtime.claim_check(
    claim="Refunds are available after 60 days.",
    context={"domain": "support"}
)

if result.decision == "UNDECIDABLE":
    # ask clarification, retrieve more evidence, or escalate
    ...
```

## 13. Success Metrics

- A copied/adapted package installs in a clean venv.
- Reference tests for imported modules are categorized as pass, adapted, or pending.
- First runtime API returns stable trivalent decisions with proof ids.
- At least one end-to-end RAG answer check works on reference GroundCite samples.
- Backlog and changelog stay synchronized after every task.

## 14. Risks

- Existing docs promise adapter behavior not implemented in current APIs.
- `OntologySync` and `TenantOntologyManager` currently have incompatible contracts.
- GroundCite contains research/eval code that must be separated from runtime-critical code.
- Legacy modules contain useful patterns but also outdated framing and optional heavy dependencies.
- A product claim stronger than "supported by evidence" would be scientifically and commercially risky.

## 15. Near-Term Decision

The next engineering milestone is not a dashboard. It is a coherent runtime contract:

- one semantic fact model;
- one decision model;
- one proof model;
- one adapter interface;
- one testable trivalent mapping from evidence/policy outcomes to runtime action.
