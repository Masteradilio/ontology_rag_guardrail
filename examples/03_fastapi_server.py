"""Runnable example: run the FastAPI HTTP runtime locally.

Run with:
    .venv\\Scripts\\python.exe examples\\03_fastapi_server.py
Then in another shell:
    curl http://127.0.0.1:8000/health
    curl -X POST http://127.0.0.1:8000/claim-check \\
         -H "X-Tenant-ID: example_tenant" \\
         -H "Content-Type: application/json" \\
         -d "{\\"claim\\": \\"Refunds are available within 30 days.\\"}"
"""

from __future__ import annotations

from quimera_semantic_trust_guardrail import create_fastapi_app
from quimera_semantic_trust_guardrail import SimpleKnowledgeAdapter


def main() -> None:
    try:
        import uvicorn
    except ImportError:
        print(
            "FastAPI runtime requires the [fastapi] extra. "
            "Install with: pip install 'quimera-semantic-trust-guardrail[fastapi]'"
        )
        return

    app = create_fastapi_app(
        proof_storage_path=".quimera_example_http_proofs",
        ontology_storage_path=".quimera_example_http_ontologies",
    )
    # Pre-seed the lazy tenant with a known fact for the demo.
    from quimera_semantic_trust_guardrail import QuimeraGuardrails
    from quimera_semantic_trust_guardrail import GuardrailsConfig

    adapter = SimpleKnowledgeAdapter()
    adapter.add_fact(
        "Refunds are available within 30 days.",
        source="policy",
        keywords=["refunds"],
    )
    config = GuardrailsConfig(
        proof_storage_path=".quimera_example_http_proofs/example_tenant",
        ontology_storage_path=".quimera_example_http_ontologies/example_tenant",
    )
    guardrails = QuimeraGuardrails(
        tenant_id="example_tenant",
        config=config,
        knowledge_adapter=adapter,
    )
    # Stash the pre-seeded instance on the app so the first request
    # reuses it instead of creating a fresh one.
    app.tenant_guardrails = {"example_tenant": guardrails}  # type: ignore[attr-defined]

    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="info")


if __name__ == "__main__":
    main()
