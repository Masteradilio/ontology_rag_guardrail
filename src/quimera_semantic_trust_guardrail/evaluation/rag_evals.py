"""Three-stage RAG evaluation contracts and metrics.

The pipeline intentionally separates retrieval quality, context quality, and
answer decision quality. No LLM call is made implicitly; post-RAG evaluation
receives an explicit answer evaluator when one is needed.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, Sequence

from pydantic import BaseModel, Field

from ..decision_model import SemanticTrustDecision, TrivalentDecision
from .embeddings import EmbeddingBackend, cosine_similarity
from .observability import EvaluationTrace


class RagDocument(BaseModel):
    document_id: str
    text: str
    metadata: Dict[str, Any] = Field(default_factory=dict)


class RagEvalCase(BaseModel):
    case_id: str
    query: str
    documents: List[RagDocument]
    relevant_document_ids: List[str] = Field(default_factory=list)
    retrieved_document_ids: List[str] = Field(default_factory=list)
    answer: str
    expected_decision: Optional[TrivalentDecision] = None


class PreRagResult(BaseModel):
    ranked_document_ids: List[str]
    relevant_document_ids: List[str]
    hit_at_k: float
    reciprocal_rank: float
    top1_similarity: float


class DuringRagResult(BaseModel):
    retrieved_document_ids: List[str]
    relevant_document_ids: List[str]
    context_precision: float
    context_recall: float
    duplicate_rate: float
    evidence_coverage: float


class PostRagResult(BaseModel):
    expected_decision: Optional[TrivalentDecision] = None
    observed_decision: Optional[TrivalentDecision] = None
    decision_correct: Optional[bool] = None
    evidence_coverage: float


class RagCaseResult(BaseModel):
    case_id: str
    pre_rag: PreRagResult
    during_rag: DuringRagResult
    post_rag: PostRagResult


class RagEvaluationReport(BaseModel):
    schema_version: str = "quimera_rag_evaluation_v1"
    sample_count: int
    top_k: int
    embedding_model: str
    stage_metrics: Dict[str, float] = Field(default_factory=dict)
    decision_distribution: Dict[str, int] = Field(default_factory=dict)
    cases: List[RagCaseResult] = Field(default_factory=list)
    limitations: List[str] = Field(default_factory=list)


AnswerEvaluator = Callable[[RagEvalCase, List[RagDocument]], Any]


def load_rag_cases(path: str | Path) -> List[RagEvalCase]:
    """Load newline-delimited RAG cases from a committed dataset."""

    cases: List[RagEvalCase] = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if line.strip():
            cases.append(RagEvalCase.model_validate(json.loads(line)))
    return cases


def _mean(values: Iterable[float]) -> float:
    items = list(values)
    return sum(items) / len(items) if items else 0.0


def _decision_from_value(value: Any) -> Optional[TrivalentDecision]:
    if isinstance(value, SemanticTrustDecision):
        return value.decision
    if isinstance(value, TrivalentDecision):
        return value
    if isinstance(value, str):
        try:
            return TrivalentDecision(value.upper())
        except ValueError:
            return None
    if isinstance(value, Mapping):
        return _decision_from_value(value.get("decision"))
    return None


def _rank_documents(
    case: RagEvalCase,
    embedder: EmbeddingBackend,
) -> tuple[List[str], Dict[str, float]]:
    texts = [case.query, *(document.text for document in case.documents)]
    vectors = embedder.encode(texts)
    query_vector = vectors[0]
    scored = [
        (document.document_id, cosine_similarity(query_vector, vectors[index + 1]))
        for index, document in enumerate(case.documents)
    ]
    scored.sort(key=lambda item: (-item[1], item[0]))
    return [item[0] for item in scored], dict(scored)


def _pre_rag(
    case: RagEvalCase,
    ranked_ids: Sequence[str],
    similarities: Mapping[str, float],
    top_k: int,
) -> PreRagResult:
    selected = list(ranked_ids[:top_k])
    relevant = set(case.relevant_document_ids)
    first_rank = next(
        (rank for rank, document_id in enumerate(ranked_ids, start=1) if document_id in relevant),
        None,
    )
    return PreRagResult(
        ranked_document_ids=list(ranked_ids),
        relevant_document_ids=list(case.relevant_document_ids),
        hit_at_k=1.0 if any(document_id in relevant for document_id in selected) else 0.0,
        reciprocal_rank=1.0 / first_rank if first_rank else 0.0,
        top1_similarity=similarities[ranked_ids[0]] if ranked_ids else 0.0,
    )


def _during_rag(case: RagEvalCase, ranked_ids: Sequence[str], top_k: int) -> DuringRagResult:
    retrieved = list(case.retrieved_document_ids or ranked_ids[:top_k])
    relevant = set(case.relevant_document_ids)
    unique_retrieved = set(retrieved)
    relevant_retrieved = unique_retrieved.intersection(relevant)
    precision = len(relevant_retrieved) / len(unique_retrieved) if unique_retrieved else 0.0
    recall = len(relevant_retrieved) / len(relevant) if relevant else 0.0
    duplicate_rate = (len(retrieved) - len(unique_retrieved)) / len(retrieved) if retrieved else 0.0
    return DuringRagResult(
        retrieved_document_ids=retrieved,
        relevant_document_ids=list(case.relevant_document_ids),
        context_precision=precision,
        context_recall=recall,
        duplicate_rate=duplicate_rate,
        evidence_coverage=recall,
    )


def _post_rag(
    case: RagEvalCase,
    context_documents: List[RagDocument],
    during: DuringRagResult,
    answer_evaluator: Optional[AnswerEvaluator],
) -> PostRagResult:
    observed = None
    if answer_evaluator is not None:
        observed = _decision_from_value(answer_evaluator(case, context_documents))
    correct = None
    if case.expected_decision is not None and observed is not None:
        correct = observed == case.expected_decision
    return PostRagResult(
        expected_decision=case.expected_decision,
        observed_decision=observed,
        decision_correct=correct,
        evidence_coverage=during.evidence_coverage,
    )


def evaluate_rag_cases(
    cases: Sequence[RagEvalCase | Mapping[str, Any]],
    embedder: EmbeddingBackend,
    *,
    answer_evaluator: Optional[AnswerEvaluator] = None,
    top_k: int = 3,
    trace: Optional[EvaluationTrace] = None,
) -> RagEvaluationReport:
    """Evaluate retrieval, assembled context, and answer decision quality."""

    if top_k < 1:
        raise ValueError("top_k must be positive")
    normalized_cases = [
        case if isinstance(case, RagEvalCase) else RagEvalCase.model_validate(case)
        for case in cases
    ]
    results: List[RagCaseResult] = []
    observed_decisions: Dict[str, int] = {}

    for case in normalized_cases:
        ranked_ids, similarities = _rank_documents(case, embedder)
        pre = _pre_rag(case, ranked_ids, similarities, top_k)
        if trace:
            trace.record(
                "pre_rag",
                "retrieval_ranked",
                attributes={
                    "case_id": case.case_id,
                    "top_k": top_k,
                    "hit_at_k": pre.hit_at_k,
                    "mrr": pre.reciprocal_rank,
                },
            )
        during = _during_rag(case, ranked_ids, top_k)
        if trace:
            trace.record(
                "during_rag",
                "context_evaluated",
                attributes={
                    "case_id": case.case_id,
                    "context_precision": during.context_precision,
                    "context_recall": during.context_recall,
                    "duplicate_rate": during.duplicate_rate,
                },
            )
        documents_by_id = {document.document_id: document for document in case.documents}
        context = [
            documents_by_id[document_id]
            for document_id in during.retrieved_document_ids
            if document_id in documents_by_id
        ]
        post = _post_rag(case, context, during, answer_evaluator)
        if trace:
            trace.record(
                "post_rag",
                "decision_evaluated",
                attributes={
                    "case_id": case.case_id,
                    "decision": post.observed_decision.value if post.observed_decision else None,
                    "correct": post.decision_correct,
                    "evidence_coverage": post.evidence_coverage,
                },
            )
        if post.observed_decision is not None:
            key = post.observed_decision.value
            observed_decisions[key] = observed_decisions.get(key, 0) + 1
        results.append(
            RagCaseResult(case_id=case.case_id, pre_rag=pre, during_rag=during, post_rag=post)
        )

    post_accuracy_values = [
        float(result.post_rag.decision_correct)
        for result in results
        if result.post_rag.decision_correct is not None
    ]
    retrieval_evaluable = [
        result for result in results if result.pre_rag.relevant_document_ids
    ]
    return RagEvaluationReport(
        sample_count=len(results),
        top_k=top_k,
        embedding_model=getattr(embedder, "model_name", embedder.__class__.__name__),
        stage_metrics={
            "pre_rag.hit_at_k": _mean(result.pre_rag.hit_at_k for result in retrieval_evaluable),
            "pre_rag.mrr": _mean(result.pre_rag.reciprocal_rank for result in retrieval_evaluable),
            "pre_rag.top1_similarity": _mean(result.pre_rag.top1_similarity for result in results),
            "pre_rag.evaluable_queries": float(len(retrieval_evaluable)),
            "during_rag.context_precision": _mean(result.during_rag.context_precision for result in results),
            "during_rag.context_recall": _mean(result.during_rag.context_recall for result in results),
            "during_rag.duplicate_rate": _mean(result.during_rag.duplicate_rate for result in results),
            "during_rag.evidence_coverage": _mean(result.during_rag.evidence_coverage for result in results),
            "post_rag.decision_accuracy": _mean(post_accuracy_values),
            "post_rag.evidence_coverage": _mean(result.post_rag.evidence_coverage for result in results),
        },
        decision_distribution=observed_decisions,
        cases=results,
        limitations=[
            "Synthetic seed cases; metrics do not estimate production RAG quality.",
            "Post-RAG quality is only evaluated when an explicit answer evaluator is supplied.",
            "Embedding scores depend on model, language, corpus, and retrieval configuration.",
        ],
    )
