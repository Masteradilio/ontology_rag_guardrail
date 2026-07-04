from __future__ import annotations

import json

from quimera_semantic_trust_guardrail.__main__ import main
from quimera_semantic_trust_guardrail.evaluation import (
    SummaryMetrics,
    load_jsonl_records,
    run_scientific_baseline,
)


def test_scientific_baseline_writes_reproducible_artifacts(tmp_path):
    run_dir = run_scientific_baseline(output_dir=tmp_path, run_id="seed-run")

    assert (run_dir / "metadata.json").exists()
    assert (run_dir / "sample_results.jsonl").exists()
    assert (run_dir / "summary.json").exists()
    assert (run_dir / "failure_analysis.json").exists()

    metadata = json.loads((run_dir / "metadata.json").read_text(encoding="utf-8"))
    assert metadata["run_id"] == "seed-run"
    assert metadata["dataset_id"] == "quimera_scientific_seed"
    assert metadata["runtime_config"]["mode"] == "deterministic"


def test_scientific_baseline_covers_all_seed_tasks(tmp_path):
    run_dir = run_scientific_baseline(output_dir=tmp_path, run_id="coverage-run")
    rows = load_jsonl_records(run_dir / "sample_results.jsonl")

    assert len(rows) == 12
    assert {row["task"] for row in rows} >= {
        "claim_check",
        "answer_check",
        "refund",
        "output",
        "action",
    }
    assert {row["observed_decision"] for row in rows} == {"TRUE", "FALSE", "UNDECIDABLE"}
    assert all(row["proof"]["proof_id"] for row in rows)


def test_scientific_baseline_summary_metrics_are_explicit(tmp_path):
    run_dir = run_scientific_baseline(output_dir=tmp_path, run_id="metrics-run")
    summary = SummaryMetrics.model_validate_json((run_dir / "summary.json").read_text(encoding="utf-8"))

    assert summary.sample_count == 12
    assert 0.0 <= summary.metrics["accuracy"] <= 1.0
    assert "false_allow_rate" in summary.metrics
    assert "useful_abstention_rate" in summary.metrics
    assert summary.counts["expected:UNDECIDABLE"] >= 1
    assert summary.limitations


def test_scientific_baseline_keeps_failure_analysis_when_runtime_disagrees(tmp_path):
    run_dir = run_scientific_baseline(output_dir=tmp_path, run_id="failure-run")
    failures = json.loads((run_dir / "failure_analysis.json").read_text(encoding="utf-8"))

    assert isinstance(failures, list)
    assert any("expected" in " ".join(item["notes"]) for item in failures)


def test_scientific_baseline_cli_writes_run(tmp_path, capsys):
    exit_code = main(
        [
            "scientific-baseline",
            "--output-dir",
            str(tmp_path),
            "--run-id",
            "cli-run",
        ]
    )

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert exit_code == 0
    assert payload["run_dir"].endswith("cli-run")
    assert (tmp_path / "cli-run" / "summary.json").exists()
