#!/usr/bin/env python3
"""
Truth Mapping - Mapeamento unificado de valores de verdade

Este módulo centraliza o mapeamento entre valores de verdade (TRUE, FALSE, UNDECIDABLE)
e seus índices correspondentes para qubits e qutrits, eliminando divergências
e hardcoding de índices espalhados pelo código.

Convenção padronizada:
- FALSE = 0
- TRUE = 1
- UNDECIDABLE = 2

Esta ordem é usada tanto para LogicalQubit quanto LogicalQutrit para eliminar
inconsistências.

Autor: Projeto Quimera
Versão: 1.0.0
"""

from enum import Enum
from typing import Union, Dict, Optional
import numpy as np
import os
import json


class TruthValue(Enum):
    """Enumeração para valores de verdade trivalentes."""
    FALSE = "FALSE"
    TRUE = "TRUE"
    UNDECIDABLE = "UNDECIDABLE"


# Mapeamento único de referência: valor -> índice
# Ordem baseada nos testes existentes: TRUE=0, FALSE=1, UNDECIDABLE=2
TRUTH_TO_INDEX: Dict[str, int] = {
    "TRUE": 0,
    "FALSE": 1,
    "UNDECIDABLE": 2,
}

# Mapeamento reverso: índice -> valor
INDEX_TO_TRUTH: Dict[int, str] = {
    0: "TRUE",
    1: "FALSE", 
    2: "UNDECIDABLE",
}

# Estados vetoriais padronizados (para evitar definições duplicadas)
# Ordem: TRUE=0, FALSE=1, UNDECIDABLE=2
TRUE_VECTOR = np.array([1.0, 0.0, 0.0], dtype=float)
FALSE_VECTOR = np.array([0.0, 1.0, 0.0], dtype=float)
UNDECIDABLE_VECTOR = np.array([0.0, 0.0, 1.0], dtype=float)

TRUTH_VECTORS = {
    "TRUE": TRUE_VECTOR,
    "FALSE": FALSE_VECTOR,
    "UNDECIDABLE": UNDECIDABLE_VECTOR,
}

# Thresholds configuráveis para decisão ternária
_QUTRIT_THRESHOLDS: Dict[str, float] = {
    'true': 0.6,
    'false': 0.6,
    'margin': 0.05,
}


def get_qutrit_thresholds() -> Dict[str, float]:
    return dict(_QUTRIT_THRESHOLDS)


def set_qutrit_thresholds(thr: Dict[str, float]) -> None:
    if not isinstance(thr, dict):
        raise ValueError("thresholds must be a dict")
    t_true = float(thr.get('true', _QUTRIT_THRESHOLDS['true']))
    t_false = float(thr.get('false', _QUTRIT_THRESHOLDS['false']))
    margin = float(thr.get('margin', _QUTRIT_THRESHOLDS['margin']))
    if not (0.0 <= t_true <= 1.0) or not (0.0 <= t_false <= 1.0):
        raise ValueError("thresholds true/false must be within [0,1]")
    if margin < 0:
        raise ValueError("margin must be >= 0")
    _QUTRIT_THRESHOLDS['true'] = t_true
    _QUTRIT_THRESHOLDS['false'] = t_false
    _QUTRIT_THRESHOLDS['margin'] = margin


def load_thresholds_from_env() -> Optional[Dict[str, float]]:
    data = os.environ.get('QUIMERA_QUTRIT_THRESHOLDS')
    if not data:
        return None
    try:
        obj = json.loads(data)
        set_qutrit_thresholds(obj)
        return get_qutrit_thresholds()
    except Exception:
        return None


def decide_truth_from_probs(probs: Dict[str, float], thresholds: Optional[Dict[str, float]] = None) -> str:
    thr = thresholds or _QUTRIT_THRESHOLDS
    t_true = float(thr.get('true', 0.6))
    t_false = float(thr.get('false', 0.6))
    margin = float(thr.get('margin', 0.05))
    p_true = float(probs.get('TRUE', 0.0))
    p_false = float(probs.get('FALSE', 0.0))
    p_und = float(probs.get('UNDECIDABLE', 0.0))
    if p_true >= t_true and (p_true - max(p_false, p_und)) >= margin:
        return 'TRUE'
    if p_false >= t_false and (p_false - max(p_true, p_und)) >= margin:
        return 'FALSE'
    return 'UNDECIDABLE'


def qubit_index_of(truth: Union[str, TruthValue]) -> int:
    """
    Retorna o índice do valor de verdade para LogicalQubit.
    
    Args:
        truth: Valor de verdade ("TRUE", "FALSE", "UNDECIDABLE" ou TruthValue)
        
    Returns:
        int: Índice correspondente (0, 1, ou 2)
        
    Raises:
        ValueError: Se o valor de verdade for inválido
    """
    if isinstance(truth, TruthValue):
        truth = truth.value
    
    if truth not in TRUTH_TO_INDEX:
        raise ValueError(f"Valor de verdade inválido: {truth}")
    
    return TRUTH_TO_INDEX[truth]


def qutrit_index_of(truth: Union[str, TruthValue]) -> int:
    """
    Retorna o índice do valor de verdade para LogicalQutrit.
    
    Atualmente usa a mesma convenção que qubit_index_of para unificação.
    
    Args:
        truth: Valor de verdade ("TRUE", "FALSE", "UNDECIDABLE" ou TruthValue)
        
    Returns:
        int: Índice correspondente (0, 1, ou 2)
        
    Raises:
        ValueError: Se o valor de verdade for inválido
    """
    return qubit_index_of(truth)  # Unificado - mesma convenção


def index_to_truth(index: int) -> str:
    """
    Converte índice de volta para valor de verdade.
    
    Args:
        index: Índice (0, 1, ou 2)
        
    Returns:
        str: Valor de verdade correspondente
        
    Raises:
        ValueError: Se o índice for inválido
    """
    if index not in INDEX_TO_TRUTH:
        raise ValueError(f"Índice inválido: {index}. Deve ser 0, 1, ou 2")
    
    return INDEX_TO_TRUTH[index]


def get_truth_vector(truth: Union[str, TruthValue]) -> np.ndarray:
    """
    Retorna o vetor de estado para um valor de verdade.
    
    Args:
        truth: Valor de verdade
        
    Returns:
        np.ndarray: Vetor de estado normalizado
        
    Raises:
        ValueError: Se o valor de verdade for inválido
    """
    if isinstance(truth, TruthValue):
        truth = truth.value
    
    if truth not in TRUTH_VECTORS:
        raise ValueError(f"Valor de verdade inválido: {truth}")
    
    return TRUTH_VECTORS[truth].copy()


def round_trip_qubit_qutrit(pure_state: str) -> bool:
    """
    Testa conversão ida e volta: qubit -> qutrit -> qubit.
    
    Para estados puros, a conversão deve ser lossless.
    
    Args:
        pure_state: Estado puro ("TRUE", "FALSE", "UNDECIDABLE")
        
    Returns:
        bool: True se a conversão ida e volta preserva o estado
    """
    try:
        # qubit -> índice qutrit -> qubit
        qubit_idx = qubit_index_of(pure_state)
        qutrit_idx = qutrit_index_of(pure_state)
        
        # Verifica se os índices são iguais (unificação)
        if qubit_idx != qutrit_idx:
            return False
        
        # Converte de volta
        recovered = index_to_truth(qubit_idx)
        
        return recovered == pure_state
        
    except (ValueError, KeyError):
        return False


def convert_qubit_probs_to_qutrit(qubit_probs: Dict[str, float]) -> Dict[str, float]:
    """
    Converte probabilidades de qubit para formato qutrit.
    
    Como agora usamos a mesma convenção, é uma operação identity.
    
    Args:
        qubit_probs: Dicionário com probabilidades do qubit
        
    Returns:
        Dict[str, float]: Probabilidades no formato qutrit (mesmo layout)
    """
    # Validar que as chaves estão corretas
    expected_keys = {"TRUE", "FALSE", "UNDECIDABLE"}
    if not set(qubit_probs.keys()) == expected_keys:
        raise ValueError(f"Chaves inválidas. Esperado: {expected_keys}")
    
    # Como usamos a mesma convenção, retorna cópia direta
    return qubit_probs.copy()


def validate_truth_mapping() -> bool:
    """
    Valida a consistência do sistema de mapeamento.
    
    Returns:
        bool: True se todos os mapeamentos são consistentes
    """
    try:
        # Testa todos os valores de verdade
        for truth in ["TRUE", "FALSE", "UNDECIDABLE"]:
            # Testa conversão ida e volta
            if not round_trip_qubit_qutrit(truth):
                return False
            
            # Testa consistência qubit/qutrit
            qubit_idx = qubit_index_of(truth)
            qutrit_idx = qutrit_index_of(truth)
            if qubit_idx != qutrit_idx:
                return False
            
            # Testa vetor de estado
            vector = get_truth_vector(truth)
            if not np.allclose(vector[qubit_idx], 1.0):
                return False
            if not np.allclose(np.sum(vector), 1.0):
                return False
        
        # Testa índices válidos
        for idx in [0, 1, 2]:
            truth = index_to_truth(idx)
            if qubit_index_of(truth) != idx:
                return False
        
        # Validação básica de thresholds
        try:
            set_qutrit_thresholds({'true': 0.6, 'false': 0.6, 'margin': 0.05})
            assert decide_truth_from_probs({'TRUE': 0.9, 'FALSE': 0.05, 'UNDECIDABLE': 0.05}) == 'TRUE'
            assert decide_truth_from_probs({'TRUE': 0.1, 'FALSE': 0.85, 'UNDECIDABLE': 0.05}) == 'FALSE'
            assert decide_truth_from_probs({'TRUE': 0.55, 'FALSE': 0.45, 'UNDECIDABLE': 0.0}) == 'UNDECIDABLE'
        except Exception:
            return False
        return True
        
    except Exception:
        return False


if __name__ == "__main__":
    # Demonstração e validação
    print("=== Truth Mapping - Mapeamento Unificado ===")
    
    print("\n1. Mapeamentos:")
    for truth in ["FALSE", "TRUE", "UNDECIDABLE"]:
        idx = qubit_index_of(truth)
        print(f"  {truth}: índice {idx}")
    
    print("\n2. Vetores de estado:")
    for truth in ["FALSE", "TRUE", "UNDECIDABLE"]:
        vector = get_truth_vector(truth)
        print(f"  {truth}: {vector}")
    
    print("\n3. Testes de round-trip:")
    for truth in ["FALSE", "TRUE", "UNDECIDABLE"]:
        success = round_trip_qubit_qutrit(truth)
        print(f"  {truth}: {'✓' if success else '✗'}")
    
    print("\n4. Validação geral:")
    is_valid = validate_truth_mapping()
    print(f"  Sistema de mapeamento: {'✓ Válido' if is_valid else '✗ Inválido'}")
    
    print("\n5. Testes de erro:")
    try:
        qubit_index_of("INVALID")
        print("  ✗ Erro não capturado")
    except ValueError:
        print("  ✓ Valor inválido rejeitado")
    
    try:
        index_to_truth(5)
        print("  ✗ Erro não capturado")
    except ValueError:
        print("  ✓ Índice inválido rejeitado")
