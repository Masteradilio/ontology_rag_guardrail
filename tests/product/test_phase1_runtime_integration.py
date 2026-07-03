import asyncio

from quimera_semantic_trust_guardrail import (
    GuardrailsConfig,
    QuimeraGuardrails,
    QuimeraOutputValidator,
    TrivalentDecision,
    SemanticFactType,
    SimpleKnowledgeAdapter,
    TenantOntologyManager,
)
from quimera_semantic_trust_guardrail.adapters.ontology_sync import (
    ExtractedFact,
    FactType,
    OntologySync,
)


def test_output_validator_uses_knowledge_adapter_for_supported_claims():
    async def run():
        adapter = SimpleKnowledgeAdapter()
        adapter.add_fact(
            "Refunds are available within 30 days.",
            source="policy",
            keywords=["refunds"],
        )
        validator = QuimeraOutputValidator(
            tenant_id="tenant_a",
            knowledge_adapter=adapter,
            config={
                "relevance_check_enabled": False,
                "compliance_check_enabled": False,
                "consistency_check_enabled": False,
                "completeness_check_enabled": False,
                "generate_proofs": False,
            },
        )

        result = await validator.validate(
            "What is the refund policy?",
            "Refunds are available within 30 days.",
        )

        assert result.hallucinations == []
        assert result.is_valid is True
        assert validator.get_statistics()["has_knowledge_adapter"] is True

    asyncio.run(run())


def test_adapter_uncertain_claim_returns_undecidable_not_false():
    async def run():
        adapter = SimpleKnowledgeAdapter()
        validator = QuimeraOutputValidator(
            tenant_id="tenant_a",
            knowledge_adapter=adapter,
            config={
                "relevance_check_enabled": False,
                "compliance_check_enabled": False,
                "consistency_check_enabled": False,
                "completeness_check_enabled": False,
                "generate_proofs": False,
            },
        )

        result = await validator.validate(
            "What is the refund policy?",
            "Refunds are available after 120 days.",
        )

        assert len(result.hallucinations) == 1
        assert result.hallucinations[0].verified is None
        assert result.hallucinations[0].confidence == 0.0

    asyncio.run(run())


def test_adapter_failure_returns_undecidable_claim_verification():
    async def run():
        class FailingAdapter:
            async def verify_claim(self, claim, context=None):
                raise RuntimeError("backend unavailable")

        validator = QuimeraOutputValidator(
            tenant_id="tenant_a",
            knowledge_adapter=FailingAdapter(),
            config={
                "relevance_check_enabled": False,
                "compliance_check_enabled": False,
                "consistency_check_enabled": False,
                "completeness_check_enabled": False,
                "generate_proofs": False,
            },
        )

        result = await validator.validate(
            "What is the refund policy?",
            "Refunds are available after 120 days.",
        )

        assert result.hallucinations[0].verified is None
        assert "Knowledge adapter failure" in result.hallucinations[0].reasoning

    asyncio.run(run())


def test_guardrails_accepts_knowledge_adapter_dependency(tmp_path):
    adapter = SimpleKnowledgeAdapter()
    config = GuardrailsConfig(
        proof_storage_path=str(tmp_path / "proofs"),
        ontology_storage_path=str(tmp_path / "ontologies"),
    )

    guardrails = QuimeraGuardrails(
        tenant_id="tenant_a",
        config=config,
        knowledge_adapter=adapter,
    )

    assert guardrails.knowledge_adapter is adapter
    assert guardrails.output_validator.knowledge_adapter is adapter
    assert guardrails.get_statistics()["has_knowledge_adapter"] is True


def test_ontology_sync_writes_extracted_facts_to_unified_model(tmp_path):
    async def run():
        manager = TenantOntologyManager(storage_path=str(tmp_path / "ontologies"))
        adapter = SimpleKnowledgeAdapter()
        sync = OntologySync(
            file_search_adapter=adapter,
            ontology_manager=manager,
            tenant_id="tenant_a",
            ontology_name="Support Docs",
        )

        added = await sync._add_facts_to_ontology(
            [
                ExtractedFact(
                    content="refund: available within 30 days",
                    fact_type=FactType.DEFINITION,
                    confidence=0.81,
                    source_document="support_policy.md",
                    source_chunk="chunk_1",
                    entities=["refund"],
                ),
                ExtractedFact(
                    content="refunds require proof of purchase",
                    fact_type=FactType.RULE,
                    confidence=0.74,
                    source_document="support_policy.md",
                ),
            ]
        )

        assert added == 2
        assert sync.ontology_id is not None
        facts = manager.list_facts("tenant_a", sync.ontology_id)
        assert len(facts) == 2
        assert facts[0].fact_type == SemanticFactType.DEFINITION
        assert facts[0].subject == "refund"
        assert facts[0].provenance.document_id == "support_policy.md"
        assert facts[0].provenance.chunk_id == "chunk_1"
        assert facts[1].fact_type == SemanticFactType.POLICY

    asyncio.run(run())


def test_ontology_manager_skips_duplicate_and_marks_conflict(tmp_path):
    manager = TenantOntologyManager(storage_path=str(tmp_path / "ontologies"))
    ontology_id = manager.create_ontology(
        tenant_id="tenant_a",
        name="Support",
        domain="support",
    )

    first_added = manager.add_fact(
        tenant_id="tenant_a",
        ontology_id=ontology_id,
        fact="Refunds are available within 30 days.",
        fact_type=SemanticFactType.FACT,
        subject="refund",
        relation="has_fact",
    )
    duplicate_added = manager.add_fact(
        tenant_id="tenant_a",
        ontology_id=ontology_id,
        fact="Refunds are available within 30 days.",
        fact_type=SemanticFactType.FACT,
        subject="refund",
        relation="has_fact",
    )
    conflict_added = manager.add_fact(
        tenant_id="tenant_a",
        ontology_id=ontology_id,
        fact="Refunds are available within 30 days.",
        fact_type=SemanticFactType.FACT,
        subject="refund",
        relation="has_fact",
        state=TrivalentDecision.FALSE,
    )

    facts = manager.list_facts("tenant_a", ontology_id)
    assert first_added is True
    assert duplicate_added is False
    assert conflict_added is True
    assert len(facts) == 2
    assert facts[0].metadata["conflict_detected"] is True
    assert facts[1].metadata["conflict_detected"] is True
