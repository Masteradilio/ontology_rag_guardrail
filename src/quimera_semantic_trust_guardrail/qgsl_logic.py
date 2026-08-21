"""
QGSL Logic - Lógica Simbólica Quântica Trivalente
==================================================

Implementa a lógica de 3 valores (TRUE/FALSE/UNDECIDABLE) que é o
diferencial do Ontology RAG Guardrail em relação a guardrails convencionais.

O estado UNDECIDABLE permite:
- Evitar falsos positivos em detecção de ameaças
- Sinalizar incerteza para revisão humana
- Graduar confiança em validações
"""

from __future__ import annotations
from enum import Enum
from dataclasses import dataclass
from typing import Optional, Dict, Any, List
import numpy as np


class TruthValue(Enum):
    """Valores de verdade trivalentes"""
    TRUE = "TRUE"
    FALSE = "FALSE"
    UNDECIDABLE = "UNDECIDABLE"
    
    def __bool__(self) -> bool:
        """TRUE é truthy, FALSE e UNDECIDABLE são falsy"""
        return self == TruthValue.TRUE
    
    def is_certain(self) -> bool:
        """Retorna True se o valor é certo (TRUE ou FALSE)"""
        return self != TruthValue.UNDECIDABLE
    
    @classmethod
    def from_probability(cls, prob: float, threshold: float = 0.7) -> TruthValue:
        """
        Converte probabilidade em valor de verdade
        
        Args:
            prob: Probabilidade entre 0.0 e 1.0
            threshold: Limiar para certeza (default 0.7)
        """
        if prob >= threshold:
            return cls.TRUE
        elif prob <= (1 - threshold):
            return cls.FALSE
        else:
            return cls.UNDECIDABLE


@dataclass
class QGSLState:
    """
    Estado QGSL completo com probabilidades
    
    Representa um estado lógico quântico-inspirado com:
    - Vetor de probabilidades [P(TRUE), P(FALSE), P(UNDECIDABLE)]
    - Valor colapsado (mais provável)
    - Confiança na decisão
    """
    probabilities: np.ndarray  # [P(T), P(F), P(U)]
    collapsed_value: TruthValue
    confidence: float
    metadata: Optional[Dict[str, Any]] = None
    
    def __post_init__(self):
        # Normaliza probabilidades
        total = np.sum(self.probabilities)
        if total > 0:
            self.probabilities = self.probabilities / total
    
    @classmethod
    def create(
        cls,
        true_prob: float = 0.0,
        false_prob: float = 0.0,
        undecidable_prob: float = 0.0,
        metadata: Optional[Dict] = None
    ) -> QGSLState:
        """Cria estado a partir de probabilidades individuais"""
        probs = np.array([true_prob, false_prob, undecidable_prob])
        
        # Normaliza
        total = np.sum(probs)
        if total > 0:
            probs = probs / total
        else:
            probs = np.array([0.0, 0.0, 1.0])  # Default: UNDECIDABLE
        
        # Colapsa para valor mais provável
        idx = np.argmax(probs)
        values = [TruthValue.TRUE, TruthValue.FALSE, TruthValue.UNDECIDABLE]
        collapsed = values[idx]
        confidence = float(probs[idx])
        
        return cls(
            probabilities=probs,
            collapsed_value=collapsed,
            confidence=confidence,
            metadata=metadata
        )
    
    @classmethod
    def from_bool(cls, value: bool, confidence: float = 1.0) -> QGSLState:
        """Cria estado a partir de booleano"""
        if value:
            probs = np.array([confidence, 1-confidence, 0.0])
            collapsed = TruthValue.TRUE
        else:
            probs = np.array([1-confidence, confidence, 0.0])
            collapsed = TruthValue.FALSE
        
        return cls(
            probabilities=probs,
            collapsed_value=collapsed,
            confidence=confidence
        )
    
    @classmethod
    def undecidable(cls, true_lean: float = 0.5) -> QGSLState:
        """Cria estado UNDECIDABLE com tendência opcional"""
        probs = np.array([true_lean * 0.4, (1-true_lean) * 0.4, 0.6])
        return cls(
            probabilities=probs,
            collapsed_value=TruthValue.UNDECIDABLE,
            confidence=0.6
        )
    
    def is_true(self) -> bool:
        return self.collapsed_value == TruthValue.TRUE
    
    def is_false(self) -> bool:
        return self.collapsed_value == TruthValue.FALSE
    
    def is_undecidable(self) -> bool:
        return self.collapsed_value == TruthValue.UNDECIDABLE
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "value": self.collapsed_value.value,
            "confidence": self.confidence,
            "probabilities": {
                "TRUE": float(self.probabilities[0]),
                "FALSE": float(self.probabilities[1]),
                "UNDECIDABLE": float(self.probabilities[2])
            },
            "metadata": self.metadata
        }


class LogicalQutrit:
    """
    Qutrit Lógico - Operações sobre estados trivalentes
    
    Implementa operações lógicas (AND, OR, NOT) sobre estados QGSL,
    preservando a semântica trivalente.
    """
    
    @staticmethod
    def NOT(state: QGSLState) -> QGSLState:
        """
        Negação lógica trivalente
        
        NOT(TRUE) = FALSE
        NOT(FALSE) = TRUE
        NOT(UNDECIDABLE) = UNDECIDABLE
        """
        # Swap TRUE e FALSE probabilities
        new_probs = np.array([
            state.probabilities[1],  # FALSE -> TRUE
            state.probabilities[0],  # TRUE -> FALSE
            state.probabilities[2]   # UNDECIDABLE mantém
        ])
        
        return QGSLState.create(
            true_prob=new_probs[0],
            false_prob=new_probs[1],
            undecidable_prob=new_probs[2]
        )
    
    @staticmethod
    def AND(state1: QGSLState, state2: QGSLState) -> QGSLState:
        """
        Conjunção lógica trivalente (Kleene)
        
        TRUE AND TRUE = TRUE
        TRUE AND FALSE = FALSE
        TRUE AND UNDECIDABLE = UNDECIDABLE
        FALSE AND anything = FALSE
        UNDECIDABLE AND UNDECIDABLE = UNDECIDABLE
        """
        # Tabela Kleene AND
        # Se algum é FALSE -> FALSE
        # Se ambos TRUE -> TRUE
        # Senão -> UNDECIDABLE
        
        p1_t, p1_f, p1_u = state1.probabilities
        p2_t, p2_f, p2_u = state2.probabilities
        
        # P(FALSE) = P(s1=F) + P(s2=F) - P(ambos=F)
        p_false = p1_f + p2_f - (p1_f * p2_f)
        
        # P(TRUE) = P(ambos=T)
        p_true = p1_t * p2_t
        
        # P(UNDECIDABLE) = resto
        p_undec = max(0, 1 - p_false - p_true)
        
        return QGSLState.create(
            true_prob=p_true,
            false_prob=p_false,
            undecidable_prob=p_undec
        )
    
    @staticmethod
    def OR(state1: QGSLState, state2: QGSLState) -> QGSLState:
        """
        Disjunção lógica trivalente (Kleene)
        
        TRUE OR anything = TRUE
        FALSE OR FALSE = FALSE
        FALSE OR UNDECIDABLE = UNDECIDABLE
        """
        p1_t, p1_f, p1_u = state1.probabilities
        p2_t, p2_f, p2_u = state2.probabilities
        
        # P(TRUE) = P(s1=T) + P(s2=T) - P(ambos=T)
        p_true = p1_t + p2_t - (p1_t * p2_t)
        
        # P(FALSE) = P(ambos=F)
        p_false = p1_f * p2_f
        
        # P(UNDECIDABLE) = resto
        p_undec = max(0, 1 - p_true - p_false)
        
        return QGSLState.create(
            true_prob=p_true,
            false_prob=p_false,
            undecidable_prob=p_undec
        )
    
    @staticmethod
    def IMPLIES(state1: QGSLState, state2: QGSLState) -> QGSLState:
        """
        Implicação lógica: A -> B é equivalente a NOT(A) OR B
        """
        not_s1 = LogicalQutrit.NOT(state1)
        return LogicalQutrit.OR(not_s1, state2)
    
    @staticmethod
    def aggregate(states: List[QGSLState], operator: str = "AND") -> QGSLState:
        """
        Agrega múltiplos estados com operador especificado
        
        Args:
            states: Lista de estados QGSL
            operator: "AND" ou "OR"
        """
        if not states:
            return QGSLState.undecidable()
        
        if len(states) == 1:
            return states[0]
        
        op_func = LogicalQutrit.AND if operator == "AND" else LogicalQutrit.OR
        
        result = states[0]
        for state in states[1:]:
            result = op_func(result, state)
        
        return result


# Constantes úteis
QGSL_TRUE = QGSLState.from_bool(True, 1.0)
QGSL_FALSE = QGSLState.from_bool(False, 1.0)
QGSL_UNDECIDABLE = QGSLState.undecidable()
