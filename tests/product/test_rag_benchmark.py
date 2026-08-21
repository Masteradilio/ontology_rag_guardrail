from __future__ import annotations

import json

from quimera_semantic_trust_guardrail.evaluation.rag_benchmark import run_rag_benchmark


class FakeEmbedding:
    model_name = "fake-benchmark-embedding"

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


def test_rag_benchmark_writes_offline_artifacts(tmp_path):
    run_dir = run_rag_benchmark(
        output_dir=tmp_path,
        run_id="benchmark",
        embedder=FakeEmbedding(),
    )

    metadata = json.loads((run_dir / "metadata.json").read_text(encoding="utf-8"))
    report = json.loads((run_dir / "report.json").read_text(encoding="utf-8"))

    assert metadata["llm_api_key_required"] is False
    assert metadata["sample_count"] == 4
    assert report["stage_metrics"]["pre_rag.hit_at_k"] == 1.0
    assert report["stage_metrics"]["during_rag.context_precision"] == 1.0
    assert report["stage_metrics"]["during_rag.candidate_context_precision"] < 1.0
    assert report["stage_metrics"]["post_rag.decision_accuracy"] == 1.0
    assert (run_dir / "summary.md").exists()
