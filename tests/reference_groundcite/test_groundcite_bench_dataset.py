import json
from pathlib import Path

from groundcite.schema import Sample


ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data" / "reference" / "groundcite_pten" / "samples"


def _load_jsonl(path: Path):
    return [Sample.model_validate_json(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_groundcite_bench_minimum_size_and_distribution():
    pt_samples = _load_jsonl(DATA_DIR / "groundcite_bench_pt.jsonl")
    en_samples = _load_jsonl(DATA_DIR / "groundcite_bench_en.jsonl")

    assert len(pt_samples) >= 80
    assert len(en_samples) >= 100

    for samples, lang in [(pt_samples, "pt-BR"), (en_samples, "en")]:
        assert {sample.lang for sample in samples} == {lang}
        by_type = {}
        by_split = {}
        for sample in samples:
            by_type[sample.metadata["type"]] = by_type.get(sample.metadata["type"], 0) + 1
            by_split[sample.metadata["split"]] = by_split.get(sample.metadata["split"], 0) + 1
        assert by_type == {
            "fully_supported": len(samples) // 4,
            "partially_unsupported": len(samples) // 4,
            "contradicted": len(samples) // 4,
            "abstain_needed": len(samples) // 4,
        }
        assert set(by_split) == {"dev", "test"}


def test_groundcite_bench_gold_spans_match_context_text():
    for path in [DATA_DIR / "groundcite_bench_pt.jsonl", DATA_DIR / "groundcite_bench_en.jsonl"]:
        for sample in _load_jsonl(path):
            assert sample.gold is not None
            contexts = {context.doc_id: context.text for context in sample.contexts}
            for claim in sample.gold.claims:
                assert claim.label in {"supported", "unsupported", "contradicted"}
                for evidence in claim.evidence:
                    span_text = contexts[evidence.doc_id][evidence.start:evidence.end]
                    assert span_text
                    assert span_text in contexts[evidence.doc_id]
            for unsupported_span in sample.gold.unsupported_spans:
                start = unsupported_span["start"]
                end = unsupported_span["end"]
                assert 0 <= start < end <= len(sample.answer)


def test_groundcite_bench_summary_matches_files():
    summary = json.loads((DATA_DIR / "groundcite_bench_summary.json").read_text(encoding="utf-8"))
    pt_samples = _load_jsonl(DATA_DIR / "groundcite_bench_pt.jsonl")
    en_samples = _load_jsonl(DATA_DIR / "groundcite_bench_en.jsonl")

    assert summary["files"]["groundcite_bench_pt.jsonl"]["sample_count"] == len(pt_samples)
    assert summary["files"]["groundcite_bench_en.jsonl"]["sample_count"] == len(en_samples)
    assert summary["combined"]["sample_count"] == len(pt_samples) + len(en_samples)
