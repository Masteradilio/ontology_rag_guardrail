"""Artifact schemas for reproducible evaluation runs."""

from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from pydantic import BaseModel, Field


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _git_commit() -> Optional[str]:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        )
    except Exception:
        return None
    return result.stdout.strip() or None


class ProviderTrace(BaseModel):
    provider_name: str
    model_name: str
    latency_ms: Optional[int] = None
    request_id: Optional[str] = None
    status: str = "not_run"
    failure_mode: Optional[str] = None


class ProofTrace(BaseModel):
    proof_id: Optional[str] = None
    proof_type: Optional[str] = None
    ontology_version: Optional[str] = None
    policy_version: Optional[str] = None
    decision_path: List[str] = Field(default_factory=list)


class EvaluationRunMetadata(BaseModel):
    run_id: str
    created_at: str = Field(default_factory=_utc_now)
    commit_sha: Optional[str] = Field(default_factory=_git_commit)
    dataset_id: str
    dataset_version: str
    ontology_version: Optional[str] = None
    policy_version: Optional[str] = None
    runtime_config: Dict[str, Any] = Field(default_factory=dict)
    providers: List[ProviderTrace] = Field(default_factory=list)


class EvaluationSampleResult(BaseModel):
    sample_id: str
    task: str
    expected_label: str
    observed_decision: str
    recommended_action: str
    correct: Optional[bool] = None
    proof: Optional[ProofTrace] = None
    provider: Optional[ProviderTrace] = None
    notes: List[str] = Field(default_factory=list)


class SummaryMetrics(BaseModel):
    run_id: str
    sample_count: int
    metrics: Dict[str, float] = Field(default_factory=dict)
    counts: Dict[str, int] = Field(default_factory=dict)
    limitations: List[str] = Field(default_factory=list)


def create_evaluation_run(
    *,
    base_dir: str | Path = "artifacts/evaluation",
    run_id: Optional[str] = None,
    metadata: EvaluationRunMetadata,
) -> Path:
    """Create a timestamped run directory and write metadata.json."""

    safe_run_id = run_id or metadata.run_id
    if not safe_run_id:
        safe_run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir = Path(base_dir) / safe_run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    (run_dir / "metadata.json").write_text(
        metadata.model_dump_json(indent=2),
        encoding="utf-8",
    )
    return run_dir


def write_jsonl(path: str | Path, records: Iterable[BaseModel | Dict[str, Any]]) -> None:
    """Write pydantic models or dicts to JSONL."""

    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8") as handle:
        for record in records:
            if isinstance(record, BaseModel):
                payload = record.model_dump()
            else:
                payload = record
            handle.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")
