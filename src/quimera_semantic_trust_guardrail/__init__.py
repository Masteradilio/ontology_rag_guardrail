"""
Quimera Guardrails - Sistema Avançado de Proteção para Agentes de IA
=====================================================================

Módulo de guardrails baseado em lógica simbólica quântica (QGSL) para
validação de inputs e outputs de agentes de IA.

Capacidades:
- Input Shield: PII, Injection, Ética, Intenção maliciosa
- Output Validator: Relevância, Alucinações, Compliance, Consistência
- Ontologias por Tenant: Base de conhecimento customizável
- Compliance Engine: LGPD, HIPAA, SOX, PCI-DSS, GDPR
- Proof Ledger: Auditoria criptográfica de todas as decisões

Uso básico:
    from quimera_guardrails import QuimeraGuardrails
    
    guardrails = QuimeraGuardrails(tenant_id="meu_tenant")
    
    # Validar input
    input_result = await guardrails.shield_input(user_message)
    if not input_result.allowed:
        return {"error": input_result.reasoning}
    
    # ... processar com agente principal ...
    
    # Validar output
    output_result = await guardrails.validate_output(query, response)
    if output_result.should_retry:
        # retry com guidance
        pass

Autor: Projeto Quimera
Versão: 1.0.0
"""

__version__ = "1.0.0"
__author__ = "Projeto Quimera"

from .main import QuimeraGuardrails, GuardrailsConfig, create_guardrails
from .input_shield import QuimeraInputShield, ShieldResult, ThreatType
from .output_validator import (
    QuimeraOutputValidator, 
    ValidationResult, 
    ValidationIssue,
    IssueDetail,
    QualityMetrics,
)
from .tenant_ontology import TenantOntologyManager, OntologyEntry, Ontology, ClaimVerification, FactConfidence
from .compliance_engine import ComplianceEngine, ComplianceStandard, ComplianceViolation, ComplianceRule
from .proof_recorder import ProofRecorder, ProofEntry, ProofType
from .ontology_versioning import (
    OntologySnapshot,
    OntologyMigration,
    OntologyVersioningStore,
    diff_payloads,
)
from .qgsl_logic import QGSLState, LogicalQutrit, TruthValue
from .decision_model import (
    TrivalentDecision,
    RecommendedAction,
    DecisionStatus,
    EvidenceRecord,
    ContradictionRecord,
    MissingRequirement,
    ProofMetadata,
    SemanticTrustDecision,
    map_groundcite_label,
)
from .semantic_fact import (
    SemanticFactType,
    SemanticFactProvenance,
    SemanticFact,
    SemanticOntology,
    semantic_facts_from_ontology_entry,
    semantic_facts_from_ontology_entries,
)
from .runtime import SemanticTrustRuntime

# Adapters para bases de conhecimento externas
from .adapters import (
    KnowledgeAdapter,
    KnowledgeFact,
    FactCache,
    CustomFileSearchAdapter,
    SimpleKnowledgeAdapter,
    create_file_search_adapter,
    create_adapter_from_env,
    # Sincronização de Ontologia (auto-alimentação)
    OntologySync,
    FactExtractor,
    PatternBasedExtractor,
    LLMBasedExtractor,
    ExtractedFact,
    FactType,
    create_ontology_sync,
    # Legado (Google)
    GoogleFileSearchAdapter,
    create_knowledge_adapter,
    HAS_GOOGLE_ADAPTER,
)

__all__ = [
    # Principal
    "QuimeraGuardrails",
    "GuardrailsConfig",
    "create_guardrails",
    
    # Input Shield
    "QuimeraInputShield",
    "ShieldResult", 
    "ThreatType",
    
    # Output Validator
    "QuimeraOutputValidator",
    "ValidationResult",
    "ValidationIssue",
    "IssueDetail",
    "QualityMetrics",
    
    # Ontologia
    "TenantOntologyManager",
    "OntologyEntry",
    "Ontology",
    "ClaimVerification",
    "FactConfidence",
    
    # Compliance
    "ComplianceEngine",
    "ComplianceStandard",
    "ComplianceViolation",
    "ComplianceRule",
    
    # Auditoria
    "ProofRecorder",
    "ProofEntry",
    "ProofType",
    "OntologySnapshot",
    "OntologyMigration",
    "OntologyVersioningStore",
    "diff_payloads",
    
    # Lógica QGSL
    "QGSLState",
    "LogicalQutrit",
    "TruthValue",
    "TrivalentDecision",
    "RecommendedAction",
    "DecisionStatus",
    "EvidenceRecord",
    "ContradictionRecord",
    "MissingRequirement",
    "ProofMetadata",
    "SemanticTrustDecision",
    "map_groundcite_label",
    "SemanticFactType",
    "SemanticFactProvenance",
    "SemanticFact",
    "SemanticOntology",
    "semantic_facts_from_ontology_entry",
    "semantic_facts_from_ontology_entries",
    "SemanticTrustRuntime",
    
    # Adapters
    "KnowledgeAdapter",
    "KnowledgeFact",
    "FactCache",
    "CustomFileSearchAdapter",
    "SimpleKnowledgeAdapter",
    "create_file_search_adapter",
    "create_adapter_from_env",
    # Sincronização de Ontologia
    "OntologySync",
    "FactExtractor",
    "PatternBasedExtractor",
    "LLMBasedExtractor",
    "ExtractedFact",
    "FactType",
    "create_ontology_sync",
    # Legado (Google)
    "GoogleFileSearchAdapter",
    "create_knowledge_adapter",
    "HAS_GOOGLE_ADAPTER",
]
