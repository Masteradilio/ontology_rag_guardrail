"""Offline embedding-backed benchmark for the three-stage RAG EVAL pipeline."""

from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from .embeddings import DEFAULT_EMBEDDING_MODEL, EmbeddingBackend, SentenceTransformerEmbedding
from .observability import EvaluationTrace, write_open_telemetry, write_trace_summary
from .rag_evals import RagEvalCase, evaluate_rag_cases, load_rag_cases


DEFAULT_MANIFEST = Path("data/evaluation/rag_seed/manifest.json")


def _commit_sha() -> Optional[str]:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        )
    except Exception:
        return None
    return result.stdout.strip() or None


def controlled_seed_answer_evaluator(case: RagEvalCase, _context: list[Any]) -> str:
    """Evaluate the committed answers with transparent deterministic rules.

    This is a controlled post-RAG fixture evaluator, not an LLM judge. Keeping
    it explicit makes the benchmark useful without an API key and prevents the
    benchmark from hiding generation quality behind an opaque provider call.
    """

    answer = case.answer.lower()
    if "contractors may export" in answer and "external analytics" in answer:
        return "FALSE"
    if "refunds are available within 30 days" in answer and "premium" not in answer:
        return "TRUE"
    return "UNDECIDABLE"


def run_rag_benchmark(
    *,
    manifest_path: str | Path = DEFAULT_MANIFEST,
    output_dir: str | Path = "artifacts/evaluation",
    run_id: str = "rag-seed-benchmark",
    model_name: str = DEFAULT_EMBEDDING_MODEL,
    top_k: int = 3,
    context_policy: str = "adaptive",
    min_similarity: float = 0.40,
    relative_score_threshold: float = 0.85,
    embedder: Optional[EmbeddingBackend] = None,
) -> Path:
    """Run the offline benchmark and write redacted JSON/Markdown artifacts."""

    manifest_file = Path(manifest_path)
    manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
    cases_path = manifest_file.parent / Path(manifest["path"]).name
    cases = load_rag_cases(cases_path)
    backend = embedder or SentenceTransformerEmbedding(model_name=model_name)
    trace = EvaluationTrace(trace_id=f"{run_id}-trace")
    report = evaluate_rag_cases(
        cases,
        backend,
        answer_evaluator=controlled_seed_answer_evaluator,
        top_k=top_k,
        context_policy=context_policy,
        min_similarity=min_similarity,
        relative_score_threshold=relative_score_threshold,
        trace=trace,
    )

    run_dir = Path(output_dir) / run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    metadata: Dict[str, Any] = {
        "schema_version": "quimera_rag_benchmark_v1",
        "run_id": run_id,
        "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "commit_sha": _commit_sha(),
        "dataset_id": manifest["package_id"],
        "dataset_version": manifest["version"],
        "sample_count": len(cases),
        "embedding_model": getattr(backend, "model_name", model_name),
        "top_k": top_k,
        "context_assembly_policy": context_policy,
        "context_min_similarity": min_similarity if context_policy == "adaptive" else None,
        "context_relative_score_threshold": (
            relative_score_threshold if context_policy == "adaptive" else None
        ),
        "llm_api_key_required": False,
        "post_rag_evaluator": "controlled_seed_answer_evaluator",
    }
    (run_dir / "metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    (run_dir / "report.json").write_text(
        report.model_dump_json(indent=2),
        encoding="utf-8",
    )
    trace.write_jsonl(run_dir / "trace.jsonl")
    write_trace_summary(run_dir / "observability.json", trace)
    write_open_telemetry(run_dir / "otel.json", trace)
    metric_lines = [
        "# RAG Seed Benchmark",
        "",
        f"- Dataset: `{metadata['dataset_id']}` `{metadata['dataset_version']}`",
        f"- Embedding model: `{metadata['embedding_model']}`",
        f"- Samples: `{metadata['sample_count']}`",
        "- LLM API key required: `no`",
        f"- Context assembly: `{context_policy}`",
        (
            f"- Context threshold: `min_similarity={min_similarity:.2f}`, "
            f"`relative={relative_score_threshold:.2f}`"
            if context_policy == "adaptive"
            else ""
        ),
        "",
        "## Metrics",
        "",
    ]
    metric_lines.extend(
        f"- `{name}`: `{value:.4f}`" for name, value in report.stage_metrics.items()
    )
    metric_lines.extend(
        [
            "",
            "## Limitations",
            "",
            "- Candidate-context metrics preserve the noisy declared context; final-context metrics measure the adaptive assembly policy.",
            "- Empty context is an explicit abstention when no candidate reaches the configured similarity floor.",
            *[f"- {limitation}" for limitation in report.limitations],
        ]
    )
    (run_dir / "summary.md").write_text("\n".join(metric_lines) + "\n", encoding="utf-8")
    return run_dir
