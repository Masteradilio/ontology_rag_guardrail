"""Ontology versioning: snapshots, diffs, rollback, and migration records.

Adds Phase 3 capabilities to the tenant ontology: explicit immutable
snapshots, deterministic diffs between snapshots and live state, rollback
that restores the live ontology to a chosen snapshot, and a JSONL
:migration record` stream linked back to proof ids.
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .semantic_fact import SemanticFact


@dataclass
class OntologySnapshot:
    """Immutable snapshot of a tenant ontology at a given version."""

    snapshot_id: str
    tenant_id: str
    ontology_id: str
    name: Optional[str]
    ontology_version: int
    captured_at_unix: float
    captured_at: str
    path: str
    fact_count: int
    entry_count: int
    proof_id: Optional[str] = None
    parent_snapshot_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class OntologyMigration:
    """Migration record linked to a proof id for audit trail linkage."""

    migration_id: str
    tenant_id: str
    ontology_id: str
    action: str  # snapshot, rollback, add_fact, remove_fact, update
    from_version: Optional[int] = None
    to_version: Optional[int] = None
    snapshot_id: Optional[str] = None
    proof_id: Optional[str] = None
    timestamp_unix: float = 0.0
    timestamp: str = ""
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _fact_key(fact: SemanticFact) -> Tuple[str, str, str]:
    return (fact.subject, fact.relation, fact.object)


def _snapshot_payload(ontology: Any) -> Dict[str, Any]:
    """Build a serializable payload from an ontology instance."""

    entries = {}
    for key, entry in ontology.entries.items():
        entries[key] = entry.to_dict()
    return {
        "ontology_id": ontology.ontology_id,
        "tenant_id": ontology.tenant_id,
        "name": ontology.name,
        "domain": ontology.domain,
        "description": ontology.description,
        "version": ontology.version,
        "created_at": ontology.created_at,
        "updated_at": ontology.updated_at,
        "entries": entries,
        "semantic_facts": [fact.model_dump(mode="json") for fact in ontology.semantic_facts],
    }


def diff_payloads(left: Dict[str, Any], right: Dict[str, Any]) -> Dict[str, Any]:
    """Compute a deterministic diff between two serialized ontology payloads."""

    def index_facts(payload: Dict[str, Any]) -> Dict[Tuple[str, str, str], Dict[str, Any]]:
        return {
            (f["subject"], f["relation"], f["object"]): f
            for f in payload.get("semantic_facts", [])
        }

    def index_entries(payload: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
        return dict(payload.get("entries", {}))

    left_facts = index_facts(left)
    right_facts = index_facts(right)
    added_facts = []
    removed_facts = []
    updated_facts = []
    for key in sorted(right_facts.keys() - left_facts.keys()):
        fact = right_facts[key]
        added_facts.append(
            {
                "subject": fact["subject"],
                "relation": fact["relation"],
                "object": fact["object"],
                "fact_type": fact.get("fact_type"),
                "state": fact.get("state"),
            }
        )
    for key in sorted(left_facts.keys() - right_facts.keys()):
        fact = left_facts[key]
        removed_facts.append(
            {
                "subject": fact["subject"],
                "relation": fact["relation"],
                "object": fact["object"],
                "fact_type": fact.get("fact_type"),
                "state": fact.get("state"),
            }
        )
    for key in sorted(left_facts.keys() & right_facts.keys()):
        before = left_facts[key]
        after = right_facts[key]
        if before != after:
            updated_facts.append(
                {
                    "subject": after["subject"],
                    "relation": after["relation"],
                    "object": after["object"],
                    "from_state": before.get("state"),
                    "to_state": after.get("state"),
                }
            )

    left_entries = index_entries(left)
    right_entries = index_entries(right)
    added_entries = sorted(set(right_entries) - set(left_entries))
    removed_entries = sorted(set(left_entries) - set(right_entries))

    return {
        "from_version": left.get("version"),
        "to_version": right.get("version"),
        "added_facts": added_facts,
        "removed_facts": removed_facts,
        "updated_facts": updated_facts,
        "added_entries": added_entries,
        "removed_entries": removed_entries,
        "summary": {
            "added_facts": len(added_facts),
            "removed_facts": len(removed_facts),
            "updated_facts": len(updated_facts),
            "added_entries": len(added_entries),
            "removed_entries": len(removed_entries),
        },
    }


class OntologyVersioningStore:
    """Snapshot, migration, diff, and rollback support for tenant ontologies.

    Designed to be attached to a :class:`TenantOntologyManager` and share its
    storage layout: ``<storage_path>/<tenant_id>/<ontology_id>/`` holds
    snapshots and a ``migrations.jsonl`` ledger.
    """

    def __init__(self, storage_path: Path) -> None:
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Paths
    # ------------------------------------------------------------------
    def _ontology_dir(self, tenant_id: str, ontology_id: str) -> Path:
        path = self.storage_path / tenant_id / ontology_id
        path.mkdir(parents=True, exist_ok=True)
        return path

    def _snapshots_dir(self, tenant_id: str, ontology_id: str) -> Path:
        path = self._ontology_dir(tenant_id, ontology_id) / "snapshots"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def _migrations_file(self, tenant_id: str, ontology_id: str) -> Path:
        return self._ontology_dir(tenant_id, ontology_id) / "migrations.jsonl"

    # ------------------------------------------------------------------
    # Snapshots
    # ------------------------------------------------------------------
    def snapshot(
        self,
        *,
        ontology: Any,
        name: Optional[str] = None,
        parent_snapshot_id: Optional[str] = None,
        proof_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> OntologySnapshot:
        tenant_id = ontology.tenant_id
        ontology_id = ontology.ontology_id
        snapshots_dir = self._snapshots_dir(tenant_id, ontology_id)
        ts_unix = time.time()
        ts_label = time.strftime("%Y%m%dT%H%M%S", time.gmtime(ts_unix)) + f"_{int((ts_unix * 1000) % 1000):03d}"
        snapshot_id = f"snap_{ts_label}"
        safe_name = ""
        if name:
            safe_name = "".join(ch for ch in name if ch.isalnum() or ch in ("-", "_"))
        filename = f"{snapshot_id}{('_' + safe_name) if safe_name else ''}.json"
        snapshot_path = snapshots_dir / filename
        payload = _snapshot_payload(ontology)
        payload["snapshot_id"] = snapshot_id
        payload["snapshot_name"] = name
        payload["captured_at_unix"] = ts_unix
        payload["parent_snapshot_id"] = parent_snapshot_id
        payload["proof_id"] = proof_id
        payload["metadata"] = metadata or {}
        snapshot_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        snapshot = OntologySnapshot(
            snapshot_id=snapshot_id,
            tenant_id=tenant_id,
            ontology_id=ontology_id,
            name=name,
            ontology_version=int(ontology.version),
            captured_at_unix=ts_unix,
            captured_at=time.strftime(
                "%Y-%m-%dT%H:%M:%SZ", time.gmtime(ts_unix)
            ),
            path=str(snapshot_path),
            fact_count=len(ontology.semantic_facts),
            entry_count=len(ontology.entries),
            proof_id=proof_id,
            parent_snapshot_id=parent_snapshot_id,
            metadata=metadata or {},
        )
        self.record_migration(
            tenant_id=tenant_id,
            ontology_id=ontology_id,
            action="snapshot",
            from_version=int(ontology.version),
            to_version=int(ontology.version),
            snapshot_id=snapshot_id,
            proof_id=proof_id,
            details={"name": name, "path": str(snapshot_path)},
        )
        return snapshot

    def list_snapshots(
        self, tenant_id: str, ontology_id: str
    ) -> List[OntologySnapshot]:
        snapshots_dir = self._snapshots_dir(tenant_id, ontology_id)
        results: List[OntologySnapshot] = []
        for file_path in sorted(snapshots_dir.glob("*.json")):
            try:
                data = json.loads(file_path.read_text(encoding="utf-8"))
            except Exception:
                continue
            results.append(
                OntologySnapshot(
                    snapshot_id=data.get("snapshot_id") or file_path.stem,
                    tenant_id=tenant_id,
                    ontology_id=ontology_id,
                    name=data.get("snapshot_name"),
                    ontology_version=int(data.get("version", 0)),
                    captured_at_unix=float(data.get("captured_at_unix", 0.0)),
                    captured_at=time.strftime(
                        "%Y-%m-%dT%H:%M:%SZ",
                        time.gmtime(float(data.get("captured_at_unix", 0.0)) or 0.0),
                    ),
                    path=str(file_path),
                    fact_count=len(data.get("semantic_facts", [])),
                    entry_count=len(data.get("entries", {})),
                    proof_id=data.get("proof_id"),
                    parent_snapshot_id=data.get("parent_snapshot_id"),
                    metadata=data.get("metadata", {}) or {},
                )
            )
        results.sort(key=lambda s: s.captured_at_unix, reverse=True)
        return results

    def get_snapshot(
        self, tenant_id: str, ontology_id: str, snapshot_id: str
    ) -> Optional[OntologySnapshot]:
        for snap in self.list_snapshots(tenant_id, ontology_id):
            if snap.snapshot_id == snapshot_id or Path(snap.path).stem.startswith(
                snapshot_id
            ):
                return snap
        return None

    def read_snapshot_payload(
        self, snapshot: OntologySnapshot
    ) -> Dict[str, Any]:
        return json.loads(Path(snapshot.path).read_text(encoding="utf-8"))

    # ------------------------------------------------------------------
    # Diff
    # ------------------------------------------------------------------
    def diff(
        self,
        *,
        left: Dict[str, Any],
        right: Dict[str, Any],
    ) -> Dict[str, Any]:
        return diff_payloads(left, right)

    def diff_snapshot_vs_live(
        self,
        *,
        tenant_id: str,
        ontology_id: str,
        snapshot_id: str,
        ontology: Any,
    ) -> Dict[str, Any]:
        snapshot = self.get_snapshot(tenant_id, ontology_id, snapshot_id)
        if snapshot is None:
            raise FileNotFoundError(
                f"Snapshot {snapshot_id!r} not found for {tenant_id}/{ontology_id}"
            )
        left = self.read_snapshot_payload(snapshot)
        right = _snapshot_payload(ontology)
        return self.diff(left=left, right=right)

    # ------------------------------------------------------------------
    # Rollback
    # ------------------------------------------------------------------
    def rollback_to_snapshot(
        self,
        *,
        manager: Any,
        tenant_id: str,
        ontology_id: str,
        snapshot_id: str,
        proof_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        snapshot = self.get_snapshot(tenant_id, ontology_id, snapshot_id)
        if snapshot is None:
            raise FileNotFoundError(
                f"Snapshot {snapshot_id!r} not found for {tenant_id}/{ontology_id}"
            )
        payload = self.read_snapshot_payload(snapshot)
        ontology = manager.get_ontology(tenant_id, ontology_id)
        if ontology is None:
            raise FileNotFoundError(
                f"Ontology {ontology_id!r} not found for tenant {tenant_id!r}"
            )
        previous_version = int(ontology.version)
        from .tenant_ontology import OntologyEntry
        from .semantic_fact import SemanticFact

        ontology.entries = {
            key: OntologyEntry.from_dict(value)
            for key, value in payload.get("entries", {}).items()
        }
        ontology.semantic_facts = [
            SemanticFact.model_validate(fact)
            for fact in payload.get("semantic_facts", [])
        ]
        ontology.version = int(payload.get("version", previous_version))
        ontology.updated_at = time.time()
        manager._save_ontology(ontology)
        manager._cache[manager._cache_key(tenant_id, ontology_id)] = ontology
        self.record_migration(
            tenant_id=tenant_id,
            ontology_id=ontology_id,
            action="rollback",
            from_version=previous_version,
            to_version=int(ontology.version),
            snapshot_id=snapshot_id,
            proof_id=proof_id,
            details={"path": snapshot.path},
        )
        return {
            "snapshot_id": snapshot_id,
            "from_version": previous_version,
            "to_version": int(ontology.version),
            "fact_count": len(ontology.semantic_facts),
            "entry_count": len(ontology.entries),
            "proof_id": proof_id,
        }

    # ------------------------------------------------------------------
    # Migration ledger
    # ------------------------------------------------------------------
    def record_migration(
        self,
        *,
        tenant_id: str,
        ontology_id: str,
        action: str,
        from_version: Optional[int] = None,
        to_version: Optional[int] = None,
        snapshot_id: Optional[str] = None,
        proof_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> OntologyMigration:
        ts = time.time()
        migration_id = f"mig_{int(ts * 1000)}_{tenant_id[:8]}_{ontology_id[:8]}"
        migration = OntologyMigration(
            migration_id=migration_id,
            tenant_id=tenant_id,
            ontology_id=ontology_id,
            action=action,
            from_version=from_version,
            to_version=to_version,
            snapshot_id=snapshot_id,
            proof_id=proof_id,
            timestamp_unix=ts,
            timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(ts)),
            details=details or {},
        )
        file_path = self._migrations_file(tenant_id, ontology_id)
        with file_path.open("a", encoding="utf-8") as fp:
            fp.write(json.dumps(migration.to_dict(), ensure_ascii=False) + "\n")
        return migration

    def list_migrations(
        self, tenant_id: str, ontology_id: str
    ) -> List[OntologyMigration]:
        file_path = self._migrations_file(tenant_id, ontology_id)
        if not file_path.exists():
            return []
        results: List[OntologyMigration] = []
        for line in file_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
            except json.JSONDecodeError:
                continue
            results.append(OntologyMigration(**data))
        results.sort(key=lambda m: m.timestamp_unix, reverse=True)
        return results
