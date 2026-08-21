from __future__ import annotations
import json
from typing import List, Dict, Any, Optional
from pathlib import Path

from .compliance_engine import ComplianceRule, ComplianceStandard, ViolationSeverity


BASE_DIR = Path(".quimera_rules")
BASE_DIR.mkdir(parents=True, exist_ok=True)

HISTORY_DIR = Path(".quimera_rules_history")
HISTORY_DIR.mkdir(parents=True, exist_ok=True)


def _tenant_file(tenant_id: str) -> Path:
    return BASE_DIR / f"{tenant_id}_rules.json"

def _history_file(tenant_id: str) -> Path:
    return HISTORY_DIR / f"{tenant_id}_history.jsonl"


def load_rules(tenant_id: str) -> List[ComplianceRule]:
    p = _tenant_file(tenant_id)
    if not p.exists():
        return []
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return []
    rules: List[ComplianceRule] = []
    for item in data:
        try:
            rules.append(ComplianceRule(
                rule_id=item["rule_id"],
                standard=ComplianceStandard(item["standard"]),
                description=item.get("description", ""),
                patterns=item.get("patterns", []),
                severity=ViolationSeverity(item.get("severity", "medium")),
                remediation=item.get("remediation", ""),
                is_regex=bool(item.get("is_regex", False)),
                context_required=item.get("context_required"),
                exceptions=item.get("exceptions")
            ))
        except Exception:
            continue
    return rules


def save_rules(tenant_id: str, rules: List[ComplianceRule]) -> bool:
    try:
        data = []
        for r in rules:
            data.append({
                "rule_id": r.rule_id,
                "standard": r.standard.value,
                "description": r.description,
                "patterns": r.patterns,
                "severity": r.severity.value,
                "remediation": r.remediation,
                "is_regex": r.is_regex,
                "context_required": r.context_required,
                "exceptions": r.exceptions,
                "scope": r.scope,
                "enabled": getattr(r, "enabled", True)
            })
        _tenant_file(tenant_id).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        try:
            rec = {"event": "save", "count": len(data)}
            with _history_file(tenant_id).open("a", encoding="utf-8") as fp:
                fp.write(json.dumps(rec, ensure_ascii=False) + "\n")
        except Exception:
            pass
        return True
    except Exception:
        return False


def add_rule(tenant_id: str, rule: ComplianceRule) -> bool:
    rules = load_rules(tenant_id)
    rules = [r for r in rules if r.rule_id != rule.rule_id]
    rules.append(rule)
    ok = save_rules(tenant_id, rules)
    try:
        rec = {"event": "add", "rule_id": rule.rule_id, "after": _rule_to_dict(rule), "timestamp": _ts(), "actor": "admin"}
        with _history_file(tenant_id).open("a", encoding="utf-8") as fp:
            fp.write(json.dumps(rec, ensure_ascii=False) + "\n")
    except Exception:
        pass
    return ok


def delete_rule(tenant_id: str, rule_id: str) -> bool:
    rules = load_rules(tenant_id)
    before = None
    for r in rules:
        if r.rule_id == rule_id:
            before = _rule_to_dict(r)
            break
    rules = [r for r in rules if r.rule_id != rule_id]
    ok = save_rules(tenant_id, rules)
    try:
        rec = {"event": "delete", "rule_id": rule_id, "before": before, "timestamp": _ts(), "actor": "admin"}
        with _history_file(tenant_id).open("a", encoding="utf-8") as fp:
            fp.write(json.dumps(rec, ensure_ascii=False) + "\n")
    except Exception:
        pass
    return ok


def get_rule(tenant_id: str, rule_id: str) -> Optional[ComplianceRule]:
    for r in load_rules(tenant_id):
        if r.rule_id == rule_id:
            return r
    return None


def update_rule(tenant_id: str, rule_id: str, updates: Dict[str, Any]) -> bool:
    rules = load_rules(tenant_id)
    updated: List[ComplianceRule] = []
    for r in rules:
        if r.rule_id == rule_id:
            standard = ComplianceStandard(updates.get("standard", r.standard.value))
            severity = ViolationSeverity(updates.get("severity", r.severity.value))
            new_r = ComplianceRule(
                rule_id=rule_id,
                standard=standard,
                description=updates.get("description", r.description),
                patterns=updates.get("patterns", r.patterns),
                severity=severity,
                remediation=updates.get("remediation", r.remediation),
                is_regex=bool(updates.get("is_regex", r.is_regex)),
                context_required=updates.get("context_required", r.context_required),
                exceptions=updates.get("exceptions", r.exceptions),
                scope=updates.get("scope", r.scope),
                enabled=bool(updates.get("enabled", getattr(r, "enabled", True)))
            )
            updated.append(new_r)
        else:
            updated.append(r)
    ok = save_rules(tenant_id, updated)
    try:
        rec = {"event": "update", "rule_id": rule_id, "updates": updates, "timestamp": _ts(), "actor": "admin"}
        with _history_file(tenant_id).open("a", encoding="utf-8") as fp:
            fp.write(json.dumps(rec, ensure_ascii=False) + "\n")
    except Exception:
        pass
    return ok

def export_rules(tenant_id: str) -> List[Dict[str, Any]]:
    rules = load_rules(tenant_id)
    result: List[Dict[str, Any]] = []
    for r in rules:
        result.append({
            "rule_id": r.rule_id,
            "standard": r.standard.value,
            "description": r.description,
            "patterns": r.patterns,
            "severity": r.severity.value,
            "remediation": r.remediation,
            "is_regex": r.is_regex,
            "context_required": r.context_required,
            "exceptions": r.exceptions,
            "scope": r.scope,
            "enabled": getattr(r, "enabled", True),
        })
    return result

def import_rules(tenant_id: str, items: List[Dict[str, Any]], replace: bool = False) -> bool:
    current = [] if replace else load_rules(tenant_id)
    existing = {r.rule_id for r in current}
    for item in items:
        try:
            rule = ComplianceRule(
                rule_id=item["rule_id"],
                standard=ComplianceStandard(item["standard"]),
                description=item.get("description", ""),
                patterns=item.get("patterns", []),
                severity=ViolationSeverity(item.get("severity", "medium")),
                remediation=item.get("remediation", ""),
                is_regex=bool(item.get("is_regex", False)),
                context_required=item.get("context_required"),
                exceptions=item.get("exceptions"),
                scope=item.get("scope"),
                enabled=bool(item.get("enabled", True)),
            )
            if rule.rule_id in existing:
                current = [r for r in current if r.rule_id != rule.rule_id]
            current.append(rule)
            existing.add(rule.rule_id)
        except Exception:
            continue
    ok = save_rules(tenant_id, current)
    try:
        rec = {"event": "import", "count": len(items), "replace": replace, "timestamp": _ts(), "actor": "admin"}
        with _history_file(tenant_id).open("a", encoding="utf-8") as fp:
            fp.write(json.dumps(rec, ensure_ascii=False) + "\n")
    except Exception:
        pass
    return ok

def _rule_to_dict(r: ComplianceRule) -> Dict[str, Any]:
    return {
        "rule_id": r.rule_id,
        "standard": r.standard.value,
        "description": r.description,
        "patterns": r.patterns,
        "severity": r.severity.value,
        "remediation": r.remediation,
        "is_regex": r.is_regex,
        "context_required": r.context_required,
        "exceptions": r.exceptions,
        "scope": r.scope,
        "enabled": getattr(r, "enabled", True),
    }

def _ts():
    import time
    return int(time.time())

def read_history(tenant_id: str) -> List[Dict[str, Any]]:
    try:
        path = _history_file(tenant_id)
        if not path.exists():
            return []
        items = []
        with path.open("r", encoding="utf-8") as fp:
            for line in fp:
                line = line.strip()
                if not line:
                    continue
                try:
                    items.append(json.loads(line))
                except Exception:
                    continue
        return items
    except Exception:
        return []
