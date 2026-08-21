"""Threshold-sweep metrics for the existing RAG evaluation contracts.

The sweep ranks each case once with :func:`evaluate_rag_cases`, then reuses
the ranked ids and similarity scores for every threshold.  This keeps the
benchmark deterministic and avoids encoding the same corpus once per curve
point.
"""

from __future__ import annotations

import csv
import html
import io
import math
from pathlib import Path
from typing import Any, Iterable, List, Mapping, Sequence

from pydantic import BaseModel, Field

from .embeddings import EmbeddingBackend
from .rag_evals import RagEvalCase, evaluate_rag_cases


class ThresholdCurvePoint(BaseModel):
    """Aggregated metrics for one absolute similarity threshold."""

    threshold: float
    context_precision: float
    context_recall: float
    context_f1: float
    abstention_rate: float
    useful_abstention_rate: float
    harmful_abstention_rate: float
    mean_context_size: float
    precision_evaluable_cases: int
    recall_evaluable_queries: int
    pre_rag_hit_at_k: float
    pre_rag_mrr: float

    @property
    def hit_at_k(self) -> float:
        """Short alias for consumers that use the pre-RAG metric name."""

        return self.pre_rag_hit_at_k

    @property
    def mrr(self) -> float:
        """Short alias for consumers that use the pre-RAG metric name."""

        return self.pre_rag_mrr


class ThresholdSweepReport(BaseModel):
    """Serializable report containing the complete threshold curve."""

    schema_version: str = "quimera_rag_threshold_sweep_v1"
    sample_count: int
    top_k: int
    relative_score_threshold: float
    embedding_model: str
    pre_rag_hit_at_k: float
    pre_rag_mrr: float
    recommended_threshold: float
    recommendation_reason: str
    curve: List[ThresholdCurvePoint] = Field(default_factory=list)

    @property
    def points(self) -> List[ThresholdCurvePoint]:
        """Alias for callers that refer to curve entries as points."""

        return self.curve

    @property
    def curve_rows(self) -> List[dict[str, Any]]:
        """Return flat, JSON-compatible rows suitable for tabular artifacts."""

        return [point.model_dump(mode="json") for point in self.curve]

    @property
    def hit_at_k(self) -> float:
        return self.pre_rag_hit_at_k

    @property
    def mrr(self) -> float:
        return self.pre_rag_mrr

    def to_json(self, *, indent: int = 2) -> str:
        """Serialize the report as JSON."""

        return self.model_dump_json(indent=indent)

    def to_csv(self) -> str:
        """Serialize curve rows as CSV without requiring a plotting package."""

        rows = self.curve_rows
        if not rows:
            return ""
        stream = io.StringIO()
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
        return stream.getvalue()

    def to_markdown(self) -> str:
        """Serialize curve rows as a compact Markdown table."""

        rows = self.curve_rows
        headers = list(rows[0]) if rows else list(ThresholdCurvePoint.model_fields)
        lines = [
            "# RAG Threshold Sweep",
            "",
            f"Recommended threshold: `{self.recommended_threshold:.4f}`",
            f"{self.recommendation_reason}",
            "",
            "| " + " | ".join(headers) + " |",
            "| " + " | ".join("---" for _ in headers) + " |",
        ]
        for row in rows:
            lines.append("| " + " | ".join(_format_table_value(row[name]) for name in headers) + " |")
        return "\n".join(lines) + "\n"

    def to_svg(self, *, width: int = 760, height: int = 420) -> str:
        """Render a dependency-free SVG line chart for the four main curves."""

        return render_threshold_curve_svg(self, width=width, height=height)

    def write_json(self, path: str | Path, *, indent: int = 2) -> None:
        Path(path).write_text(self.to_json(indent=indent) + "\n", encoding="utf-8")

    def write_csv(self, path: str | Path) -> None:
        Path(path).write_text(self.to_csv(), encoding="utf-8")

    def write_markdown(self, path: str | Path) -> None:
        Path(path).write_text(self.to_markdown(), encoding="utf-8")

    def write_svg(self, path: str | Path, *, width: int = 760, height: int = 420) -> None:
        Path(path).write_text(self.to_svg(width=width, height=height), encoding="utf-8")


def _validate_sweep_inputs(
    thresholds: Iterable[float], top_k: int, relative_score_threshold: float
) -> List[float]:
    if top_k < 1:
        raise ValueError("top_k must be positive")
    if not 0.0 <= relative_score_threshold <= 1.0:
        raise ValueError("relative_score_threshold must be between 0 and 1")

    values: List[float] = []
    for threshold in thresholds:
        value = float(threshold)
        if not math.isfinite(value):
            raise ValueError("thresholds must contain only finite numbers")
        values.append(value)
    if not values:
        raise ValueError("thresholds must contain at least one value")
    return values


def _context_f1(precision: float, recall: float) -> float:
    return 2.0 * precision * recall / (precision + recall) if precision + recall else 0.0


def _select_context(
    ranked_ids: Sequence[str],
    scores: Mapping[str, float],
    threshold: float,
    top_k: int,
    relative_score_threshold: float,
) -> List[str]:
    ranked_candidates = list(ranked_ids[:top_k])
    top1_score = scores.get(ranked_candidates[0], 0.0) if ranked_candidates else 0.0
    score_floor = max(threshold, top1_score * relative_score_threshold)
    return [
        document_id
        for document_id in ranked_candidates
        if scores.get(document_id, 0.0) >= score_floor
    ]


def sweep_context_thresholds(
    cases: Sequence[RagEvalCase | Mapping[str, Any]],
    embedder: EmbeddingBackend,
    thresholds: Iterable[float],
    *,
    top_k: int = 3,
    relative_score_threshold: float = 0.85,
) -> ThresholdSweepReport:
    """Evaluate context precision, recall, and abstention across thresholds.

    Cases are ranked exactly once.  Empty relevant-id lists remain part of the
    denominator for abstention metrics and are counted as useful abstentions
    when the selected context is empty.  They are excluded only from recall,
    because recall is undefined without a gold relevant set.
    """

    threshold_values = _validate_sweep_inputs(
        thresholds, top_k=top_k, relative_score_threshold=relative_score_threshold
    )
    baseline = evaluate_rag_cases(
        cases,
        embedder,
        top_k=top_k,
        context_policy="declared",
        relative_score_threshold=relative_score_threshold,
    )
    results = baseline.cases
    pre_rag_hit_at_k = float(baseline.stage_metrics.get("pre_rag.hit_at_k", 0.0))
    pre_rag_mrr = float(baseline.stage_metrics.get("pre_rag.mrr", 0.0))

    curve: List[ThresholdCurvePoint] = []
    for threshold in threshold_values:
        precision_sum = 0.0
        recall_sum = 0.0
        precision_evaluable_cases = 0
        recall_evaluable_queries = 0
        abstention_count = 0
        useful_abstention_count = 0
        harmful_abstention_count = 0
        context_size_sum = 0

        for result in results:
            selected = _select_context(
                result.pre_rag.ranked_document_ids,
                result.pre_rag.ranked_document_scores,
                threshold,
                top_k,
                relative_score_threshold,
            )
            selected_ids = set(selected)
            relevant_ids = set(result.pre_rag.relevant_document_ids)

            if selected:
                precision_evaluable_cases += 1
                precision_sum += len(selected_ids.intersection(relevant_ids)) / len(selected_ids)
            else:
                abstention_count += 1
                if relevant_ids:
                    harmful_abstention_count += 1
                else:
                    useful_abstention_count += 1

            if relevant_ids:
                recall_evaluable_queries += 1
                recall_sum += len(selected_ids.intersection(relevant_ids)) / len(relevant_ids)

            context_size_sum += len(selected)

        sample_count = len(results)
        context_precision = (
            precision_sum / precision_evaluable_cases if precision_evaluable_cases else 0.0
        )
        context_recall = (
            recall_sum / recall_evaluable_queries if recall_evaluable_queries else 0.0
        )
        curve.append(
            ThresholdCurvePoint(
                threshold=threshold,
                context_precision=context_precision,
                context_recall=context_recall,
                context_f1=_context_f1(context_precision, context_recall),
                abstention_rate=abstention_count / sample_count if sample_count else 0.0,
                useful_abstention_rate=(
                    useful_abstention_count / (sample_count - recall_evaluable_queries)
                    if sample_count - recall_evaluable_queries
                    else 0.0
                ),
                harmful_abstention_rate=(
                    harmful_abstention_count / recall_evaluable_queries
                    if recall_evaluable_queries
                    else 0.0
                ),
                mean_context_size=context_size_sum / sample_count if sample_count else 0.0,
                precision_evaluable_cases=precision_evaluable_cases,
                recall_evaluable_queries=recall_evaluable_queries,
                pre_rag_hit_at_k=pre_rag_hit_at_k,
                pre_rag_mrr=pre_rag_mrr,
            )
        )

    recommended = max(
        curve,
        key=lambda point: (
            point.context_f1,
            point.context_precision,
            -point.harmful_abstention_rate,
            point.threshold,
        ),
    )
    recommendation_reason = (
        f"Selected {recommended.threshold:.4f} because it maximizes context F1 "
        f"({recommended.context_f1:.3f}), then precision "
        f"({recommended.context_precision:.3f}), with harmful abstention "
        f"at {recommended.harmful_abstention_rate:.3f}."
    )
    return ThresholdSweepReport(
        sample_count=baseline.sample_count,
        top_k=top_k,
        relative_score_threshold=relative_score_threshold,
        embedding_model=baseline.embedding_model,
        pre_rag_hit_at_k=pre_rag_hit_at_k,
        pre_rag_mrr=pre_rag_mrr,
        recommended_threshold=recommended.threshold,
        recommendation_reason=recommendation_reason,
        curve=curve,
    )


def _format_table_value(value: Any) -> str:
    if isinstance(value, float):
        return f"{value:.6f}"
    return str(value)


def render_threshold_curve_svg(
    report: ThresholdSweepReport, *, width: int = 760, height: int = 420
) -> str:
    """Render a self-contained SVG line chart for a threshold report."""

    if width < 240 or height < 180:
        raise ValueError("SVG dimensions are too small for the chart")
    if not report.curve:
        raise ValueError("cannot render an empty threshold curve")

    left, right, top, bottom = 64, 22, 32, 58
    plot_width = width - left - right
    plot_height = height - top - bottom
    count = len(report.curve)

    def x_position(index: int) -> float:
        return left + (plot_width / 2 if count == 1 else plot_width * index / (count - 1))

    def y_position(value: float) -> float:
        bounded = min(1.0, max(0.0, value))
        return top + (1.0 - bounded) * plot_height

    def polyline(metric: str, color: str) -> str:
        points = " ".join(
            f"{x_position(index):.2f},{y_position(getattr(point, metric)):.2f}"
            for index, point in enumerate(report.curve)
        )
        return f'<polyline fill="none" stroke="{color}" stroke-width="2" points="{points}" />'

    series = (
        ("context_precision", "#2563eb", "Precision"),
        ("context_recall", "#059669", "Recall"),
        ("context_f1", "#dc2626", "F1"),
        ("abstention_rate", "#d97706", "Abstention"),
    )
    elements = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" role="img" aria-labelledby="title desc">',
        "<title id=\"title\">RAG threshold sweep</title>",
        (
            '<desc id="desc">Precision, recall, F1, and abstention by similarity '
            "threshold.</desc>"
        ),
        f'<rect width="{width}" height="{height}" fill="#ffffff" />',
        f'<line x1="{left}" y1="{top}" x2="{left}" y2="{height - bottom}" '
        'stroke="#374151" stroke-width="1" />',
        f'<line x1="{left}" y1="{height - bottom}" x2="{width - right}" '
        f'y2="{height - bottom}" stroke="#374151" stroke-width="1" />',
    ]
    for tick in range(6):
        value = tick / 5
        y = y_position(value)
        elements.extend(
            [
                f'<line x1="{left}" y1="{y:.2f}" x2="{width - right}" y2="{y:.2f}" '
                'stroke="#e5e7eb" stroke-width="1" />',
                f'<text x="{left - 8}" y="{y + 4:.2f}" text-anchor="end" '
                f'font-size="11" fill="#374151">{value:.1f}</text>',
            ]
        )
    for index, point in enumerate(report.curve):
        x = x_position(index)
        label = html.escape(f"{point.threshold:g}")
        elements.append(
            f'<text x="{x:.2f}" y="{height - bottom + 20}" text-anchor="middle" '
            f'font-size="10" fill="#374151">{label}</text>'
        )
    for metric, color, label in series:
        elements.append(polyline(metric, color))
    legend_x = left
    for metric, color, label in series:
        elements.extend(
            [
                f'<line x1="{legend_x}" y1="18" x2="{legend_x + 18}" y2="18" '
                f'stroke="{color}" stroke-width="3" />',
                f'<text x="{legend_x + 24}" y="22" font-size="11" fill="#374151">'
                f'{html.escape(label)}</text>',
            ]
        )
        legend_x += 112
    elements.append(
        f'<text x="{width / 2:.2f}" y="{height - 10}" text-anchor="middle" '
        'font-size="11" fill="#374151">Absolute similarity threshold</text>'
    )
    elements.append("</svg>")
    return "\n".join(elements) + "\n"


__all__ = [
    "ThresholdCurvePoint",
    "ThresholdSweepReport",
    "render_threshold_curve_svg",
    "sweep_context_thresholds",
]
