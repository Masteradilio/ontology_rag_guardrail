"""Offline portfolio showcase combining runtime decisions and RAG EVALs."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any, Dict

from ..decision_model import TrivalentDecision
from ..proof_recorder import ProofRecorder
from ..runtime import SemanticTrustRuntime
from .embeddings import DeterministicHashEmbedding
from .observability import EvaluationTrace, write_open_telemetry, write_trace_summary
from .rag_benchmark import controlled_seed_answer_evaluator
from .rag_evals import evaluate_rag_cases, load_rag_cases
from .scientific_baseline import ControlledClaimAdapter
from ..semantic_fact import SemanticFactType
from ..tenant_ontology import TenantOntologyManager


def _runtime_decisions(output_dir: Path) -> list[Dict[str, Any]]:
    async def run() -> list[Dict[str, Any]]:
        adapter = ControlledClaimAdapter()
        recorder = ProofRecorder(storage_path=str(output_dir / "claim-proofs"), enable_chain=True)
        runtime = SemanticTrustRuntime(
            "portfolio-tenant",
            knowledge_adapter=adapter,
            proof_recorder=recorder,
        )
        decisions = [
            await runtime.claim_check("Refunds are available within 30 days."),
            await runtime.claim_check("Refunds are available after 90 days."),
            await runtime.claim_check("Premium customers receive lifetime refunds."),
        ]
        return [
            {
                "claim": decision.subject,
                "decision": decision.decision.value,
                "recommended_action": decision.recommended_action.value,
                "proof_id": decision.proof.proof_id,
                "proof_lookup_ok": recorder.get_proof(decision.proof.proof_id) is not None,
                "decision_path": decision.proof.decision_path,
            }
            for decision in decisions
        ]

    return asyncio.run(run())


def _agent_decisions(output_dir: Path) -> tuple[list[Dict[str, Any]], Dict[str, Any]]:
    manager = TenantOntologyManager(storage_path=str(output_dir / "ontologies"))
    ontology_id = manager.create_ontology("portfolio-tenant", "Showcase Policies", "agent")
    manager.add_fact(
        tenant_id="portfolio-tenant",
        ontology_id=ontology_id,
        fact="support_agent may refund order for customer_support",
        fact_type=SemanticFactType.POLICY,
        subject="support_agent",
        relation="may_refund",
        state=TrivalentDecision.TRUE,
        metadata={
            "actor": "support_agent",
            "action": "refund",
            "resource": "order",
            "purpose": "customer_support",
        },
    )

    async def run() -> list[Dict[str, Any]]:
        recorder = ProofRecorder(storage_path=str(output_dir / "agent-proofs"), enable_chain=True)
        runtime = SemanticTrustRuntime(
            "portfolio-tenant",
            ontology_manager=manager,
            ontology_id=ontology_id,
            proof_recorder=recorder,
        )
        decisions = [
            await runtime.action_check(
                actor="support_agent",
                action="refund",
                resource="order",
                purpose="customer_support",
                ontology_id=ontology_id,
            ),
            await runtime.action_check(
                actor="support_agent",
                action="delete",
                resource="customer_account",
                purpose="customer_support",
                ontology_id=ontology_id,
            ),
        ]
        return [
            {
                "decision": decision.decision.value,
                "recommended_action": decision.recommended_action.value,
                "proof_id": decision.proof.proof_id,
                "proof_lookup_ok": recorder.get_proof(decision.proof.proof_id) is not None,
                "decision_path": decision.proof.decision_path,
            }
            for decision in decisions
        ]

    snapshot = manager.snapshot_ontology(
        "portfolio-tenant",
        ontology_id,
        name="portfolio_showcase",
        metadata={"reason": "offline_showcase"},
    )
    return asyncio.run(run()), {
        "ontology_id": ontology_id,
        "snapshot_id": snapshot.snapshot_id,
        "ontology_version": snapshot.ontology_version,
    }


def run_showcase(
    *,
    output_dir: str | Path = "artifacts/showcase",
    run_id: str = "portfolio-showcase",
    rag_cases_path: str | Path = "data/evaluation/rag_seed/cases.jsonl",
) -> Path:
    """Run the offline showcase without an embedding model or LLM API key."""

    run_dir = Path(output_dir) / run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    trace = EvaluationTrace(trace_id=f"{run_id}-trace")
    rag_report = evaluate_rag_cases(
        load_rag_cases(rag_cases_path),
        DeterministicHashEmbedding(),
        answer_evaluator=controlled_seed_answer_evaluator,
        trace=trace,
    )
    agent_decisions, ontology_snapshot = _agent_decisions(run_dir)
    payload = {
        "schema_version": "quimera_portfolio_showcase_v1",
        "llm_api_key_required": False,
        "runtime_decisions": _runtime_decisions(run_dir),
        "agent_decisions": agent_decisions,
        "ontology_snapshot": ontology_snapshot,
        "rag_report": rag_report.model_dump(mode="json"),
        "trace_id": trace.trace_id,
    }
    (run_dir / "showcase.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    trace.write_jsonl(run_dir / "trace.jsonl")
    write_trace_summary(run_dir / "observability.json", trace)
    write_open_telemetry(run_dir / "otel.json", trace)
    return run_dir
