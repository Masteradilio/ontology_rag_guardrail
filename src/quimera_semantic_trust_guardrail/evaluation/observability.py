"""Small dependency-free observability contracts for evaluation runs."""

from __future__ import annotations

import json
import uuid
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping, Optional

from pydantic import BaseModel, Field


_SECRET_KEY_PARTS = ("api_key", "authorization", "password", "secret", "token")


def _redact(value: Any, key: str = "") -> Any:
    if any(part in key.lower() for part in _SECRET_KEY_PARTS):
        return "[REDACTED]"
    if isinstance(value, Mapping):
        return {str(item_key): _redact(item_value, str(item_key)) for item_key, item_value in value.items()}
    if isinstance(value, list):
        return [_redact(item, key) for item in value]
    return value


class TraceEvent(BaseModel):
    trace_id: str
    span_id: str
    parent_span_id: Optional[str] = None
    stage: str
    event: str
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"))
    duration_ms: Optional[float] = None
    attributes: Dict[str, Any] = Field(default_factory=dict)


class EvaluationTrace:
    """In-memory trace recorder with JSONL export and secret redaction."""

    def __init__(self, trace_id: Optional[str] = None) -> None:
        self.trace_id = trace_id or f"trace-{uuid.uuid4().hex}"
        self.events: list[TraceEvent] = []

    def record(
        self,
        stage: str,
        event: str,
        *,
        span_id: Optional[str] = None,
        parent_span_id: Optional[str] = None,
        duration_ms: Optional[float] = None,
        attributes: Optional[Mapping[str, Any]] = None,
    ) -> TraceEvent:
        item = TraceEvent(
            trace_id=self.trace_id,
            span_id=span_id or f"span-{uuid.uuid4().hex}",
            parent_span_id=parent_span_id,
            stage=stage,
            event=event,
            duration_ms=duration_ms,
            attributes=_redact(dict(attributes or {})),
        )
        self.events.append(item)
        return item

    def summary(self) -> Dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "event_count": len(self.events),
            "events_by_stage": dict(Counter(event.stage for event in self.events)),
            "events_by_name": dict(Counter(event.event for event in self.events)),
            "decision_distribution": dict(
                Counter(
                    str(event.attributes["decision"])
                    for event in self.events
                    if event.attributes.get("decision") is not None
                )
            ),
        }

    def write_jsonl(self, path: str | Path) -> None:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("w", encoding="utf-8") as handle:
            for event in self.events:
                handle.write(event.model_dump_json() + "\n")


def write_trace_summary(path: str | Path, trace: EvaluationTrace) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(trace.summary(), ensure_ascii=False, indent=2), encoding="utf-8")
