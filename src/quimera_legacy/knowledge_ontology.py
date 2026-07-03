"""Camada de alto nível para gerenciamento de ontologias com *stores* pluggables.

Este módulo reúne as implementações de armazenamento e expõe a API única
``KnowledgeOntology`` que aceita diferentes *stores* (``InMemoryStore``,
``Neo4jStore`` etc.).
"""

from __future__ import annotations

import json
import uuid
import warnings
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Protocol, Union, Tuple
import os
from pathlib import Path
from datetime import datetime

import networkx as nx

# Importa o módulo QGSL Core
try:
    from .qgsl_core import LogicalQubit
except ImportError:  # pragma: no cover - fallback quando executado isoladamente
    from qgsl_core import LogicalQubit


@dataclass
class Fact:
    """Representa um fato no grafo de conhecimento."""

    fact_id: str
    subject: str
    relation: str
    object: str
    state: LogicalQubit
    metadata: Dict[str, Any] = None

    def __post_init__(self) -> None:
        if self.metadata is None:
            self.metadata = {}


class OntologyStore(Protocol):
    """Protocolo para backends de armazenamento de ontologia."""

    graph: nx.MultiDiGraph
    facts: Dict[str, "Fact"]
    _fact_counter: int

    def add_node(self, node_id: str, node_type: str = "entity", **attributes) -> None: ...

    def add_fact(
        self,
        subject: str,
        relation: str,
        object: str,
        initial_state: Union[LogicalQubit, str, list] = "TRUE",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str: ...

    def update_fact_state(
        self, fact_id: str, new_state: Union[LogicalQubit, str, list], emit_warning: bool = True
    ) -> bool: ...

    def get_fact(self, fact_id: str) -> Optional["Fact"]: ...

    def query(self, criteria: Dict[str, Any]) -> List["Fact"]: ...

    def query_by_node(self, node_id: str, direction: str = "both") -> List["Fact"]: ...

    def remove_fact(self, fact_id: str) -> bool: ...

    def get_contradictory_facts(self) -> List["Fact"]: ...

    def get_statistics(self) -> Dict[str, Any]: ...

    def export_to_dict(self) -> Dict[str, Any]: ...

    def clear(self) -> None: ...

    def __len__(self) -> int: ...

    def __contains__(self, fact_id: str) -> bool: ...

    def __repr__(self) -> str: ...


class InMemoryStore:
    """Sistema de ontologia de conhecimento baseado em grafos direcionados."""

    def __init__(self) -> None:
        self.graph = nx.MultiDiGraph()
        self.facts: Dict[str, Fact] = {}
        self._fact_counter = 0

    def _generate_fact_id(self) -> str:
        self._fact_counter += 1
        return f"fact_{self._fact_counter}_{uuid.uuid4().hex[:8]}"

    def add_node(self, node_id: str, node_type: str = "entity", **attributes) -> None:
        self.graph.add_node(node_id, type=node_type, **attributes)

    def add_fact(
        self,
        subject: str,
        relation: str,
        object: str,
        initial_state: Union[LogicalQubit, str, list] = "TRUE",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        if not all([subject, relation, object]):
            raise ValueError("Subject, relation e object não podem estar vazios")

        if not isinstance(initial_state, LogicalQubit):
            initial_state = LogicalQubit(initial_state)

        fact_id = self._generate_fact_id()

        if not self.graph.has_node(subject):
            self.add_node(subject)
        if not self.graph.has_node(object):
            self.add_node(object)

        fact = Fact(
            fact_id=fact_id,
            subject=subject,
            relation=relation,
            object=object,
            state=initial_state,
            metadata=metadata or {},
        )

        self.graph.add_edge(
            subject,
            object,
            key=fact_id,
            fact_id=fact_id,
            relation_type=relation,
            state=initial_state,
            metadata=fact.metadata,
        )

        self.facts[fact_id] = fact
        return fact_id

    def update_fact_state(
        self, fact_id: str, new_state: Union[LogicalQubit, str, list], emit_warning: bool = True
    ) -> bool:
        if fact_id not in self.facts:
            raise KeyError(f"Fato {fact_id} não encontrado")

        if not isinstance(new_state, LogicalQubit):
            new_state = LogicalQubit(new_state)

        fact = self.facts[fact_id]
        fact.state = new_state

        if self.graph.has_edge(fact.subject, fact.object, key=fact_id):
            self.graph[fact.subject][fact.object][fact_id]["state"] = new_state

        if new_state.collapse() == "UNDECIDABLE":
            self.handle_contradiction(fact_id, emit_warning)

        return True

    def get_fact(self, fact_id: str) -> Optional[Fact]:
        return self.facts.get(fact_id)

    def query(self, pattern: Dict[str, Any]) -> List[Fact]:
        matching_facts: List[Fact] = []
        for fact in list(self.facts.values()):
            match = True
            if "subject" in pattern and fact.subject != pattern["subject"]:
                match = False
            if "relation" in pattern and fact.relation != pattern["relation"]:
                match = False
            if "object" in pattern and fact.object != pattern["object"]:
                match = False
            if "state_type" in pattern and fact.state.collapse() != pattern["state_type"]:
                match = False
            if match:
                matching_facts.append(fact)
        return matching_facts

    def query_by_node(self, node_id: str, direction: str = "both") -> List[Fact]:
        related_facts: List[Fact] = []
        if not self.graph.has_node(node_id):
            return related_facts
        if direction in ["in", "both"]:
            # Cria lista das edges para evitar "dictionary changed size during iteration"
            for _pred, _succ, data in list(self.graph.in_edges(node_id, data=True)):
                fact_id = data.get("fact_id")
                if fact_id and fact_id in self.facts:
                    related_facts.append(self.facts[fact_id])
        if direction in ["out", "both"]:
            # Cria lista das edges para evitar "dictionary changed size during iteration"
            for _pred, _succ, data in list(self.graph.out_edges(node_id, data=True)):
                fact_id = data.get("fact_id")
                if fact_id and fact_id in self.facts:
                    related_facts.append(self.facts[fact_id])
        return related_facts

    def handle_contradiction(self, fact_id: str, emit_warning: bool = True) -> None:
        fact = self.facts.get(fact_id)
        if not fact:
            return
        if emit_warning:
            warnings.warn(
                f"Contradição detectada no fato {fact_id}: "
                f"{fact.subject} {fact.relation} {fact.object} -> UNDECIDABLE",
                UserWarning,
            )
        fact.metadata["contradiction_detected"] = True
        fact.metadata["contradiction_timestamp"] = str(uuid.uuid4())

    def get_contradictory_facts(self) -> List[Fact]:
        return [
            fact
            for fact in list(self.facts.values())
            if fact.state.collapse(deterministic=True) == "UNDECIDABLE"
        ]

    def get_all_facts(self) -> List[Fact]:
        return list(self.facts.values())

    def get_statistics(self) -> Dict[str, Any]:
        total_facts = len(self.facts)
        total_nodes = self.graph.number_of_nodes()
        total_edges = self.graph.number_of_edges()
        state_counts = {"TRUE": 0, "FALSE": 0, "UNDECIDABLE": 0}
        for fact in list(self.facts.values()):
            state = fact.state.collapse(deterministic=True)
            state_counts[state] += 1
        relation_counts: Dict[str, int] = {}
        for fact in list(self.facts.values()):
            relation = fact.relation
            relation_counts[relation] = relation_counts.get(relation, 0) + 1
        return {
            "total_facts": total_facts,
            "total_nodes": total_nodes,
            "total_edges": total_edges,
            "state_distribution": state_counts,
            "relation_distribution": relation_counts,
            "contradictory_facts": len(self.get_contradictory_facts()),
        }

    def export_to_dict(self) -> Dict[str, Any]:
        facts_data = []
        for fact in list(self.facts.values()):
            facts_data.append(
                {
                    "fact_id": fact.fact_id,
                    "subject": fact.subject,
                    "relation": fact.relation,
                    "object": fact.object,
                    "state": fact.state.state_vector.tolist(),
                    "metadata": fact.metadata,
                }
            )
        return {
            "facts": facts_data,
            "nodes": dict(self.graph.nodes(data=True)),
            "statistics": self.get_statistics(),
        }

    # --- Import from dict (for persistence) ---
    def import_from_dict(self, data: Dict[str, Any]) -> None:
        self.clear()
        try:
            nodes = data.get("nodes", {})
            for node_id, attrs in nodes.items():
                if isinstance(attrs, dict):
                    self.add_node(node_id, **attrs)
                else:  # pragma: no cover
                    self.add_node(node_id)
        except Exception:
            # Best-effort: nodes optional
            pass

        for fd in data.get("facts", []) or []:
            try:
                subj = fd.get("subject")
                rel = fd.get("relation")
                obj = fd.get("object")
                st = fd.get("state", "UNDECIDABLE")
                meta = fd.get("metadata") or {}
                if isinstance(st, list):
                    state = LogicalQubit(st)
                else:
                    state = LogicalQubit(st)
                # Keep existing fact_id when available
                fid = fd.get("fact_id")
                new_id = self._generate_fact_id() if not fid else fid
                if not self.graph.has_node(subj):
                    self.add_node(subj)
                if not self.graph.has_node(obj):
                    self.add_node(obj)
                fact = Fact(
                    fact_id=new_id,
                    subject=subj,
                    relation=rel,
                    object=obj,
                    state=state,
                    metadata=meta,
                )
                self.facts[new_id] = fact
                self.graph.add_edge(subj, obj, key=new_id, relation=rel, state=state, fact_id=new_id)
            except Exception:
                continue

    def clear(self) -> None:
        self.graph.clear()
        self.facts.clear()
        self._fact_counter = 0

    def __len__(self) -> int:  # pragma: no cover - trivial
        return len(self.facts)

    def __contains__(self, fact_id: str) -> bool:  # pragma: no cover - trivial
        return fact_id in self.facts

    def __repr__(self) -> str:  # pragma: no cover - simples
        stats = self.get_statistics()
        return (
            f"KnowledgeOntology(facts={stats['total_facts']}, "
            f"nodes={stats['total_nodes']}, "
            f"contradictions={stats['contradictory_facts']})"
        )


class Neo4jStore(InMemoryStore):
    """Backend opcional usando Neo4j."""

    def __init__(self, uri: str = "bolt://localhost:7687", user: str = "neo4j", password: str = "neo4j"):
        if not self.available():
            raise ImportError("Neo4j driver não disponível")
        try:
            from neo4j import GraphDatabase  # noqa: F401
        except Exception as exc:  # pragma: no cover - import guard
            raise ImportError("Falha ao importar neo4j") from exc
        super().__init__()

    @classmethod
    def available(cls) -> bool:
        try:
            import neo4j  # noqa: F401
            return True
        except Exception:
            return False


class KnowledgeOntology:
    """Fachada que delega operações para um ``OntologyStore``.

    Args:
        store: Implementação de :class:`OntologyStore` a ser utilizada. Caso
            ``None``, é usado :class:`InMemoryStore`.
    """

    def __init__(self, store: Optional[OntologyStore] = None) -> None:
        self.store = store or InMemoryStore()

    # ------------------------------------------------------------------
    # Propriedades de compatibilidade
    # ------------------------------------------------------------------
    @property
    def graph(self):
        return self.store.graph

    @property
    def facts(self):
        return self.store.facts

    @property
    def _fact_counter(self):  # pragma: no cover - apenas para compatibilidade
        return self.store._fact_counter

    # ------------------------------------------------------------------
    # Delegações
    # ------------------------------------------------------------------
    def add_node(self, *args, **kwargs):
        return self.store.add_node(*args, **kwargs)

    def add_fact(self, *args, **kwargs):
        return self.store.add_fact(*args, **kwargs)

    def update_fact_state(self, *args, **kwargs):
        return self.store.update_fact_state(*args, **kwargs)

    def get_fact(self, *args, **kwargs):
        return self.store.get_fact(*args, **kwargs)

    def query(self, *args, **kwargs):
        return self.store.query(*args, **kwargs)

    def query_by_node(self, *args, **kwargs):
        return self.store.query_by_node(*args, **kwargs)

    def remove_fact(self, *args, **kwargs):
        return self.store.remove_fact(*args, **kwargs)

    def get_contradictory_facts(self, *args, **kwargs):
        return self.store.get_contradictory_facts(*args, **kwargs)

    def get_all_facts(self, *args, **kwargs):
        return self.store.get_all_facts(*args, **kwargs)

    def get_statistics(self):
        return self.store.get_statistics()

    def export_to_dict(self):
        return self.store.export_to_dict()

    def clear(self):
        return self.store.clear()

    # ------------------------------------------------------------------
    # Persistência: salvar/carregar JSON/YAML + snapshots/rollback
    # ------------------------------------------------------------------
    def save_to_file(self, filepath: str) -> str:
        """Salva a ontologia em arquivo (JSON ou YAML quando disponível)."""
        data = self.export_to_dict()
        path = Path(filepath)
        path.parent.mkdir(parents=True, exist_ok=True)
        text = None
        if path.suffix.lower() in (".yaml", ".yml"):
            try:
                import yaml  # type: ignore
                text = yaml.safe_dump(data, allow_unicode=True, sort_keys=False)
            except Exception:
                text = json.dumps(data, ensure_ascii=False, indent=2)
        else:
            text = json.dumps(data, ensure_ascii=False, indent=2)
        path.write_text(text, encoding="utf-8")
        return str(path)

    @classmethod
    def load_from_file(cls, filepath: str) -> "KnowledgeOntology":
        """Carrega uma ontologia de arquivo (JSON/YAML)."""
        path = Path(filepath)
        if not path.exists():
            raise FileNotFoundError(str(path))
        content = path.read_text(encoding="utf-8")
        data: Dict[str, Any]
        if path.suffix.lower() in (".yaml", ".yml"):
            try:
                import yaml  # type: ignore
                data = yaml.safe_load(content) or {}
            except Exception:
                data = json.loads(content)
        else:
            data = json.loads(content)

        onto = cls()
        if hasattr(onto.store, "import_from_dict"):
            onto.store.import_from_dict(data)
        return onto

    # ---- snapshots / rollback / diffs ----
    def _knowledge_dir(self) -> Path:
        base = Path(os.environ.get("QUIMERA_KNOWLEDGE_DIR", ".quimera/knowledge"))
        base.mkdir(parents=True, exist_ok=True)
        return base

    def _history_file(self) -> Path:
        return self._knowledge_dir() / "history.jsonl"

    def snapshot(self, name: Optional[str] = None) -> Dict[str, Any]:
        """Cria snapshot do estado atual e registra no ledger/histórico.

        Returns: dict com snapshot_id e path
        """
        ts = datetime.utcnow().strftime("%Y%m%dT%H%M%S%f")
        snap_id = f"snap_{ts}"
        if name:
            safe = "".join(ch for ch in name if ch.isalnum() or ch in ("-","_"))
            filename = f"{snap_id}_{safe}.json"
        else:
            filename = f"{snap_id}.json"
        snap_dir = self._knowledge_dir() / "snapshots"
        snap_dir.mkdir(parents=True, exist_ok=True)
        snap_path = snap_dir / filename
        self.save_to_file(str(snap_path))

        entry = {
            "op": "snapshot",
            "snapshot_id": snap_id,
            "name": name,
            "path": str(snap_path),
            "ts": ts,
        }
        # grava em history
        try:
            with self._history_file().open("a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except Exception:
            pass
        # grava no proof_ledger
        try:
            from . import proof_ledger as _ledger  # lazy import
            _ledger.record({
                "knowledge_snapshot_id": snap_id,
                "knowledge": {
                    "op": "snapshot",
                    "path": str(snap_path),
                    "name": name,
                }
            })
        except Exception:
            pass
        return entry

    def rollback(self, snapshot: str) -> Dict[str, Any]:
        """Restaura estado a partir de um snapshot (id ou caminho)."""
        snap_path: Optional[Path] = None
        if os.path.isfile(snapshot):
            snap_path = Path(snapshot)
        else:
            # procura por id (match exato com id.json ou id_*.json)
            snaps = list((self._knowledge_dir() / "snapshots").glob("*.json"))
            # prioridade: arquivo com nome exatamente igual ao id
            for p in snaps:
                n = Path(p).name
                if n == f"{snapshot}.json":
                    snap_path = p
                    break
            if not snap_path:
                for p in snaps:
                    n = Path(p).name
                    if n.startswith(f"{snapshot}_"):
                        snap_path = p
                        break
        if not snap_path or not snap_path.exists():
            raise FileNotFoundError(f"Snapshot não encontrado: {snapshot}")

        restored = KnowledgeOntology.load_from_file(str(snap_path))
        self.store = restored.store  # substitui backend inteiro

        entry = {
            "op": "rollback",
            "snapshot": snapshot,
            "path": str(snap_path),
            "ts": datetime.utcnow().isoformat(),
        }
        try:
            with self._history_file().open("a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except Exception:
            pass
        try:
            from . import proof_ledger as _ledger
            _ledger.record({
                "knowledge": {
                    "op": "rollback",
                    "snapshot": snapshot,
                    "path": str(snap_path),
                }
            })
        except Exception:
            pass
        return entry

    def diff_with_file(self, filepath: str) -> Dict[str, Any]:
        """Calcula diff legível entre estado atual e arquivo alvo."""
        other = KnowledgeOntology.load_from_file(filepath)
        return self.diff_with_ontology(other)

    def _facts_index(self) -> Dict[Tuple[str, str, str], Fact]:
        idx: Dict[Tuple[str, str, str], Fact] = {}
        for f in list(self.get_all_facts()):
            idx[(f.subject, f.relation, f.object)] = f
        return idx

    def diff_with_ontology(self, other: "KnowledgeOntology") -> Dict[str, Any]:
        a = self._facts_index()
        b = other._facts_index()
        added = []
        removed = []
        updated = []
        for key in b.keys() - a.keys():
            f = b[key]
            added.append({"subject": f.subject, "relation": f.relation, "object": f.object})
        for key in a.keys() - b.keys():
            f = a[key]
            removed.append({"subject": f.subject, "relation": f.relation, "object": f.object})
        for key in a.keys() & b.keys():
            fa = a[key]
            fb = b[key]
            if fa.state.state_vector.tolist() != fb.state.state_vector.tolist() or (fa.metadata or {}) != (fb.metadata or {}):
                updated.append({
                    "subject": fa.subject,
                    "relation": fa.relation,
                    "object": fa.object,
                    "from": fa.state.state_vector.tolist(),
                    "to": fb.state.state_vector.tolist(),
                })
        return {"added": added, "removed": removed, "updated": updated}

    # ------------------------------------------------------------------
    # Métodos mágicos
    # ------------------------------------------------------------------
    def __len__(self):
        return len(self.store)

    def __contains__(self, fact_id: str) -> bool:
        return fact_id in self.store

    def __repr__(self) -> str:
        return repr(self.store)


# ----------------------------------------------------------------------
# Funções utilitárias
# ----------------------------------------------------------------------
def create_simple_ontology() -> KnowledgeOntology:
    """Cria uma ontologia simples com alguns fatos básicos para demonstração."""

    ontology = KnowledgeOntology()
    ontology.add_fact("Sócrates", "é", "humano", "TRUE")
    ontology.add_fact("humano", "é", "mortal", "TRUE")
    ontology.add_fact("Sócrates", "é", "mortal", "TRUE")
    ontology.add_fact("gato", "é", "animal", "TRUE")
    ontology.add_fact("animal", "precisa", "comida", "TRUE")
    return ontology


def create_medical_ontology() -> KnowledgeOntology:
    """Cria uma ontologia médica básica para demonstração."""

    ontology = KnowledgeOntology()
    ontology.add_fact("febre", "indica", "infecção", [0.7, 0.2, 0.1])
    ontology.add_fact("tosse", "indica", "gripe", [0.6, 0.3, 0.1])
    ontology.add_fact("dor_cabeça", "indica", "enxaqueca", [0.5, 0.3, 0.2])
    ontology.add_fact("gripe", "causa", "febre", [0.8, 0.1, 0.1])
    ontology.add_fact("gripe", "causa", "tosse", [0.9, 0.05, 0.05])
    ontology.add_fact("paracetamol", "trata", "febre", [0.8, 0.1, 0.1])
    ontology.add_fact("repouso", "ajuda", "gripe", [0.7, 0.2, 0.1])
    return ontology


__all__ = [
    "KnowledgeOntology",
    "Fact",
    "InMemoryStore",
    "Neo4jStore",
    "create_simple_ontology",
    "create_medical_ontology",
]
