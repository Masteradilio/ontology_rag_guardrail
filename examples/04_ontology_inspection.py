"""Runnable example: inspect ontology provenance, conflict, diff, and proof.

Run with:
    .venv\\Scripts\\python examples\\04_ontology_inspection.py
"""

from __future__ import annotations

import asyncio
import json
import tempfile
from pathlib import Path

from quimera_semantic_trust_guardrail import (
    SemanticFactType,
    TrivalentDecision,
)
from quimera_semantic_trust_guardrail.runtime import SemanticTrustRuntime
from quimera_semantic_trust_guardrail.tenant_ontology import TenantOntologyManager


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="quimera_ontology_showcase_") as tmpdir:
        base = Path(tmpdir)
        manager = TenantOntologyManager(storage_path=str(base / "ontologies"))
        ontology_id = manager.create_ontology("portfolio-tenant", "Support Policies", "support")
        fact_text = "Refunds are available within 30 days."
        manager.add_fact(
            tenant_id="portfolio-tenant",
            ontology_id=ontology_id,
            fact=fact_text,
            fact_type=SemanticFactType.POLICY,
            subject="refund",
            relation="policy",
            state=TrivalentDecision.TRUE,
            source="policy-v1",
            source_document="refund-policy",
            source_chunk="refund-policy#1",
        )
        snapshot = manager.snapshot_ontology(
            "portfolio-tenant", ontology_id, name="before-conflict"
        )
        manager.add_fact(
            tenant_id="portfolio-tenant",
            ontology_id=ontology_id,
            fact=fact_text,
            fact_type=SemanticFactType.POLICY,
            subject="refund",
            relation="policy",
            state=TrivalentDecision.FALSE,
            source="conflicting-review",
        )
        facts = [fact.model_dump(mode="json") for fact in manager.list_facts("portfolio-tenant", ontology_id)]
        diff = manager.diff_ontology("portfolio-tenant", ontology_id, snapshot.snapshot_id)

        guardrails = SemanticTrustRuntime(
            tenant_id="portfolio-tenant",
            ontology_manager=manager,
            ontology_id=ontology_id,
        )
        decision = asyncio.run(guardrails.claim_check(fact_text, ontology_id=ontology_id))
        print(json.dumps({
            "ontology_id": ontology_id,
            "snapshot_id": snapshot.snapshot_id,
            "facts": facts,
            "diff": diff,
            "decision": decision.model_dump(mode="json"),
        }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
