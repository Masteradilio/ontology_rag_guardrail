"""Central trivalent decision contract for semantic trust checks."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class TrivalentDecision(str, Enum):
    """Auditable semantic decision state."""

    TRUE = "TRUE"
    FALSE = "FALSE"
    UNDECIDABLE = "UNDECIDABLE"


class RecommendedAction(str, Enum):
    """Operational action a caller can take after a decision."""

    ALLOW = "allow"
    WARN = "warn"
    RETRY = "retry"
    ABSTAIN = "abstain"
    BLOCK = "block"
    ESCALATE = "escalate"


class DecisionStatus(str, Enum):
    """Source-facing status before it is collapsed into a trivalent state."""

    SUPPORTED = "supported"
    CONTRADICTED = "contradicted"
    UNSUPPORTED = "unsupported"
    PARTIALLY_UNSUPPORTED = "partially_unsupported"
    ERROR = "error"
    POLICY_ALLOWED = "policy_allowed"
    POLICY_DENIED = "policy_denied"
    POLICY_MISSING = "policy_missing"


class EvidenceRecord(BaseModel):
    """Evidence item used to support or explain a decision."""

    model_config = ConfigDict(extra="forbid")

    evidence_id: Optional[str] = None
    text: Optional[str] = None
    source: Optional[str] = None
    document_id: Optional[str] = None
    chunk_id: Optional[str] = None
    span_start: Optional[int] = Field(default=None, ge=0)
    span_end: Optional[int] = Field(default=None, ge=0)
    score: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_span(self) -> "EvidenceRecord":
        if self.span_start is not None and self.span_end is not None:
            if self.span_end < self.span_start:
                raise ValueError("span_end must be greater than or equal to span_start")
        return self


class ContradictionRecord(BaseModel):
    """Contradictory evidence or rule that makes a claim/action false."""

    model_config = ConfigDict(extra="forbid")

    statement: str
    evidence: List[EvidenceRecord] = Field(default_factory=list)
    source: Optional[str] = None
    rule_id: Optional[str] = None
    confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class MissingRequirement(BaseModel):
    """Evidence, policy, or ontology requirement that was needed but absent."""

    model_config = ConfigDict(extra="forbid")

    requirement_id: Optional[str] = None
    description: str
    requirement_type: str = "evidence"
    blocking: bool = True
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ProofMetadata(BaseModel):
    """Metadata required to reconstruct and audit a semantic decision."""

    model_config = ConfigDict(extra="forbid")

    proof_id: Optional[str] = None
    tenant_id: Optional[str] = None
    ontology_version: Optional[str] = None
    policy_version: Optional[str] = None
    ruleset_version: Optional[str] = None
    ledger_ref: Optional[str] = None
    generated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    decision_path: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class SemanticTrustDecision(BaseModel):
    """Single serializable result for claim, answer, action, and policy checks."""

    model_config = ConfigDict(extra="forbid")

    decision: TrivalentDecision
    recommended_action: RecommendedAction
    confidence: float = Field(ge=0.0, le=1.0)
    status: Optional[DecisionStatus] = None
    subject: Optional[str] = None
    evidence: List[EvidenceRecord] = Field(default_factory=list)
    contradictions: List[ContradictionRecord] = Field(default_factory=list)
    missing_requirements: List[MissingRequirement] = Field(default_factory=list)
    proof: ProofMetadata = Field(default_factory=ProofMetadata)
    source: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("recommended_action")
    @classmethod
    def validate_recommended_action(
        cls, action: RecommendedAction, info: Any
    ) -> RecommendedAction:
        decision = info.data.get("decision")
        if decision == TrivalentDecision.TRUE and action in {
            RecommendedAction.BLOCK,
            RecommendedAction.ABSTAIN,
        }:
            raise ValueError("TRUE decisions cannot recommend block or abstain")
        if decision == TrivalentDecision.FALSE and action == RecommendedAction.ALLOW:
            raise ValueError("FALSE decisions cannot recommend allow")
        return action

    @classmethod
    def from_groundcite_label(
        cls,
        label: str,
        *,
        confidence: float,
        subject: Optional[str] = None,
        evidence: Optional[List[EvidenceRecord]] = None,
        proof: Optional[ProofMetadata] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> "SemanticTrustDecision":
        decision, action, status = map_groundcite_label(label)
        return cls(
            decision=decision,
            recommended_action=action,
            confidence=confidence,
            status=status,
            subject=subject,
            evidence=evidence or [],
            proof=proof or ProofMetadata(),
            source="groundcite",
            metadata=metadata or {},
        )


_GROUNDCITE_LABEL_MAP: Dict[str, tuple[TrivalentDecision, RecommendedAction, DecisionStatus]] = {
    "supported": (
        TrivalentDecision.TRUE,
        RecommendedAction.ALLOW,
        DecisionStatus.SUPPORTED,
    ),
    "contradicted": (
        TrivalentDecision.FALSE,
        RecommendedAction.BLOCK,
        DecisionStatus.CONTRADICTED,
    ),
    "unsupported": (
        TrivalentDecision.UNDECIDABLE,
        RecommendedAction.ABSTAIN,
        DecisionStatus.UNSUPPORTED,
    ),
    "partially_unsupported": (
        TrivalentDecision.UNDECIDABLE,
        RecommendedAction.WARN,
        DecisionStatus.PARTIALLY_UNSUPPORTED,
    ),
    "abstain_needed": (
        TrivalentDecision.UNDECIDABLE,
        RecommendedAction.ABSTAIN,
        DecisionStatus.UNSUPPORTED,
    ),
    "error": (
        TrivalentDecision.UNDECIDABLE,
        RecommendedAction.ESCALATE,
        DecisionStatus.ERROR,
    ),
}


def map_groundcite_label(
    label: str,
) -> tuple[TrivalentDecision, RecommendedAction, DecisionStatus]:
    """Map GroundCite claim labels into the product trivalent contract."""

    normalized = label.strip().lower()
    if normalized not in _GROUNDCITE_LABEL_MAP:
        raise ValueError(f"Unsupported GroundCite label: {label!r}")
    return _GROUNDCITE_LABEL_MAP[normalized]

