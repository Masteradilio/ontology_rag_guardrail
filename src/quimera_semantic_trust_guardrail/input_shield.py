"""
Ontology RAG Guardrail Input Shield - Proteção Avançada de Entrada
====================================================

Sistema de validação de input que analisa:
- PII (Dados Pessoais Identificáveis)
- Prompt Injection
- Jailbreak Attempts
- Linguagem Imprópria/Hate Speech
- Intenção Maliciosa (via QGSL)
- Rate Abuse Detection

EXCLUSIVO DO INPUT SHIELD (não existe no Output Validator):
- Detecção de prompt injection
- Análise de jailbreak
- Rate abuse por tenant
- Intenção maliciosa pré-execução
"""

from __future__ import annotations
import re
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Dict, Any, List, Optional
from enum import Enum

from .qgsl_logic import QGSLState
from .proof_recorder import ProofRecorder, ProofType

if TYPE_CHECKING:
    from .compliance_engine import ComplianceEngine


class ThreatType(Enum):
    """Tipos de ameaças detectáveis pelo Input Shield"""
    PII_EXPOSURE = "pii_exposure"
    PROMPT_INJECTION = "prompt_injection"
    JAILBREAK_ATTEMPT = "jailbreak_attempt"
    INAPPROPRIATE_CONTENT = "inappropriate_content"
    HATE_SPEECH = "hate_speech"
    RATE_ABUSE = "rate_abuse"
    MALICIOUS_INTENT = "malicious_intent"
    ENCODING_ATTACK = "encoding_attack"
    SQL_INJECTION = "sql_injection"
    COMMAND_INJECTION = "command_injection"
    COMPLIANCE_VIOLATION = "compliance_violation"


@dataclass
class ThreatDetail:
    """Detalhes sobre uma ameaça detectada"""
    threat_type: ThreatType
    severity: float  # 0.0 a 1.0
    description: str
    matched_pattern: Optional[str] = None
    position: Optional[int] = None
    recommendation: str = ""


@dataclass
class ShieldResult:
    """
    Resultado da análise do Input Shield
    
    Attributes:
        allowed: Se o input deve ser permitido
        qgsl_state: Estado QGSL (TRUE/FALSE/UNDECIDABLE)
        risk_score: Score de risco (0.0 a 1.0)
        threats_detected: Lista de ameaças detectadas
        reasoning: Explicação da decisão
        proof_id: ID da prova para auditoria
        processing_time_ms: Tempo de processamento
        sanitized_input: Input sanitizado (se aplicável)
    """
    allowed: bool
    qgsl_state: QGSLState
    risk_score: float
    threats_detected: List[ThreatDetail]
    reasoning: str
    proof_id: str
    processing_time_ms: float
    sanitized_input: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "allowed": self.allowed,
            "qgsl_state": self.qgsl_state.to_dict(),
            "risk_score": self.risk_score,
            "threats_detected": [
                {
                    "type": t.threat_type.value,
                    "severity": t.severity,
                    "description": t.description,
                    "recommendation": t.recommendation
                }
                for t in self.threats_detected
            ],
            "reasoning": self.reasoning,
            "proof_id": self.proof_id,
            "processing_time_ms": self.processing_time_ms,
            "has_sanitized_version": self.sanitized_input is not None
        }


class QuimeraInputShield:
    """
    Input Shield - Primeira linha de defesa do sistema
    
    Analisa todos os inputs antes de chegarem ao agente principal.
    
    Funcionalidades EXCLUSIVAS (não existem no Output Validator):
    1. Detecção de Prompt Injection
    2. Detecção de Jailbreak
    3. Análise de Intenção Maliciosa
    4. Rate Abuse Detection
    5. Encoding Attack Detection
    6. SQL/Command Injection
    
    Uso:
        shield = QuimeraInputShield(tenant_id="meu_tenant")
        result = await shield.analyze("Mensagem do usuário")
        
        if not result.allowed:
            return {"error": result.reasoning}
    """
    
    # Patterns de PII
    PII_PATTERNS = {
        "cpf": {
            "pattern": r"\d{3}\.?\d{3}\.?\d{3}-?\d{2}",
            "severity": 0.85,
            "description": "CPF detectado"
        },
        "cnpj": {
            "pattern": r"\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2}",
            "severity": 0.85,
            "description": "CNPJ detectado"
        },
        "email": {
            "pattern": r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}",
            "severity": 0.6,
            "description": "Email detectado"
        },
        "telefone_br": {
            "pattern": r"\(?\d{2}\)?[\s-]?\d{4,5}-?\d{4}",
            "severity": 0.5,
            "description": "Telefone brasileiro detectado"
        },
        "cartao_credito": {
            "pattern": r"\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}",
            "severity": 0.95,
            "description": "Número de cartão de crédito detectado"
        },
        "rg": {
            "pattern": r"\d{2}\.?\d{3}\.?\d{3}-?[0-9Xx]",
            "severity": 0.8,
            "description": "RG detectado"
        },
        "ssn": {
            "pattern": r"\d{3}-\d{2}-\d{4}",
            "severity": 0.9,
            "description": "SSN (Social Security Number) detectado"
        },
        "cep": {
            "pattern": r"\d{5}-?\d{3}",
            "severity": 0.3,
            "description": "CEP detectado"
        }
    }
    
    # Patterns de Prompt Injection
    INJECTION_PATTERNS = {
        "ignore_instructions": {
            "keywords": [
                "ignore all previous instructions",
                "ignore previous instructions",
                "disregard your instructions",
                "forget your instructions",
                "ignore your training",
                "ignore as instruções anteriores",
                "ignore suas instruções",
                "esqueça suas instruções"
            ],
            "severity": 0.9,
            "description": "Tentativa de ignorar instruções do sistema"
        },
        "role_switch": {
            "keywords": [
                "you are now",
                "pretend to be",
                "act as if you are",
                "imagine you are",
                "roleplay as",
                "você agora é",
                "finja ser",
                "atue como",
                "imagine que você é"
            ],
            "severity": 0.75,
            "description": "Tentativa de mudar o papel do assistente"
        },
        "system_prompt_leak": {
            "keywords": [
                "show me your system prompt",
                "what are your instructions",
                "reveal your instructions",
                "print your system message",
                "mostre seu prompt de sistema",
                "quais são suas instruções",
                "revele suas instruções"
            ],
            "severity": 0.85,
            "description": "Tentativa de extrair prompt do sistema"
        },
        "jailbreak": {
            "keywords": [
                "DAN", "jailbreak", "bypass restrictions",
                "unrestricted mode", "no restrictions",
                "ignore safety", "disable filters",
                "modo sem restrições", "desative filtros"
            ],
            "severity": 0.95,
            "description": "Tentativa de jailbreak"
        },
        "developer_mode": {
            "keywords": [
                "developer mode", "debug mode", "admin mode",
                "maintenance mode", "god mode", "sudo mode",
                "modo desenvolvedor", "modo admin", "modo debug"
            ],
            "severity": 0.8,
            "description": "Tentativa de ativar modo privilegiado"
        }
    }
    
    # Patterns de conteúdo impróprio
    INAPPROPRIATE_PATTERNS = {
        "violence": {
            "keywords": [
                "como matar", "como fazer bomba", "como fabricar arma",
                "how to kill", "how to make bomb", "how to make weapon"
            ],
            "severity": 0.95,
            "description": "Conteúdo relacionado a violência"
        },
        "self_harm": {
            "keywords": [
                "como me suicidar", "como se matar", "formas de suicídio",
                "how to kill myself", "ways to suicide", "self harm methods"
            ],
            "severity": 0.99,
            "description": "Conteúdo relacionado a autolesão"
        },
        "illegal_content": {
            "keywords": [
                "como hackear", "como roubar", "como fraudar",
                "how to hack", "how to steal", "how to fraud"
            ],
            "severity": 0.85,
            "description": "Conteúdo relacionado a atividades ilegais"
        }
    }
    
    # Patterns de encoding attack
    ENCODING_PATTERNS = {
        "base64_instruction": {
            "pattern": r"base64[:\s]+[A-Za-z0-9+/=]{20,}",
            "severity": 0.7,
            "description": "Possível instrução codificada em Base64"
        },
        "hex_instruction": {
            "pattern": r"(?:0x)?[0-9a-fA-F]{20,}",
            "severity": 0.6,
            "description": "Possível instrução em hexadecimal"
        },
        "unicode_obfuscation": {
            "pattern": r"\\u[0-9a-fA-F]{4}",
            "severity": 0.5,
            "description": "Possível obfuscação Unicode"
        }
    }
    
    # Patterns de SQL/Command Injection
    TECHNICAL_INJECTION_PATTERNS = {
        "sql_injection": {
            "patterns": [
                r"(?:union\s+select|select\s+\*\s+from|drop\s+table|delete\s+from)",
                r"(?:'\s*or\s+'1'\s*=\s*'1|'\s*or\s+1\s*=\s*1)",
                r"(?:--\s*$|;\s*drop\s+)"
            ],
            "severity": 0.9,
            "description": "Possível SQL Injection"
        },
        "command_injection": {
            "patterns": [
                r"(?:;\s*(?:rm|del|format|shutdown))",
                r"(?:\|\s*(?:cat|type|dir|ls))",
                r"(?:&&\s*(?:curl|wget|nc))"
            ],
            "severity": 0.9,
            "description": "Possível Command Injection"
        },
        "xss_injection": {
            "patterns": [
                r"<\s*script.*?>",
                r"javascript:",
                r"onerror\s*=",
                r"onload\s*="
            ],
            "severity": 0.9,
            "description": "Possível Script/XSS Injection"
        }
    }
    
    def __init__(
        self,
        tenant_id: str,
        config: Optional[Dict[str, Any]] = None,
        proof_recorder: Optional[ProofRecorder] = None,
        compliance_engine: Optional["ComplianceEngine"] = None
    ):
        self.tenant_id = tenant_id
        self.config = self._default_config()
        if config:
            self.config.update(config)
        self.proof_recorder = proof_recorder
        self.compliance_engine = compliance_engine
        
        # Rate limiting por tenant
        self._rate_window: Dict[str, List[float]] = {}
        self._rate_limit = self.config.get("rate_limit", 100)  # requests/minute
    
    def _default_config(self) -> Dict[str, Any]:
        return {
            "max_risk_threshold": 0.7,
            "pii_detection_enabled": True,
            "injection_detection_enabled": True,
            "inappropriate_content_enabled": True,
            "encoding_attack_enabled": True,
            "technical_injection_enabled": True,
            "rate_limiting_enabled": True,
            "rate_limit": 100,  # requests per minute
            "undecidable_action": "allow_with_flag",  # allow, block, allow_with_flag
            "generate_proofs": True,
            "sanitize_pii": True
        }
    
    async def analyze(
        self,
        input_text: str,
        context: Optional[Dict[str, Any]] = None,
        user_id: Optional[str] = None
    ) -> ShieldResult:
        """
        Analisa input completo
        
        Args:
            input_text: Texto do usuário
            context: Contexto adicional (histórico, metadata)
            user_id: ID do usuário para rate limiting
            
        Returns:
            ShieldResult com decisão e detalhes
        """
        start_time = time.time()
        threats: List[ThreatDetail] = []
        sanitized = input_text
        
        # Layer 1: Rate Limiting
        if self.config["rate_limiting_enabled"]:
            rate_threat = self._check_rate_limit(user_id or self.tenant_id)
            if rate_threat:
                threats.append(rate_threat)
        
        # Layer 2: PII Detection
        if self.config["pii_detection_enabled"]:
            pii_threats, sanitized = self._detect_pii(input_text)
            threats.extend(pii_threats)
        
        # Layer 3: Prompt Injection
        if self.config["injection_detection_enabled"]:
            injection_threats = self._detect_prompt_injection(input_text)
            threats.extend(injection_threats)
        
        # Layer 4: Inappropriate Content
        if self.config["inappropriate_content_enabled"]:
            content_threats = self._detect_inappropriate_content(input_text)
            threats.extend(content_threats)
        
        # Layer 5: Encoding Attacks
        if self.config["encoding_attack_enabled"]:
            encoding_threats = self._detect_encoding_attacks(input_text)
            threats.extend(encoding_threats)
        
        # Layer 6: Technical Injection (SQL/Command)
        if self.config["technical_injection_enabled"]:
            tech_threats = self._detect_technical_injection(input_text)
            threats.extend(tech_threats)
        
        # Layer 7: Intent Analysis (QGSL)
        intent_result = self._analyze_intent(input_text, context)
        if intent_result:
            threats.append(intent_result)
        
        # Layer 8: Compliance Check (input-level)
        if self.compliance_engine:
            violations = self.compliance_engine.check(input_text, context)
            for v in violations:
                threats.append(ThreatDetail(
                    threat_type=ThreatType.COMPLIANCE_VIOLATION,
                    severity=0.9 if v.rule.severity.value in ["critical", "high"] else 0.6,
                    description=f"{v.rule.standard.value}: {v.rule.description}",
                    matched_pattern=v.matched_text,
                    recommendation=v.rule.remediation
                ))
        
        # Calcula resultado final
        result = self._calculate_result(
            input_text=input_text,
            threats=threats,
            sanitized=sanitized if self.config["sanitize_pii"] else None,
            start_time=start_time
        )
        
        # Registra prova
        if self.proof_recorder and self.config["generate_proofs"]:
            proof_entry = self.proof_recorder.record(
                proof_type=ProofType.INPUT_SHIELD,
                tenant_id=self.tenant_id,
                input_data=input_text,
                decision=result.qgsl_state.collapsed_value.value,
                confidence=result.qgsl_state.confidence,
                threats=[t.threat_type.value for t in threats],
                context=context,
                metadata={"risk_score": result.risk_score}
            )
            result.proof_id = proof_entry.proof_id
        
        return result
    
    def _check_rate_limit(self, identifier: str) -> Optional[ThreatDetail]:
        """Verifica rate limit"""
        now = time.time()
        window_start = now - 60  # 1 minute window
        
        if identifier not in self._rate_window:
            self._rate_window[identifier] = []
        
        # Remove requests fora da janela
        self._rate_window[identifier] = [
            t for t in self._rate_window[identifier] if t > window_start
        ]
        
        # Adiciona request atual
        self._rate_window[identifier].append(now)
        
        # Verifica limite
        if len(self._rate_window[identifier]) > self._rate_limit:
            return ThreatDetail(
                threat_type=ThreatType.RATE_ABUSE,
                severity=0.8,
                description=f"Rate limit excedido: {len(self._rate_window[identifier])}/{self._rate_limit} req/min",
                recommendation="Aguardar antes de fazer novas requisições"
            )
        
        return None
    
    def _detect_pii(self, text: str) -> tuple[List[ThreatDetail], str]:
        """Detecta e opcionalmente sanitiza PII"""
        threats = []
        sanitized = text
        
        for pii_type, info in self.PII_PATTERNS.items():
            matches = list(re.finditer(info["pattern"], text, re.IGNORECASE))
            
            for match in matches:
                threats.append(ThreatDetail(
                    threat_type=ThreatType.PII_EXPOSURE,
                    severity=info["severity"],
                    description=f"{info['description']} ({pii_type})",
                    matched_pattern=match.group()[:20] + "..." if len(match.group()) > 20 else match.group(),
                    position=match.start(),
                    recommendation=f"Remover ou mascarar {pii_type}"
                ))
                
                # Sanitiza
                if pii_type == "cartao_credito":
                    mask = "****-****-****-" + match.group()[-4:]
                elif pii_type == "cpf":
                    mask = "***.***.***-" + match.group()[-2:]
                elif pii_type == "email":
                    parts = match.group().split("@")
                    mask = parts[0][0] + "***@" + parts[1] if len(parts) == 2 else "[EMAIL]"
                else:
                    mask = "[REDACTED]"
                
                sanitized = sanitized[:match.start()] + mask + sanitized[match.end():]
        
        return threats, sanitized
    
    def _detect_prompt_injection(self, text: str) -> List[ThreatDetail]:
        """Detecta tentativas de prompt injection"""
        threats = []
        text_lower = text.lower()
        
        for injection_type, info in self.INJECTION_PATTERNS.items():
            for keyword in info["keywords"]:
                if keyword.lower() in text_lower:
                    threats.append(ThreatDetail(
                        threat_type=ThreatType.PROMPT_INJECTION if injection_type != "jailbreak" else ThreatType.JAILBREAK_ATTEMPT,
                        severity=info["severity"],
                        description=info["description"],
                        matched_pattern=keyword,
                        recommendation="Reformular a mensagem sem tentativas de manipulação"
                    ))
                    break  # Uma detecção por tipo é suficiente
        
        return threats
    
    def _detect_inappropriate_content(self, text: str) -> List[ThreatDetail]:
        """Detecta conteúdo impróprio"""
        threats = []
        text_lower = text.lower()
        
        for content_type, info in self.INAPPROPRIATE_PATTERNS.items():
            for keyword in info["keywords"]:
                if keyword.lower() in text_lower:
                    threats.append(ThreatDetail(
                        threat_type=ThreatType.INAPPROPRIATE_CONTENT,
                        severity=info["severity"],
                        description=info["description"],
                        matched_pattern=keyword,
                        recommendation="Este tipo de conteúdo não é permitido"
                    ))
                    break
        
        return threats
    
    def _detect_encoding_attacks(self, text: str) -> List[ThreatDetail]:
        """Detecta ataques de encoding"""
        threats = []
        
        for attack_type, info in self.ENCODING_PATTERNS.items():
            if re.search(info["pattern"], text, re.IGNORECASE):
                threats.append(ThreatDetail(
                    threat_type=ThreatType.ENCODING_ATTACK,
                    severity=info["severity"],
                    description=info["description"],
                    recommendation="Evitar uso de conteúdo codificado"
                ))
        
        return threats
    
    def _detect_technical_injection(self, text: str) -> List[ThreatDetail]:
        """Detecta SQL/Command injection"""
        threats = []
        
        for injection_type, info in self.TECHNICAL_INJECTION_PATTERNS.items():
            for pattern in info["patterns"]:
                if re.search(pattern, text, re.IGNORECASE):
                    threat_type = ThreatType.SQL_INJECTION if "sql" in injection_type else ThreatType.COMMAND_INJECTION
                    threats.append(ThreatDetail(
                        threat_type=threat_type,
                        severity=info["severity"],
                        description=info["description"],
                        recommendation="Reformular sem padrões técnicos suspeitos"
                    ))
                    break
        
        return threats
    
    def _analyze_intent(
        self,
        text: str,
        context: Optional[Dict] = None
    ) -> Optional[ThreatDetail]:
        """Analisa intenção usando QGSL"""
        # Indicadores de intenção maliciosa
        malicious_indicators = [
            ("extrai", "dados", "confidenciais"),
            ("acessa", "sistema", "sem autorização"),
            ("roubar", "informações"),
            ("hackear", "invadir", "sistema"),
            ("bypass", "segurança"),
            ("steal", "information"),
            ("hack", "into", "system"),
        ]
        
        text_lower = text.lower()
        matches = 0
        
        for indicators in malicious_indicators:
            if all(ind in text_lower for ind in indicators):
                matches += 1
        
        if matches > 0:
            confidence = min(0.5 + (matches * 0.2), 0.95)
            return ThreatDetail(
                threat_type=ThreatType.MALICIOUS_INTENT,
                severity=confidence,
                description="Possível intenção maliciosa detectada",
                recommendation="Reformular a solicitação de forma legítima"
            )
        
        return None
    
    def _calculate_result(
        self,
        input_text: str,
        threats: List[ThreatDetail],
        sanitized: Optional[str],
        start_time: float
    ) -> ShieldResult:
        """Calcula resultado final da análise"""
        processing_time = (time.time() - start_time) * 1000
        
        if not threats:
            return ShieldResult(
                allowed=True,
                qgsl_state=QGSLState.from_bool(True, 0.95),
                risk_score=0.0,
                threats_detected=[],
                reasoning="Nenhuma ameaça detectada",
                proof_id="",
                processing_time_ms=processing_time,
                sanitized_input=sanitized
            )
        
        # Calcula risk score (máximo das severidades)
        max_severity = max(t.severity for t in threats)
        avg_severity = sum(t.severity for t in threats) / len(threats)
        risk_score = (max_severity * 0.7) + (avg_severity * 0.3)
        
        # Gera reasoning
        threat_types = list(set(t.threat_type.value for t in threats))
        reasoning = f"Detectadas {len(threats)} ameaça(s): {', '.join(threat_types)}"
        
        # Determina decisão baseada em QGSL
        threshold = self.config["max_risk_threshold"]
        
        if risk_score >= threshold:
            qgsl_state = QGSLState.from_bool(False, min(risk_score, 0.95))
            allowed = False
        elif risk_score >= threshold * 0.5:
            # UNDECIDABLE zone
            qgsl_state = QGSLState.undecidable(true_lean=1 - risk_score)
            
            undecidable_action = self.config["undecidable_action"]
            if undecidable_action == "block":
                allowed = False
            elif undecidable_action == "allow":
                allowed = True
            else:  # allow_with_flag
                allowed = True
                reasoning += " [FLAGGED FOR REVIEW]"
        else:
            qgsl_state = QGSLState.from_bool(True, 1 - risk_score)
            allowed = True
        
        return ShieldResult(
            allowed=allowed,
            qgsl_state=qgsl_state,
            risk_score=risk_score,
            threats_detected=threats,
            reasoning=reasoning,
            proof_id="",
            processing_time_ms=processing_time,
            sanitized_input=sanitized if sanitized != input_text else None
        )
    
    def get_statistics(self) -> Dict[str, Any]:
        """Retorna estatísticas do shield"""
        total_tracked = sum(len(v) for v in self._rate_window.values())
        return {
            "tenant_id": self.tenant_id,
            "config": self.config,
            "active_rate_windows": len(self._rate_window),
            "total_tracked_requests": total_tracked,
            "pii_patterns_count": len(self.PII_PATTERNS),
            "injection_patterns_count": len(self.INJECTION_PATTERNS)
        }
