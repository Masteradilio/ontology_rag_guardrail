# Evaluation Plan

This plan defines how to evaluate Quimera without overstating scientific or commercial claims.

## Evaluation Axes

- Claim support: supported, contradicted, unsupported, and partially unsupported claims.
- Abstention quality: whether `UNDECIDABLE` is returned when evidence is insufficient.
- Action authorization: allow, deny, and missing-authorization paths.
- Policy compliance: LGPD, AI Act-style rules, and custom tenant policies.
- Auditability: proof lookup, hash-chain integrity, ontology version linkage, and rollback records.

## Baseline Protocol

1. Freeze a dataset of RAG answers, evidence spans, and expected claim labels.
2. Freeze an ontology/policy snapshot.
3. Run `answer_check`, `claim_check`, `action_check`, and `policy_check` on controlled cases.
4. Record decisions, recommended actions, proof ids, and proof lookup payloads.
5. Report confusion matrices for trivalent decisions, abstention rate, false allow rate, and false block rate.
6. Keep provider failures and missing-evidence cases as explicit outcomes.

## Product Regression Gate

The current local regression gate is:

```powershell
.\.venv\Scripts\python -m pytest -q
```

Focused gates:

```powershell
.\.venv\Scripts\python -m pytest tests\product -q
.\.venv\Scripts\python -m pytest tests\reference_groundcite\test_schema.py tests\reference_groundcite\test_claims.py -q
.\.venv\Scripts\python -m pytest tests\reference_quimera_original -q
```

## Scientific Reporting Rules

- Report what was measured, not what the architecture might support later.
- Keep unsupported and contradicted outcomes separate.
- Treat `UNDECIDABLE` as a first-class result, not as an error.
- Include dataset version, ontology version, policy version, and code commit.
- Document external provider unavailability as a blocker, not as a negative model result.

## Commercial Evaluation

For buyer discovery, evaluate the system on three concrete enterprise workflows:

- RAG support answer approval.
- Agent tool-call authorization.
- Policy/compliance review with audit export.

Measure setup time, false allow rate, false block rate, abstention usefulness, audit reconstruction time, and integration friction.
