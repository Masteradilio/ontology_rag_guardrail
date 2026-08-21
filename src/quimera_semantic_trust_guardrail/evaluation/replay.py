"""Replay and human-readable explanations for local evaluation artifacts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..proof_recorder import ProofRecorder
from .observability import TraceEvent


def load_trace_events(path: str | Path) -> List[TraceEvent]:
    """Load a trace JSONL file without executing application code."""

    events: List[TraceEvent] = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if line.strip():
            events.append(TraceEvent.model_validate(json.loads(line)))
    return events


def replay_trace(path: str | Path, *, case_id: Optional[str] = None) -> Dict[str, Any]:
    """Return the ordered evidence path for a trace or one case."""

    events = load_trace_events(path)
    if case_id is not None:
        events = [event for event in events if event.attributes.get("case_id") == case_id]
    events.sort(key=lambda event: event.timestamp)
    return {
        "trace_id": events[0].trace_id if events else None,
        "case_id": case_id,
        "event_count": len(events),
        "events": [event.model_dump(mode="json") for event in events],
        "decisions": [
            event.attributes["decision"]
            for event in events
            if event.attributes.get("decision") is not None
        ],
    }


def explain_trace(path: str | Path, *, case_id: Optional[str] = None) -> str:
    """Format a trace replay for a reviewer at the command line."""

    replay = replay_trace(path, case_id=case_id)
    lines = [
        f"Trace: {replay['trace_id'] or 'not found'}",
        f"Case: {case_id or 'all'}",
        f"Events: {replay['event_count']}",
    ]
    for event in replay["events"]:
        attrs = event["attributes"]
        details = []
        for key in ("decision", "context_precision", "context_recall", "correct"):
            if key in attrs:
                details.append(f"{key}={attrs[key]}")
        suffix = f" ({', '.join(details)})" if details else ""
        lines.append(f"- {event['stage']} -> {event['event']}{suffix}")
    return "\n".join(lines)


def replay_proof(storage_path: str | Path, proof_id: str) -> Dict[str, Any]:
    """Lookup one proof and verify its own hash before presenting it."""

    recorder = ProofRecorder(storage_path=str(storage_path))
    proof = recorder.lookup_proof(proof_id)
    if proof is None:
        return {"proof_id": proof_id, "found": False, "integrity_valid": False}
    return {
        "proof_id": proof.proof_id,
        "found": True,
        "integrity_valid": proof.verify_integrity(),
        "decision": proof.decision,
        "confidence": proof.confidence,
        "tenant_id": proof.tenant_id,
        "ontology_id": proof.ontology_id,
        "ontology_version": proof.ontology_version,
        "evidence_ids": proof.evidence_ids,
        "policy_ids": proof.policy_ids,
        "decision_path": proof.decision_path,
        "proof_status": proof.proof_status,
        "related_proof_id": proof.related_proof_id,
    }


def explain_proof(storage_path: str | Path, proof_id: str) -> str:
    """Format one proof ledger entry for an auditor."""

    result = replay_proof(storage_path, proof_id)
    if not result["found"]:
        return f"Proof {proof_id}: not found"
    return "\n".join(
        [
            f"Proof: {result['proof_id']}",
            f"Decision: {result['decision']}",
            f"Confidence: {result['confidence']}",
            f"Tenant: {result['tenant_id']}",
            f"Ontology: {result['ontology_id']} version {result['ontology_version']}",
            f"Evidence: {', '.join(result['evidence_ids']) or 'none'}",
            f"Decision path: {' -> '.join(result['decision_path']) or 'none'}",
            f"Integrity valid: {result['integrity_valid']}",
        ]
    )
