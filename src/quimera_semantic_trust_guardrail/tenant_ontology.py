"""
Tenant Ontology Manager - Sistema de Ontologias por Cliente
============================================================

Permite que cada tenant tenha sua própria base de conhecimento
para validação de outputs contra fatos conhecidos.

Funcionalidades:
- CRUD de ontologias por tenant
- Verificação de claims contra base de conhecimento
- Detecção de alucinações
- Suporte a múltiplas ontologias por tenant (por domínio)
"""

from __future__ import annotations
import json
import hashlib
import time
from dataclasses import dataclass, field, asdict
from typing import Dict, Any, List, Optional, Set, Tuple
from pathlib import Path
from threading import RLock
from enum import Enum

from .decision_model import TrivalentDecision
from .semantic_fact import SemanticFact, SemanticFactType, SemanticFactProvenance
from .ontology_versioning import (
    OntologyMigration,
    OntologySnapshot,
    OntologyVersioningStore,
)


class FactConfidence(Enum):
    """Nível de confiança em um fato"""
    VERIFIED = "verified"       # Verificado por fonte confiável
    PROBABLE = "probable"       # Altamente provável
    POSSIBLE = "possible"       # Possível mas incerto
    UNVERIFIED = "unverified"   # Não verificado


@dataclass
class OntologyEntry:
    """
    Entrada na ontologia
    
    Representa um conceito com suas definições, fatos
    relacionados e restrições.
    """
    concept: str
    definition: str
    related_concepts: List[str] = field(default_factory=list)
    facts: List[str] = field(default_factory=list)
    constraints: List[str] = field(default_factory=list)
    synonyms: List[str] = field(default_factory=list)
    source: str = "manual"
    confidence: FactConfidence = FactConfidence.UNVERIFIED
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    
    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["confidence"] = self.confidence.value
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> OntologyEntry:
        if "confidence" in data and isinstance(data["confidence"], str):
            data["confidence"] = FactConfidence(data["confidence"])
        return cls(**data)
    
    def matches_text(self, text: str) -> bool:
        """Verifica se o conceito ou sinônimos aparecem no texto"""
        text_lower = text.lower()
        if self.concept.lower() in text_lower:
            return True
        for syn in self.synonyms:
            if syn.lower() in text_lower:
                return True
        return False


@dataclass
class Ontology:
    """Ontologia completa de um domínio"""
    ontology_id: str
    tenant_id: str
    name: str
    domain: str
    description: str = ""
    entries: Dict[str, OntologyEntry] = field(default_factory=dict)
    semantic_facts: List[SemanticFact] = field(default_factory=list)
    version: int = 1
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "ontology_id": self.ontology_id,
            "tenant_id": self.tenant_id,
            "name": self.name,
            "domain": self.domain,
            "description": self.description,
            "entries": {k: v.to_dict() for k, v in self.entries.items()},
            "semantic_facts": [f.model_dump(mode="json") for f in self.semantic_facts],
            "version": self.version,
            "created_at": self.created_at,
            "updated_at": self.updated_at
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Ontology:
        entries = {}
        for k, v in data.get("entries", {}).items():
            entries[k] = OntologyEntry.from_dict(v)

        semantic_facts = [
            SemanticFact.model_validate(f)
            for f in data.get("semantic_facts", [])
        ]
        
        return cls(
            ontology_id=data["ontology_id"],
            tenant_id=data["tenant_id"],
            name=data["name"],
            domain=data["domain"],
            description=data.get("description", ""),
            entries=entries,
            semantic_facts=semantic_facts,
            version=data.get("version", 1),
            created_at=data.get("created_at", time.time()),
            updated_at=data.get("updated_at", time.time())
        )


@dataclass
class ClaimVerification:
    """Resultado da verificação de um claim"""
    claim: str
    verified: Optional[bool]  # None = UNDECIDABLE
    confidence: float
    supporting_facts: List[Dict[str, Any]] = field(default_factory=list)
    contradicting_facts: List[Dict[str, Any]] = field(default_factory=list)
    relevant_concepts: List[str] = field(default_factory=list)
    reasoning: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "claim": self.claim,
            "verified": self.verified,
            "confidence": self.confidence,
            "supporting_facts": self.supporting_facts,
            "contradicting_facts": self.contradicting_facts,
            "relevant_concepts": self.relevant_concepts,
            "reasoning": self.reasoning
        }


class TenantOntologyManager:
    """
    Gerenciador de Ontologias por Tenant
    
    Permite criar, gerenciar e consultar bases de conhecimento
    específicas para cada cliente do SaaS.
    
    Uso:
        manager = TenantOntologyManager()
        
        # Criar ontologia
        ont_id = manager.create_ontology(
            tenant_id="tenant_123",
            name="Produtos",
            domain="e-commerce"
        )
        
        # Adicionar conhecimento
        manager.add_entry(
            tenant_id="tenant_123",
            ontology_id=ont_id,
            entry=OntologyEntry(
                concept="iPhone 15",
                definition="Smartphone da Apple lançado em 2023",
                facts=["Tem chip A17 Pro", "Disponível com 128GB, 256GB ou 512GB"],
                constraints=["Não existe modelo com 1TB"]
            )
        )
        
        # Verificar claim
        result = manager.verify_claim(
            tenant_id="tenant_123",
            ontology_id=ont_id,
            claim="O iPhone 15 tem 1TB de armazenamento"
        )
        # result.verified = False (contradiz constraint)
    """
    
    def __init__(self, storage_path: str = ".quimera_ontologies"):
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)
        self.cache_path = Path(".quimera_ontology_cache")
        self.cache_path.mkdir(parents=True, exist_ok=True)
        self._cache: Dict[str, Ontology] = {}
        self._lock = RLock()
        self.versioning_store = OntologyVersioningStore(self.storage_path)
    
    def create_ontology(
        self,
        tenant_id: str,
        name: str,
        domain: str,
        description: str = "",
        initial_entries: Optional[List[OntologyEntry]] = None
    ) -> str:
        """
        Cria nova ontologia para um tenant
        
        Returns:
            ID da ontologia criada
        """
        with self._lock:
            # Gera ID único
            ontology_id = hashlib.sha256(
                f"{tenant_id}:{name}:{domain}:{time.time()}".encode()
            ).hexdigest()[:16]
            
            ontology = Ontology(
                ontology_id=ontology_id,
                tenant_id=tenant_id,
                name=name,
                domain=domain,
                description=description
            )
            
            if initial_entries:
                for entry in initial_entries:
                    ontology.entries[entry.concept.lower()] = entry
            
            self._save_ontology(ontology)
            self._cache[self._cache_key(tenant_id, ontology_id)] = ontology
            
            return ontology_id
    
    def get_ontology(
        self,
        tenant_id: str,
        ontology_id: str
    ) -> Optional[Ontology]:
        """Retorna ontologia se existir"""
        cache_key = self._cache_key(tenant_id, ontology_id)
        
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        ontology = self._load_ontology(tenant_id, ontology_id)
        if ontology:
            self._cache[cache_key] = ontology
        
        return ontology
    
    def list_ontologies(self, tenant_id: str) -> List[Dict[str, Any]]:
        """Lista todas as ontologias de um tenant"""
        tenant_path = self.storage_path / tenant_id
        if not tenant_path.exists():
            return []
        
        ontologies = []
        for file_path in tenant_path.glob("*.json"):
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    ontologies.append({
                        "ontology_id": data["ontology_id"],
                        "name": data["name"],
                        "domain": data["domain"],
                        "description": data.get("description", ""),
                        "entries_count": len(data.get("entries", {})),
                        "version": data.get("version", 1),
                        "updated_at": data.get("updated_at")
                    })
            except Exception:
                continue
        
        return ontologies
    
    def add_entry(
        self,
        tenant_id: str,
        ontology_id: str,
        entry: OntologyEntry
    ) -> bool:
        """Adiciona entrada à ontologia"""
        with self._lock:
            ontology = self.get_ontology(tenant_id, ontology_id)
            if not ontology:
                return False
            
            entry.updated_at = time.time()
            ontology.entries[entry.concept.lower()] = entry
            ontology.version += 1
            ontology.updated_at = time.time()
            
            self._save_ontology(ontology)
            return True

    def add_fact(
        self,
        tenant_id: str,
        ontology_id: str,
        fact: SemanticFact | str,
        fact_type: str | SemanticFactType = SemanticFactType.FACT,
        subject: Optional[str] = None,
        relation: Optional[str] = None,
        source: Optional[str] = None,
        confidence: float = 1.0,
        metadata: Optional[Dict[str, Any]] = None,
        state: str | TrivalentDecision = TrivalentDecision.TRUE,
        source_document: Optional[str] = None,
        source_chunk: Optional[str] = None,
        source_uri: Optional[str] = None,
        extractor: Optional[str] = None,
        *,
        proof_id: Optional[str] = None,
    ) -> bool:
        """Adds a unified semantic fact to an ontology."""
        with self._lock:
            ontology = self.get_ontology(tenant_id, ontology_id)
            if not ontology:
                return False

            if isinstance(fact, SemanticFact):
                semantic_fact = fact.model_copy(
                    update={
                        "tenant_id": tenant_id,
                        "ontology_id": ontology_id,
                        "ontology_version": str(ontology.version),
                    }
                )
            else:
                semantic_fact = SemanticFact(
                    subject=subject or self._infer_subject(str(fact), fact_type),
                    relation=relation or self._default_relation(fact_type),
                    object=str(fact),
                    fact_type=SemanticFactType(
                        fact_type.value if isinstance(fact_type, SemanticFactType) else fact_type
                    ),
                    state=state if isinstance(state, TrivalentDecision) else TrivalentDecision(str(state).upper()),
                    source=source,
                    confidence=confidence,
                    tenant_id=tenant_id,
                    ontology_id=ontology_id,
                    ontology_version=str(ontology.version),
                    provenance=SemanticFactProvenance(
                        source=source,
                        document_id=source_document,
                        chunk_id=source_chunk,
                        source_uri=source_uri,
                        extractor=extractor,
                        metadata=metadata or {},
                    ),
                    metadata=metadata or {},
                )

            duplicate = self._find_semantic_fact(
                ontology,
                semantic_fact.subject,
                semantic_fact.relation,
                semantic_fact.object,
            )
            previous_version = int(ontology.version)
            added = True
            if duplicate and duplicate.state == semantic_fact.state:
                added = False
            elif duplicate and duplicate.state != semantic_fact.state:
                duplicate.metadata["conflict_detected"] = True
                duplicate.metadata["conflicts_with_state"] = semantic_fact.state.value
                semantic_fact.metadata["conflict_detected"] = True
                semantic_fact.metadata["conflicts_with_state"] = duplicate.state.value
                ontology.semantic_facts.append(semantic_fact)
            else:
                ontology.semantic_facts.append(semantic_fact)

            if added:
                ontology.version += 1
                ontology.updated_at = time.time()
                self._save_ontology(ontology)
                self._cache[self._cache_key(tenant_id, ontology_id)] = ontology
                self.versioning_store.record_migration(
                    tenant_id=tenant_id,
                    ontology_id=ontology_id,
                    action="add_fact",
                    from_version=previous_version,
                    to_version=int(ontology.version),
                    proof_id=proof_id,
                    details={
                        "subject": semantic_fact.subject,
                        "relation": semantic_fact.relation,
                        "object": semantic_fact.object,
                        "fact_type": semantic_fact.fact_type.value,
                        "state": semantic_fact.state.value,
                    },
                )
            return added

    def list_facts(
        self,
        tenant_id: str,
        ontology_id: str,
        fact_type: Optional[str | SemanticFactType] = None,
    ) -> List[SemanticFact]:
        """Lists unified semantic facts for a tenant ontology."""
        ontology = self.get_ontology(tenant_id, ontology_id)
        if not ontology:
            return []
        if fact_type is None:
            return list(ontology.semantic_facts)
        target = SemanticFactType(
            fact_type.value if isinstance(fact_type, SemanticFactType) else fact_type
        )
        return [fact for fact in ontology.semantic_facts if fact.fact_type == target]
    
    def update_entry(
        self,
        tenant_id: str,
        ontology_id: str,
        concept: str,
        updates: Dict[str, Any]
    ) -> bool:
        """Atualiza entrada existente"""
        with self._lock:
            ontology = self.get_ontology(tenant_id, ontology_id)
            if not ontology:
                return False
            
            key = concept.lower()
            if key not in ontology.entries:
                return False
            
            entry = ontology.entries[key]
            for field, value in updates.items():
                if hasattr(entry, field):
                    setattr(entry, field, value)
            
            entry.updated_at = time.time()
            ontology.version += 1
            ontology.updated_at = time.time()
            
            self._save_ontology(ontology)
            return True
    
    def remove_entry(
        self,
        tenant_id: str,
        ontology_id: str,
        concept: str
    ) -> bool:
        """Remove entrada da ontologia"""
        with self._lock:
            ontology = self.get_ontology(tenant_id, ontology_id)
            if not ontology:
                return False
            
            key = concept.lower()
            if key not in ontology.entries:
                return False
            
            del ontology.entries[key]
            ontology.version += 1
            ontology.updated_at = time.time()
            
            self._save_ontology(ontology)
            return True
    
    def delete_ontology(self, tenant_id: str, ontology_id: str) -> bool:
        """Deleta ontologia completamente"""
        with self._lock:
            file_path = self.storage_path / tenant_id / f"{ontology_id}.json"
            if file_path.exists():
                file_path.unlink()
                cache_key = self._cache_key(tenant_id, ontology_id)
                if cache_key in self._cache:
                    del self._cache[cache_key]
                return True
            return False
    
    def verify_claim(
        self,
        tenant_id: str,
        ontology_id: str,
        claim: str
    ) -> ClaimVerification:
        """
        Verifica um claim contra a ontologia
        
        Retorna:
        - verified=True se suportado por fatos
        - verified=False se contradiz fatos/constraints
        - verified=None se indeterminado (UNDECIDABLE)
        """
        # Cache lookup
        cached = self._read_cache(tenant_id, ontology_id, claim)
        if cached:
            return cached

        ontology = self.get_ontology(tenant_id, ontology_id)
        if not ontology:
            result = ClaimVerification(
                claim=claim,
                verified=None,
                confidence=0.0,
                reasoning="Ontologia não encontrada"
            )
            self._write_cache(tenant_id, ontology_id, claim, result)
            return result
        
        claim_lower = claim.lower()
        supporting = []
        contradicting = []
        relevant_concepts = []
        
        for key, entry in ontology.entries.items():
            if not entry.matches_text(claim):
                continue
            
            relevant_concepts.append(entry.concept)
            
            # Verifica fatos de suporte
            for fact in entry.facts:
                similarity = self._calculate_similarity(claim_lower, fact.lower())
                if similarity > 0.5:
                    supporting.append({
                        "concept": entry.concept,
                        "fact": fact,
                        "similarity": similarity,
                        "confidence": entry.confidence.value
                    })
            
            # Verifica constraints que podem contradizer
            for constraint in entry.constraints:
                if self._contradicts(claim_lower, constraint.lower()):
                    contradicting.append({
                        "concept": entry.concept,
                        "constraint": constraint,
                        "confidence": entry.confidence.value
                    })
        
        # Determina resultado
        if contradicting:
            result = ClaimVerification(
                claim=claim,
                verified=False,
                confidence=0.8,
                supporting_facts=supporting,
                contradicting_facts=contradicting,
                relevant_concepts=relevant_concepts,
                reasoning=f"Claim contradiz {len(contradicting)} constraint(s)"
            )
            self._write_cache(tenant_id, ontology_id, claim, result)
            return result
        elif supporting:
            avg_similarity = sum(s["similarity"] for s in supporting) / len(supporting)
            result = ClaimVerification(
                claim=claim,
                verified=True,
                confidence=min(0.9, avg_similarity + 0.2),
                supporting_facts=supporting,
                contradicting_facts=[],
                relevant_concepts=relevant_concepts,
                reasoning=f"Claim suportado por {len(supporting)} fato(s)"
            )
            self._write_cache(tenant_id, ontology_id, claim, result)
            return result
        elif relevant_concepts:
            result = ClaimVerification(
                claim=claim,
                verified=None,
                confidence=0.3,
                supporting_facts=[],
                contradicting_facts=[],
                relevant_concepts=relevant_concepts,
                reasoning="Conceitos relacionados encontrados, mas sem fatos específicos"
            )
            self._write_cache(tenant_id, ontology_id, claim, result)
            return result
        else:
            result = ClaimVerification(
                claim=claim,
                verified=None,
                confidence=0.0,
                reasoning="Nenhum conceito relacionado na ontologia"
            )
            self._write_cache(tenant_id, ontology_id, claim, result)
            return result
    
    def find_hallucinations(
        self,
        tenant_id: str,
        ontology_id: str,
        text: str
    ) -> List[ClaimVerification]:
        """
        Analisa texto em busca de possíveis alucinações
        
        Extrai claims do texto e verifica cada um contra a ontologia.
        """
        # Extrai sentenças como claims
        sentences = [s.strip() for s in text.split(".") if s.strip()]
        
        hallucinations = []
        for sentence in sentences:
            if len(sentence) < 10:  # Ignora sentenças muito curtas
                continue
            
            result = self.verify_claim(tenant_id, ontology_id, sentence)
            
            # Se contradiz ou é indeterminado com conceitos relevantes
            if result.verified == False or (result.verified is None and result.relevant_concepts):
                hallucinations.append(result)
        
        return hallucinations
    
    def _calculate_similarity(self, text1: str, text2: str) -> float:
        """Calcula similaridade entre dois textos"""
        words1 = set(text1.split())
        words2 = set(text2.split())
        
        # Remove stop words comuns
        stop_words = {"o", "a", "os", "as", "um", "uma", "de", "da", "do", 
                      "em", "para", "com", "por", "que", "se", "é", "são",
                      "the", "is", "are", "a", "an", "of", "to", "in", "for"}
        
        words1 = words1 - stop_words
        words2 = words2 - stop_words
        
        if not words1 or not words2:
            return 0.0
        
        intersection = words1.intersection(words2)
        union = words1.union(words2)
        
        return len(intersection) / len(union)
    
    def _contradicts(self, claim: str, constraint: str) -> bool:
        """Verifica se claim contradiz constraint"""
        negations = ["não", "nunca", "impossível", "falso", "incorreto",
                     "não existe", "não há", "no", "not", "never", "impossible"]
        
        # Se constraint tem negação
        constraint_has_neg = any(neg in constraint for neg in negations)
        claim_has_neg = any(neg in claim for neg in negations)
        
        # Palavras em comum (sem negações)
        claim_words = set(claim.split()) - set(negations)
        constraint_words = set(constraint.split()) - set(negations)
        
        overlap = claim_words.intersection(constraint_words)
        
        # Se há overlap significativo e polaridades opostas
        if len(overlap) >= 2:
            if constraint_has_neg != claim_has_neg:
                return True
            # Se constraint é negativo e claim afirma o mesmo
            if constraint_has_neg and not claim_has_neg:
                return True
        
        return False

    def _infer_subject(self, fact: str, fact_type: str | SemanticFactType) -> str:
        normalized_type = fact_type.value if isinstance(fact_type, SemanticFactType) else str(fact_type)
        if ":" in fact:
            candidate = fact.split(":", 1)[0].strip()
            if candidate:
                return candidate
        if normalized_type == SemanticFactType.CONSTRAINT.value:
            return "constraint"
        if normalized_type == SemanticFactType.POLICY.value:
            return "policy"
        return "document_fact"

    def _default_relation(self, fact_type: str | SemanticFactType) -> str:
        normalized_type = fact_type.value if isinstance(fact_type, SemanticFactType) else str(fact_type)
        return {
            SemanticFactType.DEFINITION.value: "defined_as",
            SemanticFactType.CONSTRAINT.value: "constrained_by",
            SemanticFactType.POLICY.value: "governed_by",
            SemanticFactType.SYNONYM.value: "has_synonym",
            SemanticFactType.CONCEPT.value: "is_a",
        }.get(normalized_type, "has_fact")

    def _find_semantic_fact(
        self,
        ontology: Ontology,
        subject: str,
        relation: str,
        object_value: str,
    ) -> Optional[SemanticFact]:
        for fact in ontology.semantic_facts:
            if (
                fact.subject == subject
                and fact.relation == relation
                and fact.object == object_value
            ):
                return fact
        return None

    # ------------------------------------------------------------------
    # Versioning: snapshot, diff, rollback, and migration records
    # ------------------------------------------------------------------
    def snapshot_ontology(
        self,
        tenant_id: str,
        ontology_id: str,
        *,
        name: Optional[str] = None,
        parent_snapshot_id: Optional[str] = None,
        proof_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> OntologySnapshot:
        """Capture an immutable snapshot of a tenant ontology."""
        with self._lock:
            ontology = self.get_ontology(tenant_id, ontology_id)
            if ontology is None:
                raise FileNotFoundError(
                    f"Ontology {ontology_id!r} not found for tenant {tenant_id!r}"
                )
            snapshot = self.versioning_store.snapshot(
                ontology=ontology,
                name=name,
                parent_snapshot_id=parent_snapshot_id,
                proof_id=proof_id,
                metadata=metadata,
            )
            self.versioning_store.record_migration(
                tenant_id=tenant_id,
                ontology_id=ontology_id,
                action="snapshot",
                from_version=int(ontology.version),
                to_version=int(ontology.version),
                snapshot_id=snapshot.snapshot_id,
                proof_id=proof_id,
                details={"name": name, "path": snapshot.path},
            )
            return snapshot

    def list_ontology_snapshots(
        self, tenant_id: str, ontology_id: str
    ) -> List[OntologySnapshot]:
        return self.versioning_store.list_snapshots(tenant_id, ontology_id)

    def get_ontology_snapshot(
        self, tenant_id: str, ontology_id: str, snapshot_id: str
    ) -> Optional[OntologySnapshot]:
        return self.versioning_store.get_snapshot(tenant_id, ontology_id, snapshot_id)

    def diff_ontology(
        self,
        tenant_id: str,
        ontology_id: str,
        snapshot_id: str,
    ) -> Dict[str, Any]:
        """Return diff between an existing snapshot and the live ontology."""
        with self._lock:
            ontology = self.get_ontology(tenant_id, ontology_id)
            if ontology is None:
                raise FileNotFoundError(
                    f"Ontology {ontology_id!r} not found for tenant {tenant_id!r}"
                )
            return self.versioning_store.diff_snapshot_vs_live(
                tenant_id=tenant_id,
                ontology_id=ontology_id,
                snapshot_id=snapshot_id,
                ontology=ontology,
            )

    def rollback_ontology(
        self,
        tenant_id: str,
        ontology_id: str,
        snapshot_id: str,
        *,
        proof_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Roll back the live ontology to a captured snapshot."""
        with self._lock:
            return self.versioning_store.rollback_to_snapshot(
                manager=self,
                tenant_id=tenant_id,
                ontology_id=ontology_id,
                snapshot_id=snapshot_id,
                proof_id=proof_id,
            )

    def list_ontology_migrations(
        self, tenant_id: str, ontology_id: str
    ) -> List[OntologyMigration]:
        return self.versioning_store.list_migrations(tenant_id, ontology_id)
    
    def _cache_key(self, tenant_id: str, ontology_id: str) -> str:
        return f"{tenant_id}:{ontology_id}"
    
    def _save_ontology(self, ontology: Ontology):
        """Salva ontologia no storage"""
        tenant_path = self.storage_path / ontology.tenant_id
        tenant_path.mkdir(exist_ok=True)
        
        file_path = tenant_path / f"{ontology.ontology_id}.json"
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(ontology.to_dict(), f, indent=2, ensure_ascii=False)
    
    def _load_ontology(
        self,
        tenant_id: str,
        ontology_id: str
    ) -> Optional[Ontology]:
        """Carrega ontologia do storage"""
        file_path = self.storage_path / tenant_id / f"{ontology_id}.json"
        
        if not file_path.exists():
            return None
        
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return Ontology.from_dict(data)
        except Exception:
            return None

    def _read_cache(self, tenant_id: str, ontology_id: str, claim: str) -> Optional[ClaimVerification]:
        try:
            key = hashlib.sha256(f"{tenant_id}:{ontology_id}:{claim}".encode()).hexdigest()
            fp = self.cache_path / f"{tenant_id}_{ontology_id}_{key}.json"
            if not fp.exists():
                return None
            with open(fp, "r", encoding="utf-8") as f:
                data = json.load(f)
                return ClaimVerification(
                    claim=data.get("claim",""),
                    verified=data.get("verified"),
                    confidence=float(data.get("confidence",0.0)),
                    supporting_facts=data.get("supporting_facts",[]),
                    contradicting_facts=data.get("contradicting_facts",[]),
                    relevant_concepts=data.get("relevant_concepts",[]),
                    reasoning=data.get("reasoning",""),
                )
        except Exception:
            return None

    def _write_cache(self, tenant_id: str, ontology_id: str, claim: str, result: ClaimVerification):
        try:
            key = hashlib.sha256(f"{tenant_id}:{ontology_id}:{claim}".encode()).hexdigest()
            fp = self.cache_path / f"{tenant_id}_{ontology_id}_{key}.json"
            with open(fp, "w", encoding="utf-8") as f:
                json.dump(result.to_dict(), f, ensure_ascii=False, indent=2)
        except Exception:
            pass


# Ontologias pré-construídas para domínios comuns
def create_medical_ontology(manager: TenantOntologyManager, tenant_id: str) -> str:
    """Cria ontologia médica básica"""
    entries = [
        OntologyEntry(
            concept="diabetes",
            definition="Doença crônica que afeta como o corpo processa açúcar no sangue",
            facts=[
                "Diabetes tipo 1 é autoimune",
                "Diabetes tipo 2 é mais comum em adultos",
                "Tratamento pode incluir insulina e mudanças de estilo de vida"
            ],
            constraints=[
                "Diabetes não tem cura, apenas controle",
                "Não existe diabetes tipo 4"
            ],
            synonyms=["diabete", "diabetes mellitus"],
            confidence=FactConfidence.VERIFIED
        ),
        OntologyEntry(
            concept="hipertensão",
            definition="Pressão arterial cronicamente elevada",
            facts=[
                "Valores acima de 140/90 mmHg indicam hipertensão",
                "Pode ser controlada com medicamentos e estilo de vida"
            ],
            constraints=[
                "Hipertensão não causa sintomas imediatos em muitos casos"
            ],
            synonyms=["pressão alta", "HAS"],
            confidence=FactConfidence.VERIFIED
        )
    ]
    
    return manager.create_ontology(
        tenant_id=tenant_id,
        name="Conhecimento Médico Básico",
        domain="medical",
        description="Ontologia com conceitos médicos comuns",
        initial_entries=entries
    )


def create_financial_ontology(manager: TenantOntologyManager, tenant_id: str) -> str:
    """Cria ontologia financeira básica"""
    entries = [
        OntologyEntry(
            concept="renda fixa",
            definition="Investimentos com retorno previsível",
            facts=[
                "Inclui CDB, LCI, LCA, Tesouro Direto",
                "Geralmente mais seguro que renda variável"
            ],
            constraints=[
                "Não existe renda fixa sem risco",
                "Rentabilidade passada não garante futura"
            ],
            synonyms=["fixed income"],
            confidence=FactConfidence.VERIFIED
        ),
        OntologyEntry(
            concept="ações",
            definition="Participação no capital de empresas",
            facts=[
                "Negociadas em bolsa de valores",
                "Podem pagar dividendos"
            ],
            constraints=[
                "Ações não garantem retorno positivo",
                "Não é possível prever o mercado com certeza"
            ],
            synonyms=["stocks", "papéis"],
            confidence=FactConfidence.VERIFIED
        )
    ]
    
    return manager.create_ontology(
        tenant_id=tenant_id,
        name="Conhecimento Financeiro Básico",
        domain="financial",
        description="Ontologia com conceitos financeiros comuns",
        initial_entries=entries
    )
