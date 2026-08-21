"""Módulo de Proof Ledger para o Projeto Quimera."""

from __future__ import annotations

import json
import os
from pathlib import Path
from datetime import datetime, timezone
from threading import Lock
from typing import Any, Dict, List, Optional

import pandas as pd

import hashlib

def calculate_checksum(data: str) -> str:
    """Calcula checksum SHA-256 dos dados."""
    return hashlib.sha256(data.encode('utf-8')).hexdigest()[:16]

def get_version_tag() -> str:
    """Retorna tag de versão do sistema."""
    return "quimera-v1.0"

_LEDGER_LOCK = Lock()


def _ledger_dir() -> Path:
    path = Path(os.environ.get("QUIMERA_LEDGER_DIR", ".quimera/ledger"))
    path.mkdir(parents=True, exist_ok=True)
    return path


def record(event: Dict[str, Any]) -> Path:
    """Registra um evento no Proof Ledger.

    O evento é salvo em formato JSONL com checksum e versão.
    """

    entry = dict(event)
    entry.setdefault("ts", datetime.now(timezone.utc).isoformat())
    entry.setdefault("version", get_version_tag())

    # Calcula checksum antes de adicionar o campo
    checksum = calculate_checksum(json.dumps(entry, sort_keys=True, ensure_ascii=False))
    entry["checksum"] = checksum

    ledger_file = _ledger_dir() / "proof_ledger.jsonl"
    line = json.dumps(entry, ensure_ascii=False)

    with _LEDGER_LOCK:
        with ledger_file.open("a", encoding="utf-8") as f:
            f.write(line + "\n")

    return ledger_file


def load_entries(ledger_dir: Optional[str] = None) -> List[Dict[str, Any]]:
    """Carrega todas as entradas do ledger."""
    directory = Path(ledger_dir) if ledger_dir else _ledger_dir()
    entries: List[Dict[str, Any]] = []
    if directory.is_dir():
        for file in directory.glob("*.jsonl"):
            with file.open("r", encoding="utf-8") as f:
                for line in f:
                    try:
                        entries.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
    return entries


def entries_to_dataframe(entries: List[Dict[str, Any]], status_filter: Optional[List[str]] = None) -> pd.DataFrame:
    """Converte entradas do ledger em DataFrame filtrado por status."""
    rows = []
    for data in entries:
        row = {
            "query_id": data.get("query_id"),
            "proved": len(data.get("prove", {}).get("proved", [])),
            "rejected": len(data.get("prove", {}).get("rejected", [])),
            "undecidable": len(data.get("prove", {}).get("undecidable", [])),
        }
        rows.append(row)
    df = pd.DataFrame(rows)
    if status_filter:
        mask = False
        for status in status_filter:
            mask = mask | (df[status] > 0)
        df = df[mask]
    return df
