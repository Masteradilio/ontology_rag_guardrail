import pytest
from pydantic import ValidationError

from quimera_semantic_trust_guardrail import (
    DecisionStatus,
    EvidenceRecord,
    ProofMetadata,
    RecommendedAction,
    SemanticTrustDecision,
    TrivalentDecision,
    map_groundcite_label,
)


def test_semantic_trust_decision_serializes_to_json_safe_values():
    decision = SemanticTrustDecision(
        decision=TrivalentDecision.TRUE,
        recommended_action=RecommendedAction.ALLOW,
        confidence=0.91,
        status=DecisionStatus.SUPPORTED,
        subject="Refunds are available within 30 days.",
        evidence=[
            EvidenceRecord(
                evidence_id="ev_1",
                document_id="policy_doc",
                chunk_id="chunk_7",
                span_start=10,
                span_end=42,
                score=0.88,
            )
        ],
        proof=ProofMetadata(
            proof_id="QSTG-test-proof",
            tenant_id="tenant_a",
            ontology_version="ontology:v1",
            policy_version="policy:v1",
            decision_path=["groundcite:supported", "trivalent:TRUE"],
        ),
    )

    payload = decision.model_dump(mode="json")

    assert payload["decision"] == "TRUE"
    assert payload["recommended_action"] == "allow"
    assert payload["status"] == "supported"
    assert payload["evidence"][0]["document_id"] == "policy_doc"
    assert payload["proof"]["ontology_version"] == "ontology:v1"

    restored = SemanticTrustDecision.model_validate(payload)
    assert restored.decision == TrivalentDecision.TRUE
    assert restored.proof.proof_id == "QSTG-test-proof"


@pytest.mark.parametrize(
    ("label", "expected_decision", "expected_action", "expected_status"),
    [
        (
            "supported",
            TrivalentDecision.TRUE,
            RecommendedAction.ALLOW,
            DecisionStatus.SUPPORTED,
        ),
        (
            "contradicted",
            TrivalentDecision.FALSE,
            RecommendedAction.BLOCK,
            DecisionStatus.CONTRADICTED,
        ),
        (
            "unsupported",
            TrivalentDecision.UNDECIDABLE,
            RecommendedAction.ABSTAIN,
            DecisionStatus.UNSUPPORTED,
        ),
        (
            "partially_unsupported",
            TrivalentDecision.UNDECIDABLE,
            RecommendedAction.WARN,
            DecisionStatus.PARTIALLY_UNSUPPORTED,
        ),
    ],
)
def test_groundcite_labels_map_to_trivalent_contract(
    label, expected_decision, expected_action, expected_status
):
    decision, action, status = map_groundcite_label(label)

    assert decision == expected_decision
    assert action == expected_action
    assert status == expected_status


def test_decision_can_be_created_from_groundcite_label():
    result = SemanticTrustDecision.from_groundcite_label(
        "unsupported",
        confidence=0.44,
        subject="The answer includes an unsupported claim.",
        metadata={"claim_id": "claim_1"},
    )

    assert result.decision == TrivalentDecision.UNDECIDABLE
    assert result.recommended_action == RecommendedAction.ABSTAIN
    assert result.source == "groundcite"
    assert result.metadata["claim_id"] == "claim_1"


def test_unknown_groundcite_label_is_rejected():
    with pytest.raises(ValueError, match="Unsupported GroundCite label"):
        map_groundcite_label("maybe_supported")


def test_validation_rejects_invalid_confidence_span_and_action():
    with pytest.raises(ValidationError):
        EvidenceRecord(document_id="doc", span_start=20, span_end=10)

    with pytest.raises(ValidationError):
        SemanticTrustDecision(
            decision=TrivalentDecision.TRUE,
            recommended_action=RecommendedAction.BLOCK,
            confidence=0.7,
        )

    with pytest.raises(ValidationError):
        SemanticTrustDecision(
            decision=TrivalentDecision.FALSE,
            recommended_action=RecommendedAction.BLOCK,
            confidence=1.2,
        )

