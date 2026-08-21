import json
from importlib import import_module

import os
import sys

import pandas as pd

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

proof_ledger = import_module("core.proof_ledger")
calculate_checksum = proof_ledger.calculate_checksum
get_version_tag = proof_ledger.get_version_tag


def test_record_and_load_entries(tmp_path, monkeypatch):
    ledger_dir = tmp_path / "ledger"
    monkeypatch.setenv("QUIMERA_LEDGER_DIR", str(ledger_dir))

    event = {
        "query_id": "q1",
        "llm_primary": "local_gpt_oss",
        "llm_fallback_used": False,
        "hypotheses": [],
        "prove": {
            "proved": ["a"],
            "rejected": [],
            "undecidable": [],
            "trace": ["step"],
        },
        "security": {"status": "ok", "notes": []},
        "budget": {"energy_mj": 30, "time_ms": 1500},
        "consumption": {"energy_mj": 1.2, "time_ms": 100},
        "governor": {"beam": 3, "qutrit": True},
    }

    file_path = proof_ledger.record(event)
    assert file_path.exists()

    entries = proof_ledger.load_entries(str(ledger_dir))
    assert len(entries) == 1
    entry = entries[0]

    assert entry["version"] == get_version_tag()

    checksum = entry.pop("checksum")
    expected_checksum = calculate_checksum(json.dumps(entry, sort_keys=True, ensure_ascii=False))
    assert checksum == expected_checksum

    df = proof_ledger.entries_to_dataframe(entries, ["proved"])
    assert isinstance(df, pd.DataFrame)
    assert df.iloc[0]["proved"] == 1
    assert df.iloc[0]["rejected"] == 0
