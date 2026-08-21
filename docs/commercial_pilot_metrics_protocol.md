# Commercial Pilot Metrics Protocol

This protocol defines pilot measurements. It should be applied to real customer pilots only after data handling approval.

## Required Fields Per Sample

- `sample_id`
- workflow
- expected decision
- observed decision
- proof lookup success
- audit reconstruction minutes before Ontology RAG Guardrail
- audit reconstruction minutes after Ontology RAG Guardrail
- setup minutes
- reviewer usefulness score, from 1 to 5
- notes and blockers

## Metrics

- false allow rate: expected not `TRUE`, observed `TRUE`.
- false block rate: expected `TRUE`, observed `FALSE`.
- useful abstention rate: expected `UNDECIDABLE`, observed `UNDECIDABLE`.
- proof lookup success rate.
- audit reconstruction time delta.
- setup hours.
- reviewer usefulness average.

## Reporting Rules

- Report blockers alongside positive metrics.
- Separate product value from integration friction.
- Do not report synthetic pilot metrics as buyer validation.
- Do not use pilot metrics as legal compliance evidence.
- Keep customer-specific raw data out of Git.
