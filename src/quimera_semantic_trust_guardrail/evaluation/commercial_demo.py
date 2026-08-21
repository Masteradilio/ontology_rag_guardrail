"""Commercial discovery demo runner.

The default path is deterministic and offline. Optional LLM use is explicit and
records provider success/failure without changing the core demo decisions.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any, Dict, Optional

from ..compliance_engine import ComplianceEngine, ComplianceRule, ComplianceStandard, ViolationSeverity
from ..decision_model import TrivalentDecision
from ..runtime import SemanticTrustRuntime
from ..semantic_fact import SemanticFactType
from ..tenant_ontology import TenantOntologyManager
from .artifacts import ProviderTrace, _utc_now
from .llm_providers import FallbackLLMClient, LLMFailure, LLMRequest, NVIDIAProvider, OpenRouterProvider
from .scientific_baseline import ControlledClaimAdapter


def _decision_payload(name: str, decision: Any, expected_value: str) -> Dict[str, Any]:
    return {
        "workflow": name,
        "decision": decision.decision.value,
        "recommended_action": decision.recommended_action.value,
        "status": decision.status.value if decision.status else None,
        "expected_value": expected_value,
        "proof_id": decision.proof.proof_id,
        "decision_path": list(decision.proof.decision_path),
        "ontology_version": decision.proof.ontology_version,
        "policy_version": decision.proof.policy_version,
        "matches_expected": decision.decision.value == expected_value,
    }


def _action_runtime(storage_path: Path) -> tuple[SemanticTrustRuntime, str, TenantOntologyManager]:
    manager = TenantOntologyManager(storage_path=str(storage_path / "ontologies"))
    ontology_id = manager.create_ontology("demo_tenant", "Commercial Demo Policies", "support")
    manager.add_fact(
        tenant_id="demo_tenant",
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
        tenant_id="demo_tenant",
        ontology_id=ontology_id,
        fact="support_agent must not export customer_data",
        fact_type=SemanticFactType.POLICY,
        subject="support_agent",
        relation="must_not_export",
        state=TrivalentDecision.FALSE,
        metadata={
            "actor": "support_agent",
            "action": "export",
            "resource": "customer_data",
            "purpose": "analytics",
        },
    )
    return SemanticTrustRuntime("demo_tenant", ontology_manager=manager, ontology_id=ontology_id), ontology_id, manager


def _policy_runtime() -> SemanticTrustRuntime:
    custom_rule = ComplianceRule(
        rule_id="DEMO-CUSTOM-001",
        standard=ComplianceStandard.CUSTOM,
        description="Public responses must not expose customer data exports.",
        patterns=["export customer_data", "external analytics vendor"],
        severity=ViolationSeverity.HIGH,
        remediation="Route to approval workflow and redact sensitive details.",
    )
    engine = ComplianceEngine(
        enabled_standards=[ComplianceStandard.LGPD],
        custom_rules=[custom_rule],
    )
    return SemanticTrustRuntime("demo_tenant", compliance_engine=engine)


async def _optional_llm_trace(use_llm: bool) -> Optional[ProviderTrace]:
    if not use_llm:
        return None
    client = FallbackLLMClient([NVIDIAProvider(), OpenRouterProvider()])
    try:
        response = client.generate(
            LLMRequest(
                system="You summarize evaluation outputs without making new product claims.",
                prompt="Summarize Quimera's commercial demo in one conservative sentence.",
                temperature=0.0,
                max_tokens=80,
            )
        )
        return ProviderTrace(
            provider_name=response.provider_name,
            model_name=response.model_name,
            latency_ms=response.latency_ms,
            request_id=response.request_id,
            status="ok",
        )
    except LLMFailure as exc:
        return ProviderTrace(
            provider_name=exc.provider_name,
            model_name=client.model_name,
            status="provider_unavailable",
            failure_mode=str(exc),
        )


async def _run_async(output_dir: Path, run_id: str, use_llm: bool) -> Path:
    run_dir = output_dir / run_id
    run_dir.mkdir(parents=True, exist_ok=False)

    claim_runtime = SemanticTrustRuntime("demo_tenant", knowledge_adapter=ControlledClaimAdapter())
    action_runtime, ontology_id, manager = _action_runtime(run_dir)
    policy_runtime = _policy_runtime()

    rag_decision = await claim_runtime.answer_check(
        "Refunds are available within 30 days. Premium customers receive lifetime refunds.",
        question="What refund answer should the support agent send?",
        lang="en",
    )
    allowed_action = await action_runtime.action_check(
        actor="support_agent",
        action="refund",
        resource="order",
        purpose="customer_support",
        ontology_id=ontology_id,
    )
    missing_action = await action_runtime.action_check(
        actor="support_agent",
        action="delete",
        resource="customer_account",
        purpose="customer_support",
        ontology_id=ontology_id,
    )
    compliance_decision = await policy_runtime.policy_check(
        "Customer CPF 123.456.789-00 should be included in the public answer.",
        scope="output",
    )
    snapshot = manager.snapshot_ontology(
        "demo_tenant",
        ontology_id,
        name="commercial_demo",
        metadata={"reason": "commercial_demo"},
    )

    provider = await _optional_llm_trace(use_llm)
    workflows = [
        _decision_payload("rag_answer_approval", rag_decision, "UNDECIDABLE"),
        _decision_payload("agent_refund_authorization", allowed_action, "TRUE"),
        _decision_payload("agent_missing_authorization", missing_action, "UNDECIDABLE"),
        _decision_payload("policy_compliance_review", compliance_decision, "FALSE"),
    ]
    payload = {
        "run_id": run_id,
        "created_at": _utc_now(),
        "mode": "llm_optional" if use_llm else "deterministic_offline",
        "claim_boundary": "Commercial demo decisions are synthetic workflow evidence, not production ROI or legal certification.",
        "ontology_snapshot": {
            "snapshot_id": snapshot.snapshot_id,
            "ontology_id": ontology_id,
            "ontology_version": snapshot.ontology_version,
        },
        "provider": provider.model_dump() if provider else None,
        "workflows": workflows,
    }
    (run_dir / "commercial_demo.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return run_dir


def run_commercial_demo(
    *,
    output_dir: str | Path = "artifacts/commercial",
    run_id: str = "commercial-demo",
    use_llm: bool = False,
) -> Path:
    """Run the deterministic commercial discovery demo."""

    return asyncio.run(_run_async(Path(output_dir), run_id, use_llm))
