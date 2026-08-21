from __future__ import annotations

from quimera_semantic_trust_guardrail.evaluation.observability import EvaluationTrace
from quimera_semantic_trust_guardrail.evaluation.replay import explain_trace, replay_trace


def test_trace_replay_filters_case_and_explains_decision(tmp_path):
    trace = EvaluationTrace(trace_id="trace-replay")
    trace.record("pre_rag", "retrieval_ranked", attributes={"case_id": "one"})
    trace.record(
        "post_rag",
        "decision_evaluated",
        attributes={"case_id": "one", "decision": "TRUE", "correct": True},
    )
    trace.record("post_rag", "decision_evaluated", attributes={"case_id": "two", "decision": "FALSE"})
    path = tmp_path / "trace.jsonl"
    trace.write_jsonl(path)

    replay = replay_trace(path, case_id="one")
    assert replay["event_count"] == 2
    assert replay["decisions"] == ["TRUE"]
    explanation = explain_trace(path, case_id="one")
    assert "Trace: trace-replay" in explanation
    assert "decision_evaluated" in explanation
