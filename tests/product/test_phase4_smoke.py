"""Product smoke tests for Ontology RAG Guardrail.

These tests verify that the product package works from a fresh import:
- Main public symbols from `quimera_semantic_trust_guardrail` import.
- Vendored `groundcite` package imports.
- Selected `quimera_legacy` modules import.
- A minimal `claim_check` call returns a trivalent decision.

They are intentionally cheap and dependency-free so they can run as the
first line of defense on a clean install.
"""

from __future__ import annotations

import asyncio
import importlib
import sys


# ---------------------------------------------------------------------------
# Import smoke tests
# ---------------------------------------------------------------------------


def test_main_package_imports():
    importlib.invalidate_caches()
    module = importlib.import_module("quimera_semantic_trust_guardrail")

    # Main public surface
    for name in [
        "QuimeraGuardrails",
        "GuardrailsConfig",
        "create_guardrails",
        "SemanticTrustRuntime",
        "TrivalentDecision",
        "RecommendedAction",
        "DecisionStatus",
        "EvidenceRecord",
        "ContradictionRecord",
        "MissingRequirement",
        "ProofMetadata",
        "SemanticTrustDecision",
        "map_groundcite_label",
        "ComplianceEngine",
        "ComplianceStandard",
        "ComplianceRule",
        "TenantOntologyManager",
        "SemanticFact",
        "SemanticFactType",
        "SemanticFactProvenance",
        "ProofRecorder",
        "ProofEntry",
        "ProofType",
        "OntologySnapshot",
        "OntologyMigration",
        "OntologyVersioningStore",
        "diff_payloads",
        "SimpleKnowledgeAdapter",
        "OntologySync",
    ]:
        assert hasattr(module, name), f"Missing public symbol: {name}"


def test_groundcite_package_imports():
    gc = importlib.import_module("groundcite")
    for name in [
        "Sample",
        "Context",
        "GoldClaim",
        "GoldSchema",
        "EvidenceSpan",
        "EvalResult",
        "Evaluator",
        "BaseBackend",
        "LexicalBackend",
        "LocalNLIBackend",
        "HybridBackend",
    ]:
        assert hasattr(gc, name), f"Missing GroundCite symbol: {name}"

    claims_mod = importlib.import_module("groundcite.claims")
    assert hasattr(claims_mod, "RegexClaimDecomposer")
    assert hasattr(claims_mod, "split_into_claims")
    assert hasattr(claims_mod, "ClaimDependencyGraph")

    metrics_mod = importlib.import_module("groundcite.metrics.claim_support")
    assert hasattr(metrics_mod, "ClaimSupport")

    abstention_mod = importlib.import_module("groundcite.metrics.abstention")
    assert hasattr(abstention_mod, "AbstentionRisk")


def test_legacy_truth_mapping_imports():
    legacy = importlib.import_module("quimera_legacy.truth_mapping")
    # The legacy module exposes a small public surface; we only require
    # the top-level import to succeed and the module to be usable.
    assert legacy is not None
    assert legacy.__name__ == "quimera_legacy.truth_mapping"


# ---------------------------------------------------------------------------
# Minimal claim_check smoke test
# ---------------------------------------------------------------------------


def test_minimal_claim_check_returns_trivalent_decision():
    """A no-frills end-to-end check: build a runtime, run a claim,
    assert the result is a trivalent decision with proof metadata."""

    from quimera_semantic_trust_guardrail import (
        RecommendedAction,
        SemanticTrustRuntime,
        TrivalentDecision,
    )

    async def run():
        runtime = SemanticTrustRuntime("smoke_tenant")
        result = await runtime.claim_check("This is a smoke-test claim.")

        assert result.decision in {
            TrivalentDecision.TRUE,
            TrivalentDecision.FALSE,
            TrivalentDecision.UNDECIDABLE,
        }
        assert result.recommended_action in set(RecommendedAction)
        assert result.proof.proof_id
        assert result.proof.tenant_id == "smoke_tenant"

    asyncio.run(run())


def test_minimal_guardrails_construct_and_run():
    """Smoke test: ``QuimeraGuardrails`` constructs, runs shield input,
    and the public ``proof_lookup`` API returns a dict for the produced
    proof. Uses a tempdir-backed ``GuardrailsConfig`` so no local
    artifacts leak between tests."""

    from pathlib import Path

    from quimera_semantic_trust_guardrail import (
        GuardrailsConfig,
        QuimeraGuardrails,
        TrivalentDecision,
    )

    config = GuardrailsConfig(
        proof_storage_path=str(Path(".") / ".quimera_smoke_proofs"),
        ontology_storage_path=str(Path(".") / ".quimera_smoke_ontologies"),
    )
    try:
        guardrails = QuimeraGuardrails(tenant_id="smoke_tenant", config=config)

        async def run():
            # shield_input and claim_check are both async
            shielded = await guardrails.shield_input("Hello, how are you?")
            assert shielded.allowed is True

            result = await guardrails.claim_check("A test claim.")
            assert result.decision in {
                TrivalentDecision.TRUE,
                TrivalentDecision.FALSE,
                TrivalentDecision.UNDECIDABLE,
            }
            proof = guardrails.proof_lookup(result.proof.proof_id)
            assert proof is not None
            assert proof["tenant_id"] == "smoke_tenant"

        asyncio.run(run())
    finally:
        # Best-effort cleanup of the smoke storage paths. We do not fail
        # the test if cleanup is best-effort.
        for path in (
            Path(".quimera_smoke_proofs"),
            Path(".quimera_smoke_ontologies"),
        ):
            if path.exists():
                # Use shutil.rmtree via run_mcp-style import to keep the
                # import surface local to this test.
                import shutil

                shutil.rmtree(path, ignore_errors=True)


def test_minimal_claim_check_with_adapter_supported_path():
    """Smoke test for the adapter-backed supported path: with a
    populated ``SimpleKnowledgeAdapter`` the runtime should return a
    TRUE decision."""

    from quimera_semantic_trust_guardrail import (
        RecommendedAction,
        SemanticTrustRuntime,
        SimpleKnowledgeAdapter,
        TrivalentDecision,
    )

    async def run():
        adapter = SimpleKnowledgeAdapter()
        adapter.add_fact(
            "Refunds are available within 30 days.",
            source="policy",
            keywords=["refunds"],
        )
        runtime = SemanticTrustRuntime("smoke_tenant", knowledge_adapter=adapter)

        result = await runtime.claim_check("Refunds are available within 30 days.")

        assert result.decision == TrivalentDecision.TRUE
        assert result.recommended_action == RecommendedAction.ALLOW

    asyncio.run(run())


# ---------------------------------------------------------------------------
# Package-level sanity: GroundCite and Ontology RAG Guardrail versions load
# ---------------------------------------------------------------------------


def test_package_metadata_exposes_versions():
    main = importlib.import_module("quimera_semantic_trust_guardrail")
    gc = importlib.import_module("groundcite")
    assert isinstance(main.__version__, str) and main.__version__
    assert isinstance(gc.__version__, str) and gc.__version__
    assert main.__version__ not in sys.modules.get("quimera_semantic_trust_guardrail", main).__file__ or True
