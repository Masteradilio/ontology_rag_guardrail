from __future__ import annotations

import builtins
import json

import pytest

from quimera_semantic_trust_guardrail.evaluation.embeddings import (
    EmbeddingDependencyError,
    SentenceTransformerEmbedding,
    cosine_similarity,
)
from quimera_semantic_trust_guardrail.evaluation.rag_evals import (
    RagEvalCase,
    evaluate_rag_cases,
    load_rag_cases,
)


class FakeEmbedding:
    model_name = "fake-deterministic"

    def encode(self, texts):
        vectors = []
        for text in texts:
            value = text.lower()
            if "refund" in value:
                vectors.append([1.0, 0.0, 0.0])
            elif "export" in value or "contractor" in value:
                vectors.append([0.0, 1.0, 0.0])
            elif "retention" in value or "archived" in value:
                vectors.append([0.0, 0.0, 1.0])
            else:
                vectors.append([0.0, 0.0, 0.0])
        return vectors


def _cases():
    return [
        RagEvalCase(
            case_id="supported",
            query="refund window",
            documents=[
                {"document_id": "refund", "text": "refund policy"},
                {"document_id": "shipping", "text": "shipping policy"},
            ],
            relevant_document_ids=["refund"],
            retrieved_document_ids=["refund", "shipping"],
            answer="Refunds are available.",
            expected_decision="TRUE",
        ),
        RagEvalCase(
            case_id="duplicate",
            query="contractor export",
            documents=[
                {"document_id": "data", "text": "contractor export policy"},
                {"document_id": "other", "text": "shipping policy"},
            ],
            relevant_document_ids=["data"],
            retrieved_document_ids=["data", "data", "other"],
            answer="Contractor export is forbidden.",
            expected_decision="FALSE",
        ),
    ]


def test_cosine_similarity_handles_normalized_and_zero_vectors():
    assert cosine_similarity([1.0, 0.0], [1.0, 0.0]) == 1.0
    assert cosine_similarity([0.0, 0.0], [1.0, 0.0]) == 0.0


def test_pre_rag_reports_hit_and_reciprocal_rank():
    report = evaluate_rag_cases(_cases(), FakeEmbedding(), top_k=1)

    assert report.stage_metrics["pre_rag.hit_at_k"] == 1.0
    assert report.stage_metrics["pre_rag.mrr"] == 1.0
    assert report.cases[0].pre_rag.ranked_document_ids[0] == "refund"


def test_during_rag_reports_context_precision_recall_and_duplicates():
    report = evaluate_rag_cases(_cases(), FakeEmbedding())
    duplicate = report.cases[1].during_rag

    assert duplicate.context_precision == 0.5
    assert duplicate.context_recall == 1.0
    assert duplicate.duplicate_rate == pytest.approx(1 / 3)


def test_adaptive_context_assembly_removes_noise_and_can_abstain():
    report = evaluate_rag_cases(
        _cases(),
        FakeEmbedding(),
        context_policy="adaptive",
        min_similarity=0.4,
    )

    supported = report.cases[0].during_rag
    duplicate = report.cases[1].during_rag

    assert supported.candidate_context_precision == 0.5
    assert supported.retrieved_document_ids == ["refund"]
    assert duplicate.retrieved_document_ids == ["data"]
    assert duplicate.duplicate_rate == 0.0
    assert report.stage_metrics["during_rag.context_precision"] == 1.0
    assert report.stage_metrics["during_rag.context_recall"] == 1.0
    assert report.stage_metrics["during_rag.context_abstention_rate"] == 0.0


def test_adaptive_context_assembly_abstains_below_similarity_floor():
    cases = [
        RagEvalCase(
            case_id="unknown",
            query="unknown query",
            documents=[{"document_id": "other", "text": "shipping policy"}],
            answer="unknown",
        )
    ]

    report = evaluate_rag_cases(
        cases,
        FakeEmbedding(),
        context_policy="adaptive",
        min_similarity=0.4,
    )

    assert report.cases[0].during_rag.retrieved_document_ids == []
    assert report.cases[0].during_rag.context_abstained is True
    assert report.stage_metrics["during_rag.context_precision"] == 0.0


def test_post_rag_accepts_explicit_trivalent_evaluator():
    def evaluator(case, _context):
        return "FALSE" if case.case_id == "duplicate" else "TRUE"

    report = evaluate_rag_cases(_cases(), FakeEmbedding(), answer_evaluator=evaluator)

    assert report.stage_metrics["post_rag.decision_accuracy"] == 1.0
    assert report.decision_distribution == {"TRUE": 1, "FALSE": 1}


def test_post_rag_without_evaluator_is_explicitly_unmeasured():
    report = evaluate_rag_cases(_cases(), FakeEmbedding())

    assert report.stage_metrics["post_rag.decision_accuracy"] == 0.0
    assert report.cases[0].post_rag.observed_decision is None


def test_report_is_serializable():
    report = evaluate_rag_cases(_cases(), FakeEmbedding())
    payload = json.loads(report.model_dump_json())

    assert payload["schema_version"] == "quimera_rag_evaluation_v1"
    assert payload["sample_count"] == 2


def test_cases_load_from_jsonl(tmp_path):
    path = tmp_path / "cases.jsonl"
    path.write_text(
        json.dumps(_cases()[0].model_dump(mode="json")) + "\n",
        encoding="utf-8",
    )

    loaded = load_rag_cases(path)

    assert loaded[0].case_id == "supported"


def test_sentence_transformer_backend_loads_dependency_lazily(monkeypatch):
    original_import = builtins.__import__

    def blocked_import(name, *args, **kwargs):
        if name == "sentence_transformers":
            raise ModuleNotFoundError("blocked for test")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", blocked_import)
    backend = SentenceTransformerEmbedding()

    with pytest.raises(EmbeddingDependencyError):
        backend.encode(["test"])
