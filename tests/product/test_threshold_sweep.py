from __future__ import annotations

import json

import pytest

from quimera_semantic_trust_guardrail.evaluation.rag_evals import RagEvalCase
from quimera_semantic_trust_guardrail.evaluation.threshold_sweep import (
    sweep_context_thresholds,
)


class FakeEmbedding:
    model_name = "fake-threshold-embedding"

    def __init__(self):
        self.calls = 0

    def encode(self, texts):
        self.calls += 1
        vectors = []
        for text in texts:
            value = text.lower()
            if "unknown" in value:
                vectors.append([0.0, 0.0, 0.0])
            elif "alpha" in value:
                vectors.append([1.0, 0.0, 0.0])
            elif "beta" in value:
                vectors.append([0.8, 0.6, 0.0])
            elif "gamma" in value:
                vectors.append([0.0, 1.0, 0.0])
            else:
                vectors.append([0.0, 0.0, 1.0])
        return vectors


def _cases():
    return [
        RagEvalCase(
            case_id="gold-supported",
            query="alpha",
            documents=[
                {"document_id": "alpha", "text": "alpha evidence"},
                {"document_id": "beta", "text": "beta evidence"},
            ],
            relevant_document_ids=["alpha"],
            answer="supported",
        ),
        RagEvalCase(
            case_id="gold-harmful",
            query="gamma",
            documents=[
                {"document_id": "gamma", "text": "gamma evidence"},
                {"document_id": "noise", "text": "unrelated"},
            ],
            relevant_document_ids=["gamma"],
            answer="supported",
        ),
        RagEvalCase(
            case_id="no-gold",
            query="unknown",
            documents=[
                {"document_id": "noise", "text": "unrelated"},
            ],
            relevant_document_ids=[],
            answer="abstain",
        ),
    ]


def test_sweep_is_monotone_and_keeps_no_gold_abstentions():
    embedder = FakeEmbedding()
    report = sweep_context_thresholds(
        _cases(), embedder, thresholds=[0.01, 0.9, 1.01], top_k=2, relative_score_threshold=0.0
    )

    assert embedder.calls == len(_cases())
    assert [point.mean_context_size for point in report.curve] == [1.0, 2 / 3, 0.0]
    assert [point.abstention_rate for point in report.curve] == [1 / 3, 1 / 3, 1.0]
    assert report.curve[0].recall_evaluable_queries == 2
    assert report.curve[-1].precision_evaluable_cases == 0


def test_useful_and_harmful_abstention_use_gold_denominators():
    report = sweep_context_thresholds(
        _cases(), FakeEmbedding(), thresholds=[0.9], top_k=1, relative_score_threshold=0.0
    )
    point = report.curve[0]

    assert point.abstention_rate == pytest.approx(1 / 3)
    assert point.useful_abstention_rate == pytest.approx(1.0)
    assert point.harmful_abstention_rate == pytest.approx(0.0)

    high = sweep_context_thresholds(
        _cases(), FakeEmbedding(), thresholds=[1.01], top_k=1, relative_score_threshold=0.0
    ).curve[0]
    assert high.useful_abstention_rate == pytest.approx(1.0)
    assert high.harmful_abstention_rate == pytest.approx(1.0)


def test_recommendation_uses_f1_then_precision_and_is_serializable():
    report = sweep_context_thresholds(
        _cases(), FakeEmbedding(), thresholds=[0.0, 0.9, 1.01], top_k=1, relative_score_threshold=0.0
    )

    assert report.recommended_threshold == 0.9
    assert "maximizes context F1" in report.recommendation_reason
    assert report.curve[0].pre_rag_hit_at_k == report.curve[-1].pre_rag_hit_at_k == 1.0
    assert report.curve[0].pre_rag_mrr == report.curve[-1].pre_rag_mrr == 1.0

    payload = json.loads(report.model_dump_json())
    assert payload["schema_version"] == "quimera_rag_threshold_sweep_v1"
    assert payload["curve"][1]["threshold"] == 0.9
    assert report.curve_rows[0]["context_f1"] == report.curve[0].context_f1
    assert "context_precision" in report.to_csv()
    assert "| threshold |" in report.to_markdown()
    assert report.to_svg().startswith("<svg ")


def test_input_validation_is_local_and_does_not_need_network():
    with pytest.raises(ValueError, match="at least one"):
        sweep_context_thresholds(_cases(), FakeEmbedding(), thresholds=[])
    with pytest.raises(ValueError, match="between 0 and 1"):
        sweep_context_thresholds(_cases(), FakeEmbedding(), thresholds=[0.4], relative_score_threshold=1.1)
