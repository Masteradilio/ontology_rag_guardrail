import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SUMMARY = ROOT / "data" / "samples" / "groundcite_bench_summary.json"


def test_dataset_summary_has_hashes_and_annotation_status():
    summary = json.loads(SUMMARY.read_text(encoding="utf-8"))
    assert summary["schema_version"] == "groundcite_bench_summary_v2"
    assert "files" in summary
    for name in ["groundcite_bench_pt.jsonl", "groundcite_bench_en.jsonl"]:
        item = summary["files"][name]
        assert len(item["sha256"]) == 64
        assert item["sample_count"] > 0
        assert item["claim_count"] >= item["sample_count"]
        assert item["split_distribution"]
        assert item["annotation_status_distribution"]
        assert item["schema_error_count"] == 0


def test_combined_summary_counts_match_file_summaries():
    summary = json.loads(SUMMARY.read_text(encoding="utf-8"))
    files = summary["files"].values()
    assert summary["combined"]["sample_count"] == sum(item["sample_count"] for item in files)
    assert summary["combined"]["claim_count"] == sum(item["claim_count"] for item in files)
