# Commercial ICP And Use Cases

Status: discovery package for Phase C0.

This document turns the scientific evidence package into buyer hypotheses. It does not claim production ROI yet.

## ICP 1: AI Platform Team Deploying Enterprise RAG

- Buyer: Head of AI Platform, CTO, or Head of Data Platform.
- Users: RAG platform engineers, evaluation engineers, support automation owners.
- Pain: support answers can mix supported and unsupported claims, and audit teams cannot easily reconstruct why an answer was allowed.
- Current workaround: prompt rules, citation display, manual review, and ad hoc eval notebooks.
- Quimera workflow: run `answer_check` after generation; return allow, retry, abstain, or block with proof metadata.
- Pilot success criteria:
  - unsupported claims route to `UNDECIDABLE`;
  - contradicted claims route to block;
  - proof id is stored in the application trace;
  - audit reconstruction time is lower than the current manual process.

## ICP 2: SaaS Team Embedding Agent Tool Calls

- Buyer: VP Product, CTO, or Head of Engineering.
- Users: agent framework engineers and workflow owners.
- Pain: agents can attempt tool calls without explicit semantic authorization.
- Current workaround: hard-coded allowlists, prompt restrictions, and manual approval for high-risk tools.
- Quimera workflow: run `action_check` before tool execution.
- Pilot success criteria:
  - allowed actions execute;
  - denied actions block;
  - missing authorization escalates as `UNDECIDABLE`;
  - tenant isolation is visible in proof metadata.

## ICP 3: Compliance/Risk Team Auditing LLM Decisions

- Buyer: CISO, DPO, Head of Risk, or Compliance Director.
- Users: risk analysts, privacy analysts, AI governance reviewers.
- Pain: LLM decisions are hard to audit after the fact, especially when policy and evidence changed.
- Current workaround: sampling reviews, screenshots, logs, and separate policy spreadsheets.
- Quimera workflow: run `policy_check`, preserve proof metadata, and link decisions to ontology/policy versions.
- Pilot success criteria:
  - LGPD/custom policy violations are detected in controlled cases;
  - proof lookup reconstructs decision path;
  - policy/ontology version is captured where applicable;
  - limitations are explicit and do not replace legal review.

## Priority

Start with ICP 1 and ICP 2 in parallel discovery conversations. ICP 1 validates RAG groundedness value; ICP 2 validates agent authorization value. ICP 3 is likely higher-friction but important for enterprise buying committees.
