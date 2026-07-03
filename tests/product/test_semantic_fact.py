import pytest
from pydantic import ValidationError

from quimera_legacy.knowledge_ontology import KnowledgeOntology
from quimera_semantic_trust_guardrail import (
    FactConfidence,
    KnowledgeFact,
    OntologyEntry,
    SemanticFact,
    SemanticFactProvenance,
    SemanticFactType,
    SemanticOntology,
    TrivalentDecision,
    semantic_facts_from_ontology_entry,
)


def test_ontology_entry_expands_to_semantic_facts():
    entry = OntologyEntry(
        concept="refund",
        definition="A customer reimbursement process.",
        related_concepts=["chargeback"],
        facts=["Refunds are available within 30 days."],
        constraints=["Refunds are not available after 90 days."],
        synonyms=["reimbursement"],
        source="policy_manual",
        confidence=FactConfidence.VERIFIED,
    )

    facts = semantic_facts_from_ontology_entry(
        entry,
        tenant_id="tenant_a",
        ontology_id="support",
        ontology_version="v1",
    )

    types = [fact.fact_type for fact in facts]
    assert SemanticFactType.CONCEPT in types
    assert SemanticFactType.DEFINITION in types
    assert SemanticFactType.FACT in types
    assert SemanticFactType.CONSTRAINT in types
    assert SemanticFactType.SYNONYM in types
    assert all(fact.tenant_id == "tenant_a" for fact in facts)
    assert all(fact.ontology_id == "support" for fact in facts)
    assert facts[0].aliases == ["reimbursement"]
    assert facts[0].confidence == 1.0


def test_knowledge_fact_converts_with_provenance():
    retrieved = KnowledgeFact(
        content="Refunds are available within 30 days.",
        source="support_policy.pdf",
        relevance_score=0.86,
        metadata={"subject": "refund", "source_uri": "s3://docs/support_policy.pdf"},
        chunk_id="chunk_1",
        document_id="doc_1",
    )

    fact = SemanticFact.from_knowledge_fact(
        retrieved,
        tenant_id="tenant_a",
        ontology_version="adapter:v1",
    )

    assert fact.subject == "refund"
    assert fact.relation == "supports"
    assert fact.object == "Refunds are available within 30 days."
    assert fact.confidence == 0.86
    assert fact.state == TrivalentDecision.TRUE
    assert fact.provenance.document_id == "doc_1"
    assert fact.provenance.chunk_id == "chunk_1"
    assert fact.provenance.source_uri == "s3://docs/support_policy.pdf"


def test_legacy_fact_converts_state_and_metadata():
    legacy = KnowledgeOntology()
    legacy_fact_id = legacy.add_fact(
        "refund",
        "allowed_until",
        "30 days",
        "TRUE",
        metadata={"source": "legacy_graph", "confidence": 0.75},
    )
    legacy_fact = legacy.get_fact(legacy_fact_id)

    fact = SemanticFact.from_legacy_fact(
        legacy_fact,
        tenant_id="tenant_a",
        ontology_version="legacy:v1",
    )

    assert fact.subject == "refund"
    assert fact.relation == "allowed_until"
    assert fact.object == "30 days"
    assert fact.state == TrivalentDecision.TRUE
    assert fact.source == "legacy_graph"
    assert fact.confidence == 0.75
    assert fact.metadata["legacy_fact_id"] == legacy_fact_id


def test_semantic_ontology_enforces_tenant_isolation():
    ontology = SemanticOntology(
        tenant_id="tenant_a",
        ontology_id="support",
        version="v1",
    )
    fact = SemanticFact(
        subject="refund",
        relation="has_fact",
        object="Refunds are available within 30 days.",
        tenant_id="tenant_a",
    )

    ontology.add_fact(fact)

    assert ontology.facts[0].ontology_id == "support"
    assert ontology.facts[0].ontology_version == "v1"

    wrong_tenant_fact = fact.model_copy(update={"tenant_id": "tenant_b"})
    with pytest.raises(ValueError, match="tenant_id"):
        ontology.add_fact(wrong_tenant_fact)


def test_semantic_fact_validation_rejects_invalid_ranges():
    with pytest.raises(ValidationError):
        SemanticFactProvenance(span_start=10, span_end=5)

    with pytest.raises(ValidationError):
        SemanticFact(
            subject="refund",
            relation="has_fact",
            object="Refunds are available within 30 days.",
            tenant_id="tenant_a",
            confidence=1.2,
        )
