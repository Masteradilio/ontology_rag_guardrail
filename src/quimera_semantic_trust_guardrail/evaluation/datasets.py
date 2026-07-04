"""Dataset helpers for controlled validation packages."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from pydantic import BaseModel, Field


class ControlledDataset(BaseModel):
    dataset_id: str
    version: str
    task: str
    path: str
    sample_count: int
    label_distribution: Dict[str, int] = Field(default_factory=dict)
    limitations: List[str] = Field(default_factory=list)


class DatasetManifest(BaseModel):
    schema_version: str = "quimera_scientific_dataset_manifest_v1"
    package_id: str
    version: str
    datasets: List[ControlledDataset]


def load_jsonl_records(path: str | Path) -> List[Dict[str, Any]]:
    target = Path(path)
    return [json.loads(line) for line in target.read_text(encoding="utf-8").splitlines() if line.strip()]


def load_dataset_manifest(path: str | Path) -> DatasetManifest:
    return DatasetManifest.model_validate_json(Path(path).read_text(encoding="utf-8"))
