from __future__ import annotations

import json
from pathlib import Path

from quimera_semantic_trust_guardrail.__main__ import main
from quimera_semantic_trust_guardrail.evaluation import run_commercial_demo


COMMERCIAL_DOCS = [
    Path("docs/commercial_icp_use_cases.md"),
    Path("docs/commercial_one_pager.md"),
    Path("docs/commercial_security_compliance_faq.md"),
    Path("docs/commercial_pilot_proposal_template.md"),
    Path("docs/commercial_metrics_sheet.md"),
    Path("docs/commercial_integration_diagram.md"),
]

FORBIDDEN_COMMERCIAL_CLAIMS = [
    "eliminates hallucinations",
    "certify legal compliance",
    "production accuracy",
    "superiority",
]


def test_commercial_discovery_documents_exist_and_are_conservative():
    for path in COMMERCIAL_DOCS:
        text = path.read_text(encoding="utf-8")
        assert text.strip(), path
        lowered = text.lower()
        for claim in FORBIDDEN_COMMERCIAL_CLAIMS:
            if claim in lowered:
                assert "does not" in lowered or "do not" in lowered or "not legal certification" in lowered


def test_commercial_demo_runs_offline_and_covers_core_workflows(tmp_path):
    run_dir = run_commercial_demo(output_dir=tmp_path, run_id="demo-test")
    payload = json.loads((run_dir / "commercial_demo.json").read_text(encoding="utf-8"))

    assert payload["mode"] == "deterministic_offline"
    assert payload["provider"] is None
    assert payload["ontology_snapshot"]["snapshot_id"]
    workflows = {item["workflow"]: item for item in payload["workflows"]}
    assert workflows["rag_answer_approval"]["decision"] == "UNDECIDABLE"
    assert workflows["agent_refund_authorization"]["decision"] == "TRUE"
    assert workflows["agent_missing_authorization"]["decision"] == "UNDECIDABLE"
    assert workflows["policy_compliance_review"]["decision"] == "FALSE"
    assert all(item["proof_id"] for item in workflows.values())


def test_commercial_demo_cli_runs_offline(tmp_path, capsys):
    exit_code = main(["commercial-demo", "--output-dir", str(tmp_path), "--run-id", "cli-commercial"])

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert exit_code == 0
    assert payload["run_dir"].endswith("cli-commercial")
    assert (tmp_path / "cli-commercial" / "commercial_demo.json").exists()
