"""Unified semantic fact and ontology contracts."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Iterable, List, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .decision_model import TrivalentDecision


class SemanticFactType(str, Enum):
    """Supported semantic fact categories for ontology and policy modeling."""

    CONCEPT = "concept"
    DEFINITION = "definition"
    FACT = "fact"
    CONSTRAINT = "constraint"
    SYNONYM = "synonym"
    POLICY = "policy"


class SemanticFactProvenance(BaseModel):
    """Source details needed to audit how a fact entered the ontology."""

    model_config = ConfigDict(extra="forbid")

    source: Optional[str] = None
    document_id: Optional[str] = None
    chunk_id: Optional[str] = None
    span_start: Optional[int] = Field(default=None, ge=0)
    span_end: Optional[int] = Field(default=None, ge=0)
    source_uri: Optional[str] = None
    extractor: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_span(self) -> "SemanticFactProvenance":
        if self.span_start is not None and self.span_end is not None:
            if self.span_end < self.span_start:
                raise ValueError("span_end must be greater than or equal to span_start")
        return self


class SemanticFact(BaseModel):
    """Tenant-scoped semantic fact contract shared by runtime, ontology, and policy."""

    model_config = ConfigDict(extra="forbid")

    subject: str = Field(min_length=1)
    relation: str = Field(min_length=1)
    object: str = Field(min_length=1)
    fact_type: SemanticFactType = SemanticFactType.FACT
    state: TrivalentDecision = TrivalentDecision.TRUE
    source: Optional[str] = None
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    valid_from: Optional[datetime] = None
    valid_until: Optional[datetime] = None
    tenant_id: str = Field(min_length=1)
    ontology_id: Optional[str] = None
    ontology_version: Optional[str] = None
    policy_id: Optional[str] = None
    policy_version: Optional[str] = None
    provenance: SemanticFactProvenance = Field(default_factory=SemanticFactProvenance)
    aliases: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @model_validator(mode="after")
    def validate_validity_window(self) -> "SemanticFact":
        if self.valid_from and self.valid_until and self.valid_until < self.valid_from:
            raise ValueError("valid_until must be greater than or equal to valid_from")
        return self

    @classmethod
    def from_knowledge_fact(
        cls,
        fact: Any,
        *,
        tenant_id: str,
        relation: str = "supports",
        subject: Optional[str] = None,
        ontology_version: Optional[str] = None,
    ) -> "SemanticFact":
        """Create a semantic fact from a retrieved adapter `KnowledgeFact`."""

        metadata = dict(getattr(fact, "metadata", {}) or {})
        source = getattr(fact, "source", None)
        return cls(
            subject=subject or metadata.get("subject") or "retrieved_evidence",
            relation=relation,
            object=getattr(fact, "content"),
            fact_type=SemanticFactType.FACT,
            state=TrivalentDecision.TRUE,
            source=source,
            confidence=float(getattr(fact, "relevance_score", 0.0)),
            tenant_id=tenant_id,
            ontology_version=ontology_version,
            provenance=SemanticFactProvenance(
                source=source,
                document_id=getattr(fact, "document_id", None),
                chunk_id=getattr(fact, "chunk_id", None),
                source_uri=metadata.get("source_uri"),
                metadata=metadata,
            ),
            metadata=metadata,
        )

    @classmethod
    def from_legacy_fact(
        cls,
        fact: Any,
        *,
        tenant_id: str,
        ontology_version: Optional[str] = None,
    ) -> "SemanticFact":
        """Create a semantic fact from `quimera_legacy.knowledge_ontology.Fact`."""

        state = _coerce_legacy_state(getattr(fact, "state", None))
        metadata = dict(getattr(fact, "metadata", {}) or {})
        return cls(
            subject=getattr(fact, "subject"),
            relation=getattr(fact, "relation"),
            object=getattr(fact, "object"),
            fact_type=SemanticFactType.FACT,
            state=state,
            source=metadata.get("source"),
            confidence=float(metadata.get("confidence", 1.0)),
            tenant_id=tenant_id,
            ontology_version=ontology_version,
            metadata={"legacy_fact_id": getattr(fact, "fact_id", None), **metadata},
        )


class SemanticOntology(BaseModel):
    """Minimal tenant-scoped collection for unified semantic facts."""

    model_config = ConfigDict(extra="forbid")

    tenant_id: str = Field(min_length=1)
    ontology_id: str = Field(min_length=1)
    version: str = "1"
    facts: List[SemanticFact] = Field(default_factory=list)

    def add_fact(self, fact: SemanticFact) -> None:
        if fact.tenant_id != self.tenant_id:
            raise ValueError("fact tenant_id must match ontology tenant_id")
        if fact.ontology_id and fact.ontology_id != self.ontology_id:
            raise ValueError("fact ontology_id must match ontology ontology_id")
        self.facts.append(
            fact.model_copy(
                update={
                    "ontology_id": self.ontology_id,
                    "ontology_version": fact.ontology_version or self.version,
                }
            )
        )

    def facts_by_type(self, fact_type: SemanticFactType) -> List[SemanticFact]:
        return [fact for fact in self.facts if fact.fact_type == fact_type]


def semantic_facts_from_ontology_entry(
    entry: Any,
    *,
    tenant_id: str,
    ontology_id: Optional[str] = None,
    ontology_version: Optional[str] = None,
) -> List[SemanticFact]:
    """Expand the legacy tenant `OntologyEntry` shape into semantic facts."""

    concept = getattr(entry, "concept")
    source = getattr(entry, "source", None)
    confidence = _confidence_to_score(getattr(entry, "confidence", None))
    common = {
        "tenant_id": tenant_id,
        "ontology_id": ontology_id,
        "ontology_version": ontology_version,
        "source": source,
        "confidence": confidence,
        "provenance": SemanticFactProvenance(source=source),
    }

    facts = [
        SemanticFact(
            subject=concept,
            relation="is_a",
            object="concept",
            fact_type=SemanticFactType.CONCEPT,
            aliases=list(getattr(entry, "synonyms", []) or []),
            **common,
        ),
        SemanticFact(
            subject=concept,
            relation="defined_as",
            object=getattr(entry, "definition"),
            fact_type=SemanticFactType.DEFINITION,
            **common,
        ),
    ]

    for related in getattr(entry, "related_concepts", []) or []:
        facts.append(
            SemanticFact(
                subject=concept,
                relation="related_to",
                object=related,
                fact_type=SemanticFactType.FACT,
                **common,
            )
        )

    for text in getattr(entry, "facts", []) or []:
        facts.append(
            SemanticFact(
                subject=concept,
                relation="has_fact",
                object=text,
                fact_type=SemanticFactType.FACT,
                **common,
            )
        )

    for constraint in getattr(entry, "constraints", []) or []:
        facts.append(
            SemanticFact(
                subject=concept,
                relation="constrained_by",
                object=constraint,
                fact_type=SemanticFactType.CONSTRAINT,
                state=TrivalentDecision.TRUE,
                **common,
            )
        )

    for synonym in getattr(entry, "synonyms", []) or []:
        facts.append(
            SemanticFact(
                subject=concept,
                relation="has_synonym",
                object=synonym,
                fact_type=SemanticFactType.SYNONYM,
                **common,
            )
        )

    return facts


def semantic_facts_from_ontology_entries(
    entries: Iterable[Any],
    *,
    tenant_id: str,
    ontology_id: Optional[str] = None,
    ontology_version: Optional[str] = None,
) -> List[SemanticFact]:
    facts: List[SemanticFact] = []
    for entry in entries:
        facts.extend(
            semantic_facts_from_ontology_entry(
                entry,
                tenant_id=tenant_id,
                ontology_id=ontology_id,
                ontology_version=ontology_version,
            )
        )
    return facts


def _coerce_legacy_state(state: Any) -> TrivalentDecision:
    if hasattr(state, "collapse"):
        state = state.collapse(deterministic=True)
    if isinstance(state, TrivalentDecision):
        return state
    return TrivalentDecision(str(state).upper())


def _confidence_to_score(confidence: Any) -> float:
    value = getattr(confidence, "value", confidence)
    return {
        "verified": 1.0,
        "probable": 0.8,
        "possible": 0.5,
        "unverified": 0.0,
        None: 0.0,
    }.get(value, 0.0)
