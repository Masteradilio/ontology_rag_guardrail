from __future__ import annotations

import json

from quimera_semantic_trust_guardrail.evaluation.showcase import run_showcase


def test_showcase_runs_without_llm_or_embedding_model(tmp_path):
    run_dir = run_showcase(output_dir=tmp_path, run_id="showcase")
    payload = json.loads((run_dir / "showcase.json").read_text(encoding="utf-8"))

    assert payload["llm_api_key_required"] is False
    assert {item["decision"] for item in payload["runtime_decisions"]} == {
        "TRUE",
        "FALSE",
        "UNDECIDABLE",
    }
    assert all(item["proof_lookup_ok"] for item in payload["runtime_decisions"])
    assert {item["decision"] for item in payload["agent_decisions"]} == {
        "TRUE",
        "UNDECIDABLE",
    }
    assert all(item["proof_lookup_ok"] for item in payload["agent_decisions"])
    assert payload["ontology_snapshot"]["snapshot_id"]
    assert (run_dir / "trace.jsonl").exists()
