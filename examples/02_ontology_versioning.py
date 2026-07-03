"""Runnable example: tenant ontology with snapshot, rollback, and proof
trail.

Run with:
    .venv\\Scripts\\python.exe examples\\02_ontology_versioning.py
"""

from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path

from quimera_semantic_trust_guardrail import (
    GuardrailsConfig,
    QuimeraGuardrails,
    SemanticFactType,
    TrivalentDecision,
)


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="quimera_example_") as tmpdir:
        base = Path(tmpdir)
        config = GuardrailsConfig(
            proof_storage_path=str(base / "proofs"),
            ontology_storage_path=str(base / "ontologies"),
        )
        guardrails = QuimeraGuardrails(tenant_id="example_tenant", config=config)

        ontology_id = guardrails.create_ontology(
            name="Support policies",
            domain="support",
        )
        guardrails.add_knowledge(
            concept="refund",
            definition="refund policy",
            facts=["Refunds are available within 30 days."],
        )

        snapshot = guardrails.snapshot_ontology(name="v1")
        print("Initial snapshot:", json.dumps(snapshot, indent=2, ensure_ascii=False))

        # Apply a destructive edit
        guardrails.ontology_manager.add_fact(
            tenant_id="example_tenant",
            ontology_id=ontology_id,
            fact="Refunds are unlimited.",
            fact_type=SemanticFactType.POLICY,
            subject="refund",
            relation="has_fact",
            state=TrivalentDecision.FALSE,
        )

        live_facts = guardrails.ontology_manager.list_facts(
            "example_tenant", ontology_id
        )
        print("\nLive facts after destructive edit:", len(live_facts))

        rollback = guardrails.rollback_ontology(snapshot["snapshot_id"])
        print("\nRollback result:", json.dumps(rollback, indent=2, ensure_ascii=False))

        facts_after = guardrails.ontology_manager.list_facts(
            "example_tenant", ontology_id
        )
        print("\nFacts after rollback:", len(facts_after))

        migrations = guardrails.list_ontology_migrations()
        print(
            "\nMigration history:",
            json.dumps(migrations, indent=2, ensure_ascii=False),
        )

    # Cleanup any leftover artifacts in the cwd just in case.
    for leftover in (Path(".quimera_example_proofs"), Path(".quimera_example_ontologies")):
        if leftover.exists():
            shutil.rmtree(leftover, ignore_errors=True)


if __name__ == "__main__":
    main()
