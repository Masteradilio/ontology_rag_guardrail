# Proof And Audit Guide

The proof ledger is the audit trail for semantic trust decisions. It is designed to reconstruct why a runtime decision was returned.

## What A Proof Should Contain

Each runtime decision should preserve:

- proof id and proof type.
- tenant id.
- decision and recommended action.
- ontology id and ontology version.
- policy id, policy version, and ruleset version when applicable.
- evidence ids and policy ids used by the decision.
- adapter source when evidence came from an external knowledge adapter.
- decision path.
- related proof id for snapshot, rollback, or migration chains.
- hash-chain metadata for integrity checks.

## Lookup APIs

Use:

- `proof_lookup(proof_id)` to retrieve one proof.
- `list_proofs_for_ontology(ontology_id)` for ontology-scoped review.
- `verify_integrity` and `verify_chain` on the recorder/store where available.

## Operational Practice

Store proof ids in application logs and customer-facing incident records. For regulated workflows, keep the input, retrieved evidence ids, model answer, final action, proof id, and human override outcome in the same incident package.

## Limitations

The proof ledger proves what the runtime observed and decided under a specific configuration. It does not prove that the source evidence was complete, legally correct, or true in the real world.
