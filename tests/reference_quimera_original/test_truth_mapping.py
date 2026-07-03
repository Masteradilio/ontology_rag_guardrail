#!/usr/bin/env python3
"""
Testes para o módulo truth_mapping.py

Este arquivo testa a unificação da ordem T/F/U entre qubit e qutrit,
conforme especificado na Tarefa 1 do TODO_correcoes_melhorias.md.

Autor: Projeto Quimera
Versão: 1.0.0
"""

import pytest
import numpy as np
import sys
import os

# Adiciona o diretório core ao path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'core'))

from truth_mapping import (
    TruthValue,
    TRUTH_TO_INDEX,
    INDEX_TO_TRUTH,
    TRUTH_VECTORS,
    qubit_index_of,
    qutrit_index_of,
    index_to_truth,
    get_truth_vector,
    round_trip_qubit_qutrit,
    convert_qubit_probs_to_qutrit,
    validate_truth_mapping
)


class TestTruthMappingConstants:
    """Testa as constantes e mapeamentos básicos."""
    
    def test_truth_to_index_mapping(self):
        """Testa o mapeamento de valores de verdade para índices."""
        assert TRUTH_TO_INDEX["TRUE"] == 0
        assert TRUTH_TO_INDEX["FALSE"] == 1
        assert TRUTH_TO_INDEX["UNDECIDABLE"] == 2
    
    def test_index_to_truth_mapping(self):
        """Testa o mapeamento reverso de índices para valores de verdade."""
        assert INDEX_TO_TRUTH[0] == "TRUE"
        assert INDEX_TO_TRUTH[1] == "FALSE"
        assert INDEX_TO_TRUTH[2] == "UNDECIDABLE"
    
    def test_truth_vectors_consistency(self):
        """Testa se os vetores de verdade estão corretos."""
        # TRUE = [1, 0, 0]
        assert np.allclose(TRUTH_VECTORS["TRUE"], [1.0, 0.0, 0.0])
        # FALSE = [0, 1, 0]
        assert np.allclose(TRUTH_VECTORS["FALSE"], [0.0, 1.0, 0.0])
        # UNDECIDABLE = [0, 0, 1]
        assert np.allclose(TRUTH_VECTORS["UNDECIDABLE"], [0.0, 0.0, 1.0])
    
    def test_truth_vectors_normalized(self):
        """Testa se os vetores de verdade estão normalizados."""
        for truth, vector in TRUTH_VECTORS.items():
            assert np.allclose(np.sum(vector), 1.0), f"Vetor {truth} não está normalizado"


class TestIndexHelpers:
    """Testa as funções helper de mapeamento de índices."""
    
    def test_qubit_index_of_string(self):
        """Testa qubit_index_of com strings."""
        assert qubit_index_of("TRUE") == 0
        assert qubit_index_of("FALSE") == 1
        assert qubit_index_of("UNDECIDABLE") == 2
    
    def test_qubit_index_of_enum(self):
        """Testa qubit_index_of com TruthValue enum."""
        assert qubit_index_of(TruthValue.TRUE) == 0
        assert qubit_index_of(TruthValue.FALSE) == 1
        assert qubit_index_of(TruthValue.UNDECIDABLE) == 2
    
    def test_qutrit_index_of_string(self):
        """Testa qutrit_index_of com strings."""
        assert qutrit_index_of("TRUE") == 0
        assert qutrit_index_of("FALSE") == 1
        assert qutrit_index_of("UNDECIDABLE") == 2
    
    def test_qutrit_index_of_enum(self):
        """Testa qutrit_index_of com TruthValue enum."""
        assert qutrit_index_of(TruthValue.TRUE) == 0
        assert qutrit_index_of(TruthValue.FALSE) == 1
        assert qutrit_index_of(TruthValue.UNDECIDABLE) == 2
    
    def test_qubit_qutrit_consistency(self):
        """Testa se qubit e qutrit usam a mesma convenção (unificação)."""
        for truth in ["FALSE", "TRUE", "UNDECIDABLE"]:
            qubit_idx = qubit_index_of(truth)
            qutrit_idx = qutrit_index_of(truth)
            assert qubit_idx == qutrit_idx, f"Inconsistência para {truth}: qubit={qubit_idx}, qutrit={qutrit_idx}"
    
    def test_index_to_truth_valid(self):
        """Testa index_to_truth com índices válidos."""
        assert index_to_truth(0) == "TRUE"
        assert index_to_truth(1) == "FALSE"
        assert index_to_truth(2) == "UNDECIDABLE"
    
    def test_index_to_truth_invalid(self):
        """Testa index_to_truth com índices inválidos."""
        with pytest.raises(ValueError, match="Índice inválido"):
            index_to_truth(3)
        with pytest.raises(ValueError, match="Índice inválido"):
            index_to_truth(-1)
    
    def test_qubit_index_of_invalid(self):
        """Testa qubit_index_of com valores inválidos."""
        with pytest.raises(ValueError, match="Valor de verdade inválido"):
            qubit_index_of("INVALID")
        with pytest.raises(ValueError, match="Valor de verdade inválido"):
            qubit_index_of("maybe")


class TestVectorHelpers:
    """Testa as funções helper de vetores de estado."""
    
    def test_get_truth_vector_string(self):
        """Testa get_truth_vector com strings."""
        true_vec = get_truth_vector("TRUE")
        false_vec = get_truth_vector("FALSE")
        undecidable_vec = get_truth_vector("UNDECIDABLE")
        
        assert np.allclose(true_vec, [1.0, 0.0, 0.0])
        assert np.allclose(false_vec, [0.0, 1.0, 0.0])
        assert np.allclose(undecidable_vec, [0.0, 0.0, 1.0])
    
    def test_get_truth_vector_enum(self):
        """Testa get_truth_vector com TruthValue enum."""
        true_vec = get_truth_vector(TruthValue.TRUE)
        false_vec = get_truth_vector(TruthValue.FALSE)
        undecidable_vec = get_truth_vector(TruthValue.UNDECIDABLE)
        
        assert np.allclose(true_vec, [1.0, 0.0, 0.0])
        assert np.allclose(false_vec, [0.0, 1.0, 0.0])
        assert np.allclose(undecidable_vec, [0.0, 0.0, 1.0])
    
    def test_get_truth_vector_copy(self):
        """Testa se get_truth_vector retorna cópias independentes."""
        vec1 = get_truth_vector("TRUE")
        vec2 = get_truth_vector("TRUE")
        
        # Modifica uma cópia
        vec1[0] = 0.5
        
        # A outra não deve ser afetada
        assert not np.allclose(vec1, vec2)
        assert np.allclose(vec2, [1.0, 0.0, 0.0])
    
    def test_get_truth_vector_invalid(self):
        """Testa get_truth_vector com valores inválidos."""
        with pytest.raises(ValueError, match="Valor de verdade inválido"):
            get_truth_vector("INVALID")


class TestRoundTripConversion:
    """Testa as conversões ida e volta (round-trip)."""
    
    def test_round_trip_pure_states(self):
        """Testa round-trip para estados puros."""
        for truth in ["FALSE", "TRUE", "UNDECIDABLE"]:
            assert round_trip_qubit_qutrit(truth), f"Round-trip falhou para {truth}"
    
    def test_round_trip_consistency(self):
        """Testa consistência do round-trip."""
        for truth in ["FALSE", "TRUE", "UNDECIDABLE"]:
            # qubit -> índice -> truth
            qubit_idx = qubit_index_of(truth)
            recovered_from_qubit = index_to_truth(qubit_idx)
            assert recovered_from_qubit == truth
            
            # qutrit -> índice -> truth
            qutrit_idx = qutrit_index_of(truth)
            recovered_from_qutrit = index_to_truth(qutrit_idx)
            assert recovered_from_qutrit == truth
            
            # qubit e qutrit devem dar o mesmo resultado
            assert qubit_idx == qutrit_idx
    
    def test_round_trip_invalid(self):
        """Testa round-trip com valores inválidos."""
        assert not round_trip_qubit_qutrit("INVALID")
        assert not round_trip_qubit_qutrit("maybe")


class TestProbabilityConversion:
    """Testa conversão de probabilidades entre qubit e qutrit."""
    
    def test_convert_qubit_probs_to_qutrit_valid(self):
        """Testa conversão válida de probabilidades."""
        qubit_probs = {
            "TRUE": 0.5,
            "FALSE": 0.3,
            "UNDECIDABLE": 0.2
        }
        
        qutrit_probs = convert_qubit_probs_to_qutrit(qubit_probs)
        
        # Como usamos a mesma convenção, deve ser idêntico
        assert qutrit_probs == qubit_probs
        
        # Mas deve ser uma cópia independente
        qubit_probs["TRUE"] = 0.8
        assert qutrit_probs["TRUE"] == 0.5
    
    def test_convert_qubit_probs_to_qutrit_invalid_keys(self):
        """Testa conversão com chaves inválidas."""
        invalid_probs = {
            "TRUE": 0.5,
            "FALSE": 0.3,
            "MAYBE": 0.2  # Chave inválida
        }
        
        with pytest.raises(ValueError, match="Chaves inválidas"):
            convert_qubit_probs_to_qutrit(invalid_probs)
    
    def test_convert_qubit_probs_to_qutrit_missing_keys(self):
        """Testa conversão com chaves faltando."""
        incomplete_probs = {
            "TRUE": 0.5,
            "FALSE": 0.5
            # UNDECIDABLE está faltando
        }
        
        with pytest.raises(ValueError, match="Chaves inválidas"):
            convert_qubit_probs_to_qutrit(incomplete_probs)


class TestSystemValidation:
    """Testa a validação geral do sistema de mapeamento."""
    
    def test_validate_truth_mapping_success(self):
        """Testa se a validação geral passa."""
        assert validate_truth_mapping(), "Validação do sistema de mapeamento falhou"
    
    def test_mapping_bidirectional_consistency(self):
        """Testa consistência bidirecional dos mapeamentos."""
        # Testa todos os valores de verdade
        for truth in ["FALSE", "TRUE", "UNDECIDABLE"]:
            # truth -> index -> truth
            idx = qubit_index_of(truth)
            recovered = index_to_truth(idx)
            assert recovered == truth
        
        # Testa todos os índices
        for idx in [0, 1, 2]:
            # index -> truth -> index
            truth = index_to_truth(idx)
            recovered = qubit_index_of(truth)
            assert recovered == idx
    
    def test_vector_index_consistency(self):
        """Testa consistência entre vetores e índices."""
        for truth in ["FALSE", "TRUE", "UNDECIDABLE"]:
            idx = qubit_index_of(truth)
            vector = get_truth_vector(truth)
            
            # O vetor deve ter 1.0 na posição do índice
            assert np.allclose(vector[idx], 1.0), f"Inconsistência para {truth}: índice {idx}, vetor {vector}"
            
            # E 0.0 nas outras posições
            for i in range(3):
                if i != idx:
                    assert np.allclose(vector[i], 0.0), f"Inconsistência para {truth}: posição {i} deveria ser 0.0"


class TestEdgeCases:
    """Testa casos extremos e situações especiais."""
    
    def test_case_sensitivity(self):
        """Testa se as funções são case-sensitive."""
        # Deve funcionar com maiúsculas
        assert qubit_index_of("TRUE") == 0
        assert qubit_index_of("FALSE") == 1
        
        # Deve falhar com minúsculas (case-sensitive)
        with pytest.raises(ValueError):
            qubit_index_of("true")
        with pytest.raises(ValueError):
            qubit_index_of("false")
    
    def test_enum_vs_string_consistency(self):
        """Testa consistência entre enum e string."""
        for truth_str, truth_enum in [("FALSE", TruthValue.FALSE), 
                                      ("TRUE", TruthValue.TRUE), 
                                      ("UNDECIDABLE", TruthValue.UNDECIDABLE)]:
            assert qubit_index_of(truth_str) == qubit_index_of(truth_enum)
            assert qutrit_index_of(truth_str) == qutrit_index_of(truth_enum)
            assert np.allclose(get_truth_vector(truth_str), get_truth_vector(truth_enum))


if __name__ == "__main__":
    # Executa os testes quando o arquivo é executado diretamente
    pytest.main([__file__, "-v"])