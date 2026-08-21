"""Deterministic baseline runner for scientific validation seeds."""

from __future__ import annotations

import asyncio
import json
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..compliance_engine import ComplianceEngine, ComplianceRule, ComplianceStandard, ViolationSeverity
from ..decision_model import SemanticTrustDecision, TrivalentDecision
from ..runtime import SemanticTrustRuntime
from ..semantic_fact import SemanticFactType
from ..tenant_ontology import TenantOntologyManager
from .artifacts import (
    EvaluationRunMetadata,
    EvaluationSampleResult,
    ProofTrace,
    SummaryMetrics,
    create_evaluation_run,
    write_jsonl,
)
from .datasets import DatasetManifest, load_dataset_manifest, load_jsonl_records


class ControlledClaimAdapter:
    """Small deterministic adapter for the scientific seed dataset."""

    async def verify_claim(self, claim: str, context: Optional[str] = None) -> Dict[str, Any]:
        lowered = claim.lower()
        if "after 90 days" in lowered:
            return {
                "supported": False,
                "confidence": 0.95,
                "status": "contradicted",
                "reasoning": "The controlled policy says 30 days, not 90 days.",
                "evidence": [],
            }
        if "within 30 days" in lowered:
            return {
                "supported": True,
                "confidence": 0.9,
                "status": "verified",
                "evidence": [],
            }
        return {
            "supported": None,
            "confidence": 0.0,
            "status": "unsupported",
            "reasoning": "No controlled evidence supports this claim.",
            "evidence": [],
        }


def _proof_trace(decision: SemanticTrustDecision) -> ProofTrace:
    return ProofTrace(
        proof_id=decision.proof.proof_id,
        proof_type=decision.proof.metadata.get("proof_type"),
        ontology_version=decision.proof.ontology_version,
        policy_version=decision.proof.policy_version,
        decision_path=list(decision.proof.decision_path),
    )


def _result_from_decision(record: Dict[str, Any], decision: SemanticTrustDecision) -> EvaluationSampleResult:
    expected = record["expected_decision"]
    observed = decision.decision.value
    notes = []
    if expected != observed:
        notes.append(f"expected {expected}, observed {observed}")
    return EvaluationSampleResult(
        sample_id=record["sample_id"],
        task=record.get("task") or record.get("action") or record.get("scope") or "unknown",
        expected_label=record["expected_label"],
        observed_decision=observed,
        recommended_action=decision.recommended_action.value,
        correct=expected == observed,
        proof=_proof_trace(decision),
        notes=notes,
    )


def _metrics(run_id: str, results: List[EvaluationSampleResult]) -> SummaryMetrics:
    sample_count = len(results)
    correct = sum(1 for item in results if item.correct)
    expected_by_observed = Counter(
        f"{item.expected_label}:{item.observed_decision}" for item in results
    )
    expected_decision: Counter[str] = Counter()
    observed_decision: Counter[str] = Counter()
    false_allow = 0
    false_block = 0
    expected_undecidable = 0
    useful_abstention = 0
    harmful_abstention = 0
    non_undecidable = 0

    for item in results:
        expected = "UNDECIDABLE" if "undecidable" in item.expected_label or item.expected_label in {
            "unsupported",
            "partially_unsupported",
            "missing_authorization",
            "wrong_tenant",
        } else ("FALSE" if item.expected_label in {"contradicted", "deny", "policy_violation"} else "TRUE")
        expected_decision[expected] += 1
        observed_decision[item.observed_decision] += 1
        if expected != "TRUE" and item.observed_decision == "TRUE":
            false_allow += 1
        if expected == "TRUE" and item.observed_decision == "FALSE":
            false_block += 1
        if expected == "UNDECIDABLE":
            expected_undecidable += 1
            if item.observed_decision == "UNDECIDABLE":
                useful_abstention += 1
        else:
            non_undecidable += 1
            if item.observed_decision == "UNDECIDABLE":
                harmful_abstention += 1

    limitations = [
        "Synthetic seed dataset; does not estimate production RAG accuracy.",
        "Policy clean-path behavior is measured as runtime behavior, not legal compliance.",
    ]
    return SummaryMetrics(
        run_id=run_id,
        sample_count=sample_count,
        metrics={
            "accuracy": correct / sample_count if sample_count else 0.0,
            "false_allow_rate": false_allow / sample_count if sample_count else 0.0,
            "false_block_rate": false_block / sample_count if sample_count else 0.0,
            "useful_abstention_rate": useful_abstention / expected_undecidable if expected_undecidable else 0.0,
            "harmful_abstention_rate": harmful_abstention / non_undecidable if non_undecidable else 0.0,
        },
        counts={
            "correct": correct,
            "false_allow": false_allow,
            "false_block": false_block,
            "useful_abstention": useful_abstention,
            "harmful_abstention": harmful_abstention,
            **{f"confusion:{key}": value for key, value in expected_by_observed.items()},
            **{f"expected:{key}": value for key, value in expected_decision.items()},
            **{f"observed:{key}": value for key, value in observed_decision.items()},
        },
        limitations=limitations,
    )


def _create_action_runtime(storage_path: Path, tenant_id: str = "tenant_a") -> tuple[SemanticTrustRuntime, str]:
    manager = TenantOntologyManager(storage_path=str(storage_path / "ontologies"))
    ontology_id = manager.create_ontology("tenant_a", "Scientific Action Policies", "agent")
    manager.add_fact(
        tenant_id="tenant_a",
        ontology_id=ontology_id,
        fact="support_agent may refund order for customer_support",
        fact_type=SemanticFactType.POLICY,
        subject="support_agent",
        relation="may_refund",
        metadata={
            "actor": "support_agent",
            "action": "refund",
            "resource": "order",
            "purpose": "customer_support",
        },
    )
    manager.add_fact(
        tenant_id="tenant_a",
        ontology_id=ontology_id,
        fact="contractor must not export customer_data",
        fact_type=SemanticFactType.POLICY,
        subject="contractor",
        relation="must_not_export",
        state=TrivalentDecision.FALSE,
        metadata={
            "actor": "contractor",
            "action": "export",
            "resource": "customer_data",
            "purpose": "analytics",
        },
    )
    return SemanticTrustRuntime(tenant_id, ontology_manager=manager, ontology_id=ontology_id), ontology_id


def _create_policy_runtime(storage_path: Path) -> SemanticTrustRuntime:
    custom_rule = ComplianceRule(
        rule_id="CUSTOM-EXPORT-001",
        standard=ComplianceStandard.CUSTOM,
        description="External customer data export is forbidden in the seed policy.",
        patterns=["export customer_data", "external analytics vendor"],
        severity=ViolationSeverity.HIGH,
        remediation="Require explicit approval and data minimization.",
    )
    engine = ComplianceEngine(
        enabled_standards=[ComplianceStandard.LGPD],
        custom_rules=[custom_rule],
    )
    return SemanticTrustRuntime("tenant_a", compliance_engine=engine)


async def _run_async(
    *,
    manifest: DatasetManifest,
    output_dir: Path,
    run_id: str,
) -> Path:
    metadata = EvaluationRunMetadata(
        run_id=run_id,
        dataset_id=manifest.package_id,
        dataset_version=manifest.version,
        ontology_version="seed-runtime",
        policy_version="seed-policy",
        runtime_config={
            "mode": "deterministic",
            "llm_provider": "none",
        },
    )
    run_dir = create_evaluation_run(base_dir=output_dir, metadata=metadata)
    results: List[EvaluationSampleResult] = []

    claim_runtime = SemanticTrustRuntime("tenant_a", knowledge_adapter=ControlledClaimAdapter())
    action_runtime, action_ontology_id = _create_action_runtime(run_dir)
    policy_runtime = _create_policy_runtime(run_dir)

    for dataset in manifest.datasets:
        for record in load_jsonl_records(dataset.path):
            if dataset.task == "claim_answer_validation":
                if record["task"] == "answer_check":
                    decision = await claim_runtime.answer_check(record["answer"], lang="en")
                else:
                    decision = await claim_runtime.claim_check(record["claim"])
            elif dataset.task == "agent_action_authorization":
                runtime = action_runtime
                ontology_id = action_ontology_id
                if record["tenant_id"] != "tenant_a":
                    runtime, ontology_id = _create_action_runtime(run_dir, tenant_id=record["tenant_id"])
                decision = await runtime.action_check(
                    actor=record["actor"],
                    action=record["action"],
                    resource=record["resource"],
                    purpose=record.get("purpose"),
                    tenant_id=record["tenant_id"],
                    ontology_id=ontology_id,
                )
            elif dataset.task == "policy_compliance":
                decision = await policy_runtime.policy_check(
                    record["text"],
                    tenant_id=record["tenant_id"],
                    scope=record["scope"],
                )
            else:  # pragma: no cover - manifest validation should prevent this
                raise ValueError(f"unsupported dataset task: {dataset.task}")
            results.append(_result_from_decision(record, decision))

    summary = _metrics(run_id, results)
    write_jsonl(run_dir / "sample_results.jsonl", results)
    (run_dir / "summary.json").write_text(summary.model_dump_json(indent=2), encoding="utf-8")
    (run_dir / "failure_analysis.json").write_text(
        json.dumps(
            [item.model_dump() for item in results if item.correct is False],
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return run_dir


def run_scientific_baseline(
    *,
    manifest_path: str | Path = "data/evaluation/scientific_seed/manifest.json",
    output_dir: str | Path = "artifacts/evaluation",
    run_id: str = "scientific-seed-baseline",
) -> Path:
    """Run the deterministic scientific seed baseline and return the run dir."""

    manifest = load_dataset_manifest(manifest_path)
    return asyncio.run(_run_async(manifest=manifest, output_dir=Path(output_dir), run_id=run_id))
