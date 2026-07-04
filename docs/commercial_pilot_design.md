# Commercial Pilot Design

Status: Phase C1 planning artifact. This is not evidence of buyer demand yet.

## Pilot 1: RAG Answer Approval

- Duration: 2 weeks after data/security approval.
- Goal: validate claim-level RAG answer approval with auditable abstention.
- Inputs:
  - support answers;
  - retrieved evidence ids;
  - expected claim labels from customer review.
- Integration points:
  - post-generation `answer_check`;
  - application trace storing `proof_id`;
  - retry/abstain route for `UNDECIDABLE`.
- Success metrics:
  - false allow rate;
  - false block rate;
  - useful abstention rate;
  - audit reconstruction time.
- Exit criteria:
  - proceed if unsupported/contradicted claims route away from silent allow;
  - iterate if evidence mapping is incomplete but abstention is useful;
  - stop if unsupported-answer audit is not a repeated pain.

## Pilot 2: Agent Tool-Call Authorization

- Duration: 2 weeks after workflow mapping.
- Goal: validate semantic authorization before tool execution.
- Inputs:
  - tool call traces;
  - actor/action/resource/purpose tuples;
  - tenant policy facts.
- Integration points:
  - pre-tool `action_check`;
  - approval/escalation queue;
  - proof id in agent trace.
- Success metrics:
  - false allow rate;
  - false block rate;
  - useful abstention rate;
  - proof lookup success rate.
- Exit criteria:
  - proceed if allow/deny/missing authorization paths are useful;
  - iterate if policy modeling needs refinement;
  - stop if hard-coded controls are sufficient and audit is not a pain.

## Pilot 3: Policy/Compliance Audit

- Duration: 2 weeks after policy scope is agreed.
- Goal: validate policy/compliance review with proof metadata and explicit limitations.
- Inputs:
  - LLM outputs;
  - policy rules;
  - reviewer labels.
- Integration points:
  - `policy_check`;
  - proof lookup;
  - risk review export.
- Success metrics:
  - proof lookup success rate;
  - audit reconstruction time;
  - reviewer usefulness score.
- Exit criteria:
  - proceed if reviewers reconstruct decisions faster;
  - iterate if policy uncertainty needs stricter configuration;
  - stop if reviewers do not trust or use proof records.

## Security Constraints

- Synthetic data first.
- Customer data only after written approval.
- No external LLM provider calls unless approved.
- Proof logs must not include raw secrets or unnecessary personal data.
- Legal review remains outside Quimera scope.
