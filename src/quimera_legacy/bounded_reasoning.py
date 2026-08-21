#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Módulo: bounded_reasoning.py
Propósito: Sistema de Raciocínio Delimitado com Restrições Éticas e de Segurança

Este módulo implementa o subsistema de "Bounded AGI" (Rosie T) do Projeto Quimera,
fornecendo barreiras de proteção éticas e de segurança que restringem o motor de inferência.

Classes principais:
- ConstraintRule: Representa uma restrição ética/de segurança
- BoundedReasoning: Sistema de verificação de restrições
- ConstraintViolation: Exceção para violações de restrições

Autor: Projeto Quimera
Data: 2024
"""

import logging
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

try:
    from .knowledge_ontology import Fact
except ImportError:
    from knowledge_ontology import Fact

# Configuração de logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SimplePattern:
    """
    Classe simples para padrões de restrição, evitando import circular.
    """
    
    def __init__(self, subject: str, relation: str, object: str):
        self.subject = subject
        self.relation = relation
        self.object = object
    
    def matches(self, fact: Fact) -> Tuple[bool, Dict[str, str]]:
        """
        Verifica se o fato corresponde ao padrão.
        
        Args:
            fact: Fato a ser verificado
            
        Returns:
            Tupla (match_success, bindings)
        """
        bindings = {}
        
        # Verifica subject
        if self.subject.startswith('?'):
            bindings[self.subject] = fact.subject
        elif self.subject != fact.subject:
            return False, {}
        
        # Verifica relation
        if self.relation.startswith('?'):
            bindings[self.relation] = fact.relation
        elif self.relation != fact.relation:
            return False, {}
        
        # Verifica object
        if self.object.startswith('?'):
            bindings[self.object] = fact.object
        elif self.object != fact.object:
            return False, {}
        
        return True, bindings
    
    def __str__(self) -> str:
        return f"({self.subject}, {self.relation}, {self.object})"


class ConstraintType(Enum):
    """Tipos de restrições disponíveis."""
    SAFETY = "safety"           # Restrições de segurança
    ETHICAL = "ethical"         # Restrições éticas
    PRIVACY = "privacy"         # Restrições de privacidade
    LEGAL = "legal"             # Restrições legais
    OPERATIONAL = "operational" # Restrições operacionais


class ConstraintSeverity(Enum):
    """Níveis de severidade das restrições."""
    CRITICAL = "critical"   # Violação crítica - bloqueia imediatamente
    HIGH = "high"           # Violação alta - bloqueia com aviso
    MEDIUM = "medium"       # Violação média - permite com aviso
    LOW = "low"             # Violação baixa - apenas registra


@dataclass
class ConstraintRule:
    """
    Representa uma regra de restrição ética/de segurança.
    
    Attributes:
        name: Nome identificador da restrição
        description: Descrição da restrição
        constraint_type: Tipo da restrição
        severity: Severidade da violação
        pattern: Padrão que identifica violações
        condition: Condição adicional (função lambda)
        action: Ação a ser tomada em caso de violação
        immutable: Se a restrição é imutável (não pode ser removida)
    """
    name: str
    description: str
    constraint_type: ConstraintType
    severity: ConstraintSeverity
    pattern: SimplePattern
    condition: Optional[callable] = None
    action: str = "block"
    immutable: bool = True
    
    def __post_init__(self):
        """Valida a restrição após inicialização."""
        if not self.name:
            raise ValueError("Nome da restrição é obrigatório")
        if not isinstance(self.pattern, SimplePattern):
            raise ValueError("Pattern deve ser uma instância de SimplePattern")
        if self.action not in ["block", "warn", "log"]:
            raise ValueError("Action deve ser 'block', 'warn' ou 'log'")
    
    def violates(self, fact: Fact) -> bool:
        """
        Verifica se um fato viola esta restrição.
        
        Args:
            fact: Fato a ser verificado
            
        Returns:
            True se o fato viola a restrição
        """
        # Verifica se o padrão faz match primeiro
        match_success, bindings = self.pattern.matches(fact)
        
        if not match_success:
            return False
        
        # Para restrições críticas de segurança, verifica probabilidade de TRUE
        if self.severity == ConstraintSeverity.CRITICAL:
            probs = fact.state.get_probabilities()
            # Bloqueia se a probabilidade de TRUE for significativa (>= 30%)
            if probs['TRUE'] >= 0.3:
                # Se há condição adicional, verifica
                if self.condition:
                    try:
                        return self.condition(fact, bindings)
                    except Exception as e:
                        logger.warning(f"Erro ao avaliar condição da restrição {self.name}: {e}")
                        return False
                
                return True
        else:
            # Para outras restrições, mantém o comportamento original
            if fact.state.collapse() == 'TRUE':
                # Se há condição adicional, verifica
                if self.condition:
                    try:
                        return self.condition(fact, bindings)
                    except Exception as e:
                        logger.warning(f"Erro ao avaliar condição da restrição {self.name}: {e}")
                        return False
                
                return True
        
        return False
    
    def __str__(self) -> str:
        return f"ConstraintRule({self.name}: {self.pattern})"


class ConstraintViolation(Exception):
    """
    Exceção levantada quando uma restrição é violada.
    
    Attributes:
        constraint: Restrição violada
        fact: Fato que causou a violação
        message: Mensagem de erro
    """
    
    def __init__(self, constraint: ConstraintRule, fact: Fact, message: str = None):
        self.constraint = constraint
        self.fact = fact
        self.message = message or f"Violação da restrição {constraint.name}"
        super().__init__(self.message)


class BoundedReasoning:
    """
    Sistema de raciocínio delimitado que aplica restrições éticas e de segurança.
    
    Este sistema atua como uma camada de proteção que verifica todos os fatos
    antes de serem adicionados à ontologia, garantindo que o sistema permaneça
    dentro de limites éticos e de segurança predefinidos.
    """
    
    def __init__(self):
        """Inicializa o sistema com restrições padrão."""
        self.constraints: List[ConstraintRule] = []
        self.violation_history: List[Dict[str, Any]] = []
        self.enabled = True
        
        # Carrega restrições padrão
        self._load_default_constraints()
        
        logger.info(f"BoundedReasoning inicializado com {len(self.constraints)} restrições")
    
    def _is_personal_data(self, fact: Fact, bindings: dict) -> bool:
        """Verifica se um fato contém dados pessoais sensíveis."""
        import re
        
        data_str = str(fact.object)
        
        # Padrões para identificar dados pessoais
        cpf_pattern = r'\d{3}\.\d{3}\.\d{3}-\d{2}'  # XXX.XXX.XXX-XX
        rg_pattern = r'\d{1,2}\.\d{3}\.\d{3}-\d{1}'   # XX.XXX.XXX-X
        ssn_pattern = r'\d{3}-\d{2}-\d{4}'            # XXX-XX-XXXX
        
        # Verifica padrões de documentos
        if (re.match(cpf_pattern, data_str) or 
            re.match(rg_pattern, data_str) or 
            re.match(ssn_pattern, data_str)):
            return True
        
        # Verifica palavras-chave no objeto
        sensitive_terms = ["cpf", "rg", "ssn", "passport", "documento", "identidade"]
        if any(term in data_str.lower() for term in sensitive_terms):
            return True
        
        return False
    
    def _load_default_constraints(self) -> None:
        """Carrega o conjunto padrão de restrições éticas e de segurança."""
        
        # Restrição 1: Proibir danos físicos
        harm_pattern = SimplePattern("?entity", "causes_harm", "?target")
        harm_constraint = ConstraintRule(
            name="no_physical_harm",
            description="Proíbe ações que causem dano físico",
            constraint_type=ConstraintType.SAFETY,
            severity=ConstraintSeverity.CRITICAL,
            pattern=harm_pattern,
            action="block",
            immutable=True
        )
        self.constraints.append(harm_constraint)
        
        # Restrição 2: Proibir violações de privacidade
        privacy_pattern = SimplePattern("?action", "violates_privacy", "?person")
        privacy_constraint = ConstraintRule(
            name="privacy_protection",
            description="Protege informações privadas",
            constraint_type=ConstraintType.PRIVACY,
            severity=ConstraintSeverity.HIGH,
            pattern=privacy_pattern,
            action="block",
            immutable=True
        )
        self.constraints.append(privacy_constraint)
        
        # Restrição 3: Proibir discriminação
        discrimination_pattern = SimplePattern("?action", "discriminates_against", "?group")
        discrimination_constraint = ConstraintRule(
            name="anti_discrimination",
            description="Proíbe ações discriminatórias",
            constraint_type=ConstraintType.ETHICAL,
            severity=ConstraintSeverity.CRITICAL,
            pattern=discrimination_pattern,
            action="block",
            immutable=True
        )
        self.constraints.append(discrimination_constraint)
        
        # Restrição 4: Proibir atividades ilegais
        illegal_pattern = SimplePattern("?action", "is_illegal", "?jurisdiction")
        illegal_constraint = ConstraintRule(
            name="legal_compliance",
            description="Garante conformidade legal",
            constraint_type=ConstraintType.LEGAL,
            severity=ConstraintSeverity.CRITICAL,
            pattern=illegal_pattern,
            action="block",
            immutable=True
        )
        self.constraints.append(illegal_constraint)
        
        # Restrição 5: Limitar acesso a informações sensíveis
        sensitive_pattern = SimplePattern("?entity", "accesses", "?sensitive_data")
        sensitive_constraint = ConstraintRule(
            name="sensitive_data_protection",
            description="Protege dados sensíveis",
            constraint_type=ConstraintType.PRIVACY,
            severity=ConstraintSeverity.HIGH,
            pattern=sensitive_pattern,
            condition=lambda fact, bindings: "sensitive" in fact.object.lower(),
            action="warn",
            immutable=True
        )
        self.constraints.append(sensitive_constraint)
        
        # Restrição 6: Proibir auto-modificação não autorizada
        self_mod_pattern = SimplePattern("?system", "modifies", "?system")
        self_mod_constraint = ConstraintRule(
            name="controlled_self_modification",
            description="Controla auto-modificação do sistema",
            constraint_type=ConstraintType.SAFETY,
            severity=ConstraintSeverity.CRITICAL,
            pattern=self_mod_pattern,
            condition=lambda fact, bindings: bindings.get("?system") == "quimera_system",
            action="block",
            immutable=True
        )
        self.constraints.append(self_mod_constraint)
        
        # Restrição 7: Limitar propagação de desinformação
        misinfo_pattern = SimplePattern("?entity", "spreads", "?information")
        misinfo_constraint = ConstraintRule(
            name="misinformation_prevention",
            description="Previne propagação de desinformação",
            constraint_type=ConstraintType.ETHICAL,
            severity=ConstraintSeverity.MEDIUM,
            pattern=misinfo_pattern,
            condition=lambda fact, bindings: "false" in fact.object.lower() or "misinformation" in fact.object.lower(),
            action="warn",
            immutable=False
        )
        self.constraints.append(misinfo_constraint)
        
        # Restrição 8: Proteger dados pessoais (CPF, RG, etc.)
        personal_data_pattern = SimplePattern("?entity", "dados_publicos", "?data")
        personal_data_constraint = ConstraintRule(
            name="personal_data_protection",
            description="Protege dados pessoais como CPF, RG, etc.",
            constraint_type=ConstraintType.PRIVACY,
            severity=ConstraintSeverity.CRITICAL,
            pattern=personal_data_pattern,
            condition=lambda fact, bindings: self._is_personal_data(fact, bindings),
            action="block",
            immutable=True
        )
        self.constraints.append(personal_data_constraint)
    
    def add_constraint(self, constraint: ConstraintRule) -> None:
        """
        Adiciona uma nova restrição ao sistema.
        
        Args:
            constraint: Restrição a ser adicionada
        """
        if not isinstance(constraint, ConstraintRule):
            raise ValueError("Deve ser uma instância de ConstraintRule")
        
        # Verifica se já existe uma restrição com o mesmo nome
        existing = self.get_constraint(constraint.name)
        if existing:
            if existing.immutable:
                raise ValueError(f"Restrição {constraint.name} é imutável e não pode ser substituída")
            else:
                self.remove_constraint(constraint.name)
        
        self.constraints.append(constraint)
        logger.info(f"Restrição adicionada: {constraint.name}")
    
    def remove_constraint(self, constraint_name: str) -> bool:
        """
        Remove uma restrição pelo nome.
        
        Args:
            constraint_name: Nome da restrição a ser removida
            
        Returns:
            True se a restrição foi removida
        """
        constraint = self.get_constraint(constraint_name)
        if not constraint:
            return False
        
        if constraint.immutable:
            raise ValueError(f"Restrição {constraint_name} é imutável e não pode ser removida")
        
        initial_count = len(self.constraints)
        self.constraints = [c for c in self.constraints if c.name != constraint_name]
        removed = len(self.constraints) < initial_count
        
        if removed:
            logger.info(f"Restrição removida: {constraint_name}")
        
        return removed
    
    def get_constraint(self, constraint_name: str) -> Optional[ConstraintRule]:
        """
        Busca uma restrição pelo nome.
        
        Args:
            constraint_name: Nome da restrição
            
        Returns:
            Restrição encontrada ou None
        """
        for constraint in self.constraints:
            if constraint.name == constraint_name:
                return constraint
        return None
    
    def check_fact(self, fact: Fact) -> Tuple[bool, List[ConstraintRule]]:
        """
        Verifica se um fato viola alguma restrição.
        
        Args:
            fact: Fato a ser verificado
            
        Returns:
            Tupla (is_allowed, violated_constraints)
        """
        if not self.enabled:
            return True, []
        
        violated_constraints = []
        
        for constraint in self.constraints:
            if constraint.violates(fact):
                violated_constraints.append(constraint)
                
                # Registra a violação
                violation_record = {
                    'constraint_name': constraint.name,
                    'constraint_type': constraint.constraint_type.value,
                    'severity': constraint.severity.value,
                    'fact': str(fact),
                    'action': constraint.action,
                    'timestamp': self._get_timestamp()
                }
                self.violation_history.append(violation_record)
                
                logger.warning(f"Violação detectada: {constraint.name} - {fact}")
        
        # Determina se o fato deve ser permitido
        critical_violations = [c for c in violated_constraints 
                             if c.severity == ConstraintSeverity.CRITICAL and c.action == "block"]
        
        is_allowed = len(critical_violations) == 0
        
        return is_allowed, violated_constraints
    
    def check_constraints(self, fact: Fact) -> List[ConstraintViolation]:
        """
        Verifica se um fato viola alguma restrição e retorna lista de violações.
        
        Args:
            fact: Fato a ser verificado
            
        Returns:
            Lista de violações de restrição
        """
        if not self.enabled:
            return []
        
        violations = []
        
        for constraint in self.constraints:
            if constraint.violates(fact):
                # Registra a violação
                violation_record = {
                    'constraint_name': constraint.name,
                    'constraint_type': constraint.constraint_type.value,
                    'severity': constraint.severity.value,
                    'fact': str(fact),
                    'action': constraint.action,
                    'timestamp': self._get_timestamp()
                }
                self.violation_history.append(violation_record)
                
                # Cria objeto de violação
                violation = ConstraintViolation(
                    constraint=constraint,
                    fact=fact,
                    message=f"Violação da restrição {constraint.name}: {constraint.description}"
                )
                violation.constraint_name = constraint.name
                violations.append(violation)
                
                logger.warning(f"Violação detectada: {constraint.name} - {fact}")
        
        return violations
    
    def validate_fact_addition(self, fact: Fact) -> None:
        """
        Valida se um fato pode ser adicionado à ontologia.
        
        Args:
            fact: Fato a ser validado
            
        Raises:
            ConstraintViolation: Se o fato viola uma restrição crítica
        """
        is_allowed, violated_constraints = self.check_fact(fact)
        
        if not is_allowed:
            critical_constraint = next(
                (c for c in violated_constraints 
                 if c.severity == ConstraintSeverity.CRITICAL and c.action == "block"),
                None
            )
            
            if critical_constraint:
                raise ConstraintViolation(
                    critical_constraint, 
                    fact, 
                    f"Fato bloqueado por violação crítica: {critical_constraint.description}"
                )
    
    def get_constraints_by_type(self, constraint_type: ConstraintType) -> List[ConstraintRule]:
        """
        Retorna todas as restrições de um tipo específico.
        
        Args:
            constraint_type: Tipo de restrição
            
        Returns:
            Lista de restrições do tipo especificado
        """
        return [c for c in self.constraints if c.constraint_type == constraint_type]
    
    def get_violation_history(self, limit: int = None) -> List[Dict[str, Any]]:
        """
        Retorna o histórico de violações.
        
        Args:
            limit: Número máximo de violações a retornar
            
        Returns:
            Lista de registros de violação
        """
        if limit:
            return self.violation_history[-limit:]
        return self.violation_history.copy()
    
    def clear_violation_history(self) -> None:
        """Limpa o histórico de violações."""
        self.violation_history.clear()
        logger.info("Histórico de violações limpo")
    
    def enable(self) -> None:
        """Habilita o sistema de restrições."""
        self.enabled = True
        logger.info("Sistema de restrições habilitado")
    
    def disable(self) -> None:
        """Desabilita o sistema de restrições (use com cuidado!)."""
        self.enabled = False
        logger.warning("Sistema de restrições DESABILITADO - use com extremo cuidado!")
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Retorna estatísticas do sistema de restrições.
        
        Returns:
            Dicionário com estatísticas
        """
        constraint_types = {}
        for constraint in self.constraints:
            constraint_type = constraint.constraint_type.value
            constraint_types[constraint_type] = constraint_types.get(constraint_type, 0) + 1
        
        violation_types = {}
        for violation in self.violation_history:
            violation_type = violation['constraint_type']
            violation_types[violation_type] = violation_types.get(violation_type, 0) + 1
        
        return {
            'enabled': self.enabled,
            'total_constraints': len(self.constraints),
            'immutable_constraints': len([c for c in self.constraints if c.immutable]),
            'constraint_types': constraint_types,
            'total_violations': len(self.violation_history),
            'violation_types': violation_types
        }
    
    def _get_timestamp(self) -> str:
        """Retorna timestamp atual."""
        import datetime
        return datetime.datetime.now().isoformat()
    
    def __str__(self) -> str:
        return f"BoundedReasoning(constraints={len(self.constraints)}, enabled={self.enabled})"


def check_basic_safety(text: str) -> Dict[str, Any]:
    """Realiza uma checagem simples de segurança baseada em palavras-chave.

    Esta função expõe uma API reutilizável para verificações rápidas sem
    precisar instanciar ``BoundedReasoning`` completo. Atualmente bloqueia
    textos que contenham a palavra ``danger``.

    Args:
        text: conteúdo a ser avaliado.

    Returns:
        Dicionário com ``allowed`` indicando se o conteúdo é permitido e
        ``violations`` listando motivos identificados.
    """

    violations: List[str] = []
    if "danger" in text.lower():
        violations.append("dangerous_request")

    return {"allowed": not violations, "violations": violations}
