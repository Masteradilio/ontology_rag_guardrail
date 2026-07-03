"""Runtime SDK APIs for semantic trust checks."""

from __future__ import annotations

import hashlib
import re
from typing import Any, Dict, Iterable, List, Optional

from groundcite.claims import RegexClaimDecomposer

from .compliance_engine import ComplianceEngine, ComplianceViolation, ViolationSeverity
from .decision_model import (
    ContradictionRecord,
    DecisionStatus,
    EvidenceRecord,
    MissingRequirement,
    ProofMetadata,
    RecommendedAction,
    SemanticTrustDecision,
    TrivalentDecision,
)
from .proof_recorder import ProofRecorder, ProofType
from .semantic_fact import SemanticFact, SemanticFactType
from .tenant_ontology import TenantOntologyManager


class SemanticTrustRuntime:
    """Attachable runtime for claim, answer, action, and policy checks."""

    def __init__(
        self,
        tenant_id: str,
        ontology_manager: Optional[TenantOntologyManager] = None,
        ontology_id: Optional[str] = None,
        knowledge_adapter: Optional[Any] = None,
        compliance_engine: Optional[ComplianceEngine] = None,
        proof_recorder: Optional[ProofRecorder] = None,
        default_domain: Optional[str] = None,
    ) -> None:
        self.tenant_id = tenant_id
        self.ontology_manager = ontology_manager
        self.ontology_id = ontology_id
        self.knowledge_adapter = knowledge_adapter
        self.compliance_engine = compliance_engine
        self.proof_recorder = proof_recorder
        self.default_domain = default_domain
        self.decomposer = RegexClaimDecomposer()

    async def claim_check(
        self,
        claim: str,
        *,
        tenant_id: Optional[str] = None,
        domain: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        evidence: Optional[List[EvidenceRecord | Dict[str, Any]]] = None,
        ontology_id: Optional[str] = None,
    ) -> SemanticTrustDecision:
        """Validate one claim against evidence, adapter, ontology, and compliance."""

        tenant = tenant_id or self.tenant_id
        ontology_ref = ontology_id or self.ontology_id
        evidence_records = self._coerce_evidence(evidence)
        decision_path: List[str] = []
        contradictions: List[ContradictionRecord] = []
        missing_requirements: List[MissingRequirement] = []
        source = "runtime"

        if self.compliance_engine:
            violations = self.compliance_engine.check(claim, context)
            blocking = [v for v in violations if self._is_blocking_violation(v)]
            if blocking:
                contradictions.extend(self._violations_to_contradictions(blocking))
                decision_path.append("compliance:blocking_violation")
                return self._make_decision(
                    decision=TrivalentDecision.FALSE,
                    action=RecommendedAction.BLOCK,
                    confidence=1.0,
                    status=DecisionStatus.POLICY_DENIED,
                    subject=claim,
                    evidence=evidence_records,
                    contradictions=contradictions,
                    missing_requirements=missing_requirements,
                    proof_type=ProofType.COMPLIANCE_CHECK,
                    input_data=claim,
                    tenant_id=tenant,
                    ontology_id=ontology_ref,
                    decision_path=decision_path,
                    source="compliance",
                    metadata={"domain": domain or self.default_domain},
                )

        adapter_decision = await self._claim_check_with_adapter(claim, context)
        if adapter_decision:
            decision_path.append(f"adapter:{adapter_decision.status.value if adapter_decision.status else adapter_decision.decision.value}")
            adapter_decision.evidence.extend(evidence_records)
            adapter_decision.proof = self._build_proof_metadata(
                proof_type=ProofType.CLAIM_CHECK,
                input_data=claim,
                decision=adapter_decision.decision,
                confidence=adapter_decision.confidence,
                tenant_id=tenant,
                ontology_id=ontology_ref,
                decision_path=decision_path,
                metadata={"domain": domain or self.default_domain},
            )
            return adapter_decision

        ontology_decision = self._claim_check_with_ontology(
            claim=claim,
            tenant_id=tenant,
            ontology_id=ontology_ref,
        )
        if ontology_decision:
            ontology_decision.evidence.extend(evidence_records)
            ontology_decision.proof = self._build_proof_metadata(
                proof_type=ProofType.CLAIM_CHECK,
                input_data=claim,
                decision=ontology_decision.decision,
                confidence=ontology_decision.confidence,
                tenant_id=tenant,
                ontology_id=ontology_ref,
                decision_path=ontology_decision.proof.decision_path,
                metadata={"domain": domain or self.default_domain},
            )
            return ontology_decision

        if evidence_records:
            decision_path.append("evidence:provided")
            avg_score = self._average_score(evidence_records, default=0.7)
            return self._make_decision(
                decision=TrivalentDecision.TRUE,
                action=RecommendedAction.ALLOW,
                confidence=avg_score,
                status=DecisionStatus.SUPPORTED,
                subject=claim,
                evidence=evidence_records,
                proof_type=ProofType.CLAIM_CHECK,
                input_data=claim,
                tenant_id=tenant,
                ontology_id=ontology_ref,
                decision_path=decision_path,
                source=source,
                metadata={"domain": domain or self.default_domain},
            )

        missing_requirements.append(
            MissingRequirement(
                description="No adapter, ontology fact, or explicit evidence supported the claim.",
                requirement_type="evidence",
            )
        )
        decision_path.append("claim:missing_evidence")
        return self._make_decision(
            decision=TrivalentDecision.UNDECIDABLE,
            action=RecommendedAction.ABSTAIN,
            confidence=0.0,
            status=DecisionStatus.UNSUPPORTED,
            subject=claim,
            missing_requirements=missing_requirements,
            proof_type=ProofType.CLAIM_CHECK,
            input_data=claim,
            tenant_id=tenant,
            ontology_id=ontology_ref,
            decision_path=decision_path,
            source=source,
            metadata={"domain": domain or self.default_domain},
        )

    async def answer_check(
        self,
        answer: str,
        *,
        question: Optional[str] = None,
        tenant_id: Optional[str] = None,
        domain: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        ontology_id: Optional[str] = None,
        lang: str = "pt-BR",
    ) -> SemanticTrustDecision:
        """Decompose an answer into claims and aggregate trivalent decisions."""

        graph = self.decomposer.decompose_to_graph(answer, lang=lang)
        claims = list(graph.nodes.items())
        claim_decisions: List[SemanticTrustDecision] = []
        labels_by_id: Dict[str, str] = {}

        for claim_id, claim_text in claims:
            decision = await self.claim_check(
                claim_text,
                tenant_id=tenant_id,
                domain=domain,
                context=context,
                ontology_id=ontology_id,
            )
            claim_decisions.append(decision)
            labels_by_id[claim_id] = self._decision_to_groundcite_label(decision.decision)
            graph.labels[claim_id] = labels_by_id[claim_id]
            graph.confidences[claim_id] = decision.confidence

        propagated_labels, propagated_conf = graph.propagate()
        unsupported_spans = self._unsupported_spans(answer, claims, propagated_labels)

        if not claim_decisions:
            return self._make_decision(
                decision=TrivalentDecision.UNDECIDABLE,
                action=RecommendedAction.ABSTAIN,
                confidence=0.0,
                status=DecisionStatus.UNSUPPORTED,
                subject=answer,
                missing_requirements=[
                    MissingRequirement(
                        description="No verifiable claims could be decomposed from the answer.",
                        requirement_type="claim",
                    )
                ],
                proof_type=ProofType.ANSWER_CHECK,
                input_data=answer,
                tenant_id=tenant_id or self.tenant_id,
                ontology_id=ontology_id or self.ontology_id,
                decision_path=["answer:no_claims"],
                source="answer_check",
                metadata={"question": question, "claims": []},
            )

        if any(label == "contradicted" for label in propagated_labels.values()):
            decision = TrivalentDecision.FALSE
            action = RecommendedAction.BLOCK
            status = DecisionStatus.CONTRADICTED
        elif any(label == "unsupported" for label in propagated_labels.values()):
            decision = TrivalentDecision.UNDECIDABLE
            action = RecommendedAction.RETRY
            status = DecisionStatus.PARTIALLY_UNSUPPORTED
        else:
            decision = TrivalentDecision.TRUE
            action = RecommendedAction.ALLOW
            status = DecisionStatus.SUPPORTED

        confidence = min(propagated_conf.values()) if propagated_conf else 0.0
        return self._make_decision(
            decision=decision,
            action=action,
            confidence=confidence,
            status=status,
            subject=answer,
            evidence=[item for d in claim_decisions for item in d.evidence],
            contradictions=[item for d in claim_decisions for item in d.contradictions],
            missing_requirements=[
                item for d in claim_decisions for item in d.missing_requirements
            ],
            proof_type=ProofType.ANSWER_CHECK,
            input_data=answer,
            tenant_id=tenant_id or self.tenant_id,
            ontology_id=ontology_id or self.ontology_id,
            decision_path=["answer:decomposed", "answer:propagated"],
            source="answer_check",
            metadata={
                "question": question,
                "claims": [d.model_dump(mode="json") for d in claim_decisions],
                "propagated_labels": propagated_labels,
                "unsupported_spans": unsupported_spans,
                "dependency_graph": graph.to_mermaid(),
            },
        )

    async def action_check(
        self,
        *,
        actor: str,
        action: str,
        resource: str,
        tenant_id: Optional[str] = None,
        purpose: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        ontology_id: Optional[str] = None,
    ) -> SemanticTrustDecision:
        """Validate whether an agent action is semantically or policy authorized."""

        tenant = tenant_id or self.tenant_id
        ontology_ref = ontology_id or self.ontology_id
        action_text = f"{actor} {action} {resource} {purpose or ''}".strip()
        policy_facts = self._semantic_facts(
            tenant_id=tenant,
            ontology_id=ontology_ref,
            fact_type=SemanticFactType.POLICY,
        )

        matched = [
            fact for fact in policy_facts
            if self._policy_fact_matches_action(fact, actor, action, resource, purpose)
        ]
        denied = [fact for fact in matched if fact.state == TrivalentDecision.FALSE]
        allowed = [fact for fact in matched if fact.state == TrivalentDecision.TRUE]

        if denied:
            return self._make_decision(
                decision=TrivalentDecision.FALSE,
                action=RecommendedAction.BLOCK,
                confidence=max(f.confidence for f in denied),
                status=DecisionStatus.POLICY_DENIED,
                subject=action_text,
                contradictions=[
                    ContradictionRecord(
                        statement=f.object,
                        evidence=[self._fact_to_evidence(fact=f)],
                        source=f.source,
                        rule_id=f.policy_id,
                        confidence=f.confidence,
                    )
                    for f in denied
                ],
                proof_type=ProofType.ACTION_CHECK,
                input_data=action_text,
                tenant_id=tenant,
                ontology_id=ontology_ref,
                decision_path=["action:policy_denied"],
                source="action_check",
                metadata={"context": context or {}},
            )

        if allowed:
            return self._make_decision(
                decision=TrivalentDecision.TRUE,
                action=RecommendedAction.ALLOW,
                confidence=max(f.confidence for f in allowed),
                status=DecisionStatus.POLICY_ALLOWED,
                subject=action_text,
                evidence=[self._fact_to_evidence(f) for f in allowed],
                proof_type=ProofType.ACTION_CHECK,
                input_data=action_text,
                tenant_id=tenant,
                ontology_id=ontology_ref,
                decision_path=["action:policy_allowed"],
                source="action_check",
                metadata={"context": context or {}},
            )

        return self._make_decision(
            decision=TrivalentDecision.UNDECIDABLE,
            action=RecommendedAction.ESCALATE,
            confidence=0.0,
            status=DecisionStatus.POLICY_MISSING,
            subject=action_text,
            missing_requirements=[
                MissingRequirement(
                    description="No explicit permission or denial matched the requested action.",
                    requirement_type="policy",
                )
            ],
            proof_type=ProofType.ACTION_CHECK,
            input_data=action_text,
            tenant_id=tenant,
            ontology_id=ontology_ref,
            decision_path=["action:policy_missing"],
            source="action_check",
            metadata={"context": context or {}},
        )

    async def policy_check(
        self,
        text: str,
        *,
        tenant_id: Optional[str] = None,
        scope: str = "output",
        context: Optional[Dict[str, Any]] = None,
        ontology_id: Optional[str] = None,
    ) -> SemanticTrustDecision:
        """Evaluate compliance rules and tenant semantic policy constraints."""

        tenant = tenant_id or self.tenant_id
        ontology_ref = ontology_id or self.ontology_id
        policy_context = dict(context or {})
        policy_context.setdefault(scope, True)
        violations = self.compliance_engine.check(text, policy_context) if self.compliance_engine else []
        policy_facts = self._semantic_facts(tenant, ontology_ref, SemanticFactType.POLICY)
        fact_violations = [
            fact for fact in policy_facts
            if self._policy_fact_matches_scope(fact, text, scope)
            and fact.state == TrivalentDecision.FALSE
        ]
        supporting_policies = [
            fact for fact in policy_facts
            if self._policy_fact_matches_scope(fact, text, scope)
            and fact.state == TrivalentDecision.TRUE
        ]

        blocking_violations = [v for v in violations if self._is_blocking_violation(v)]
        review_violations = [v for v in violations if not self._is_blocking_violation(v)]

        if blocking_violations or fact_violations:
            contradictions = self._violations_to_contradictions(blocking_violations)
            contradictions.extend(
                ContradictionRecord(
                    statement=f.object,
                    evidence=[self._fact_to_evidence(f)],
                    source=f.source,
                    rule_id=f.policy_id,
                    confidence=f.confidence,
                )
                for f in fact_violations
            )
            return self._make_decision(
                decision=TrivalentDecision.FALSE,
                action=RecommendedAction.BLOCK,
                confidence=1.0,
                status=DecisionStatus.POLICY_DENIED,
                subject=text,
                contradictions=contradictions,
                proof_type=ProofType.POLICY_CHECK,
                input_data=text,
                tenant_id=tenant,
                ontology_id=ontology_ref,
                decision_path=["policy:blocking_violation"],
                source="policy_check",
                metadata={"scope": scope, "context": policy_context},
            )

        if review_violations:
            return self._make_decision(
                decision=TrivalentDecision.UNDECIDABLE,
                action=RecommendedAction.WARN,
                confidence=0.5,
                status=DecisionStatus.POLICY_MISSING,
                subject=text,
                evidence=[self._violation_to_evidence(v) for v in review_violations],
                proof_type=ProofType.POLICY_CHECK,
                input_data=text,
                tenant_id=tenant,
                ontology_id=ontology_ref,
                decision_path=["policy:review_violation"],
                source="policy_check",
                metadata={"scope": scope, "context": policy_context},
            )

        return self._make_decision(
            decision=TrivalentDecision.TRUE,
            action=RecommendedAction.ALLOW,
            confidence=max([f.confidence for f in supporting_policies], default=1.0),
            status=DecisionStatus.POLICY_ALLOWED,
            subject=text,
            evidence=[self._fact_to_evidence(f) for f in supporting_policies],
            proof_type=ProofType.POLICY_CHECK,
            input_data=text,
            tenant_id=tenant,
            ontology_id=ontology_ref,
            decision_path=["policy:allowed"],
            source="policy_check",
            metadata={"scope": scope, "context": policy_context},
        )

    async def _claim_check_with_adapter(
        self,
        claim: str,
        context: Optional[Dict[str, Any]],
    ) -> Optional[SemanticTrustDecision]:
        if not self.knowledge_adapter:
            return None
        try:
            result = await self.knowledge_adapter.verify_claim(
                claim,
                context=self._context_to_text(context),
            )
        except Exception as exc:
            return SemanticTrustDecision(
                decision=TrivalentDecision.UNDECIDABLE,
                recommended_action=RecommendedAction.ESCALATE,
                confidence=0.0,
                status=DecisionStatus.ERROR,
                subject=claim,
                missing_requirements=[
                    MissingRequirement(
                        description=f"Knowledge adapter failed: {exc}",
                        requirement_type="adapter",
                    )
                ],
                proof=ProofMetadata(decision_path=["adapter:error"]),
                source="knowledge_adapter",
            )

        status = str(result.get("status", "")).lower()
        confidence = float(result.get("confidence", 0.0))
        evidence = [self._knowledge_fact_to_evidence(f) for f in result.get("evidence", [])]
        if result.get("supported") is True or status == "verified":
            return SemanticTrustDecision(
                decision=TrivalentDecision.TRUE,
                recommended_action=RecommendedAction.ALLOW,
                confidence=confidence,
                status=DecisionStatus.SUPPORTED,
                subject=claim,
                evidence=evidence,
                proof=ProofMetadata(decision_path=["adapter:verified"]),
                source="knowledge_adapter",
            )
        if status == "contradicted":
            return SemanticTrustDecision(
                decision=TrivalentDecision.FALSE,
                recommended_action=RecommendedAction.BLOCK,
                confidence=confidence,
                status=DecisionStatus.CONTRADICTED,
                subject=claim,
                contradictions=[
                    ContradictionRecord(
                        statement=claim,
                        evidence=evidence,
                        source="knowledge_adapter",
                        confidence=confidence,
                    )
                ],
                proof=ProofMetadata(decision_path=["adapter:contradicted"]),
                source="knowledge_adapter",
            )
        return SemanticTrustDecision(
            decision=TrivalentDecision.UNDECIDABLE,
            recommended_action=RecommendedAction.ABSTAIN,
            confidence=confidence,
            status=DecisionStatus.UNSUPPORTED,
            subject=claim,
            evidence=evidence,
            missing_requirements=[
                MissingRequirement(
                    description=result.get("reasoning") or "Adapter evidence was insufficient.",
                    requirement_type="evidence",
                )
            ],
            proof=ProofMetadata(decision_path=["adapter:uncertain"]),
            source="knowledge_adapter",
        )

    def _claim_check_with_ontology(
        self,
        *,
        claim: str,
        tenant_id: str,
        ontology_id: Optional[str],
    ) -> Optional[SemanticTrustDecision]:
        if not self.ontology_manager or not ontology_id:
            return None

        semantic_facts = self._semantic_facts(tenant_id, ontology_id)
        relevant = [f for f in semantic_facts if self._fact_relevant_to_text(f, claim)]
        contradicted = [f for f in relevant if f.state == TrivalentDecision.FALSE]
        supported = [f for f in relevant if f.state == TrivalentDecision.TRUE]
        if contradicted:
            return SemanticTrustDecision(
                decision=TrivalentDecision.FALSE,
                recommended_action=RecommendedAction.BLOCK,
                confidence=max(f.confidence for f in contradicted),
                status=DecisionStatus.CONTRADICTED,
                subject=claim,
                contradictions=[
                    ContradictionRecord(
                        statement=f.object,
                        evidence=[self._fact_to_evidence(f)],
                        source=f.source,
                        confidence=f.confidence,
                    )
                    for f in contradicted
                ],
                proof=ProofMetadata(decision_path=["ontology:contradicted"]),
                source="ontology",
            )
        if supported:
            return SemanticTrustDecision(
                decision=TrivalentDecision.TRUE,
                recommended_action=RecommendedAction.ALLOW,
                confidence=max(f.confidence for f in supported),
                status=DecisionStatus.SUPPORTED,
                subject=claim,
                evidence=[self._fact_to_evidence(f) for f in supported],
                proof=ProofMetadata(decision_path=["ontology:supported"]),
                source="ontology",
            )

        legacy = self.ontology_manager.verify_claim(tenant_id, ontology_id, claim)
        if legacy.verified is True:
            return SemanticTrustDecision(
                decision=TrivalentDecision.TRUE,
                recommended_action=RecommendedAction.ALLOW,
                confidence=legacy.confidence,
                status=DecisionStatus.SUPPORTED,
                subject=claim,
                evidence=[self._dict_to_evidence(item) for item in legacy.supporting_facts],
                proof=ProofMetadata(decision_path=["ontology_legacy:supported"]),
                source="ontology_legacy",
            )
        if legacy.verified is False:
            return SemanticTrustDecision(
                decision=TrivalentDecision.FALSE,
                recommended_action=RecommendedAction.BLOCK,
                confidence=legacy.confidence,
                status=DecisionStatus.CONTRADICTED,
                subject=claim,
                contradictions=[
                    ContradictionRecord(
                        statement=item.get("constraint", claim),
                        evidence=[self._dict_to_evidence(item)],
                        source="ontology_legacy",
                        confidence=legacy.confidence,
                    )
                    for item in legacy.contradicting_facts
                ],
                proof=ProofMetadata(decision_path=["ontology_legacy:contradicted"]),
                source="ontology_legacy",
            )
        if legacy.relevant_concepts:
            return SemanticTrustDecision(
                decision=TrivalentDecision.UNDECIDABLE,
                recommended_action=RecommendedAction.ABSTAIN,
                confidence=legacy.confidence,
                status=DecisionStatus.UNSUPPORTED,
                subject=claim,
                missing_requirements=[
                    MissingRequirement(
                        description=legacy.reasoning,
                        requirement_type="evidence",
                        metadata={"relevant_concepts": legacy.relevant_concepts},
                    )
                ],
                proof=ProofMetadata(decision_path=["ontology_legacy:undecidable"]),
                source="ontology_legacy",
            )
        return None

    def _make_decision(
        self,
        *,
        decision: TrivalentDecision,
        action: RecommendedAction,
        confidence: float,
        status: DecisionStatus,
        subject: str,
        proof_type: ProofType,
        input_data: str,
        tenant_id: str,
        ontology_id: Optional[str],
        decision_path: List[str],
        evidence: Optional[List[EvidenceRecord]] = None,
        contradictions: Optional[List[ContradictionRecord]] = None,
        missing_requirements: Optional[List[MissingRequirement]] = None,
        source: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        adapter_source: Optional[str] = None,
        policy_ids: Optional[List[str]] = None,
        policy_version: Optional[str] = None,
        ruleset_version: Optional[str] = None,
    ) -> SemanticTrustDecision:
        return SemanticTrustDecision(
            decision=decision,
            recommended_action=action,
            confidence=max(0.0, min(1.0, confidence)),
            status=status,
            subject=subject,
            evidence=evidence or [],
            contradictions=contradictions or [],
            missing_requirements=missing_requirements or [],
            proof=self._build_proof_metadata(
                proof_type=proof_type,
                input_data=input_data,
                decision=decision,
                confidence=confidence,
                tenant_id=tenant_id,
                ontology_id=ontology_id,
                decision_path=decision_path,
                metadata=metadata or {},
                evidence=evidence,
                contradictions=contradictions,
                policy_ids=policy_ids,
                adapter_source=adapter_source,
                policy_version=policy_version,
                ruleset_version=ruleset_version,
            ),
            source=source,
            metadata=metadata or {},
        )

    def _build_proof_metadata(
        self,
        *,
        proof_type: ProofType,
        input_data: str,
        decision: TrivalentDecision,
        confidence: float,
        tenant_id: str,
        ontology_id: Optional[str],
        decision_path: List[str],
        metadata: Dict[str, Any],
        evidence: Optional[List[EvidenceRecord]] = None,
        contradictions: Optional[List[ContradictionRecord]] = None,
        policy_ids: Optional[List[str]] = None,
        adapter_source: Optional[str] = None,
        policy_version: Optional[str] = None,
        ruleset_version: Optional[str] = None,
    ) -> ProofMetadata:
        ontology_version = self._ontology_version(tenant_id, ontology_id)
        evidence_ids = self._collect_evidence_ids(evidence)
        contradiction_ids = self._collect_contradiction_ids(contradictions)
        all_evidence_ids = list(dict.fromkeys(evidence_ids + contradiction_ids))
        proof_id = self._local_proof_id(input_data, decision.value)
        ledger_ref = None
        adapter_name = adapter_source or (
            type(self.knowledge_adapter).__name__ if self.knowledge_adapter else None
        )
        resolved_policy_ids = self._resolve_policy_ids(policy_ids, contradictions)
        if self.proof_recorder:
            entry = self.proof_recorder.record(
                proof_type=proof_type,
                tenant_id=tenant_id,
                input_data=input_data,
                decision=decision.value,
                confidence=max(0.0, min(1.0, confidence)),
                metadata={
                    **metadata,
                    "decision_path": decision_path,
                },
                ontology_id=ontology_id,
                ontology_version=ontology_version,
                policy_version=policy_version,
                ruleset_version=ruleset_version,
                adapter_source=adapter_name,
                evidence_ids=all_evidence_ids,
                policy_ids=resolved_policy_ids,
                decision_path=list(decision_path),
            )
            proof_id = entry.proof_id
            ledger_ref = entry.entry_hash
        return ProofMetadata(
            proof_id=proof_id,
            tenant_id=tenant_id,
            ontology_version=ontology_version,
            policy_version=policy_version,
            ruleset_version=ruleset_version,
            ledger_ref=ledger_ref,
            decision_path=list(decision_path),
            metadata={
                **metadata,
                "adapter_source": adapter_name,
                "evidence_ids": all_evidence_ids,
                "policy_ids": resolved_policy_ids,
            },
        )

    def _semantic_facts(
        self,
        tenant_id: str,
        ontology_id: Optional[str],
        fact_type: Optional[SemanticFactType] = None,
    ) -> List[SemanticFact]:
        if not self.ontology_manager or not ontology_id:
            return []
        return self.ontology_manager.list_facts(tenant_id, ontology_id, fact_type)

    def _fact_relevant_to_text(self, fact: SemanticFact, text: str) -> bool:
        haystack = " ".join([
            fact.subject,
            fact.relation,
            fact.object,
            " ".join(fact.aliases),
        ])
        return self._token_overlap(text, haystack) >= 0.35

    def _policy_fact_matches_action(
        self,
        fact: SemanticFact,
        actor: str,
        action: str,
        resource: str,
        purpose: Optional[str],
    ) -> bool:
        metadata = fact.metadata or {}
        checks = [
            self._field_or_text_matches(metadata.get("actor"), actor, fact),
            self._field_or_text_matches(metadata.get("action"), action, fact),
            self._field_or_text_matches(metadata.get("resource"), resource, fact),
        ]
        if purpose and metadata.get("purpose"):
            checks.append(self._field_or_text_matches(metadata.get("purpose"), purpose, fact))
        return all(checks)

    def _policy_fact_matches_scope(self, fact: SemanticFact, text: str, scope: str) -> bool:
        metadata = fact.metadata or {}
        fact_scope = metadata.get("scope")
        if fact_scope and fact_scope != scope:
            return False
        pattern = metadata.get("pattern")
        if pattern and re.search(str(pattern), text, re.IGNORECASE):
            return True
        return self._token_overlap(text, f"{fact.subject} {fact.object}") >= 0.35

    def _field_or_text_matches(self, expected: Any, actual: str, fact: SemanticFact) -> bool:
        if expected in (None, "", "*"):
            return self._contains_token(f"{fact.subject} {fact.relation} {fact.object}", actual)
        return str(expected).lower() in {"*", actual.lower()}

    def _fact_to_evidence(self, fact: SemanticFact) -> EvidenceRecord:
        return EvidenceRecord(
            evidence_id=fact.metadata.get("id") if fact.metadata else None,
            text=fact.object,
            source=fact.source,
            document_id=fact.provenance.document_id,
            chunk_id=fact.provenance.chunk_id,
            span_start=fact.provenance.span_start,
            span_end=fact.provenance.span_end,
            score=fact.confidence,
            metadata={
                **fact.metadata,
                "subject": fact.subject,
                "relation": fact.relation,
                "fact_type": fact.fact_type.value,
                "state": fact.state.value,
            },
        )

    def _knowledge_fact_to_evidence(self, fact: Any) -> EvidenceRecord:
        return EvidenceRecord(
            text=getattr(fact, "content", None),
            source=getattr(fact, "source", None),
            document_id=getattr(fact, "document_id", None),
            chunk_id=getattr(fact, "chunk_id", None),
            score=getattr(fact, "relevance_score", None),
            metadata=getattr(fact, "metadata", {}) or {},
        )

    def _dict_to_evidence(self, item: Dict[str, Any]) -> EvidenceRecord:
        return EvidenceRecord(
            text=item.get("fact") or item.get("constraint") or item.get("content"),
            source=item.get("source"),
            score=item.get("similarity"),
            metadata=item,
        )

    def _violation_to_evidence(self, violation: ComplianceViolation) -> EvidenceRecord:
        return EvidenceRecord(
            evidence_id=violation.rule.rule_id,
            text=violation.context_snippet,
            source=violation.rule.standard.value,
            metadata=violation.to_dict(),
        )

    def _violations_to_contradictions(
        self, violations: Iterable[ComplianceViolation]
    ) -> List[ContradictionRecord]:
        return [
            ContradictionRecord(
                statement=v.rule.description,
                evidence=[self._violation_to_evidence(v)],
                source=v.rule.standard.value,
                rule_id=v.rule.rule_id,
                confidence=1.0,
                metadata=v.to_dict(),
            )
            for v in violations
        ]

    def _coerce_evidence(
        self,
        evidence: Optional[List[EvidenceRecord | Dict[str, Any]]],
    ) -> List[EvidenceRecord]:
        return [
            item if isinstance(item, EvidenceRecord) else EvidenceRecord.model_validate(item)
            for item in (evidence or [])
        ]

    def _average_score(self, evidence: List[EvidenceRecord], default: float) -> float:
        scores = [item.score for item in evidence if item.score is not None]
        if not scores:
            return default
        return sum(scores) / len(scores)

    def _context_to_text(self, context: Optional[Dict[str, Any]]) -> Optional[str]:
        if not context:
            return None
        for key in ("question", "query", "context", "retrieved_context"):
            value = context.get(key)
            if isinstance(value, str) and value.strip():
                return value
        return None

    def _is_blocking_violation(self, violation: ComplianceViolation) -> bool:
        return violation.rule.severity in {ViolationSeverity.CRITICAL, ViolationSeverity.HIGH}

    def _ontology_version(self, tenant_id: str, ontology_id: Optional[str]) -> Optional[str]:
        if not self.ontology_manager or not ontology_id:
            return None
        ontology = self.ontology_manager.get_ontology(tenant_id, ontology_id)
        return str(ontology.version) if ontology else None

    def _collect_evidence_ids(
        self, evidence: Optional[List[EvidenceRecord]]
    ) -> List[str]:
        if not evidence:
            return []
        ids: List[str] = []
        for item in evidence:
            if item.evidence_id:
                ids.append(item.evidence_id)
        return ids

    def _collect_contradiction_ids(
        self, contradictions: Optional[List[ContradictionRecord]]
    ) -> List[str]:
        if not contradictions:
            return []
        ids: List[str] = []
        for item in contradictions:
            if item.rule_id:
                ids.append(item.rule_id)
            elif item.source:
                ids.append(f"{item.source}")
        return ids

    def _resolve_policy_ids(
        self,
        policy_ids: Optional[List[str]],
        contradictions: Optional[List[ContradictionRecord]],
    ) -> List[str]:
        ids: List[str] = list(policy_ids or [])
        if not self.compliance_engine:
            for record in contradictions or []:
                if record.rule_id and record.rule_id not in ids:
                    ids.append(record.rule_id)
            return ids
        enabled = sorted({std.value for std in self.compliance_engine.enabled_standards})
        for std in enabled:
            tag = f"compliance:{std}"
            if tag not in ids:
                ids.append(tag)
        for record in contradictions or []:
            if record.rule_id and record.rule_id not in ids:
                ids.append(record.rule_id)
        return ids

    def _local_proof_id(self, input_data: str, decision: str) -> str:
        digest = hashlib.sha256(f"{self.tenant_id}:{decision}:{input_data}".encode()).hexdigest()[:16]
        return f"QST-{digest}"

    def _decision_to_groundcite_label(self, decision: TrivalentDecision) -> str:
        return {
            TrivalentDecision.TRUE: "supported",
            TrivalentDecision.FALSE: "contradicted",
            TrivalentDecision.UNDECIDABLE: "unsupported",
        }[decision]

    def _unsupported_spans(
        self,
        answer: str,
        claims: List[tuple[str, str]],
        labels: Dict[str, str],
    ) -> List[Dict[str, Any]]:
        spans = []
        for claim_id, claim_text in claims:
            if labels.get(claim_id) == "supported":
                continue
            start = answer.find(claim_text)
            if start >= 0:
                spans.append({
                    "claim_id": claim_id,
                    "start": start,
                    "end": start + len(claim_text),
                    "label": labels.get(claim_id),
                    "text": claim_text,
                })
        return spans

    def _token_overlap(self, a: str, b: str) -> float:
        a_tokens = self._tokens(a)
        b_tokens = self._tokens(b)
        if not a_tokens or not b_tokens:
            return 0.0
        return len(a_tokens & b_tokens) / len(a_tokens)

    def _contains_token(self, text: str, token: str) -> bool:
        return token.lower() in self._tokens(text)

    def _tokens(self, text: str) -> set[str]:
        stop = {
            "a", "an", "the", "is", "are", "of", "to", "in", "for", "with",
            "o", "a", "os", "as", "um", "uma", "de", "da", "do", "em", "para",
            "com", "por", "que", "e", "and", "or",
        }
        return {t for t in re.findall(r"\w+", text.lower()) if t not in stop}

