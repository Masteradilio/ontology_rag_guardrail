#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Validation Cascade utilities for reinforcing "no hallucinations" guarantees.

Steps implemented:
- symbolic_contradictions: detect A and ¬A by checking ontology facts with FALSE state
  for the same (subject, relation, object) asserted by hypotheses.
- temporal_consistency: minimal check for monotonic timestamps (keys: 't' or 'time')
  for the same (subject, relation) within a request.
- semantic_consistency: light heuristics for symmetric relations (same_as/equals/equivalent).

Returned structure is suitable for inclusion in the proof ledger.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

try:
    from .knowledge_ontology import KnowledgeOntology, Fact
except Exception:  # pragma: no cover
    from core.knowledge_ontology import KnowledgeOntology, Fact


def _collapse_state(f: Fact) -> str:
    try:
        return f.state.collapse(deterministic=True)
    except Exception:
        # Defensive fallback
        try:
            return f.state.collapse()
        except Exception:
            return "UNDECIDABLE"


def check_symbolic_contradictions(hypotheses: List[Dict[str, Any]], ontology: KnowledgeOntology) -> Dict[str, Any]:
    issues: List[Dict[str, Any]] = []
    facts = list(ontology.get_all_facts()) if ontology else []
    # Build quick index by triple
    idx: Dict[Tuple[str, str, str], List[Fact]] = {}
    for f in facts:
        idx.setdefault((f.subject, f.relation, f.object), []).append(f)

    for hyp in hypotheses or []:
        s = hyp.get("subject")
        r = hyp.get("relation")
        o = hyp.get("object")
        if not (s and r and o):
            continue
        for f in idx.get((s, r, o), []):
            state = _collapse_state(f)
            if state == "FALSE":
                issues.append({
                    "triple": {"subject": s, "relation": r, "object": o},
                    "fact_id": f.fact_id,
                    "reason": "contradicts ontology (FALSE)",
                })
                break

    return {
        "name": "symbolic_contradictions",
        "status": "issues" if issues else "ok",
        "issues": issues,
    }


def check_temporal_consistency(hypotheses: List[Dict[str, Any]]) -> Dict[str, Any]:
    # Group by (subject, relation) and look at monotonic non-decreasing t/time
    series: Dict[Tuple[str, str], List[float]] = {}
    for hyp in hypotheses or []:
        s = hyp.get("subject")
        r = hyp.get("relation")
        t = hyp.get("t", hyp.get("time"))
        if s and r and isinstance(t, (int, float)):
            series.setdefault((s, r), []).append(float(t))

    problems: List[Dict[str, Any]] = []
    for key, times in series.items():
        if len(times) < 2:
            continue
        # Check if list is non-decreasing
        non_decreasing = all(times[i] <= times[i + 1] for i in range(len(times) - 1))
        if not non_decreasing:
            problems.append({
                "subject": key[0],
                "relation": key[1],
                "times": times,
                "reason": "non_monotonic_time",
            })

    return {
        "name": "temporal_consistency",
        "status": "warn" if problems else "ok",
        "issues": problems,
    }


def check_semantic_consistency(hypotheses: List[Dict[str, Any]], ontology: Optional[KnowledgeOntology] = None) -> Dict[str, Any]:
    symmetric_relations = {"same_as", "equals", "equivalent"}
    hyps = hypotheses or []
    seen: set[Tuple[str, str, str]] = set()
    for h in hyps:
        s = h.get("subject")
        r = h.get("relation")
        o = h.get("object")
        if s and r and o:
            seen.add((s, r, o))

    warns: List[Dict[str, Any]] = []
    for (s, r, o) in list(seen):
        if r in symmetric_relations:
            inverse = (o, r, s)
            if inverse not in seen:
                # try ontology
                has_inverse = False
                try:
                    if ontology:
                        for f in list(ontology.get_all_facts()):
                            if f.subject == o and f.relation == r and f.object == s and _collapse_state(f) == "TRUE":
                                has_inverse = True
                                break
                except Exception:
                    pass
                if not has_inverse:
                    warns.append({
                        "missing_inverse": {"subject": o, "relation": r, "object": s},
                        "reason": "symmetric_relation_missing_inverse",
                    })

    return {
        "name": "semantic_consistency",
        "status": "warn" if warns else "ok",
        "issues": warns,
    }


def run_cascaded_validations(hypotheses: List[Dict[str, Any]], ontology: KnowledgeOntology, cfg: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    cfg = cfg or {}
    strict = bool(cfg.get("strict", False))

    steps: List[Dict[str, Any]] = []
    s1 = check_symbolic_contradictions(hypotheses, ontology)
    steps.append(s1)
    s2 = check_temporal_consistency(hypotheses)
    steps.append(s2)
    s3 = check_semantic_consistency(hypotheses, ontology)
    steps.append(s3)

    # Verdict rules:
    # - any contradiction => blocked
    # - if strict and any warn => blocked
    # - if any warn => warn, else ok
    has_issues = any(s.get("status") == "issues" for s in steps)
    has_warns = any(s.get("status") == "warn" for s in steps)

    if has_issues:
        verdict = "blocked"
    elif strict and has_warns:
        verdict = "blocked"
    elif has_warns:
        verdict = "warn"
    else:
        verdict = "ok"

    return {
        "enabled": True,
        "verdict": verdict,
        "steps": steps,
    }

