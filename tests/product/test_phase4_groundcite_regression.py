"""Phase 4 regression tests: adapted GroundCite suite + product quality gates.

These tests adapt the most useful parts of the GroundCite reference suite
(`tests/reference_groundcite/test_claims.py` and
`tests/reference_groundcite/test_schema.py`) as product-level regression
tests, and add the product-level quality gates for claim support and
abstention.

Research-only tests (dataset summary integrity, scientific reporting
guardrails, and the hybrid backend fast-path tests) remain under
`tests/reference_groundcite/` and are NOT executed in the product
regression scope.
"""

from __future__ import annotations

import asyncio
import json

import pytest
from pydantic import ValidationError

from groundcite.claims import (
    RegexClaimDecomposer,
    split_into_claims,
)
from groundcite.metrics.abstention import AbstentionRisk
from groundcite.metrics.claim_support import ClaimSupport
from groundcite.schema import (
    Context,
    Sample,
    EvalResult,
)
from groundcite.backends.base import BaseBackend

from quimera_semantic_trust_guardrail import (
    DecisionStatus,
    RecommendedAction,
    SemanticTrustRuntime,
    SimpleKnowledgeAdapter,
    TrivalentDecision,
    map_groundcite_label,
)
from groundcite.evaluator import Evaluator


# ---------------------------------------------------------------------------
# Adapted from tests/reference_groundcite/test_claims.py
# ---------------------------------------------------------------------------


def test_adapted_split_into_claims_simple_sentences():
    """Adapted from the GroundCite reference suite.

    The product runtime uses ``RegexClaimDecomposer`` in ``answer_check``,
    so the claim-splitting contract must remain a product-level regression.
    """
    claims = split_into_claims("Machado de Assis foi um grande escritor. Ele fundou a ABL!")
    assert len(claims) == 2
    assert claims[0] == "Machado de Assis foi um grande escritor."
    assert claims[1] == "Ele fundou a ABL!"


def test_adapted_split_into_claims_preserves_abbreviations():
    """Adapted: abbreviations should not break sentences in PT-BR and EN."""
    pt_claims = split_into_claims(
        "O Dr. Machado de Assis morava na Av. Paulista, etc. Ele era muito respeitado.",
        lang="pt-BR",
    )
    assert len(pt_claims) == 2
    assert pt_claims[0] == "O Dr. Machado de Assis morava na Av. Paulista, etc."
    assert pt_claims[1] == "Ele era muito respeitado."

    en_claims = split_into_claims(
        "SpaceX was founded by Mr. Elon Musk in the U.S. at 2002. They want to go to Mars.",
        lang="en",
    )
    assert len(en_claims) == 2
    assert en_claims[0] == "SpaceX was founded by Mr. Elon Musk in the U.S. at 2002."
    assert en_claims[1] == "They want to go to Mars."


def test_adapted_split_into_claims_empty_or_short_text():
    """Adapted: short / empty inputs must return no claims."""
    assert split_into_claims("") == []
    assert split_into_claims("Oi.") == []


def test_product_answer_check_uses_adapted_decomposition():
    """Product-quality gate: ``answer_check`` must rely on the same
    decomposition contract as the GroundCite reference suite."""

    async def run():
        runtime = SemanticTrustRuntime("tenant_a")
        # First claim is unknown; second is unknown too, so the answer must
        # not be marked TRUE and the decomposition should produce >= 2 claims.
        result = await runtime.answer_check(
            "Refunds are available within 30 days. We are headquartered in Berlin."
        )

        assert result.decision in {TrivalentDecision.UNDECIDABLE, TrivalentDecision.FALSE}
        assert result.recommended_action in {
            RecommendedAction.ABSTAIN,
            RecommendedAction.RETRY,
            RecommendedAction.BLOCK,
        }
        # The dependency graph must be present in the proof metadata
        assert "dependency_graph" in result.proof.metadata
        assert "graph TD" in result.proof.metadata["dependency_graph"]

    asyncio.run(run())


# ---------------------------------------------------------------------------
# Adapted from tests/reference_groundcite/test_schema.py
# ---------------------------------------------------------------------------


def test_adapted_context_schema_minimal_and_full():
    """Adapted: the product runtime imports ``Context`` from GroundCite,
    so the schema contract is part of the product regression surface."""
    full = Context(
        doc_id="doc_123",
        text="Exemplo de contexto para testes.",
        title="Título",
        source="http://exemplo.com",
        license="MIT",
    )
    assert full.title == "Título"
    assert full.license == "MIT"

    minimal = Context(doc_id="doc_456", text="Texto mínimo apenas.")
    assert minimal.title is None
    assert minimal.source is None

    with pytest.raises(ValidationError):
        Context(doc_id="doc_789")


def test_adapted_sample_schema_loads_from_jsonl_payload():
    """Adapted: Sample.model_validate_json is used by the GroundCite
    reference benchmark loader and by future product benchmark adapters."""
    payload = json.dumps(
        {
            "id": "pt_smoke_001",
            "lang": "pt-BR",
            "question": "Quem fundou a ABL?",
            "contexts": [{"doc_id": "doc_001", "text": "Machado de Assis fundou a ABL."}],
            "answer": "Machado fundou.",
        }
    )
    sample = Sample.model_validate_json(payload)
    assert sample.id == "pt_smoke_001"
    assert len(sample.contexts) == 1
    assert sample.contexts[0].doc_id == "doc_001"
    assert sample.gold is None


def test_adapted_groundcite_label_mapping_to_trivalent():
    """The decision model still maps GroundCite labels to the trivalent
    product contract; this is now a product regression gate."""
    assert map_groundcite_label("supported") == (
        TrivalentDecision.TRUE,
        RecommendedAction.ALLOW,
        DecisionStatus.SUPPORTED,
    )
    assert map_groundcite_label("contradicted") == (
        TrivalentDecision.FALSE,
        RecommendedAction.BLOCK,
        DecisionStatus.CONTRADICTED,
    )
    assert map_groundcite_label("unsupported") == (
        TrivalentDecision.UNDECIDABLE,
        RecommendedAction.ABSTAIN,
        DecisionStatus.UNSUPPORTED,
    )
    assert map_groundcite_label("partially_unsupported") == (
        TrivalentDecision.UNDECIDABLE,
        RecommendedAction.WARN,
        DecisionStatus.PARTIALLY_UNSUPPORTED,
    )


# ---------------------------------------------------------------------------
# Product quality gates: claim support and abstention
# ---------------------------------------------------------------------------


class _StubSupportedBackend(BaseBackend):
    """Backend deterministically returning 'supported' for any claim."""

    def predict_support(self, claim, contexts, metadata=None):
        return {
            "label": "supported",
            "confidence": 0.95,
            "evidence_doc_idx": 0,
            "evidence_span": (0, len(contexts[0])) if contexts else None,
        }


class _StubContradictedBackend(BaseBackend):
    """Backend deterministically returning 'contradicted' for any claim."""

    def predict_support(self, claim, contexts, metadata=None):
        return {
            "label": "contradicted",
            "confidence": 0.91,
            "evidence_doc_idx": 0,
            "evidence_span": (0, len(contexts[0])) if contexts else None,
        }


def test_claim_support_quality_gate_supported_answer_is_true():
    """Quality gate: an answer fully covered by the adapter must reach
    ``claim_support_rate`` 1.0 and the abstention metric must recommend
    NOT abstaining."""

    sample = Sample(
        id="gate_supported_001",
        lang="en",
        question="What is the refund policy?",
        contexts=[Context(doc_id="d1", text="Refunds are available within 30 days.")],
        answer="Refunds are available within 30 days.",
    )
    backend = _StubSupportedBackend()
    claims = RegexClaimDecomposer().decompose(sample.answer, lang=sample.lang)

    metric = ClaimSupport()
    scores, analyzed = metric.evaluate(sample, backend, claims)

    assert scores["claim_support_rate"] == 1.0
    assert scores["claim_support_supported_count"] == len(claims)
    assert all(item["pred_label"] == "supported" for item in analyzed)

    abstention = AbstentionRisk()
    risk = abstention.evaluate(sample, scores)
    assert risk["abstention_risk"] == 0.0
    assert risk["recommend_abstention"] is False


def test_claim_support_quality_gate_contradicted_answer_abstains():
    """Quality gate: any contradicted claim must force abstention risk
    to 1.0 and recommend abstention."""

    sample = Sample(
        id="gate_contradicted_001",
        lang="en",
        question="What is the refund policy?",
        contexts=[Context(doc_id="d1", text="Refunds are available within 30 days.")],
        answer="Refunds are available within 365 days.",
    )
    backend = _StubContradictedBackend()
    claims = RegexClaimDecomposer().decompose(sample.answer, lang=sample.lang)

    metric = ClaimSupport()
    scores, _ = metric.evaluate(sample, backend, claims)

    assert scores["claim_support_rate"] == 0.0
    assert scores["claim_support_contradicted_count"] == 1.0

    abstention = AbstentionRisk()
    risk = abstention.evaluate(sample, scores)
    assert risk["abstention_risk"] == 1.0
    assert risk["recommend_abstention"] is True


def test_claim_support_quality_gate_unsupported_answer_recommends_abstain():
    """Quality gate: an unsupported claim must trigger abstention via
    the weighted risk formula."""

    class _UnsupportedBackend(BaseBackend):
        def predict_support(self, claim, contexts, metadata=None):
            return {
                "label": "unsupported",
                "confidence": 0.30,
                "evidence_doc_idx": None,
                "evidence_span": None,
            }

    sample = Sample(
        id="gate_unsupported_001",
        lang="en",
        question="What is the refund policy?",
        contexts=[Context(doc_id="d1", text="Returns require a receipt.")],
        answer="Refunds are available within 7 days.",
    )
    claims = RegexClaimDecomposer().decompose(sample.answer, lang=sample.lang)
    scores, _ = ClaimSupport().evaluate(sample, _UnsupportedBackend(), claims)

    assert scores["claim_support_rate"] == 0.0
    assert scores["claim_support_unsupported_count"] == float(len(claims))

    risk = AbstentionRisk().evaluate(sample, scores)
    # 100% unsupported claims => 0.7 * 1.0 + 0.3 * 0.0 = 0.7
    assert risk["abstention_risk"] == pytest.approx(0.7, abs=1e-6)
    assert risk["recommend_abstention"] is True


def test_runtime_claim_support_quality_gate_returns_allow():
    """Quality gate for the product runtime: with a populated adapter,
    ``claim_check`` must return ALLOW + TRUE."""

    async def run():
        adapter = SimpleKnowledgeAdapter()
        adapter.add_fact(
            "Refunds are available within 30 days.",
            source="policy",
            keywords=["refunds"],
        )
        runtime = SemanticTrustRuntime("tenant_a", knowledge_adapter=adapter)

        result = await runtime.claim_check("Refunds are available within 30 days.")

        assert result.decision == TrivalentDecision.TRUE
        assert result.recommended_action == RecommendedAction.ALLOW
        assert result.status == DecisionStatus.SUPPORTED
        assert result.confidence > 0.5

    asyncio.run(run())


def test_runtime_abstention_quality_gate_returns_abstain():
    """Quality gate for the product runtime: with no adapter, no
    ontology, and no evidence, ``claim_check`` must return
    UNDECIDABLE + ABSTAIN and produce a missing_requirement for evidence."""

    async def run():
        runtime = SemanticTrustRuntime("tenant_a")

        result = await runtime.claim_check(
            "An obscure claim with no known support anywhere."
        )

        assert result.decision == TrivalentDecision.UNDECIDABLE
        assert result.recommended_action == RecommendedAction.ABSTAIN
        assert result.status == DecisionStatus.UNSUPPORTED
        assert any(
            req.requirement_type == "evidence" for req in result.missing_requirements
        )

    asyncio.run(run())


# ---------------------------------------------------------------------------
# Lightweight integration with the GroundCite Evaluator
# ---------------------------------------------------------------------------


def test_groundcite_evaluator_runs_with_adapted_lexical_backend():
    """Sanity check: the vendored GroundCite ``Evaluator`` can be used
    with the in-tree ``LexicalBackend`` for a small sample. This locks
    the public surface the product depends on."""

    sample = Sample(
        id="eval_smoke_001",
        lang="pt-BR",
        question="Quem fundou a ABL?",
        contexts=[Context(doc_id="d1", text="Machado de Assis fundou a Academia Brasileira de Letras.")],
        answer="Machado de Assis fundou a ABL.",
    )
    # ``LexicalBackend`` is part of the GroundCite API used by the
    # product. Importing it lazily here keeps the smoke test light.
    from groundcite.backends import LexicalBackend

    evaluator = Evaluator(backend=LexicalBackend(), metrics=[ClaimSupport()])
    result = evaluator.evaluate(sample)

    assert isinstance(result, EvalResult)
    assert "claim_support_rate" in result.scores
    assert result.claims
    # The lexical backend has fuzzy match support; for an exact substring
    # match the rate must be >= 0 and at most 1.
    assert 0.0 <= result.scores["claim_support_rate"] <= 1.0


def test_claim_dependency_graph_is_exposed_for_answer_check():
    """The product's ``answer_check`` exposes the propagated dependency
    graph in the proof metadata; this is the contract adapted from the
    GroundCite ClaimDependencyGraph API."""

    async def run():
        runtime = SemanticTrustRuntime("tenant_a")
        result = await runtime.answer_check(
            "Machado de Assis fundou a Academia Brasileira de Letras. "
            "Ele escreveu Dom Casmurro."
        )

        assert "dependency_graph" in result.proof.metadata
        graph_text = result.proof.metadata["dependency_graph"]
        assert "graph TD" in graph_text
        # The two-claim answer must have produced two nodes
        assert "c1:" in graph_text
        assert "c2:" in graph_text

    asyncio.run(run())
