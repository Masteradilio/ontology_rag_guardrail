"""
Proof Recorder - Sistema de Auditoria Criptográfica
====================================================

Registra todas as decisões do Quimera com:
- Hash criptográfico (SHA-256)
- Timestamp preciso
- Contexto completo
- Encadeamento de provas (blockchain-like)
"""

from __future__ import annotations
import hashlib
import json
import time
import os
from dataclasses import dataclass, field, asdict
from typing import Dict, Any, List, Optional
from pathlib import Path
from threading import Lock
from datetime import datetime
from enum import Enum


class ProofType(Enum):
    """Tipos de prova"""
    INPUT_SHIELD = "input_shield"
    OUTPUT_VALIDATION = "output_validation"
    COMPLIANCE_CHECK = "compliance_check"
    ONTOLOGY_VERIFICATION = "ontology_verification"
    CLAIM_CHECK = "claim_check"
    ANSWER_CHECK = "answer_check"
    ACTION_CHECK = "action_check"
    POLICY_CHECK = "policy_check"
    ONTOLOGY_SNAPSHOT = "ontology_snapshot"
    ONTOLOGY_ROLLBACK = "ontology_rollback"
    ONTOLOGY_MIGRATION = "ontology_migration"


@dataclass
class ProofEntry:
    """
    Entrada no ledger de provas

    Cada decisão do Quimera gera uma entrada imutável
    que pode ser auditada posteriormente.
    """

    # Identidade e proveniência
    proof_id: str
    proof_type: ProofType
    tenant_id: str
    timestamp: str
    timestamp_unix: float

    # Hashes de entrada
    input_hash: str

    # Resultado
    decision: str  # TRUE, FALSE, UNDECIDABLE
    confidence: float

    # Contexto (opcional)
    context_hash: Optional[str] = None

    # Detalhes
    threats_detected: List[str] = field(default_factory=list)
    issues_detected: List[str] = field(default_factory=list)

    # Encadeamento
    previous_proof_hash: Optional[str] = None
    entry_hash: str = ""

    # Phase 3: schema enriquecido para auditoria reprodutível
    ontology_id: Optional[str] = None
    ontology_version: Optional[str] = None
    policy_id: Optional[str] = None
    policy_version: Optional[str] = None
    ruleset_version: Optional[str] = None
    adapter_source: Optional[str] = None
    evidence_ids: List[str] = field(default_factory=list)
    policy_ids: List[str] = field(default_factory=list)
    decision_path: List[str] = field(default_factory=list)
    proof_status: str = "recorded"
    related_proof_id: Optional[str] = None

    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not self.entry_hash:
            self.entry_hash = self._calculate_hash()

    def _calculate_hash(self) -> str:
        """Calcula hash da entrada para integridade"""
        data = {
            "proof_id": self.proof_id,
            "proof_type": self.proof_type.value if isinstance(self.proof_type, ProofType) else self.proof_type,
            "tenant_id": self.tenant_id,
            "timestamp_unix": self.timestamp_unix,
            "input_hash": self.input_hash,
            "decision": self.decision,
            "confidence": self.confidence,
            "previous_proof_hash": self.previous_proof_hash,
            "ontology_id": self.ontology_id,
            "ontology_version": self.ontology_version,
            "policy_id": self.policy_id,
            "policy_version": self.policy_version,
            "ruleset_version": self.ruleset_version,
            "adapter_source": self.adapter_source,
            "evidence_ids": list(self.evidence_ids),
            "policy_ids": list(self.policy_ids),
            "decision_path": list(self.decision_path),
            "proof_status": self.proof_status,
            "related_proof_id": self.related_proof_id,
        }
        data_str = json.dumps(data, sort_keys=True)
        return hashlib.sha256(data_str.encode()).hexdigest()
    
    def verify_integrity(self) -> bool:
        """Verifica se a entrada não foi alterada"""
        return self.entry_hash == self._calculate_hash()
    
    def to_dict(self) -> Dict[str, Any]:
        """Converte para dicionário"""
        data = asdict(self)
        if isinstance(self.proof_type, ProofType):
            data["proof_type"] = self.proof_type.value
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ProofEntry:
        """Cria entrada a partir de dicionário"""
        if isinstance(data.get("proof_type"), str):
            data["proof_type"] = ProofType(data["proof_type"])
        return cls(**data)


class ProofRecorder:
    """
    Gravador de provas com armazenamento persistente
    
    Características:
    - Thread-safe
    - Encadeamento de hashes (blockchain-like)
    - Verificação de integridade
    - Busca por tenant/tipo/período
    """
    
    def __init__(
        self,
        storage_path: str = ".quimera_proofs",
        enable_chain: bool = True
    ):
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)
        self.enable_chain = enable_chain
        self._lock = Lock()
        self._last_hash: Optional[str] = None
        self._load_last_hash()
    
    def _load_last_hash(self):
        """Carrega último hash para encadeamento"""
        chain_file = self.storage_path / "chain_state.json"
        if chain_file.exists():
            try:
                with open(chain_file, "r") as f:
                    state = json.load(f)
                    self._last_hash = state.get("last_hash")
            except Exception:
                self._last_hash = None
    
    def _save_last_hash(self):
        """Salva último hash"""
        chain_file = self.storage_path / "chain_state.json"
        with open(chain_file, "w") as f:
            json.dump({"last_hash": self._last_hash}, f)
    
    def record(
        self,
        proof_type: ProofType,
        tenant_id: str,
        input_data: str,
        decision: str,
        confidence: float,
        threats: Optional[List[str]] = None,
        issues: Optional[List[str]] = None,
        context: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        *,
        ontology_id: Optional[str] = None,
        ontology_version: Optional[str] = None,
        policy_id: Optional[str] = None,
        policy_version: Optional[str] = None,
        ruleset_version: Optional[str] = None,
        adapter_source: Optional[str] = None,
        evidence_ids: Optional[List[str]] = None,
        policy_ids: Optional[List[str]] = None,
        decision_path: Optional[List[str]] = None,
        proof_status: str = "recorded",
        related_proof_id: Optional[str] = None,
    ) -> ProofEntry:
        """
        Registra uma decisão no ledger

        Args:
            proof_type: Tipo de prova (INPUT_SHIELD, OUTPUT_VALIDATION, etc)
            tenant_id: ID do tenant
            input_data: Dados de entrada (serão hasheados)
            decision: Decisão tomada (TRUE, FALSE, UNDECIDABLE)
            confidence: Confiança na decisão (0.0 a 1.0)
            threats: Lista de ameaças detectadas
            issues: Lista de problemas encontrados
            context: Contexto adicional (será hasheado)
            metadata: Metadados extras
            ontology_id: ID da ontologia usada na decisão
            ontology_version: Versão da ontologia usada na decisão
            policy_id: ID da policy principal avaliada
            policy_version: Versão do pacote de policies
            ruleset_version: Versão do ruleset de compliance
            adapter_source: Identificador do adapter de conhecimento
            evidence_ids: IDs de evidências que sustentaram a decisão
            policy_ids: IDs de policies consultadas
            decision_path: Passos de decisão executados
            proof_status: Estado do proof (recorded, rolled_back, etc.)
            related_proof_id: ID de prova relacionada (ex: proof de snapshot)

        Returns:
            ProofEntry com hash único
        """
        with self._lock:
            now = time.time()

            # Gera ID único
            proof_id = self._generate_proof_id(proof_type, tenant_id, now)

            # Calcula hashes
            input_hash = hashlib.sha256(input_data.encode()).hexdigest()[:32]
            context_hash = None
            if context:
                context_str = json.dumps(context, sort_keys=True, default=str)
                context_hash = hashlib.sha256(context_str.encode()).hexdigest()[:32]

            # Cria entrada
            entry = ProofEntry(
                proof_id=proof_id,
                proof_type=proof_type,
                tenant_id=tenant_id,
                timestamp=datetime.utcnow().isoformat() + "Z",
                timestamp_unix=now,
                input_hash=input_hash,
                context_hash=context_hash,
                decision=decision,
                confidence=confidence,
                threats_detected=threats or [],
                issues_detected=issues or [],
                previous_proof_hash=self._last_hash if self.enable_chain else None,
                ontology_id=ontology_id,
                ontology_version=ontology_version,
                policy_id=policy_id,
                policy_version=policy_version,
                ruleset_version=ruleset_version,
                adapter_source=adapter_source,
                evidence_ids=list(evidence_ids or []),
                policy_ids=list(policy_ids or []),
                decision_path=list(decision_path or []),
                proof_status=proof_status,
                related_proof_id=related_proof_id,
                metadata=metadata or {},
            )

            # Salva entrada
            self._save_entry(entry)

            # Atualiza chain
            if self.enable_chain:
                self._last_hash = entry.entry_hash
                self._save_last_hash()

            return entry
    
    def _generate_proof_id(
        self,
        proof_type: ProofType,
        tenant_id: str,
        timestamp: float
    ) -> str:
        """Gera ID único para prova"""
        prefix = {
            ProofType.INPUT_SHIELD: "QIS",
            ProofType.OUTPUT_VALIDATION: "QOV",
            ProofType.COMPLIANCE_CHECK: "QCC",
            ProofType.ONTOLOGY_VERIFICATION: "QON",
            ProofType.CLAIM_CHECK: "QCM",
            ProofType.ANSWER_CHECK: "QAN",
            ProofType.ACTION_CHECK: "QAC",
            ProofType.POLICY_CHECK: "QPL",
            ProofType.ONTOLOGY_SNAPSHOT: "QSN",
            ProofType.ONTOLOGY_ROLLBACK: "QRB",
            ProofType.ONTOLOGY_MIGRATION: "QMG",
        }.get(proof_type, "QPR")

        data = f"{tenant_id}:{timestamp}:{os.urandom(8).hex()}"
        hash_part = hashlib.sha256(data.encode()).hexdigest()[:16]

        return f"{prefix}-{hash_part}"
    
    def _save_entry(self, entry: ProofEntry):
        """Salva entrada no storage"""
        # Organiza por tenant e data
        date_str = datetime.utcnow().strftime("%Y-%m-%d")
        tenant_path = self.storage_path / entry.tenant_id / date_str
        tenant_path.mkdir(parents=True, exist_ok=True)
        
        # Arquivo JSONL por dia
        ledger_file = tenant_path / "proofs.jsonl"
        
        with open(ledger_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry.to_dict(), ensure_ascii=False) + "\n")
    
    def get_proof(self, proof_id: str) -> Optional[ProofEntry]:
        """Busca prova por ID"""
        # Busca em todos os tenants
        for tenant_dir in self.storage_path.iterdir():
            if not tenant_dir.is_dir() or tenant_dir.name.startswith("."):
                continue
            
            for date_dir in tenant_dir.iterdir():
                if not date_dir.is_dir():
                    continue
                
                ledger_file = date_dir / "proofs.jsonl"
                if not ledger_file.exists():
                    continue
                
                with open(ledger_file, "r", encoding="utf-8") as f:
                    for line in f:
                        if proof_id in line:
                            data = json.loads(line)
                            if data.get("proof_id") == proof_id:
                                return ProofEntry.from_dict(data)
        
        return None
    
    def get_tenant_proofs(
        self,
        tenant_id: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        proof_type: Optional[ProofType] = None,
        limit: int = 100
    ) -> List[ProofEntry]:
        """
        Busca provas de um tenant
        
        Args:
            tenant_id: ID do tenant
            start_date: Data inicial (YYYY-MM-DD)
            end_date: Data final (YYYY-MM-DD)
            proof_type: Filtrar por tipo
            limit: Máximo de resultados
        """
        tenant_path = self.storage_path / tenant_id
        if not tenant_path.exists():
            return []
        
        entries = []
        
        for date_dir in sorted(tenant_path.iterdir(), reverse=True):
            if not date_dir.is_dir():
                continue
            
            date_str = date_dir.name
            
            # Filtro de data
            if start_date and date_str < start_date:
                continue
            if end_date and date_str > end_date:
                continue
            
            ledger_file = date_dir / "proofs.jsonl"
            if not ledger_file.exists():
                continue
            
            with open(ledger_file, "r", encoding="utf-8") as f:
                for line in f:
                    if len(entries) >= limit:
                        break
                    
                    data = json.loads(line)
                    
                    # Filtro de tipo
                    if proof_type:
                        if data.get("proof_type") != proof_type.value:
                            continue
                    
                    entries.append(ProofEntry.from_dict(data))
            
            if len(entries) >= limit:
                break
        
        return entries
    
    def verify_chain(self, tenant_id: str) -> Dict[str, Any]:
        """
        Verifica integridade da chain de provas de um tenant

        Returns:
            Relatório de verificação
        """
        proofs = self.get_tenant_proofs(tenant_id, limit=10000)

        if not proofs:
            return {
                "valid": True,
                "message": "Nenhuma prova encontrada",
                "total_proofs": 0
            }

        # Ordena por timestamp
        proofs.sort(key=lambda p: p.timestamp_unix)

        invalid_entries = []
        broken_chain = []

        prev_hash = None
        for proof in proofs:
            # Verifica integridade da entrada
            if not proof.verify_integrity():
                invalid_entries.append(proof.proof_id)

            # Verifica encadeamento
            if prev_hash and proof.previous_proof_hash != prev_hash:
                broken_chain.append(proof.proof_id)

            prev_hash = proof.entry_hash

        return {
            "valid": len(invalid_entries) == 0 and len(broken_chain) == 0,
            "total_proofs": len(proofs),
            "invalid_entries": invalid_entries,
            "broken_chain_at": broken_chain,
            "first_proof": proofs[0].proof_id if proofs else None,
            "last_proof": proofs[-1].proof_id if proofs else None
        }

    def lookup_proof(self, proof_id: str) -> Optional[ProofEntry]:
        """Public lookup API by proof id. Returns the entry or None."""
        return self.get_proof(proof_id)

    def list_tenant_proofs_with_provenance(
        self,
        tenant_id: str,
        *,
        ontology_id: Optional[str] = None,
        proof_type: Optional[ProofType] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: int = 200,
    ) -> List[ProofEntry]:
        """List proofs filtered by ontology and type, returning the enriched entries."""
        entries = self.get_tenant_proofs(
            tenant_id=tenant_id,
            start_date=start_date,
            end_date=end_date,
            proof_type=proof_type,
            limit=limit,
        )
        if ontology_id is None:
            return entries
        return [entry for entry in entries if entry.ontology_id == ontology_id]

    def get_statistics(self, tenant_id: str) -> Dict[str, Any]:
        """Retorna estatísticas de provas do tenant"""
        proofs = self.get_tenant_proofs(tenant_id, limit=10000)

        if not proofs:
            return {"total": 0}

        stats = {
            "total": len(proofs),
            "by_type": {},
            "by_decision": {},
            "avg_confidence": 0.0,
            "threats_detected": 0,
            "issues_detected": 0,
            "by_ontology": {},
            "by_adapter": {},
        }

        total_confidence = 0.0

        for proof in proofs:
            # Por tipo
            ptype = proof.proof_type.value if isinstance(proof.proof_type, ProofType) else proof.proof_type
            stats["by_type"][ptype] = stats["by_type"].get(ptype, 0) + 1

            # Por decisão
            stats["by_decision"][proof.decision] = stats["by_decision"].get(proof.decision, 0) + 1

            # Confidence
            total_confidence += proof.confidence

            # Contadores
            stats["threats_detected"] += len(proof.threats_detected)
            stats["issues_detected"] += len(proof.issues_detected)

            # Distribuição por ontologia
            if proof.ontology_id:
                stats["by_ontology"][proof.ontology_id] = (
                    stats["by_ontology"].get(proof.ontology_id, 0) + 1
                )
            if proof.adapter_source:
                stats["by_adapter"][proof.adapter_source] = (
                    stats["by_adapter"].get(proof.adapter_source, 0) + 1
                )

        stats["avg_confidence"] = total_confidence / len(proofs)

        return stats
