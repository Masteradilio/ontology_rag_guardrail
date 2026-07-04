from __future__ import annotations

import json
from pathlib import Path

from quimera_semantic_trust_guardrail.evaluation import (
    PilotReviewSample,
    compute_pilot_metrics,
    default_pilot_scopes,
    write_default_pilot_package,
)


def _samples():
    return [
        PilotReviewSample(
            sample_id="rag-1",
            workflow="rag_answer_approval",
            expected_decision="TRUE",
            observed_decision="TRUE",
            proof_lookup_ok=True,
            audit_reconstruction_minutes_before=20,
            audit_reconstruction_minutes_after=5,
            setup_minutes=60,
            reviewer_usefulness_score=4,
        ),
        PilotReviewSample(
            sample_id="rag-2",
            workflow="rag_answer_approval",
            expected_decision="UNDECIDABLE",
            observed_decision="UNDECIDABLE",
            proof_lookup_ok=True,
            audit_reconstruction_minutes_before=22,
            audit_reconstruction_minutes_after=6,
            setup_minutes=30,
            reviewer_usefulness_score=5,
        ),
        PilotReviewSample(
            sample_id="agent-1",
            workflow="agent_tool_authorization",
            expected_decision="FALSE",
            observed_decision="TRUE",
            proof_lookup_ok=False,
            audit_reconstruction_minutes_before=10,
            audit_reconstruction_minutes_after=8,
            setup_minutes=45,
            notes=["false allow to investigate"],
        ),
    ]


def test_default_pilot_scopes_cover_three_workflows():
    scopes = default_pilot_scopes()

    assert {scope.workflow for scope in scopes} == {
        "rag_answer_approval",
        "agent_tool_authorization",
        "policy_compliance_audit",
    }
    assert all(scope.duration_days == 14 for scope in scopes)
    assert all(scope.security_constraints for scope in scopes)


def test_compute_pilot_metrics_separates_value_from_blockers():
    metrics = compute_pilot_metrics(
        _samples(),
        workflow="rag_answer_approval",
        blockers=["evidence mapping needs customer review"],
    )

    assert metrics.sample_count == 2
    assert metrics.false_allow_rate == 0.0
    assert metrics.false_block_rate == 0.0
    assert metrics.useful_abstention_rate == 1.0
    assert metrics.proof_lookup_success_rate == 1.0
    assert metrics.audit_reconstruction_time_delta_pct > 0.7
    assert metrics.setup_hours == 1.5
    assert metrics.reviewer_usefulness_avg == 4.5
    assert metrics.blockers == ["evidence mapping needs customer review"]


def test_compute_pilot_metrics_catches_false_allow():
    metrics = compute_pilot_metrics(_samples(), workflow="agent_tool_authorization")

    assert metrics.sample_count == 1
    assert metrics.false_allow_rate == 1.0
    assert metrics.proof_lookup_success_rate == 0.0


def test_write_default_pilot_package(tmp_path):
    output_dir = write_default_pilot_package(tmp_path)
    payload = json.loads((output_dir / "pilot_scopes.json").read_text(encoding="utf-8"))

    assert len(payload) == 3
    assert payload[0]["duration_days"] == 14


def test_c1_documents_exist_and_preserve_claim_boundaries():
    docs = [
        Path("docs/commercial_pilot_design.md"),
        Path("docs/commercial_pilot_metrics_protocol.md"),
        Path("docs/commercial_pricing_packaging_hypotheses.md"),
        Path("docs/commercial_pilot_report_template.md"),
    ]
    for path in docs:
        text = path.read_text(encoding="utf-8")
        assert text.strip()
    assert "not validated pricing" in Path("docs/commercial_pricing_packaging_hypotheses.md").read_text(encoding="utf-8")
    assert "not legal certification" in Path("docs/commercial_pilot_report_template.md").read_text(encoding="utf-8")
