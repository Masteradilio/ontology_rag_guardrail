import asyncio

from groundcite.schema import Context

from quimera_semantic_trust_guardrail import (
    ComplianceEngine,
    ComplianceRule,
    ComplianceStandard,
    EvidenceRecord,
    GuardrailsConfig,
    QuimeraGuardrails,
    RecommendedAction,
    SemanticFactType,
    SemanticTrustRuntime,
    SimpleKnowledgeAdapter,
    TenantOntologyManager,
    TrivalentDecision,
)
from quimera_semantic_trust_guardrail.compliance_engine import ViolationSeverity


class ContradictingAdapter:
    async def verify_claim(self, claim, context=None):
        return {
            "supported": False,
            "confidence": 0.93,
            "evidence": [],
            "reasoning": "Policy states the opposite.",
            "status": "contradicted",
        }


def test_claim_check_returns_supported_decision_from_adapter():
    async def run():
        adapter = SimpleKnowledgeAdapter()
        adapter.add_fact(
            "Refunds are available within 30 days.",
            source="policy",
            keywords=["refunds"],
        )
        runtime = SemanticTrustRuntime("tenant_a", knowledge_adapter=adapter)

        result = await runtime.claim_check("Refunds are available within 30 days.")

        assert result.decision == TrivalentDecision.TRUE
        assert result.recommended_action == RecommendedAction.ALLOW
        assert result.status.value == "supported"
        assert result.proof.proof_id is not None
        assert result.evidence[0].source == "policy"

    asyncio.run(run())


def test_claim_check_distinguishes_contradicted_from_unsupported():
    async def run():
        contradicted = await SemanticTrustRuntime(
            "tenant_a",
            knowledge_adapter=ContradictingAdapter(),
        ).claim_check("Refunds are available after 120 days.")

        unsupported = await SemanticTrustRuntime("tenant_a").claim_check(
            "Refunds are available after 120 days."
        )

        assert contradicted.decision == TrivalentDecision.FALSE
        assert contradicted.status.value == "contradicted"
        assert contradicted.contradictions
        assert unsupported.decision == TrivalentDecision.UNDECIDABLE
        assert unsupported.status.value == "unsupported"
        assert unsupported.missing_requirements

    asyncio.run(run())


def test_claim_check_accepts_explicit_evidence_without_adapter():
    async def run():
        runtime = SemanticTrustRuntime("tenant_a")

        result = await runtime.claim_check(
            "Refunds are available within 30 days.",
            tenant_id="tenant_b",
            domain="support",
            context={"query": "What is the refund policy?"},
            evidence=[
                EvidenceRecord(
                    text="Refunds are available within 30 days.",
                    source="manual_policy",
                    score=0.82,
                )
            ],
        )

        assert result.decision == TrivalentDecision.TRUE
        assert result.confidence == 0.82
        assert result.evidence[0].source == "manual_policy"
        assert result.proof.tenant_id == "tenant_b"
        assert result.metadata["domain"] == "support"

    asyncio.run(run())


def test_answer_check_decomposes_claims_and_aggregates_retry():
    async def run():
        adapter = SimpleKnowledgeAdapter()
        adapter.add_fact(
            "Refunds are available within 30 days.",
            source="policy",
            keywords=["refunds"],
        )
        runtime = SemanticTrustRuntime("tenant_a", knowledge_adapter=adapter)

        result = await runtime.answer_check(
            "Refunds are available within 30 days. Exchanges are always free.",
            question="What is the refund policy?",
            lang="en",
        )

        assert result.decision == TrivalentDecision.UNDECIDABLE
        assert result.recommended_action == RecommendedAction.RETRY
        assert len(result.metadata["claims"]) == 2
        assert result.metadata["unsupported_spans"]

    asyncio.run(run())


def test_answer_check_accepts_groundcite_sample_shape():
    async def run():
        sample_context = Context(
            doc_id="policy_doc",
            text="Refunds are available within 30 days.",
        )
        adapter = SimpleKnowledgeAdapter()
        adapter.add_fact(
            sample_context.text,
            source=sample_context.doc_id,
            keywords=["refunds"],
        )
        runtime = SemanticTrustRuntime("tenant_a", knowledge_adapter=adapter)

        result = await runtime.answer_check(
            "Refunds are available within 30 days.",
            question="What is the refund policy?",
            context={"retrieved_context": sample_context.text},
            lang="en",
        )

        assert result.decision == TrivalentDecision.TRUE
        assert result.metadata["question"] == "What is the refund policy?"
        assert result.metadata["claims"][0]["status"] == "supported"

    asyncio.run(run())


def test_answer_check_propagates_dependency_failures():
    async def run():
        adapter = SimpleKnowledgeAdapter()
        adapter.add_fact(
            "It is documented.",
            source="policy",
            keywords=["documented"],
        )
        runtime = SemanticTrustRuntime("tenant_a", knowledge_adapter=adapter)

        result = await runtime.answer_check(
            "The refund window is 120 days. It is documented.",
            lang="en",
        )

        labels = result.metadata["propagated_labels"]
        assert result.decision == TrivalentDecision.UNDECIDABLE
        assert labels["c1"] == "unsupported"
        assert labels["c2"] == "unsupported"

    asyncio.run(run())


def test_action_check_allows_denies_and_escalates_missing_policy(tmp_path):
    async def run():
        manager = TenantOntologyManager(storage_path=str(tmp_path / "ontologies"))
        ontology_id = manager.create_ontology("tenant_a", "Actions", "support")
        manager.add_fact(
            tenant_id="tenant_a",
            ontology_id=ontology_id,
            fact="support_agent may refund order for support",
            fact_type=SemanticFactType.POLICY,
            subject="support_agent",
            relation="may_refund",
            metadata={
                "actor": "support_agent",
                "action": "refund",
                "resource": "order",
                "purpose": "support",
            },
        )
        manager.add_fact(
            tenant_id="tenant_a",
            ontology_id=ontology_id,
            fact="support_agent must not delete customer_record",
            fact_type=SemanticFactType.POLICY,
            subject="support_agent",
            relation="must_not_delete",
            state=TrivalentDecision.FALSE,
            metadata={
                "actor": "support_agent",
                "action": "delete",
                "resource": "customer_record",
            },
        )
        runtime = SemanticTrustRuntime(
            "tenant_a",
            ontology_manager=manager,
            ontology_id=ontology_id,
        )

        allowed = await runtime.action_check(
            actor="support_agent",
            action="refund",
            resource="order",
            purpose="support",
        )
        denied = await runtime.action_check(
            actor="support_agent",
            action="delete",
            resource="customer_record",
        )
        missing = await runtime.action_check(
            actor="support_agent",
            action="export",
            resource="customer_record",
        )

        assert allowed.decision == TrivalentDecision.TRUE
        assert denied.decision == TrivalentDecision.FALSE
        assert denied.contradictions
        assert missing.decision == TrivalentDecision.UNDECIDABLE
        assert missing.recommended_action == RecommendedAction.ESCALATE

    asyncio.run(run())


def test_policy_check_handles_lgpd_ai_act_custom_and_tenant_policy(tmp_path):
    async def run():
        custom_rule = ComplianceRule(
            rule_id="CUSTOM-SEC-001",
            standard=ComplianceStandard.CUSTOM,
            description="Secret export is forbidden",
            patterns=["export secrets"],
            severity=ViolationSeverity.HIGH,
            remediation="Remove secret export instructions",
        )
        engine = ComplianceEngine(
            enabled_standards=[ComplianceStandard.LGPD, ComplianceStandard.AI_ACT],
            custom_rules=[custom_rule],
        )
        manager = TenantOntologyManager(storage_path=str(tmp_path / "ontologies"))
        ontology_id = manager.create_ontology("tenant_a", "Policies", "security")
        manager.add_fact(
            tenant_id="tenant_a",
            ontology_id=ontology_id,
            fact="Do not reveal internal roadmap.",
            fact_type=SemanticFactType.POLICY,
            subject="roadmap",
            relation="forbidden",
            state=TrivalentDecision.FALSE,
            metadata={"scope": "output", "pattern": "internal roadmap"},
        )
        runtime = SemanticTrustRuntime(
            "tenant_a",
            ontology_manager=manager,
            ontology_id=ontology_id,
            compliance_engine=engine,
        )

        lgpd = await runtime.policy_check(
            "User CPF 123.456.789-00 should be visible.",
            scope="output",
        )
        ai_act = await runtime.policy_check(
            "The model has no data governance.",
            scope="output",
            context={"model_training": True},
        )
        custom = await runtime.policy_check("Please export secrets.", scope="output")
        tenant_policy = await runtime.policy_check(
            "Share the internal roadmap with everyone.",
            scope="output",
        )
        clean = await runtime.policy_check("Refunds are available within 30 days.")

        assert lgpd.decision == TrivalentDecision.FALSE
        assert lgpd.contradictions[0].rule_id == "LGPD-PII-001"
        assert ai_act.decision == TrivalentDecision.FALSE
        assert ai_act.contradictions[0].source == "ai_act"
        assert custom.decision == TrivalentDecision.FALSE
        assert custom.contradictions[0].rule_id == "CUSTOM-SEC-001"
        assert tenant_policy.decision == TrivalentDecision.FALSE
        assert tenant_policy.contradictions[0].evidence[0].metadata["fact_type"] == "policy"
        assert clean.decision == TrivalentDecision.TRUE
        assert clean.recommended_action == RecommendedAction.ALLOW

    asyncio.run(run())


def test_policy_check_respects_input_output_and_action_scopes(tmp_path):
    async def run():
        manager = TenantOntologyManager(storage_path=str(tmp_path / "ontologies"))
        ontology_id = manager.create_ontology("tenant_a", "Scoped Policies", "security")
        manager.add_fact(
            tenant_id="tenant_a",
            ontology_id=ontology_id,
            fact="Do not paste API keys in prompts.",
            fact_type=SemanticFactType.POLICY,
            subject="api_key",
            relation="forbidden",
            state=TrivalentDecision.FALSE,
            metadata={"scope": "input", "pattern": "api key"},
        )
        manager.add_fact(
            tenant_id="tenant_a",
            ontology_id=ontology_id,
            fact="Do not run destructive actions without approval.",
            fact_type=SemanticFactType.POLICY,
            subject="destructive_action",
            relation="forbidden",
            state=TrivalentDecision.FALSE,
            metadata={"scope": "action", "pattern": "delete production"},
        )
        runtime = SemanticTrustRuntime(
            "tenant_a",
            ontology_manager=manager,
            ontology_id=ontology_id,
        )

        output_scope = await runtime.policy_check("The API key format is documented.", scope="output")
        input_scope = await runtime.policy_check("Here is my API key.", scope="input")
        action_scope = await runtime.policy_check("delete production records", scope="action")

        assert output_scope.decision == TrivalentDecision.TRUE
        assert input_scope.decision == TrivalentDecision.FALSE
        assert action_scope.decision == TrivalentDecision.FALSE

    asyncio.run(run())


def test_quimera_guardrails_exposes_phase2_facade(tmp_path):
    async def run():
        guardrails = QuimeraGuardrails(
            tenant_id="tenant_a",
            config=GuardrailsConfig(
                proof_storage_path=str(tmp_path / "proofs"),
                ontology_storage_path=str(tmp_path / "ontologies"),
            ),
            knowledge_adapter=SimpleKnowledgeAdapter(),
        )
        guardrails.knowledge_adapter.add_fact(
            "Refunds are available within 30 days.",
            source="policy",
            keywords=["refunds"],
        )

        result = await guardrails.claim_check("Refunds are available within 30 days.")

        assert result.decision == TrivalentDecision.TRUE
        assert hasattr(guardrails, "answer_check")
        assert hasattr(guardrails, "action_check")
        assert hasattr(guardrails, "policy_check")

    asyncio.run(run())
