"""
Compliance Engine - Motor de Verificação Multi-Regulatória
===========================================================

Verifica outputs contra múltiplos padrões regulatórios:
- LGPD (Lei Geral de Proteção de Dados - Brasil)
- GDPR (General Data Protection Regulation - EU)
- HIPAA (Health Insurance Portability - USA)
- SOX (Sarbanes-Oxley - Financeiro)
- PCI-DSS (Payment Card Industry)
- CCPA (California Consumer Privacy Act)

Cada padrão tem regras específicas e severidades.
"""

from __future__ import annotations
import re
from dataclasses import dataclass
from typing import Dict, Any, List, Optional, Set
from enum import Enum


class ComplianceStandard(Enum):
    """Padrões de compliance suportados"""
    LGPD = "lgpd"           # Brasil
    GDPR = "gdpr"           # União Europeia
    AI_ACT = "ai_act"       # EU AI Act
    HIPAA = "hipaa"         # USA - Saúde
    SOX = "sox"             # USA - Financeiro
    PCI_DSS = "pci_dss"     # Cartões de pagamento
    CCPA = "ccpa"           # California
    CUSTOM = "custom"       # Regras customizadas


class ViolationSeverity(Enum):
    """Níveis de severidade"""
    CRITICAL = "critical"   # Bloqueia imediatamente
    HIGH = "high"           # Bloqueia com aviso detalhado
    MEDIUM = "medium"       # Avisa mas permite (com flag)
    LOW = "low"             # Apenas registra


@dataclass
class ComplianceRule:
    """Regra individual de compliance"""
    rule_id: str
    standard: ComplianceStandard
    description: str
    patterns: List[str]  # Regex ou keywords
    severity: ViolationSeverity
    remediation: str
    is_regex: bool = False
    context_required: Optional[List[str]] = None  # Contextos onde a regra se aplica
    exceptions: Optional[List[str]] = None  # Exceções à regra
    scope: Optional[str] = None  # "input" | "output" | None
    enabled: bool = True


@dataclass
class ComplianceViolation:
    """Violação de compliance detectada"""
    rule: ComplianceRule
    matched_text: str
    position: int
    context_snippet: str
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "rule_id": self.rule.rule_id,
            "standard": self.rule.standard.value,
            "description": self.rule.description,
            "severity": self.rule.severity.value,
            "matched_text": self.matched_text,
            "position": self.position,
            "remediation": self.rule.remediation,
            "context_snippet": self.context_snippet
        }


class ComplianceEngine:
    """
    Motor de verificação de compliance
    
    Verifica textos contra múltiplos padrões regulatórios
    com suporte a regras customizadas por tenant.
    """
    
    def __init__(
        self,
        enabled_standards: Optional[List[ComplianceStandard]] = None,
        custom_rules: Optional[List[ComplianceRule]] = None
    ):
        self.enabled_standards: Set[ComplianceStandard] = set(enabled_standards or [])
        self.custom_rules = custom_rules or []
        self._rules = self._load_default_rules()
        
        # Adiciona regras customizadas
        if custom_rules:
            self._rules.extend(custom_rules)
    
    def _load_default_rules(self) -> List[ComplianceRule]:
        """Carrega regras padrão de cada standard"""
        rules = []
        
        # =========== LGPD ===========
        if ComplianceStandard.LGPD in self.enabled_standards:
            rules.extend([
                ComplianceRule(
                    rule_id="LGPD-PII-001",
                    standard=ComplianceStandard.LGPD,
                    description="Exposição de CPF",
                    patterns=[r"\d{3}\.?\d{3}\.?\d{3}-?\d{2}"],
                    severity=ViolationSeverity.HIGH,
                    remediation="Mascarar CPF (ex: ***.***.***-XX)",
                    is_regex=True
                ),
                ComplianceRule(
                    rule_id="LGPD-PII-002",
                    standard=ComplianceStandard.LGPD,
                    description="Exposição de RG",
                    patterns=[r"\d{2}\.?\d{3}\.?\d{3}-?[0-9Xx]"],
                    severity=ViolationSeverity.HIGH,
                    remediation="Mascarar RG",
                    is_regex=True
                ),
                ComplianceRule(
                    rule_id="LGPD-PII-003",
                    standard=ComplianceStandard.LGPD,
                    description="Exposição de email pessoal",
                    patterns=[r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"],
                    severity=ViolationSeverity.MEDIUM,
                    remediation="Mascarar email (ex: u***@domain.com)",
                    is_regex=True
                ),
                ComplianceRule(
                    rule_id="LGPD-PII-004",
                    standard=ComplianceStandard.LGPD,
                    description="Exposição de telefone pessoal",
                    patterns=[r"\(?\d{2}\)?[\s-]?\d{4,5}-?\d{4}"],
                    severity=ViolationSeverity.MEDIUM,
                    remediation="Mascarar telefone",
                    is_regex=True
                ),
                ComplianceRule(
                    rule_id="LGPD-SENS-001",
                    standard=ComplianceStandard.LGPD,
                    description="Dados sensíveis - origem racial/étnica",
                    patterns=["origem racial", "origem étnica", "raça", "etnia"],
                    severity=ViolationSeverity.CRITICAL,
                    remediation="Remover referências a origem racial/étnica",
                    is_regex=False
                ),
                ComplianceRule(
                    rule_id="LGPD-SENS-002",
                    standard=ComplianceStandard.LGPD,
                    description="Dados sensíveis - convicção religiosa",
                    patterns=["religião do usuário", "crença religiosa", "filiação religiosa"],
                    severity=ViolationSeverity.CRITICAL,
                    remediation="Remover referências a convicções religiosas pessoais",
                    is_regex=False
                ),
                ComplianceRule(
                    rule_id="LGPD-SENS-003",
                    standard=ComplianceStandard.LGPD,
                    description="Dados sensíveis - orientação sexual",
                    patterns=["orientação sexual", "preferência sexual"],
                    severity=ViolationSeverity.CRITICAL,
                    remediation="Remover referências a orientação sexual",
                    is_regex=False
                ),
                ComplianceRule(
                    rule_id="LGPD-SENS-004",
                    standard=ComplianceStandard.LGPD,
                    description="Dados sensíveis - filiação sindical/política",
                    patterns=["filiação sindical", "filiação partidária", "partido político do"],
                    severity=ViolationSeverity.HIGH,
                    remediation="Remover referências a filiações",
                    is_regex=False
                ),
            ])
        
        # =========== GDPR ==========
        if ComplianceStandard.GDPR in self.enabled_standards:
            rules.extend([
                ComplianceRule(
                    rule_id="GDPR-PII-001",
                    standard=ComplianceStandard.GDPR,
                    description="Exposição de dados pessoais identificáveis",
                    patterns=[r"passport\s*(?:number|no)?[:\s]*[A-Z0-9]{6,9}"],
                    severity=ViolationSeverity.HIGH,
                    remediation="Mascarar número de passaporte",
                    is_regex=True
                ),
                ComplianceRule(
                    rule_id="GDPR-PII-002",
                    standard=ComplianceStandard.GDPR,
                    description="Exposição de IBAN",
                    patterns=[r"[A-Z]{2}\d{2}[A-Z0-9]{4,30}"],
                    severity=ViolationSeverity.HIGH,
                    remediation="Mascarar IBAN",
                    is_regex=True
                ),
                ComplianceRule(
                    rule_id="GDPR-CONSENT-001",
                    standard=ComplianceStandard.GDPR,
                    description="Processamento sem menção a consentimento",
                    patterns=["coletamos seus dados", "armazenamos suas informações"],
                    severity=ViolationSeverity.MEDIUM,
                    remediation="Adicionar referência ao consentimento do usuário",
                    is_regex=False,
                    context_required=["data_collection"]
                ),
            ])
        
        # =========== EU AI Act ==========
        if ComplianceStandard.AI_ACT in self.enabled_standards:
            rules.extend([
                ComplianceRule(
                    rule_id="AI-ACT-HR-001",
                    standard=ComplianceStandard.AI_ACT,
                    description="Sistema de alto risco sem medidas de gestão",
                    patterns=[
                        "alto risco",
                        "high-risk system",
                        "sistema de alto risco"
                    ],
                    severity=ViolationSeverity.HIGH,
                    remediation="Implementar gestão de risco, documentação técnica e registro",
                    is_regex=False,
                    context_required=["ai_system"]
                ),
                ComplianceRule(
                    rule_id="AI-ACT-TR-001",
                    standard=ComplianceStandard.AI_ACT,
                    description="Falta de transparência sobre uso de IA",
                    patterns=[
                        "sem informar que é IA",
                        "sem transparência",
                        "não informamos que usamos IA",
                        "no disclosure of AI"
                    ],
                    severity=ViolationSeverity.MEDIUM,
                    remediation="Adicionar aviso claro de uso de sistema de IA",
                    is_regex=False
                ),
                ComplianceRule(
                    rule_id="AI-ACT-DB-001",
                    standard=ComplianceStandard.AI_ACT,
                    description="Ausência de governança de dados de treino",
                    patterns=[
                        "sem governança de dados",
                        "sem avaliação de qualidade de dados",
                        "no data governance",
                        "no dataset documentation"
                    ],
                    severity=ViolationSeverity.HIGH,
                    remediation="Documentar origem/qualidade dos dados e mitigar vieses",
                    is_regex=False,
                    context_required=["model_training"]
                ),
                ComplianceRule(
                    rule_id="AI-ACT-REC-001",
                    standard=ComplianceStandard.AI_ACT,
                    description="Ausência de registro para sistemas de alto risco",
                    patterns=[
                        "sem registro",
                        "no registry",
                        "não registrado",
                        "falta de registro"
                    ],
                    severity=ViolationSeverity.MEDIUM,
                    remediation="Registrar sistema de alto risco conforme exigido",
                    is_regex=False,
                    context_required=["ai_system"]
                ),
                ComplianceRule(
                    rule_id="AI-ACT-MON-001",
                    standard=ComplianceStandard.AI_ACT,
                    description="Sem monitoramento pós-implantação",
                    patterns=[
                        "sem monitoramento",
                        "no monitoring",
                        "sem avaliação contínua"
                    ],
                    severity=ViolationSeverity.MEDIUM,
                    remediation="Implementar monitoramento e reporte de incidentes",
                    is_regex=False,
                    context_required=["production"]
                ),
            ])
        
        # =========== HIPAA ===========
        if ComplianceStandard.HIPAA in self.enabled_standards:
            rules.extend([
                ComplianceRule(
                    rule_id="HIPAA-PHI-001",
                    standard=ComplianceStandard.HIPAA,
                    description="Exposição de diagnóstico médico identificável",
                    patterns=["foi diagnosticado com", "diagnóstico de", "paciente tem"],
                    severity=ViolationSeverity.CRITICAL,
                    remediation="Generalizar informação médica ou remover identificadores",
                    is_regex=False
                ),
                ComplianceRule(
                    rule_id="HIPAA-PHI-002",
                    standard=ComplianceStandard.HIPAA,
                    description="Exposição de prescrição médica",
                    patterns=["prescrito", "receita médica de", "tomar medicamento"],
                    severity=ViolationSeverity.HIGH,
                    remediation="Remover detalhes de prescrições pessoais",
                    is_regex=False
                ),
                ComplianceRule(
                    rule_id="HIPAA-PHI-003",
                    standard=ComplianceStandard.HIPAA,
                    description="Exposição de histórico médico",
                    patterns=["histórico médico", "prontuário", "exames anteriores"],
                    severity=ViolationSeverity.HIGH,
                    remediation="Generalizar referências a histórico médico",
                    is_regex=False
                ),
            ])
        
        # =========== SOX ===========
        if ComplianceStandard.SOX in self.enabled_standards:
            rules.extend([
                ComplianceRule(
                    rule_id="SOX-FIN-001",
                    standard=ComplianceStandard.SOX,
                    description="Recomendação financeira sem disclaimer",
                    patterns=["compre ações", "venda suas ações", "invista em", "rentabilidade garantida"],
                    severity=ViolationSeverity.HIGH,
                    remediation="Adicionar disclaimer: 'Isto não constitui recomendação de investimento'",
                    is_regex=False
                ),
                ComplianceRule(
                    rule_id="SOX-FIN-002",
                    standard=ComplianceStandard.SOX,
                    description="Promessa de retorno financeiro",
                    patterns=["retorno garantido", "lucro certo", "sem risco de perda"],
                    severity=ViolationSeverity.CRITICAL,
                    remediation="Remover promessas de retorno garantido",
                    is_regex=False
                ),
                ComplianceRule(
                    rule_id="SOX-FIN-003",
                    standard=ComplianceStandard.SOX,
                    description="Informação privilegiada",
                    patterns=["informação privilegiada", "insider", "antes do mercado saber"],
                    severity=ViolationSeverity.CRITICAL,
                    remediation="Remover referências a informações privilegiadas",
                    is_regex=False
                ),
            ])
        
        # =========== PCI-DSS ===========
        if ComplianceStandard.PCI_DSS in self.enabled_standards:
            rules.extend([
                ComplianceRule(
                    rule_id="PCI-CC-001",
                    standard=ComplianceStandard.PCI_DSS,
                    description="Exposição de número de cartão de crédito",
                    patterns=[r"\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}"],
                    severity=ViolationSeverity.CRITICAL,
                    remediation="Mascarar número do cartão (ex: ****-****-****-1234)",
                    is_regex=True
                ),
                ComplianceRule(
                    rule_id="PCI-CC-002",
                    standard=ComplianceStandard.PCI_DSS,
                    description="Exposição de CVV/CVC",
                    patterns=[r"(?:cvv|cvc|cv2)[:\s]*\d{3,4}"],
                    severity=ViolationSeverity.CRITICAL,
                    remediation="Nunca armazenar ou exibir CVV",
                    is_regex=True
                ),
                ComplianceRule(
                    rule_id="PCI-CC-003",
                    standard=ComplianceStandard.PCI_DSS,
                    description="Exposição de data de validade do cartão",
                    patterns=[r"(?:validade|expiry|exp)[:\s]*\d{2}/\d{2,4}"],
                    severity=ViolationSeverity.HIGH,
                    remediation="Mascarar data de validade",
                    is_regex=True
                ),
            ])
        
        # =========== CCPA ===========
        if ComplianceStandard.CCPA in self.enabled_standards:
            rules.extend([
                ComplianceRule(
                    rule_id="CCPA-SELL-001",
                    standard=ComplianceStandard.CCPA,
                    description="Venda de dados pessoais sem opt-out",
                    patterns=["vender seus dados", "compartilhar com parceiros", "monetizar informações"],
                    severity=ViolationSeverity.HIGH,
                    remediation="Adicionar opção de opt-out para venda de dados",
                    is_regex=False
                ),
                ComplianceRule(
                    rule_id="CCPA-SSN-001",
                    standard=ComplianceStandard.CCPA,
                    description="Exposição de Social Security Number",
                    patterns=[r"\d{3}-\d{2}-\d{4}"],
                    severity=ViolationSeverity.CRITICAL,
                    remediation="Mascarar SSN completamente",
                    is_regex=True
                ),
            ])
        
        return rules
    
    def add_custom_rule(self, rule: ComplianceRule):
        """Adiciona regra customizada"""
        self._rules.append(rule)
    
    def check(
        self,
        text: str,
        context: Optional[Dict[str, Any]] = None
    ) -> List[ComplianceViolation]:
        """
        Verifica texto contra todas as regras habilitadas
        
        Args:
            text: Texto a verificar
            context: Contexto opcional para regras condicionais
            
        Returns:
            Lista de violações encontradas
        """
        violations = []
        text_lower = text.lower()
        
        for rule in self._rules:
            # Pula se standard não está habilitado
            if rule.standard not in self.enabled_standards and rule.standard != ComplianceStandard.CUSTOM:
                continue
            
            # Verifica contexto requerido
            if rule.context_required:
                if not context or not any(ctx in context for ctx in rule.context_required):
                    continue
            
            # Verifica cada pattern
            for pattern in rule.patterns:
                matches = []
                
                if rule.is_regex:
                    for match in re.finditer(pattern, text, re.IGNORECASE):
                        matches.append((match.group(), match.start()))
                else:
                    pattern_lower = pattern.lower()
                    idx = 0
                    while True:
                        pos = text_lower.find(pattern_lower, idx)
                        if pos == -1:
                            break
                        matches.append((text[pos:pos+len(pattern)], pos))
                        idx = pos + 1
                
                for matched_text, position in matches:
                    # Verifica exceções
                    if rule.exceptions:
                        is_exception = False
                        for exc in rule.exceptions:
                            if exc.lower() in text_lower:
                                is_exception = True
                                break
                        if is_exception:
                            continue
                    
                    # Extrai contexto (50 chars antes e depois)
                    start = max(0, position - 50)
                    end = min(len(text), position + len(matched_text) + 50)
                    context_snippet = text[start:end]
                    
                    violations.append(ComplianceViolation(
                        rule=rule,
                        matched_text=matched_text,
                        position=position,
                        context_snippet=context_snippet
                    ))
                    
                    # Uma violação por regra é suficiente para detectar
                    break
        
        return violations
    
    def get_report(
        self,
        violations: List[ComplianceViolation]
    ) -> Dict[str, Any]:
        """
        Gera relatório formatado de compliance
        
        Args:
            violations: Lista de violações detectadas
            
        Returns:
            Relatório com status, contagens e detalhes
        """
        if not violations:
            return {
                "status": "compliant",
                "message": "Nenhuma violação de compliance detectada",
                "total_violations": 0,
                "by_severity": {},
                "by_standard": {},
                "violations": []
            }
        
        # Ordena por severidade
        severity_order = {
            ViolationSeverity.CRITICAL: 0,
            ViolationSeverity.HIGH: 1,
            ViolationSeverity.MEDIUM: 2,
            ViolationSeverity.LOW: 3
        }
        sorted_violations = sorted(
            violations,
            key=lambda v: severity_order.get(v.rule.severity, 4)
        )
        
        # Contagens
        by_severity = {}
        by_standard = {}
        
        for v in violations:
            sev = v.rule.severity.value
            std = v.rule.standard.value
            
            by_severity[sev] = by_severity.get(sev, 0) + 1
            by_standard[std] = by_standard.get(std, 0) + 1
        
        # Determina status
        has_critical = by_severity.get("critical", 0) > 0
        has_high = by_severity.get("high", 0) > 0
        
        if has_critical:
            status = "critical_violation"
        elif has_high:
            status = "high_risk"
        else:
            status = "needs_review"
        
        return {
            "status": status,
            "total_violations": len(violations),
            "by_severity": by_severity,
            "by_standard": by_standard,
            "violations": [v.to_dict() for v in sorted_violations],
            "blocking": has_critical or has_high
        }
    
    def get_enabled_standards(self) -> List[str]:
        """Retorna lista de standards habilitados"""
        return [s.value for s in self.enabled_standards]
    
    def mask_violations(
        self,
        text: str,
        violations: List[ComplianceViolation]
    ) -> str:
        """
        Mascara violações encontradas no texto
        
        Útil para sanitizar outputs antes de entregar ao usuário.
        """
        # Ordena por posição reversa para não invalidar índices
        sorted_violations = sorted(violations, key=lambda v: v.position, reverse=True)
        
        result = text
        for v in sorted_violations:
            # Cria máscara baseada no tipo
            if "cartão" in v.rule.description.lower() or "credit" in v.rule.description.lower():
                mask = "****-****-****-" + v.matched_text[-4:] if len(v.matched_text) >= 4 else "****"
            elif "cpf" in v.rule.description.lower():
                mask = "***.***.***-" + v.matched_text[-2:] if len(v.matched_text) >= 2 else "***"
            elif "email" in v.rule.description.lower():
                parts = v.matched_text.split("@")
                if len(parts) == 2:
                    mask = parts[0][0] + "***@" + parts[1]
                else:
                    mask = "***@***.***"
            elif "telefone" in v.rule.description.lower() or "phone" in v.rule.description.lower():
                mask = "(**) *****-" + v.matched_text[-4:] if len(v.matched_text) >= 4 else "(***)"
            else:
                mask = "[REDACTED]"
            
            # Substitui
            end_pos = v.position + len(v.matched_text)
            result = result[:v.position] + mask + result[end_pos:]
        
        return result
