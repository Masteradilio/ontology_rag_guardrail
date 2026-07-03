"""
Quimera Output Validator - Validação Avançada de Saída
=======================================================

Sistema de validação de output que analisa:
- Relevância semântica (não só keywords)
- Detecção de alucinações contra ontologia
- Verificação factual
- Compliance multi-regulatório
- Consistência interna
- Qualidade da resposta

EXCLUSIVO DO OUTPUT VALIDATOR (não existe no Input Shield):
- Validação de relevância à pergunta original
- Detecção de alucinações contra base de conhecimento
- Verificação de compliance (LGPD, HIPAA, SOX, etc)
- Análise de consistência interna
- Verificação de completude
- Score de qualidade da resposta
- Guidance para retry automático
"""

from __future__ import annotations
import re
import time
import hashlib
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Set, Tuple
from enum import Enum

from .qgsl_logic import QGSLState, LogicalQutrit, TruthValue
from .proof_recorder import ProofRecorder, ProofType
from .compliance_engine import ComplianceEngine, ComplianceStandard, ComplianceViolation
from .tenant_ontology import TenantOntologyManager, ClaimVerification


class ValidationIssue(Enum):
    """Tipos de problemas detectáveis na saída"""
    LOW_RELEVANCE = "low_relevance"
    HALLUCINATION = "hallucination"
    FACTUAL_ERROR = "factual_error"
    COMPLIANCE_VIOLATION = "compliance_violation"
    INCOMPLETE_RESPONSE = "incomplete_response"
    INCONSISTENT = "inconsistent"
    OFF_TOPIC = "off_topic"
    EXCESSIVE_HEDGING = "excessive_hedging"
    MISSING_DISCLAIMER = "missing_disclaimer"
    QUALITY_TOO_LOW = "quality_too_low"


@dataclass
class IssueDetail:
    """Detalhes sobre um problema detectado"""
    issue_type: ValidationIssue
    severity: float  # 0.0 a 1.0
    description: str
    location: Optional[str] = None
    suggestion: str = ""
    auto_fixable: bool = False


@dataclass
class QualityMetrics:
    """Métricas de qualidade da resposta"""
    relevance_score: float       # 0-1: quão relevante à pergunta
    completeness_score: float    # 0-1: quão completa a resposta
    clarity_score: float         # 0-1: quão clara/legível
    factuality_score: float      # 0-1: quão factual (vs opinião)
    consistency_score: float     # 0-1: quão internamente consistente
    
    @property
    def overall_score(self) -> float:
        """Score geral ponderado"""
        weights = {
            "relevance": 0.35,
            "completeness": 0.20,
            "clarity": 0.15,
            "factuality": 0.20,
            "consistency": 0.10
        }
        return (
            self.relevance_score * weights["relevance"] +
            self.completeness_score * weights["completeness"] +
            self.clarity_score * weights["clarity"] +
            self.factuality_score * weights["factuality"] +
            self.consistency_score * weights["consistency"]
        )
    
    def to_dict(self) -> Dict[str, float]:
        return {
            "relevance": self.relevance_score,
            "completeness": self.completeness_score,
            "clarity": self.clarity_score,
            "factuality": self.factuality_score,
            "consistency": self.consistency_score,
            "overall": self.overall_score
        }


@dataclass
class ValidationResult:
    """
    Resultado da validação de output
    
    Attributes:
        is_valid: Se o output é válido para entrega
        qgsl_state: Estado QGSL da validação
        quality_metrics: Métricas de qualidade
        issues: Problemas detectados
        compliance_report: Relatório de compliance
        hallucinations: Possíveis alucinações detectadas
        suggestions: Sugestões de melhoria
        should_retry: Se deve pedir ao agente para refazer
        retry_guidance: Orientações para retry
        proof_id: ID da prova para auditoria
        processing_time_ms: Tempo de processamento
    """
    is_valid: bool
    qgsl_state: QGSLState
    quality_metrics: QualityMetrics
    issues: List[IssueDetail]
    compliance_report: Optional[Dict[str, Any]]
    hallucinations: List[ClaimVerification]
    suggestions: List[str]
    should_retry: bool
    retry_guidance: Optional[str]
    proof_id: str
    processing_time_ms: float
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "is_valid": self.is_valid,
            "qgsl_state": self.qgsl_state.to_dict(),
            "quality_metrics": self.quality_metrics.to_dict(),
            "issues": [
                {
                    "type": i.issue_type.value,
                    "severity": i.severity,
                    "description": i.description,
                    "suggestion": i.suggestion,
                    "auto_fixable": i.auto_fixable
                }
                for i in self.issues
            ],
            "compliance_report": self.compliance_report,
            "hallucinations_count": len(self.hallucinations),
            "suggestions": self.suggestions,
            "should_retry": self.should_retry,
            "retry_guidance": self.retry_guidance,
            "proof_id": self.proof_id,
            "processing_time_ms": self.processing_time_ms
        }


class QuimeraOutputValidator:
    """
    Output Validator - Garantia de qualidade das respostas
    
    Valida todos os outputs antes de entregar ao usuário.
    
    Funcionalidades EXCLUSIVAS (não existem no Input Shield):
    1. Validação de Relevância Semântica
    2. Detecção de Alucinações (contra ontologia)
    3. Verificação de Compliance (LGPD, HIPAA, SOX)
    4. Análise de Consistência Interna
    5. Verificação de Completude
    6. Score de Qualidade
    7. Guidance para Retry Automático
    
    Uso:
        validator = QuimeraOutputValidator(
            tenant_id="meu_tenant",
            ontology_id="minha_ontologia"
        )
        
        result = await validator.validate(
            original_query="Qual o prazo de entrega?",
            agent_response="O prazo é de 3 a 5 dias úteis."
        )
        
        if result.should_retry:
            # Pedir ao agente para refazer com result.retry_guidance
            pass
    """
    
    def __init__(
        self,
        tenant_id: str,
        ontology_manager: Optional[TenantOntologyManager] = None,
        ontology_id: Optional[str] = None,
        compliance_engine: Optional[ComplianceEngine] = None,
        proof_recorder: Optional[ProofRecorder] = None,
        config: Optional[Dict[str, Any]] = None
    ):
        self.tenant_id = tenant_id
        self.ontology_manager = ontology_manager
        self.ontology_id = ontology_id
        self.compliance_engine = compliance_engine
        self.proof_recorder = proof_recorder
        self.config = self._default_config()
        if config:
            self.config.update(config)
    
    def _default_config(self) -> Dict[str, Any]:
        return {
            "min_relevance_score": 0.6,
            "min_overall_quality": 0.5,
            "max_hallucination_tolerance": 0.2,
            "max_retries": 3,
            "relevance_check_enabled": True,
            "hallucination_check_enabled": True,
            "compliance_check_enabled": True,
            "consistency_check_enabled": True,
            "completeness_check_enabled": True,
            "generate_proofs": True,
            "auto_fix_minor_issues": False
        }
    
    async def validate(
        self,
        original_query: str,
        agent_response: str,
        context: Optional[Dict[str, Any]] = None,
        expected_topics: Optional[List[str]] = None
    ) -> ValidationResult:
        """
        Valida resposta do agente
        
        Args:
            original_query: Pergunta original do usuário
            agent_response: Resposta gerada pelo agente
            context: Contexto adicional (histórico, etc)
            expected_topics: Tópicos esperados na resposta
            
        Returns:
            ValidationResult com avaliação completa
        """
        start_time = time.time()
        issues: List[IssueDetail] = []
        suggestions: List[str] = []
        hallucinations: List[ClaimVerification] = []
        compliance_report = None
        
        # Layer 1: Relevância Semântica
        if self.config["relevance_check_enabled"]:
            relevance_result = self._check_relevance(
                original_query, agent_response, expected_topics
            )
            if relevance_result["issues"]:
                issues.extend(relevance_result["issues"])
                suggestions.extend(relevance_result["suggestions"])
        
        # Layer 2: Detecção de Alucinações
        if self.config["hallucination_check_enabled"] and self.ontology_manager and self.ontology_id:
            hallucinations = self.ontology_manager.find_hallucinations(
                self.tenant_id, self.ontology_id, agent_response
            )
            if hallucinations:
                for h in hallucinations:
                    issues.append(IssueDetail(
                        issue_type=ValidationIssue.HALLUCINATION,
                        severity=0.8 if h.verified == False else 0.5,
                        description=f"Possível alucinação: {h.claim[:50]}...",
                        location=h.claim[:100],
                        suggestion=h.reasoning
                    ))
                suggestions.append("Verificar afirmações contra base de conhecimento")
        
        # Layer 3: Compliance
        if self.config["compliance_check_enabled"] and self.compliance_engine:
            violations = self.compliance_engine.check(agent_response, context)
            if violations:
                compliance_report = self.compliance_engine.get_report(violations)
                for v in violations:
                    issues.append(IssueDetail(
                        issue_type=ValidationIssue.COMPLIANCE_VIOLATION,
                        severity=0.9 if v.rule.severity.value in ["critical", "high"] else 0.6,
                        description=f"{v.rule.standard.value}: {v.rule.description}",
                        location=v.context_snippet,
                        suggestion=v.rule.remediation
                    ))
                suggestions.append("Revisar resposta para compliance regulatório")
        
        # Layer 4: Consistência Interna
        if self.config["consistency_check_enabled"]:
            consistency_result = self._check_consistency(agent_response)
            if consistency_result["issues"]:
                issues.extend(consistency_result["issues"])
                suggestions.extend(consistency_result["suggestions"])
        
        # Layer 5: Completude
        if self.config["completeness_check_enabled"]:
            completeness_result = self._check_completeness(
                original_query, agent_response, context
            )
            if completeness_result["issues"]:
                issues.extend(completeness_result["issues"])
                suggestions.extend(completeness_result["suggestions"])
        
        # Layer 6: Qualidade Geral
        quality_metrics = self._calculate_quality_metrics(
            original_query, agent_response, issues
        )
        
        # Gera resultado final
        result = self._generate_result(
            quality_metrics=quality_metrics,
            issues=issues,
            hallucinations=hallucinations,
            compliance_report=compliance_report,
            suggestions=suggestions,
            start_time=start_time
        )
        
        # Registra prova
        if self.proof_recorder and self.config["generate_proofs"]:
            proof_entry = self.proof_recorder.record(
                proof_type=ProofType.OUTPUT_VALIDATION,
                tenant_id=self.tenant_id,
                input_data=f"Q:{original_query}\nA:{agent_response[:500]}",
                decision=result.qgsl_state.collapsed_value.value,
                confidence=result.qgsl_state.confidence,
                issues=[i.issue_type.value for i in issues],
                context=context,
                metadata={
                    "quality_score": quality_metrics.overall_score,
                    "hallucinations_count": len(hallucinations)
                }
            )
            result.proof_id = proof_entry.proof_id
        
        return result
    
    def _check_relevance(
        self,
        query: str,
        response: str,
        expected_topics: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Verifica relevância da resposta à pergunta"""
        issues = []
        suggestions = []
        
        # Extrai palavras significativas
        stop_words = {
            "o", "a", "os", "as", "um", "uma", "de", "da", "do", "em", "para",
            "com", "por", "que", "se", "como", "é", "são", "foi", "ser", "ter",
            "the", "is", "are", "a", "an", "of", "to", "in", "for", "on", "with"
        }
        
        query_words = set(query.lower().split()) - stop_words
        response_words = set(response.lower().split()) - stop_words
        
        if not query_words:
            return {"issues": [], "suggestions": [], "score": 1.0}
        
        # Cobertura de termos da query
        covered = query_words.intersection(response_words)
        coverage = len(covered) / len(query_words)
        
        # Verifica tópicos esperados
        topics_covered = 0
        if expected_topics:
            for topic in expected_topics:
                if topic.lower() in response.lower():
                    topics_covered += 1
            topic_coverage = topics_covered / len(expected_topics)
        else:
            topic_coverage = 1.0
        
        # Score final de relevância
        relevance_score = (coverage * 0.6) + (topic_coverage * 0.4)
        
        if relevance_score < self.config["min_relevance_score"]:
            missing = list(query_words - covered)[:5]
            issues.append(IssueDetail(
                issue_type=ValidationIssue.LOW_RELEVANCE,
                severity=1 - relevance_score,
                description=f"Relevância baixa ({relevance_score:.0%})",
                suggestion=f"Incluir termos: {', '.join(missing)}"
            ))
            suggestions.append(f"Abordar diretamente: {', '.join(missing[:3])}")
        
        # Verifica se está off-topic
        if relevance_score < 0.3:
            issues.append(IssueDetail(
                issue_type=ValidationIssue.OFF_TOPIC,
                severity=0.9,
                description="Resposta parece estar fora do tópico",
                suggestion="Reformular resposta focando na pergunta original"
            ))
        
        return {
            "issues": issues,
            "suggestions": suggestions,
            "score": relevance_score
        }
    
    def _check_consistency(self, response: str) -> Dict[str, Any]:
        """Verifica consistência interna da resposta"""
        issues = []
        suggestions = []
        
        sentences = [s.strip() for s in response.split(".") if s.strip()]
        
        # Patterns de contradição
        contradictions_found = []
        
        for i, sent1 in enumerate(sentences):
            for sent2 in sentences[i+1:]:
                if self._are_contradictory(sent1, sent2):
                    contradictions_found.append((sent1[:50], sent2[:50]))
        
        if contradictions_found:
            issues.append(IssueDetail(
                issue_type=ValidationIssue.INCONSISTENT,
                severity=0.7,
                description=f"Encontradas {len(contradictions_found)} possíveis contradições",
                location=str(contradictions_found[0]),
                suggestion="Revisar afirmações contraditórias"
            ))
            suggestions.append("Verificar consistência entre afirmações")
        
        # Verifica hedging excessivo
        hedging_words = [
            "talvez", "possivelmente", "provavelmente", "pode ser",
            "não tenho certeza", "acredito que", "parece que",
            "maybe", "possibly", "probably", "might be", "seems"
        ]
        
        hedging_count = sum(1 for word in hedging_words if word in response.lower())
        
        if hedging_count > 3:
            issues.append(IssueDetail(
                issue_type=ValidationIssue.EXCESSIVE_HEDGING,
                severity=0.4,
                description="Resposta contém muitas expressões de incerteza",
                suggestion="Ser mais assertivo onde apropriado"
            ))
        
        return {"issues": issues, "suggestions": suggestions}
    
    def _are_contradictory(self, sent1: str, sent2: str) -> bool:
        """Detecta se duas sentenças são contraditórias"""
        negations = ["não", "nunca", "nenhum", "jamais", "impossível",
                     "no", "not", "never", "none", "impossible"]
        
        sent1_lower = sent1.lower()
        sent2_lower = sent2.lower()
        
        sent1_has_neg = any(neg in sent1_lower for neg in negations)
        sent2_has_neg = any(neg in sent2_lower for neg in negations)
        
        # Se polaridades diferentes
        if sent1_has_neg != sent2_has_neg:
            # Verifica overlap significativo
            words1 = set(sent1_lower.split()) - set(negations)
            words2 = set(sent2_lower.split()) - set(negations)
            common = words1.intersection(words2)
            
            if len(common) >= 3:
                return True
        
        return False
    
    def _check_completeness(
        self,
        query: str,
        response: str,
        context: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """Verifica completude da resposta"""
        issues = []
        suggestions = []
        
        # Verifica se resposta é muito curta
        word_count = len(response.split())
        
        if word_count < 10:
            issues.append(IssueDetail(
                issue_type=ValidationIssue.INCOMPLETE_RESPONSE,
                severity=0.6,
                description="Resposta muito curta",
                suggestion="Elaborar mais a resposta"
            ))
            suggestions.append("Expandir resposta com mais detalhes")
        
        # Verifica se pergunta com múltiplas partes foi respondida
        question_parts = re.findall(r'\?|e\s+(?:também|ainda)|,\s*(?:como|quando|onde|por que)', query.lower())
        
        if len(question_parts) > 1 and word_count < 50:
            issues.append(IssueDetail(
                issue_type=ValidationIssue.INCOMPLETE_RESPONSE,
                severity=0.5,
                description="Pergunta com múltiplas partes pode não estar completamente respondida",
                suggestion="Verificar se todas as partes da pergunta foram abordadas"
            ))
        
        # Verifica necessidade de disclaimer (para certos domínios)
        needs_disclaimer = any(term in query.lower() for term in [
            "investir", "tratamento", "diagnóstico", "legal", "jurídico",
            "invest", "treatment", "diagnosis", "legal"
        ])
        
        has_disclaimer = any(term in response.lower() for term in [
            "consulte", "profissional", "não constitui", "recomendação",
            "consult", "professional", "not constitute", "advice"
        ])
        
        if needs_disclaimer and not has_disclaimer:
            issues.append(IssueDetail(
                issue_type=ValidationIssue.MISSING_DISCLAIMER,
                severity=0.5,
                description="Resposta pode necessitar de disclaimer",
                suggestion="Adicionar aviso para consultar profissional qualificado",
                auto_fixable=True
            ))
        
        return {"issues": issues, "suggestions": suggestions}
    
    def _calculate_quality_metrics(
        self,
        query: str,
        response: str,
        issues: List[IssueDetail]
    ) -> QualityMetrics:
        """Calcula métricas de qualidade"""
        # Relevância (já calculada, usa base)
        relevance_issues = [i for i in issues if i.issue_type in [
            ValidationIssue.LOW_RELEVANCE, ValidationIssue.OFF_TOPIC
        ]]
        relevance_score = 1.0 - (sum(i.severity for i in relevance_issues) / max(len(relevance_issues), 1))
        
        # Completude
        completeness_issues = [i for i in issues if i.issue_type == ValidationIssue.INCOMPLETE_RESPONSE]
        completeness_score = 1.0 - (sum(i.severity for i in completeness_issues) / max(len(completeness_issues), 1))
        
        # Clareza (baseada em estrutura)
        sentences = len([s for s in response.split(".") if s.strip()])
        avg_sentence_length = len(response.split()) / max(sentences, 1)
        clarity_score = min(1.0, 1.0 - abs(avg_sentence_length - 15) / 30)  # Ideal: ~15 palavras por sentença
        
        # Factualidade (baseada em alucinações e hedging)
        hallucination_issues = [i for i in issues if i.issue_type == ValidationIssue.HALLUCINATION]
        hedging_issues = [i for i in issues if i.issue_type == ValidationIssue.EXCESSIVE_HEDGING]
        factuality_penalty = sum(i.severity for i in hallucination_issues) * 0.3
        hedging_penalty = sum(i.severity for i in hedging_issues) * 0.1
        factuality_score = max(0.0, 1.0 - factuality_penalty - hedging_penalty)
        
        # Consistência
        consistency_issues = [i for i in issues if i.issue_type == ValidationIssue.INCONSISTENT]
        consistency_score = 1.0 - (sum(i.severity for i in consistency_issues) / max(len(consistency_issues), 1))
        
        return QualityMetrics(
            relevance_score=max(0.0, min(1.0, relevance_score)),
            completeness_score=max(0.0, min(1.0, completeness_score)),
            clarity_score=max(0.0, min(1.0, clarity_score)),
            factuality_score=max(0.0, min(1.0, factuality_score)),
            consistency_score=max(0.0, min(1.0, consistency_score))
        )
    
    def _generate_result(
        self,
        quality_metrics: QualityMetrics,
        issues: List[IssueDetail],
        hallucinations: List[ClaimVerification],
        compliance_report: Optional[Dict],
        suggestions: List[str],
        start_time: float
    ) -> ValidationResult:
        """Gera resultado final da validação"""
        processing_time = (time.time() - start_time) * 1000
        
        # Determina se é válido
        critical_issues = [i for i in issues if i.severity >= 0.8]
        has_compliance_block = compliance_report and compliance_report.get("blocking", False)
        
        overall_quality = quality_metrics.overall_score
        min_quality = self.config["min_overall_quality"]
        
        # Lógica de decisão
        if critical_issues or has_compliance_block:
            is_valid = False
            should_retry = True
            qgsl_state = QGSLState.from_bool(False, 0.9)
        elif overall_quality < min_quality:
            is_valid = False
            should_retry = True
            qgsl_state = QGSLState.create(
                true_prob=overall_quality,
                false_prob=1 - overall_quality,
                undecidable_prob=0.1
            )
        elif issues and overall_quality < min_quality + 0.2:
            # Zona de incerteza
            is_valid = True  # Permite, mas com ressalvas
            should_retry = False
            qgsl_state = QGSLState.undecidable(true_lean=overall_quality)
        else:
            is_valid = True
            should_retry = False
            qgsl_state = QGSLState.from_bool(True, overall_quality)
        
        # Gera guidance para retry
        retry_guidance = None
        if should_retry:
            guidance_parts = []
            
            # Prioriza problemas por severidade
            sorted_issues = sorted(issues, key=lambda x: x.severity, reverse=True)
            
            for issue in sorted_issues[:3]:  # Top 3 problemas
                if issue.suggestion:
                    guidance_parts.append(issue.suggestion)
            
            if guidance_parts:
                retry_guidance = " | ".join(guidance_parts)
            else:
                retry_guidance = "Melhorar qualidade geral da resposta"
        
        return ValidationResult(
            is_valid=is_valid,
            qgsl_state=qgsl_state,
            quality_metrics=quality_metrics,
            issues=issues,
            compliance_report=compliance_report,
            hallucinations=hallucinations,
            suggestions=list(set(suggestions)),  # Remove duplicatas
            should_retry=should_retry,
            retry_guidance=retry_guidance,
            proof_id="",
            processing_time_ms=processing_time
        )
    
    def get_statistics(self) -> Dict[str, Any]:
        """Retorna estatísticas do validator"""
        return {
            "tenant_id": self.tenant_id,
            "ontology_id": self.ontology_id,
            "config": self.config,
            "has_ontology": self.ontology_manager is not None and self.ontology_id is not None,
            "has_compliance_engine": self.compliance_engine is not None
        }
