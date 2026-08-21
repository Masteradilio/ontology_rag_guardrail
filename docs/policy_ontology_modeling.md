# Policy And Ontology Modeling Guide

Ontology RAG Guardrail uses semantic facts as the common representation for business facts, definitions, constraints, synonyms, and policy rules.

## Modeling Principles

- Model tenant-specific meaning explicitly.
- Prefer narrow facts over broad natural-language policy blobs.
- Preserve source provenance for every imported fact.
- Use `UNDECIDABLE` when evidence is incomplete.
- Version ontology and policy changes before relying on them in production.

## Fact Shape

A useful production fact should include:

- subject, relation, object.
- fact type: concept, definition, fact, constraint, synonym, or policy.
- trivalent state.
- tenant id.
- ontology version and policy version where applicable.
- confidence and validity period when known.
- provenance: document id, chunk id, span, source URI, and extractor.

## Policy Facts

Policy facts should be testable by runtime checks. For example:

```text
support_agent may refund order when purpose=customer_support
contractor must_not export customer_data
assistant must redact personal_data for external_channel
```

Policy absence should normally produce `UNDECIDABLE`, not implicit allow.

## Conflict Handling

When two facts assert incompatible states for the same triple, keep both records with provenance and mark conflict metadata. Do not silently overwrite the old fact. The proof ledger should show which version was active when a decision was made.

## Versioning

Use snapshots before policy imports or ontology migrations. Rollback should create its own audit event rather than deleting the historical state.
