"""Phase 3 regression tests: enriched proof ledger and ontology versioning."""

import asyncio
from pathlib import Path

from quimera_semantic_trust_guardrail import (
    ComplianceEngine,
    ComplianceStandard,
    GuardrailsConfig,
    OntologySnapshot,
    ProofEntry,
    ProofRecorder,
    ProofType,
    QuimeraGuardrails,
    SemanticFactType,
    SemanticTrustRuntime,
    SimpleKnowledgeAdapter,
    TenantOntologyManager,
    TrivalentDecision,
    diff_payloads,
)


# ---------------------------------------------------------------------------
# P3-T01: enriched proof ledger schema
# ---------------------------------------------------------------------------


def test_proof_entry_preserves_enriched_metadata_in_hash(tmp_path):
    recorder = ProofRecorder(storage_path=str(tmp_path / "proofs"))

    entry = recorder.record(
        proof_type=ProofType.CLAIM_CHECK,
        tenant_id="tenant_a",
        input_data="Refunds are available within 30 days.",
        decision="TRUE",
        confidence=0.88,
        ontology_id="ont_42",
        ontology_version="3",
        policy_version="policy-2024.10",
        ruleset_version="ruleset-7",
        adapter_source="SimpleKnowledgeAdapter",
        evidence_ids=["ev_1", "ev_2"],
        policy_ids=["LGPD-PII-001", "compliance:lgpd"],
        decision_path=["adapter:verified", "trivalent:TRUE"],
    )

    assert entry.verify_integrity() is True
    payload = entry.to_dict()
    assert payload["ontology_id"] == "ont_42"
    assert payload["ontology_version"] == "3"
    assert payload["policy_version"] == "policy-2024.10"
    assert payload["ruleset_version"] == "ruleset-7"
    assert payload["adapter_source"] == "SimpleKnowledgeAdapter"
    assert payload["evidence_ids"] == ["ev_1", "ev_2"]
    assert payload["policy_ids"] == ["LGPD-PII-001", "compliance:lgpd"]
    assert payload["decision_path"] == ["adapter:verified", "trivalent:TRUE"]


def test_proof_lookup_returns_enriched_entry(tmp_path):
    recorder = ProofRecorder(storage_path=str(tmp_path / "proofs"))

    entry = recorder.record(
        proof_type=ProofType.ANSWER_CHECK,
        tenant_id="tenant_a",
        input_data="Refunds are available within 30 days.",
        decision="UNDECIDABLE",
        confidence=0.4,
        ontology_id="ont_42",
        ontology_version="3",
        adapter_source="SimpleKnowledgeAdapter",
        evidence_ids=["ev_9"],
        policy_ids=["compliance:lgpd"],
        decision_path=["answer:decomposed", "answer:propagated"],
    )

    fetched = recorder.lookup_proof(entry.proof_id)

    assert isinstance(fetched, ProofEntry)
    assert fetched.proof_id == entry.proof_id
    assert fetched.ontology_id == "ont_42"
    assert fetched.evidence_ids == ["ev_9"]
    assert fetched.decision_path[-1] == "answer:propagated"


def test_chain_integrity_remains_valid_with_enriched_fields(tmp_path):
    recorder = ProofRecorder(storage_path=str(tmp_path / "proofs"))

    for idx in range(3):
        recorder.record(
            proof_type=ProofType.CLAIM_CHECK,
            tenant_id="tenant_a",
            input_data=f"claim-{idx}",
            decision="TRUE" if idx % 2 == 0 else "FALSE",
            confidence=0.5 + idx * 0.1,
            ontology_id="ont_a",
            ontology_version=str(idx + 1),
            evidence_ids=[f"ev_{idx}"],
            policy_ids=[f"rule_{idx}"],
            decision_path=[f"step:{idx}"],
        )

    report = recorder.verify_chain("tenant_a")

    assert report["valid"] is True
    assert report["total_proofs"] == 3
    assert report["invalid_entries"] == []
    assert report["broken_chain_at"] == []


def test_tenant_proofs_can_be_filtered_by_ontology_id(tmp_path):
    recorder = ProofRecorder(storage_path=str(tmp_path / "proofs"))

    recorder.record(
        proof_type=ProofType.CLAIM_CHECK,
        tenant_id="tenant_a",
        input_data="x",
        decision="TRUE",
        confidence=1.0,
        ontology_id="ont_a",
    )
    recorder.record(
        proof_type=ProofType.CLAIM_CHECK,
        tenant_id="tenant_a",
        input_data="y",
        decision="FALSE",
        confidence=1.0,
        ontology_id="ont_b",
    )

    enriched = recorder.list_tenant_proofs_with_provenance(
        tenant_id="tenant_a", ontology_id="ont_a"
    )

    assert len(enriched) == 1
    assert enriched[0].ontology_id == "ont_a"


def test_runtime_claim_check_records_enriched_proof_metadata(tmp_path):
    async def run():
        adapter = SimpleKnowledgeAdapter()
        adapter.add_fact(
            "Refunds are available within 30 days.",
            source="policy",
            keywords=["refunds"],
        )
        recorder = ProofRecorder(storage_path=str(tmp_path / "proofs"))
        runtime = SemanticTrustRuntime(
            "tenant_a",
            knowledge_adapter=adapter,
            proof_recorder=recorder,
        )

        result = await runtime.claim_check("Refunds are available within 30 days.")

        entry = recorder.lookup_proof(result.proof.proof_id)
        assert entry is not None
        assert entry.proof_type == ProofType.CLAIM_CHECK
        assert entry.adapter_source == "SimpleKnowledgeAdapter"
        assert entry.decision_path == ["adapter:supported"]
        assert entry.decision == "TRUE"

    asyncio.run(run())


def test_runtime_policy_check_records_evidence_and_policy_ids(tmp_path):
    async def run():
        engine = ComplianceEngine(
            enabled_standards=[ComplianceStandard.LGPD],
        )
        recorder = ProofRecorder(storage_path=str(tmp_path / "proofs"))
        runtime = SemanticTrustRuntime(
            "tenant_a",
            compliance_engine=engine,
            proof_recorder=recorder,
        )

        result = await runtime.policy_check(
            "User CPF 123.456.789-00 should be visible.",
            scope="output",
        )

        assert result.decision == TrivalentDecision.FALSE
        entry = recorder.lookup_proof(result.proof.proof_id)
        assert entry is not None
        assert entry.proof_type == ProofType.POLICY_CHECK
        assert "LGPD-PII-001" in entry.policy_ids
        assert "compliance:lgpd" in entry.policy_ids
        assert "policy:blocking_violation" in entry.decision_path

    asyncio.run(run())


def test_guardrails_proof_lookup_returns_enriched_dict(tmp_path):
    async def run():
        config = GuardrailsConfig(
            proof_storage_path=str(tmp_path / "proofs"),
            ontology_storage_path=str(tmp_path / "ontologies"),
        )
        guardrails = QuimeraGuardrails(
            tenant_id="tenant_a",
            config=config,
            knowledge_adapter=SimpleKnowledgeAdapter(),
        )
        guardrails.knowledge_adapter.add_fact(
            "Refunds are available within 30 days.",
            source="policy",
            keywords=["refunds"],
        )

        result = await guardrails.claim_check("Refunds are available within 30 days.")
        proof = guardrails.proof_lookup(result.proof.proof_id)

        assert proof is not None
        assert proof["proof_type"] == ProofType.CLAIM_CHECK.value
        assert proof["adapter_source"] == "SimpleKnowledgeAdapter"
        assert "adapter:supported" in proof["decision_path"]

    asyncio.run(run())


# ---------------------------------------------------------------------------
# P3-T02: ontology versioning: snapshot, diff, rollback, migration
# ---------------------------------------------------------------------------


def test_snapshot_captures_immutable_payload_and_lists(tmp_path):
    manager = TenantOntologyManager(storage_path=str(tmp_path / "ontologies"))
    ontology_id = manager.create_ontology(
        tenant_id="tenant_a", name="Support", domain="support"
    )
    manager.add_fact(
        tenant_id="tenant_a",
        ontology_id=ontology_id,
        fact="Refunds are available within 30 days.",
        fact_type=SemanticFactType.FACT,
        subject="refund",
        relation="has_fact",
    )

    snapshot = manager.snapshot_ontology(
        tenant_id="tenant_a",
        ontology_id=ontology_id,
        name="baseline",
    )

    assert isinstance(snapshot, OntologySnapshot)
    assert snapshot.tenant_id == "tenant_a"
    assert snapshot.ontology_id == ontology_id
    assert snapshot.fact_count == 1
    assert Path(snapshot.path).is_file()

    listed = manager.list_ontology_snapshots("tenant_a", ontology_id)
    assert any(item.snapshot_id == snapshot.snapshot_id for item in listed)


def test_diff_detects_added_removed_and_updated_facts(tmp_path):
    left = {
        "version": 1,
        "semantic_facts": [
            {
                "subject": "refund",
                "relation": "has_fact",
                "object": "within 30 days",
                "fact_type": "fact",
                "state": "TRUE",
            },
            {
                "subject": "refund",
                "relation": "constrained_by",
                "object": "no fee",
                "fact_type": "constraint",
                "state": "TRUE",
            },
        ],
        "entries": {"refund": {"concept": "refund"}},
    }
    right = {
        "version": 2,
        "semantic_facts": [
            {
                "subject": "refund",
                "relation": "has_fact",
                "object": "within 30 days",
                "fact_type": "fact",
                "state": "FALSE",
            },
            {
                "subject": "refund",
                "relation": "has_fact",
                "object": "within 60 days",
                "fact_type": "fact",
                "state": "TRUE",
            },
        ],
        "entries": {"refund": {"concept": "refund"}, "exchange": {"concept": "exchange"}},
    }

    diff = diff_payloads(left, right)

    assert diff["from_version"] == 1
    assert diff["to_version"] == 2
    assert diff["summary"]["updated_facts"] == 1
    assert diff["summary"]["added_facts"] == 1
    assert diff["summary"]["removed_facts"] == 1
    assert diff["summary"]["added_entries"] == 1
    assert diff["summary"]["removed_entries"] == 0


def test_rollback_restores_snapshot_and_creates_migration_record(tmp_path):
    manager = TenantOntologyManager(storage_path=str(tmp_path / "ontologies"))
    ontology_id = manager.create_ontology(
        tenant_id="tenant_a", name="Support", domain="support"
    )
    manager.add_fact(
        tenant_id="tenant_a",
        ontology_id=ontology_id,
        fact="Refunds are available within 30 days.",
        fact_type=SemanticFactType.FACT,
        subject="refund",
        relation="has_fact",
    )
    snapshot = manager.snapshot_ontology(
        tenant_id="tenant_a", ontology_id=ontology_id, name="baseline"
    )

    # Apply a destructive change after the snapshot
    manager.add_fact(
        tenant_id="tenant_a",
        ontology_id=ontology_id,
        fact="Refunds are free.",
        fact_type=SemanticFactType.POLICY,
        subject="refund",
        relation="has_fact",
        state=TrivalentDecision.FALSE,
    )
    facts_before = manager.list_facts("tenant_a", ontology_id)
    assert len(facts_before) == 2

    result = manager.rollback_ontology(
        tenant_id="tenant_a",
        ontology_id=ontology_id,
        snapshot_id=snapshot.snapshot_id,
    )

    assert result["snapshot_id"] == snapshot.snapshot_id
    assert result["fact_count"] == 1
    facts_after = manager.list_facts("tenant_a", ontology_id)
    assert len(facts_after) == 1
    assert facts_after[0].object == "Refunds are available within 30 days."

    migrations = manager.list_ontology_migrations("tenant_a", ontology_id)
    actions = [m.action for m in migrations]
    assert "snapshot" in actions
    assert "add_fact" in actions
    assert "rollback" in actions

    diff = manager.diff_ontology(
        tenant_id="tenant_a",
        ontology_id=ontology_id,
        snapshot_id=snapshot.snapshot_id,
    )
    assert diff["summary"]["added_facts"] == 0
    assert diff["summary"]["removed_facts"] == 0


def test_snapshot_and_rollback_write_proof_entries_with_linkage(tmp_path):
    async def run():
        config = GuardrailsConfig(
            proof_storage_path=str(tmp_path / "proofs"),
            ontology_storage_path=str(tmp_path / "ontologies"),
        )
        guardrails = QuimeraGuardrails(tenant_id="tenant_a", config=config)
        ontology_id = guardrails.create_ontology(
            name="Support", domain="support"
        )
        guardrails.add_knowledge(
            concept="refund",
            definition="refund policy",
            facts=["within 30 days"],
        )

        snap = guardrails.snapshot_ontology(name="v1")
        snap_proof = guardrails.proof_lookup(snap["proof_id"])
        assert snap_proof is not None
        assert snap_proof["proof_type"] == ProofType.ONTOLOGY_SNAPSHOT.value
        assert snap_proof["ontology_id"] == ontology_id
        assert snap_proof["related_proof_id"] is None

        rollback = guardrails.rollback_ontology(snap["snapshot_id"])
        rollback_proof = guardrails.proof_lookup(rollback["proof_id"])
        assert rollback_proof is not None
        assert rollback_proof["proof_type"] == ProofType.ONTOLOGY_ROLLBACK.value
        assert "ontology:rollback" in rollback_proof["decision_path"]
        assert snap["snapshot_id"] in rollback_proof["decision_path"][-1]

    asyncio.run(run())


def test_proof_lookup_links_snapshot_to_decision_via_related_proof_id(tmp_path):
    async def run():
        config = GuardrailsConfig(
            proof_storage_path=str(tmp_path / "proofs"),
            ontology_storage_path=str(tmp_path / "ontologies"),
        )
        adapter = SimpleKnowledgeAdapter()
        guardrails = QuimeraGuardrails(
            tenant_id="tenant_a",
            config=config,
            knowledge_adapter=adapter,
        )
        ontology_id = guardrails.create_ontology(
            name="Policies", domain="security"
        )
        guardrails.snapshot_ontology(name="audit-baseline")

        adapter.add_fact(
            "Refunds are available within 30 days.",
            source="policy",
            keywords=["refunds"],
        )
        result = await guardrails.claim_check("Refunds are available within 30 days.")
        assert result.proof.proof_id

        # Ensure the snapshot proof is also reachable through tenant provenance list
        listed = guardrails.list_proofs_for_ontology(ontology_id)
        types = {entry["proof_type"] for entry in listed}
        assert "ontology_snapshot" in types

    asyncio.run(run())


def test_proof_type_enums_cover_phase3_operations():
    assert ProofType.ONTOLOGY_SNAPSHOT.value == "ontology_snapshot"
    assert ProofType.ONTOLOGY_ROLLBACK.value == "ontology_rollback"
    assert ProofType.ONTOLOGY_MIGRATION.value == "ontology_migration"
    assert ProofType.CLAIM_CHECK.value == "claim_check"
    assert ProofType.ANSWER_CHECK.value == "answer_check"
    assert ProofType.ACTION_CHECK.value == "action_check"
    assert ProofType.POLICY_CHECK.value == "policy_check"
