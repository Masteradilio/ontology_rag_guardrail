from __future__ import annotations

import json

from quimera_semantic_trust_guardrail.evaluation.observability import (
    EvaluationTrace,
    write_trace_summary,
)


def test_trace_redacts_secret_attributes_and_exports_jsonl(tmp_path):
    trace = EvaluationTrace(trace_id="trace-test")
    trace.record(
        "post_rag",
        "decision",
        attributes={"decision": "UNDECIDABLE", "api_key": "do-not-write"},
    )
    trace.write_jsonl(tmp_path / "trace.jsonl")
    payload = (tmp_path / "trace.jsonl").read_text(encoding="utf-8")

    assert "do-not-write" not in payload
    assert "[REDACTED]" in payload


def test_trace_summary_groups_stages_and_decisions(tmp_path):
    trace = EvaluationTrace(trace_id="trace-summary")
    trace.record("pre_rag", "retrieval_ranked", attributes={"case_id": "one"})
    trace.record("post_rag", "decision_evaluated", attributes={"decision": "TRUE"})
    trace.record("post_rag", "decision_evaluated", attributes={"decision": "UNDECIDABLE"})
    write_trace_summary(tmp_path / "summary.json", trace)
    summary = json.loads((tmp_path / "summary.json").read_text(encoding="utf-8"))

    assert summary["event_count"] == 3
    assert summary["events_by_stage"]["post_rag"] == 2
    assert summary["decision_distribution"] == {"TRUE": 1, "UNDECIDABLE": 1}


def test_trace_summary_contains_operational_metrics_and_otel_export(tmp_path):
    trace = EvaluationTrace(trace_id="trace-metrics")
    trace.record(
        "llm",
        "generation",
        duration_ms=12.5,
        attributes={
            "decision": "UNDECIDABLE",
            "usage": {"total_tokens": 7},
            "status": "failed",
        },
    )
    summary = trace.summary()
    assert summary["metrics"]["latency_ms_total"] == 12.5
    assert summary["metrics"]["abstention_count"] == 1
    assert summary["metrics"]["failure_count"] == 1
    assert summary["metrics"]["total_tokens"] == 7

    trace.write_open_telemetry(tmp_path / "otel.json")
    payload = json.loads((tmp_path / "otel.json").read_text(encoding="utf-8"))
    assert len(payload["resourceSpans"][0]["scopeSpans"][0]["spans"]) == 1
