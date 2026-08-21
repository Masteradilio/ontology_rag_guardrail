"""Runner for the reproducible enterprise RAG threshold benchmark."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Optional

from .embeddings import DEFAULT_EMBEDDING_MODEL, EmbeddingBackend, SentenceTransformerEmbedding
from .rag_benchmark import _commit_sha
from .rag_evals import load_rag_cases
from .threshold_sweep import ThresholdSweepReport, sweep_context_thresholds


DEFAULT_THRESHOLD_MANIFEST = Path("data/evaluation/rag_enterprise_v1/manifest.json")
DEFAULT_THRESHOLDS = tuple(round(0.20 + step * 0.01, 2) for step in range(61))


def _load_manifest_cases(manifest_path: str | Path):
    manifest_file = Path(manifest_path)
    manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
    manifest_path_value = Path(manifest["path"])
    candidates = [
        manifest_path_value,
        manifest_file.parent / manifest_path_value,
        manifest_file.parent / manifest_path_value.name,
    ]
    cases_path = next((candidate for candidate in candidates if candidate.exists()), None)
    if cases_path is None:
        raise FileNotFoundError(f"dataset cases file not found for {manifest_file}")
    return manifest, load_rag_cases(cases_path)


def _summary(manifest: dict, report: ThresholdSweepReport) -> str:
    lines = [
        "# Enterprise RAG Threshold Benchmark",
        "",
        f"- Dataset: `{manifest['package_id']}` `{manifest['version']}`",
        f"- Samples: `{report.sample_count}`",
        f"- Embedding model: `{report.embedding_model}`",
        f"- Top-k: `{report.top_k}`",
        f"- Relative score threshold: `{report.relative_score_threshold:.2f}`",
        f"- Recommended absolute threshold: `{report.recommended_threshold:.4f}`",
        "- LLM API key required: `no`",
        "",
        "## Curve",
        "",
        report.to_markdown().split("\n", 5)[-1],
        "## Interpretation",
        "",
        "- Precision is averaged over cases receiving non-empty final context.",
        "- Recall is averaged over queries with at least one gold relevant document.",
        "- Useful abstention means no-gold cases received empty context; harmful abstention means gold cases did.",
        "- The recommended threshold maximizes F1 on this semisynthetic corpus and is not a production calibration claim.",
        "- No post-RAG answer generation or LLM judge is run by this threshold-only benchmark.",
        "",
        "## Provenance",
        "",
        f"- Source type: `{manifest['provenance']['source_type']}`",
        f"- Contains production records: `{manifest['provenance']['contains_production_records']}`",
        f"- Contains personal data: `{manifest['provenance']['contains_personal_data']}`",
    ]
    return "\n".join(lines) + "\n"


def run_threshold_benchmark(
    *,
    manifest_path: str | Path = DEFAULT_THRESHOLD_MANIFEST,
    output_dir: str | Path = "artifacts/evaluation",
    run_id: str = "rag-enterprise-threshold-benchmark",
    model_name: str = DEFAULT_EMBEDDING_MODEL,
    top_k: int = 3,
    relative_score_threshold: float = 0.85,
    thresholds: Optional[Iterable[float]] = None,
    embedder: Optional[EmbeddingBackend] = None,
) -> Path:
    """Run one embedding pass and write curve artifacts for the portfolio."""

    manifest, cases = _load_manifest_cases(manifest_path)
    backend = embedder or SentenceTransformerEmbedding(model_name=model_name)
    report = sweep_context_thresholds(
        cases,
        backend,
        thresholds if thresholds is not None else DEFAULT_THRESHOLDS,
        top_k=top_k,
        relative_score_threshold=relative_score_threshold,
    )

    run_dir = Path(output_dir) / run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    metadata = {
        "schema_version": "quimera_rag_threshold_benchmark_v1",
        "run_id": run_id,
        "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "commit_sha": _commit_sha(),
        "dataset_id": manifest["package_id"],
        "dataset_version": manifest["version"],
        "sample_count": len(cases),
        "embedding_model": getattr(backend, "model_name", model_name),
        "top_k": top_k,
        "relative_score_threshold": relative_score_threshold,
        "thresholds": [point.threshold for point in report.curve],
        "recommended_threshold": report.recommended_threshold,
        "llm_api_key_required": False,
        "post_rag_evaluation": "not_run_context_curve_only",
        "provenance": manifest.get("provenance", {}),
    }
    (run_dir / "metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (run_dir / "manifest_snapshot.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    report.write_json(run_dir / "report.json")
    report.write_csv(run_dir / "threshold_curve.csv")
    report.write_markdown(run_dir / "threshold_curve.md")
    report.write_svg(run_dir / "threshold_curve.svg")
    (run_dir / "summary.md").write_text(_summary(manifest, report), encoding="utf-8")
    return run_dir


__all__ = [
    "DEFAULT_THRESHOLD_MANIFEST",
    "DEFAULT_THRESHOLDS",
    "run_threshold_benchmark",
]
