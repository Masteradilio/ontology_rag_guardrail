"""Small dependency-free observability contracts for evaluation runs."""

from __future__ import annotations

import json
import uuid
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Mapping, Optional

from pydantic import BaseModel, Field


_SECRET_KEY_PARTS = ("api_key", "authorization", "password", "secret", "token")


def _redact(value: Any, key: str = "") -> Any:
    normalized_key = key.lower()
    token_count_key = normalized_key in {"input_tokens", "output_tokens", "total_tokens"}
    if not token_count_key and any(part in normalized_key for part in _SECRET_KEY_PARTS):
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
        durations = [event.duration_ms for event in self.events if event.duration_ms is not None]
        decisions = Counter(
            str(event.attributes["decision"])
            for event in self.events
            if event.attributes.get("decision") is not None
        )
        failures = sum(
            1
            for event in self.events
            if event.attributes.get("status") in {"failed", "error"}
            or event.attributes.get("failure") is True
        )
        total_tokens = 0
        estimated_cost = 0.0
        for event in self.events:
            usage = event.attributes.get("usage", {})
            if isinstance(usage, Mapping):
                total_tokens += int(usage.get("total_tokens", 0) or 0)
            total_tokens += int(event.attributes.get("total_tokens", 0) or 0)
            estimated_cost += float(event.attributes.get("estimated_cost_usd", 0.0) or 0.0)
        return {
            "trace_id": self.trace_id,
            "event_count": len(self.events),
            "events_by_stage": dict(Counter(event.stage for event in self.events)),
            "events_by_name": dict(Counter(event.event for event in self.events)),
            "decision_distribution": dict(decisions),
            "metrics": {
                "latency_ms_total": sum(durations),
                "latency_ms_average": sum(durations) / len(durations) if durations else 0.0,
                "latency_ms_max": max(durations) if durations else 0.0,
                "decision_count": sum(decisions.values()),
                "abstention_count": decisions.get("UNDECIDABLE", 0),
                "failure_count": failures,
                "total_tokens": total_tokens,
                "estimated_cost_usd": estimated_cost,
            },
        }

    def write_jsonl(self, path: str | Path) -> None:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("w", encoding="utf-8") as handle:
            for event in self.events:
                handle.write(event.model_dump_json() + "\n")

    def open_telemetry_payload(self, service_name: str = "quimera-evaluation") -> Dict[str, Any]:
        """Return a dependency-free OTLP/JSON-shaped export.

        The payload is intentionally data-only. An application can send it to
        an OTLP collector or translate it through its preferred SDK without
        forcing the base package to depend on OpenTelemetry.
        """

        spans = []
        for event in self.events:
            start = datetime.fromisoformat(event.timestamp.replace("Z", "+00:00"))
            start_ns = int(start.timestamp() * 1_000_000_000)
            duration_ns = int((event.duration_ms or 0.0) * 1_000_000)
            attributes = [
                {"key": str(key), "value": {"stringValue": str(value)}}
                for key, value in event.attributes.items()
                if value is not None and not isinstance(value, (dict, list))
            ]
            spans.append(
                {
                    "traceId": event.trace_id,
                    "spanId": event.span_id,
                    "parentSpanId": event.parent_span_id,
                    "name": f"{event.stage}.{event.event}",
                    "startTimeUnixNano": str(start_ns),
                    "endTimeUnixNano": str(start_ns + duration_ns),
                    "attributes": attributes,
                }
            )
        return {
            "resourceSpans": [
                {
                    "resource": {"attributes": [{"key": "service.name", "value": {"stringValue": service_name}}]},
                    "scopeSpans": [{"scope": {"name": "quimera.evaluation"}, "spans": spans}],
                }
            ]
        }

    def write_open_telemetry(self, path: str | Path, service_name: str = "quimera-evaluation") -> None:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            json.dumps(self.open_telemetry_payload(service_name), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )


def write_trace_summary(path: str | Path, trace: EvaluationTrace) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(trace.summary(), ensure_ascii=False, indent=2), encoding="utf-8")


def write_open_telemetry(
    path: str | Path,
    trace: EvaluationTrace,
    service_name: str = "quimera-evaluation",
) -> None:
    trace.write_open_telemetry(path, service_name=service_name)
