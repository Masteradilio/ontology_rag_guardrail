"""Commercial pilot planning and metrics helpers.

These helpers prepare pilot artifacts and compute metrics from reviewed pilot
samples. They do not claim buyer validation; real customer feedback must be
collected separately.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Iterable, List, Literal, Optional

from pydantic import BaseModel, Field


PilotWorkflow = Literal["rag_answer_approval", "agent_tool_authorization", "policy_compliance_audit"]


class PilotScope(BaseModel):
    workflow: PilotWorkflow
    duration_days: int = 14
    goal: str
    inputs: List[str]
    integration_points: List[str]
    success_metrics: List[str]
    exit_criteria: Dict[str, str]
    security_constraints: List[str]


class PilotReviewSample(BaseModel):
    sample_id: str
    workflow: PilotWorkflow
    expected_decision: Literal["TRUE", "FALSE", "UNDECIDABLE"]
    observed_decision: Literal["TRUE", "FALSE", "UNDECIDABLE"]
    proof_lookup_ok: bool
    audit_reconstruction_minutes_before: float
    audit_reconstruction_minutes_after: float
    setup_minutes: float = 0.0
    reviewer_usefulness_score: Optional[float] = Field(default=None, ge=1.0, le=5.0)
    notes: List[str] = Field(default_factory=list)


class PilotMetrics(BaseModel):
    workflow: str
    sample_count: int
    false_allow_rate: float
    false_block_rate: float
    useful_abstention_rate: float
    proof_lookup_success_rate: float
    audit_minutes_before_avg: float
    audit_minutes_after_avg: float
    audit_reconstruction_time_delta_pct: float
    setup_hours: float
    reviewer_usefulness_avg: Optional[float]
    blockers: List[str] = Field(default_factory=list)


def default_pilot_scopes() -> List[PilotScope]:
    """Return the initial 2-week pilot designs for C1."""

    common_constraints = [
        "Synthetic data first; customer data only after written approval.",
        "No external LLM provider calls unless the customer approves them.",
        "Proof logs must not include raw secrets or unnecessary personal data.",
        "Human review remains required for high-risk UNDECIDABLE decisions.",
    ]
    return [
        PilotScope(
            workflow="rag_answer_approval",
            goal="Validate claim-level RAG answer approval with auditable abstention.",
            inputs=["support answers", "retrieved evidence ids", "expected claim labels"],
            integration_points=["post-generation answer_check", "application trace proof_id"],
            success_metrics=[
                "false_allow_rate",
                "false_block_rate",
                "useful_abstention_rate",
                "audit_reconstruction_time_delta_pct",
            ],
            exit_criteria={
                "proceed": "Unsupported or contradicted claims are routed away from silent allow.",
                "iterate": "Useful abstention exists but integration or evidence mapping is incomplete.",
                "stop": "The workflow has no repeated audit or unsupported-answer pain.",
            },
            security_constraints=common_constraints,
        ),
        PilotScope(
            workflow="agent_tool_authorization",
            goal="Validate semantic authorization before agent tool execution.",
            inputs=["tool call traces", "actor/action/resource/purpose tuples", "policy facts"],
            integration_points=["pre-tool action_check", "approval/escalation queue"],
            success_metrics=[
                "false_allow_rate",
                "false_block_rate",
                "useful_abstention_rate",
                "proof_lookup_success_rate",
            ],
            exit_criteria={
                "proceed": "Allowed, denied, and missing authorization paths are useful to workflow owners.",
                "iterate": "Policy modeling needs refinement but proof traces are useful.",
                "stop": "Existing hard-coded controls are sufficient and audit is not a pain.",
            },
            security_constraints=common_constraints,
        ),
        PilotScope(
            workflow="policy_compliance_audit",
            goal="Validate policy/compliance review with proof metadata and explicit limitations.",
            inputs=["LLM outputs", "policy rules", "review labels"],
            integration_points=["policy_check", "proof lookup", "risk review dashboard export"],
            success_metrics=[
                "proof_lookup_success_rate",
                "audit_reconstruction_time_delta_pct",
                "reviewer_usefulness_avg",
            ],
            exit_criteria={
                "proceed": "Risk reviewers can reconstruct decisions faster with proof metadata.",
                "iterate": "Policy uncertainty needs stricter configuration before paid use.",
                "stop": "Reviewers do not trust or use the proof records.",
            },
            security_constraints=common_constraints + ["Legal review remains outside Quimera scope."],
        ),
    ]


def compute_pilot_metrics(
    samples: Iterable[PilotReviewSample],
    *,
    workflow: PilotWorkflow,
    blockers: Optional[List[str]] = None,
) -> PilotMetrics:
    records = [sample for sample in samples if sample.workflow == workflow]
    count = len(records)
    if count == 0:
        raise ValueError(f"no pilot samples for workflow {workflow}")

    false_allow = sum(
        1 for sample in records
        if sample.expected_decision != "TRUE" and sample.observed_decision == "TRUE"
    )
    false_block = sum(
        1 for sample in records
        if sample.expected_decision == "TRUE" and sample.observed_decision == "FALSE"
    )
    expected_abstain = [sample for sample in records if sample.expected_decision == "UNDECIDABLE"]
    useful_abstention = sum(
        1 for sample in expected_abstain if sample.observed_decision == "UNDECIDABLE"
    )
    proof_ok = sum(1 for sample in records if sample.proof_lookup_ok)
    before_avg = sum(sample.audit_reconstruction_minutes_before for sample in records) / count
    after_avg = sum(sample.audit_reconstruction_minutes_after for sample in records) / count
    delta_pct = ((before_avg - after_avg) / before_avg) if before_avg else 0.0
    setup_hours = sum(sample.setup_minutes for sample in records) / 60.0
    scores = [sample.reviewer_usefulness_score for sample in records if sample.reviewer_usefulness_score is not None]

    return PilotMetrics(
        workflow=workflow,
        sample_count=count,
        false_allow_rate=false_allow / count,
        false_block_rate=false_block / count,
        useful_abstention_rate=useful_abstention / len(expected_abstain) if expected_abstain else 0.0,
        proof_lookup_success_rate=proof_ok / count,
        audit_minutes_before_avg=before_avg,
        audit_minutes_after_avg=after_avg,
        audit_reconstruction_time_delta_pct=delta_pct,
        setup_hours=setup_hours,
        reviewer_usefulness_avg=sum(scores) / len(scores) if scores else None,
        blockers=blockers or [],
    )


def write_default_pilot_package(output_dir: str | Path) -> Path:
    """Write pilot scope templates as JSON for downstream pilots."""

    target = Path(output_dir)
    target.mkdir(parents=True, exist_ok=True)
    scopes = default_pilot_scopes()
    (target / "pilot_scopes.json").write_text(
        json.dumps([scope.model_dump() for scope in scopes], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return target
