from __future__ import annotations

import json

from quimera_semantic_trust_guardrail.evaluation.threshold_benchmark import run_threshold_benchmark


class FakeEmbedding:
    model_name = "fake-enterprise-threshold-embedding"

    def encode(self, texts):
        vectors = []
        for text in texts:
            value = text.lower()
            if "must not" in value or "within" in value or "requires" in value:
                vectors.append([1.0, 0.0, 0.0])
            elif "what" in value or "which" in value or "how" in value:
                vectors.append([0.9, 0.1, 0.0])
            else:
                vectors.append([0.0, 1.0, 0.0])
        return vectors


def test_threshold_benchmark_writes_reproducible_curve_artifacts(tmp_path):
    run_dir = run_threshold_benchmark(
        output_dir=tmp_path,
        run_id="enterprise-threshold",
        embedder=FakeEmbedding(),
        thresholds=[0.2, 0.5, 0.8],
    )

    metadata = json.loads((run_dir / "metadata.json").read_text(encoding="utf-8"))
    report = json.loads((run_dir / "report.json").read_text(encoding="utf-8"))

    assert metadata["sample_count"] == 96
    assert metadata["llm_api_key_required"] is False
    assert report["sample_count"] == 96
    assert len(report["curve"]) == 3
    assert (run_dir / "threshold_curve.csv").exists()
    assert (run_dir / "threshold_curve.md").exists()
    assert (run_dir / "threshold_curve.svg").read_text(encoding="utf-8").startswith("<svg ")
