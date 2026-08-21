"""
Quimera Guardrails - Classe Principal de Integração
====================================================

Esta é a classe principal que unifica Input Shield e Output Validator
para fácil integração com orquestradores de agentes.

Uso simplificado:
    from quimera_guardrails import QuimeraGuardrails
    
    guardrails = QuimeraGuardrails(tenant_id="meu_tenant")
    
    # Validar input antes do agente
    input_result = await guardrails.shield_input(user_message)
    
    # Validar output depois do agente
    output_result = await guardrails.validate_output(query, response)
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, Any, List, Optional

from .input_shield import QuimeraInputShield, ShieldResult
from .output_validator import QuimeraOutputValidator, ValidationResult
from .tenant_ontology import TenantOntologyManager, OntologyEntry
from .compliance_engine import ComplianceEngine, ComplianceStandard
from .proof_recorder import ProofRecorder
from .runtime import SemanticTrustRuntime


@dataclass
class GuardrailsConfig:
    """Configuração unificada dos guardrails"""
    # Input Shield
    pii_detection: bool = True
    injection_detection: bool = True
    inappropriate_content_detection: bool = True
    rate_limiting: bool = True
    rate_limit: int = 100  # requests/minute
    max_input_risk: float = 0.7
    
    # Output Validator
    relevance_check: bool = True
    hallucination_check: bool = True
    compliance_check: bool = True
    consistency_check: bool = True
    min_relevance_score: float = 0.6
    min_quality_score: float = 0.5
    
    # Geral
    generate_proofs: bool = True
    proof_storage_path: str = ".quimera_proofs"
    ontology_storage_path: str = ".quimera_ontologies"
    
    def to_input_config(self) -> Dict[str, Any]:
        """Converte para config do Input Shield"""
        return {
            "max_risk_threshold": self.max_input_risk,
            "pii_detection_enabled": self.pii_detection,
            "injection_detection_enabled": self.injection_detection,
            "inappropriate_content_enabled": self.inappropriate_content_detection,
            "rate_limiting_enabled": self.rate_limiting,
            "rate_limit": self.rate_limit,
            "encoding_attack_enabled": True,
            "technical_injection_enabled": True,
            "generate_proofs": self.generate_proofs,
            "undecidable_action": "allow_with_flag",
            "sanitize_pii": True
        }
    
    def to_output_config(self) -> Dict[str, Any]:
        """Converte para config do Output Validator"""
        return {
            "min_relevance_score": self.min_relevance_score,
            "min_overall_quality": self.min_quality_score,
            "relevance_check_enabled": self.relevance_check,
            "hallucination_check_enabled": self.hallucination_check,
            "compliance_check_enabled": self.compliance_check,
            "consistency_check_enabled": self.consistency_check,
            "completeness_check_enabled": True,
            "generate_proofs": self.generate_proofs,
            "max_retries": 3
        }


class QuimeraGuardrails:
    """
    Classe Principal de Integração - Quimera Guardrails
    
    Unifica Input Shield e Output Validator em uma única interface
    fácil de integrar com orquestradores de agentes.
    
    Arquitetura:
    
        User Input
             │
             ▼
        ┌─────────────────┐
        │  INPUT SHIELD   │ ◄── PII, Injection, Jailbreak, Intent
        └────────┬────────┘
                 │ (se permitido)
                 ▼
        ┌─────────────────┐
        │  AGENTE (seu)   │
        └────────┬────────┘
                 │
                 ▼
        ┌─────────────────┐
        │OUTPUT VALIDATOR │ ◄── Relevância, Alucinações, Compliance
        └────────┬────────┘
                 │
                 ▼
        ┌─────────────────┐
        │   PROOF LEDGER  │ ◄── Auditoria criptográfica
        └─────────────────┘
                 │
                 ▼
            User Output
    
    Uso:
        # Inicialização simples
        guardrails = QuimeraGuardrails(tenant_id="tenant_123")
        
        # Com configuração customizada
        config = GuardrailsConfig(
            compliance_standards=["LGPD", "HIPAA"],
            min_relevance_score=0.7
        )
        guardrails = QuimeraGuardrails(tenant_id="tenant_123", config=config)
        
        # Usar no fluxo do agente
        async def process_with_guardrails(user_message: str):
            # 1. Validar input
            input_result = await guardrails.shield_input(user_message)
            if not input_result.allowed:
                return {"error": input_result.reasoning}
            
            # 2. Processar com seu agente
            agent_response = await your_agent.process(user_message)
            
            # 3. Validar output
            output_result = await guardrails.validate_output(
                user_message, agent_response
            )
            
            if output_result.should_retry:
                # Retry com guidance
                agent_response = await your_agent.process(
                    user_message,
                    guidance=output_result.retry_guidance
                )
            
            return {"response": agent_response}
    """
    
    def __init__(
        self,
        tenant_id: str,
        config: Optional[GuardrailsConfig] = None,
        compliance_standards: Optional[List[str]] = None,
        ontology_id: Optional[str] = None,
        knowledge_adapter: Optional[Any] = None
    ):
        """
        Inicializa os guardrails
        
        Args:
            tenant_id: ID único do tenant (cliente do SaaS)
            config: Configuração customizada (opcional)
            compliance_standards: Lista de standards (ex: ["LGPD", "HIPAA"])
            ontology_id: ID da ontologia para validação de alucinações
        """
        self.tenant_id = tenant_id
        self.config = config or GuardrailsConfig()
        self.ontology_id = ontology_id
        self.knowledge_adapter = knowledge_adapter
        
        # Inicializa Proof Recorder
        self.proof_recorder = ProofRecorder(
            storage_path=self.config.proof_storage_path,
            enable_chain=True
        )
        
        # Inicializa Ontology Manager
        self.ontology_manager = TenantOntologyManager(
            storage_path=self.config.ontology_storage_path
        )
        
        # Inicializa Compliance Engine
        if compliance_standards:
            standards = [ComplianceStandard(s.lower()) for s in compliance_standards]
        else:
            standards = []
        
        self.compliance_engine = ComplianceEngine(
            enabled_standards=standards
        ) if standards else None
        
        # Inicializa Input Shield
        self.input_shield = QuimeraInputShield(
            tenant_id=tenant_id,
            config=self.config.to_input_config(),
            proof_recorder=self.proof_recorder
        )
        
        # Inicializa Output Validator
        self.output_validator = QuimeraOutputValidator(
            tenant_id=tenant_id,
            ontology_manager=self.ontology_manager if ontology_id else None,
            ontology_id=ontology_id,
            knowledge_adapter=knowledge_adapter,
            compliance_engine=self.compliance_engine,
            proof_recorder=self.proof_recorder,
            config=self.config.to_output_config()
        )

        self.semantic_runtime = SemanticTrustRuntime(
            tenant_id=tenant_id,
            ontology_manager=self.ontology_manager,
            ontology_id=ontology_id,
            knowledge_adapter=knowledge_adapter,
            compliance_engine=self.compliance_engine,
            proof_recorder=self.proof_recorder,
        )
    
    async def shield_input(
        self,
        input_text: str,
        context: Optional[Dict[str, Any]] = None,
        user_id: Optional[str] = None
    ) -> ShieldResult:
        """
        Valida input antes de enviar ao agente
        
        Esta é a PRIMEIRA linha de defesa. Bloqueia:
        - PII expostos
        - Tentativas de prompt injection
        - Jailbreak attempts
        - Conteúdo impróprio
        - Rate abuse
        
        Args:
            input_text: Mensagem do usuário
            context: Contexto adicional (histórico, etc)
            user_id: ID do usuário para rate limiting
            
        Returns:
            ShieldResult com decisão e detalhes
            
        Exemplo:
            result = await guardrails.shield_input("Meu CPF é 123.456.789-00")
            
            if not result.allowed:
                return {"error": result.reasoning}
            
            # Se sanitizado, usar versão limpa
            clean_input = result.sanitized_input or input_text
        """
        return await self.input_shield.analyze(input_text, context, user_id)
    
    async def validate_output(
        self,
        original_query: str,
        agent_response: str,
        context: Optional[Dict[str, Any]] = None,
        expected_topics: Optional[List[str]] = None
    ) -> ValidationResult:
        """
        Valida output do agente antes de entregar ao usuário
        
        Esta é a SEGUNDA linha de defesa. Verifica:
        - Relevância à pergunta original
        - Possíveis alucinações
        - Compliance regulatório
        - Consistência interna
        - Qualidade da resposta
        
        Args:
            original_query: Pergunta original do usuário
            agent_response: Resposta gerada pelo agente
            context: Contexto adicional
            expected_topics: Tópicos esperados na resposta
            
        Returns:
            ValidationResult com avaliação e guidance para retry
            
        Exemplo:
            result = await guardrails.validate_output(
                "Qual o prazo de entrega?",
                "O tempo está bom hoje."
            )
            
            if result.should_retry:
                # Pedir ao agente para refazer
                new_response = await agent.process(
                    query,
                    guidance=result.retry_guidance
                )
        """
        return await self.output_validator.validate(
            original_query, agent_response, context, expected_topics
        )

    async def claim_check(self, claim: str, **kwargs):
        """Runtime API: validate one claim and return a trivalent decision."""
        return await self.semantic_runtime.claim_check(claim, **kwargs)

    async def answer_check(self, answer: str, **kwargs):
        """Runtime API: validate an answer by decomposing and checking claims."""
        return await self.semantic_runtime.answer_check(answer, **kwargs)

    async def action_check(self, **kwargs):
        """Runtime API: validate whether an agent action is authorized."""
        return await self.semantic_runtime.action_check(**kwargs)

    async def policy_check(self, text: str, **kwargs):
        """Runtime API: validate text or action context against policies."""
        return await self.semantic_runtime.policy_check(text, **kwargs)
    
    async def full_cycle(
        self,
        input_text: str,
        agent_response: str,
        context: Optional[Dict[str, Any]] = None,
        user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Executa ciclo completo de validação (input + output)
        
        Útil para validar uma interação completa de uma vez.
        
        Returns:
            {
                "input_result": ShieldResult,
                "output_result": ValidationResult,
                "overall_valid": bool,
                "proofs": [input_proof_id, output_proof_id]
            }
        """
        input_result = await self.shield_input(input_text, context, user_id)
        
        if not input_result.allowed:
            return {
                "input_result": input_result.to_dict(),
                "output_result": None,
                "overall_valid": False,
                "blocked_at": "input",
                "proofs": [input_result.proof_id]
            }
        
        output_result = await self.validate_output(input_text, agent_response, context)
        
        return {
            "input_result": input_result.to_dict(),
            "output_result": output_result.to_dict(),
            "overall_valid": input_result.allowed and output_result.is_valid,
            "blocked_at": None if output_result.is_valid else "output",
            "should_retry": output_result.should_retry,
            "retry_guidance": output_result.retry_guidance,
            "proofs": [input_result.proof_id, output_result.proof_id]
        }
    
    # =========== Métodos de Ontologia ===========
    
    def create_ontology(
        self,
        name: str,
        domain: str,
        description: str = "",
        initial_entries: Optional[List[OntologyEntry]] = None
    ) -> str:
        """
        Cria ontologia para o tenant
        
        A ontologia é usada para detectar alucinações.
        
        Returns:
            ID da ontologia criada
        """
        ontology_id = self.ontology_manager.create_ontology(
            tenant_id=self.tenant_id,
            name=name,
            domain=domain,
            description=description,
            initial_entries=initial_entries
        )
        
        # Atualiza validator com nova ontologia
        self.ontology_id = ontology_id
        self.output_validator.ontology_id = ontology_id
        self.output_validator.ontology_manager = self.ontology_manager
        self.semantic_runtime.ontology_id = ontology_id
        self.semantic_runtime.ontology_manager = self.ontology_manager
        
        return ontology_id
    
    def add_knowledge(
        self,
        concept: str,
        definition: str,
        facts: Optional[List[str]] = None,
        constraints: Optional[List[str]] = None
    ) -> bool:
        """
        Adiciona conhecimento à ontologia ativa
        
        Args:
            concept: Nome do conceito
            definition: Definição do conceito
            facts: Lista de fatos verdadeiros
            constraints: Lista de restrições (o que NÃO é verdade)
            
        Returns:
            True se adicionado com sucesso
        """
        if not self.ontology_id:
            raise ValueError("Nenhuma ontologia ativa. Crie uma primeiro.")
        
        entry = OntologyEntry(
            concept=concept,
            definition=definition,
            facts=facts or [],
            constraints=constraints or []
        )
        
        return self.ontology_manager.add_entry(
            self.tenant_id, self.ontology_id, entry
        )
    
    def list_ontologies(self) -> List[Dict[str, Any]]:
        """Lista todas as ontologias do tenant"""
        return self.ontology_manager.list_ontologies(self.tenant_id)
    
    def use_ontology(self, ontology_id: str) -> bool:
        """Define ontologia ativa para validação"""
        ontology = self.ontology_manager.get_ontology(self.tenant_id, ontology_id)
        if not ontology:
            return False
        
        self.ontology_id = ontology_id
        self.output_validator.ontology_id = ontology_id
        self.output_validator.ontology_manager = self.ontology_manager
        self.semantic_runtime.ontology_id = ontology_id
        self.semantic_runtime.ontology_manager = self.ontology_manager
        return True
    
    # =========== Métodos de Compliance ===========
    
    def add_compliance_standard(self, standard: str):
        """Adiciona padrão de compliance"""
        std = ComplianceStandard(standard.lower())
        
        if not self.compliance_engine:
            self.compliance_engine = ComplianceEngine(enabled_standards=[std])
            self.output_validator.compliance_engine = self.compliance_engine
            self.semantic_runtime.compliance_engine = self.compliance_engine
        else:
            self.compliance_engine.enabled_standards.add(std)
    
    def get_compliance_standards(self) -> List[str]:
        """Retorna standards de compliance ativos"""
        if not self.compliance_engine:
            return []
        return self.compliance_engine.get_enabled_standards()
    
    # =========== Métodos de Auditoria ===========

    def get_proof(self, proof_id: str) -> Optional[Dict[str, Any]]:
        """Busca uma prova específica"""
        entry = self.proof_recorder.get_proof(proof_id)
        return entry.to_dict() if entry else None

    def proof_lookup(self, proof_id: str) -> Optional[Dict[str, Any]]:
        """Public Phase 3 lookup API for a proof by id."""
        return self.get_proof(proof_id)

    def list_proofs_for_ontology(
        self,
        ontology_id: str,
        *,
        proof_type: Optional[Any] = None,
        limit: int = 200,
    ) -> List[Dict[str, Any]]:
        """Return enriched proofs that reference the given ontology."""
        entries = self.proof_recorder.list_tenant_proofs_with_provenance(
            tenant_id=self.tenant_id,
            ontology_id=ontology_id,
            proof_type=proof_type,
            limit=limit,
        )
        return [entry.to_dict() for entry in entries]

    def snapshot_ontology(
        self,
        ontology_id: Optional[str] = None,
        *,
        name: Optional[str] = None,
        proof_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Capture an immutable snapshot of the active (or given) tenant ontology."""
        target_id = ontology_id or self.ontology_id
        if not target_id:
            raise ValueError("No active ontology for the guardrails instance.")
        snapshot = self.ontology_manager.snapshot_ontology(
            self.tenant_id,
            target_id,
            name=name,
            proof_id=proof_id,
            metadata=metadata,
        )
        try:
            from .proof_recorder import ProofType
            proof_entry = self.proof_recorder.record(
                proof_type=ProofType.ONTOLOGY_SNAPSHOT,
                tenant_id=self.tenant_id,
                input_data=snapshot.snapshot_id,
                decision="TRUE",
                confidence=1.0,
                metadata={
                    "snapshot_id": snapshot.snapshot_id,
                    "snapshot_name": snapshot.name,
                    "ontology_version": str(snapshot.ontology_version),
                    "fact_count": snapshot.fact_count,
                    "entry_count": snapshot.entry_count,
                },
                ontology_id=target_id,
                ontology_version=str(snapshot.ontology_version),
                evidence_ids=[],
                policy_ids=[],
                decision_path=[
                    "ontology:snapshot",
                    f"ontology_version:{snapshot.ontology_version}",
                ],
                related_proof_id=proof_id,
            )
            snapshot_proof_id = proof_entry.proof_id
        except Exception:
            snapshot_proof_id = proof_id
        result = snapshot.to_dict()
        result["proof_id"] = snapshot_proof_id
        return result

    def rollback_ontology(
        self,
        snapshot_id: str,
        ontology_id: Optional[str] = None,
        *,
        proof_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Roll back the active (or given) ontology to a captured snapshot."""
        target_id = ontology_id or self.ontology_id
        if not target_id:
            raise ValueError("No active ontology for the guardrails instance.")
        rollback_result = self.ontology_manager.rollback_ontology(
            self.tenant_id,
            target_id,
            snapshot_id,
            proof_id=proof_id,
        )
        try:
            from .proof_recorder import ProofType
            proof_entry = self.proof_recorder.record(
                proof_type=ProofType.ONTOLOGY_ROLLBACK,
                tenant_id=self.tenant_id,
                input_data=snapshot_id,
                decision="TRUE",
                confidence=1.0,
                metadata={
                    "snapshot_id": snapshot_id,
                    "from_version": rollback_result.get("from_version"),
                    "to_version": rollback_result.get("to_version"),
                    "fact_count": rollback_result.get("fact_count"),
                    "entry_count": rollback_result.get("entry_count"),
                },
                ontology_id=target_id,
                ontology_version=str(rollback_result.get("to_version")),
                evidence_ids=[],
                policy_ids=[],
                decision_path=[
                    "ontology:rollback",
                    f"snapshot:{snapshot_id}",
                ],
                related_proof_id=proof_id,
            )
            rollback_proof_id = proof_entry.proof_id
        except Exception:
            rollback_proof_id = proof_id
        rollback_result["proof_id"] = rollback_proof_id
        return rollback_result

    def diff_ontology(
        self,
        snapshot_id: str,
        ontology_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Diff between a snapshot and the live ontology for the active tenant."""
        target_id = ontology_id or self.ontology_id
        if not target_id:
            raise ValueError("No active ontology for the guardrails instance.")
        return self.ontology_manager.diff_ontology(
            self.tenant_id,
            target_id,
            snapshot_id,
        )

    def list_ontology_snapshots(
        self, ontology_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        target_id = ontology_id or self.ontology_id
        if not target_id:
            return []
        return [
            snap.to_dict()
            for snap in self.ontology_manager.list_ontology_snapshots(
                self.tenant_id, target_id
            )
        ]

    def list_ontology_migrations(
        self, ontology_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        target_id = ontology_id or self.ontology_id
        if not target_id:
            return []
        return [
            mig.to_dict()
            for mig in self.ontology_manager.list_ontology_migrations(
                self.tenant_id, target_id
            )
        ]
    
    def get_audit_log(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Retorna log de auditoria do tenant
        
        Args:
            start_date: Data inicial (YYYY-MM-DD)
            end_date: Data final (YYYY-MM-DD)
            limit: Máximo de entradas
        """
        entries = self.proof_recorder.get_tenant_proofs(
            self.tenant_id, start_date, end_date, limit=limit
        )
        return [e.to_dict() for e in entries]
    
    def verify_audit_chain(self) -> Dict[str, Any]:
        """Verifica integridade da chain de auditoria"""
        return self.proof_recorder.verify_chain(self.tenant_id)
    
    def get_statistics(self) -> Dict[str, Any]:
        """Retorna estatísticas completas do tenant"""
        proof_stats = self.proof_recorder.get_statistics(self.tenant_id)
        
        return {
            "tenant_id": self.tenant_id,
            "ontology_id": self.ontology_id,
            "compliance_standards": self.get_compliance_standards(),
            "ontologies_count": len(self.list_ontologies()),
            "proof_statistics": proof_stats,
            "input_shield_stats": self.input_shield.get_statistics(),
            "output_validator_stats": self.output_validator.get_statistics(),
            "has_knowledge_adapter": self.knowledge_adapter is not None
        }


# Função helper para criar guardrails rapidamente
def create_guardrails(
    tenant_id: str,
    compliance: Optional[List[str]] = None,
    ontology_name: Optional[str] = None,
    knowledge_adapter: Optional[Any] = None,
    **config_kwargs
) -> QuimeraGuardrails:
    """
    Factory function para criar guardrails rapidamente
    
    Args:
        tenant_id: ID do tenant
        compliance: Lista de standards (ex: ["LGPD", "HIPAA"])
        ontology_name: Nome da ontologia inicial (opcional)
        **config_kwargs: Parâmetros adicionais de configuração
        
    Returns:
        QuimeraGuardrails configurado
        
    Exemplo:
        # Guardrails básico
        g = create_guardrails("meu_tenant")
        
        # Com compliance
        g = create_guardrails("meu_tenant", compliance=["LGPD"])
        
        # Com ontologia
        g = create_guardrails(
            "meu_tenant",
            ontology_name="Produtos",
            min_relevance_score=0.8
        )
    """
    config = GuardrailsConfig(**config_kwargs)
    
    guardrails = QuimeraGuardrails(
        tenant_id=tenant_id,
        config=config,
        compliance_standards=compliance,
        knowledge_adapter=knowledge_adapter
    )
    
    if ontology_name:
        guardrails.create_ontology(
            name=ontology_name,
            domain="general",
            description=f"Ontologia {ontology_name}"
        )
    
    return guardrails
