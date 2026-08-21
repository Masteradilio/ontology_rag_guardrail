from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from quimera_semantic_trust_guardrail.evaluation.rag_evals import load_rag_cases


DATASET_DIR = Path("data/evaluation/rag_enterprise_v1")


def test_enterprise_benchmark_manifest_is_balanced_and_provenance_labeled():
    manifest = json.loads((DATASET_DIR / "manifest.json").read_text(encoding="utf-8"))
    cases = load_rag_cases(DATASET_DIR / "cases.jsonl")
    case_types = Counter(case.metadata["case_type"] for case in cases)

    assert manifest["sample_count"] == 96
    assert len(cases) == manifest["sample_count"]
    assert case_types == {
        "supported": 24,
        "contradicted": 24,
        "insufficient": 24,
        "partial": 24,
    }
    assert manifest["provenance"]["contains_production_records"] is False
    assert all(case.metadata["privacy_status"] == "synthetic_no_personal_data" for case in cases)
