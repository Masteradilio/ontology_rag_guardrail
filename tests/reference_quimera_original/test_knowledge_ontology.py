#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Testes Unitários para Knowledge Ontology Module - Projeto Quimera

Este arquivo contém testes abrangentes para o sistema de ontologia de conhecimento,
validando todas as funcionalidades principais da classe KnowledgeOntology.

Autor: Projeto Quimera
Versão: 1.0
"""

import pytest
import numpy as np
import warnings

# Importa os módulos a serem testados
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'core'))

try:
    from core.qgsl_core import LogicalQubit
    from core.knowledge_ontology import KnowledgeOntology, Fact, create_simple_ontology, create_medical_ontology
except ImportError:
    from qgsl_core import LogicalQubit
    from knowledge_ontology import KnowledgeOntology, Fact, create_simple_ontology, create_medical_ontology


class TestFact:
    """Testes para a classe Fact."""
    
    def test_fact_creation(self):
        """Testa criação básica de um fato."""
        state = LogicalQubit('TRUE')
        fact = Fact(
            fact_id="test_fact_1",
            subject="Sócrates",
            relation="é",
            object="humano",
            state=state
        )
        
        assert fact.fact_id == "test_fact_1"
        assert fact.subject == "Sócrates"
        assert fact.relation == "é"
        assert fact.object == "humano"
        assert fact.state == state
        assert fact.metadata == {}
    
    def test_fact_with_metadata(self):
        """Testa criação de fato com metadados."""
        state = LogicalQubit('TRUE')
        metadata = {"source": "knowledge_base", "confidence": 0.9}
        
        fact = Fact(
            fact_id="test_fact_2",
            subject="Python",
            relation="é",
            object="linguagem",
            state=state,
            metadata=metadata
        )
        
        assert fact.metadata == metadata
        assert fact.metadata["source"] == "knowledge_base"
        assert fact.metadata["confidence"] == 0.9


class TestKnowledgeOntology:
    """Testes para a classe KnowledgeOntology."""
    
    def setup_method(self):
        """Configuração executada antes de cada teste."""
        self.ontology = KnowledgeOntology()
    
    def test_initialization(self):
        """Testa inicialização da ontologia."""
        assert len(self.ontology) == 0
        assert self.ontology.graph.number_of_nodes() == 0
        assert self.ontology.graph.number_of_edges() == 0
        assert self.ontology._fact_counter == 0
    
    def test_add_node(self):
        """Testa adição de nós."""
        self.ontology.add_node("Sócrates", "person", age=70)
        
        assert self.ontology.graph.has_node("Sócrates")
        assert self.ontology.graph.nodes["Sócrates"]["type"] == "person"
        assert self.ontology.graph.nodes["Sócrates"]["age"] == 70
    
    def test_add_fact_basic(self):
        """Testa adição básica de fatos."""
        fact_id = self.ontology.add_fact("Sócrates", "é", "humano")
        
        assert fact_id in self.ontology.facts
        assert len(self.ontology) == 1
        assert self.ontology.graph.number_of_nodes() == 2
        assert self.ontology.graph.number_of_edges() == 1
        
        fact = self.ontology.get_fact(fact_id)
        assert fact.subject == "Sócrates"
        assert fact.relation == "é"
        assert fact.object == "humano"
        assert fact.state.collapse() == "TRUE"
    
    def test_add_fact_with_logical_qubit(self):
        """Testa adição de fato com LogicalQubit."""
        state = LogicalQubit([0.7, 0.2, 0.1])
        fact_id = self.ontology.add_fact("paciente", "tem", "febre", state)
        
        fact = self.ontology.get_fact(fact_id)
        assert np.allclose(fact.state.state_vector, [0.7, 0.2, 0.1])
    
    def test_add_fact_with_list_state(self):
        """Testa adição de fato com estado como lista."""
        fact_id = self.ontology.add_fact("diagnóstico", "indica", "gripe", [0.6, 0.3, 0.1])
        
        fact = self.ontology.get_fact(fact_id)
        assert np.allclose(fact.state.state_vector, [0.6, 0.3, 0.1])
    
    def test_add_fact_with_metadata(self):
        """Testa adição de fato com metadados."""
        metadata = {"source": "medical_db", "timestamp": "2024-01-01"}
        fact_id = self.ontology.add_fact(
            "paciente", "apresenta", "sintoma", "TRUE", metadata
        )
        
        fact = self.ontology.get_fact(fact_id)
        assert fact.metadata == metadata

    def test_multiple_facts_between_same_nodes(self):
        """Garante que múltiplos fatos entre os mesmos nós não se sobrescrevem."""
        fact1 = self.ontology.add_fact("A", "rel1", "B", "TRUE")
        fact2 = self.ontology.add_fact("A", "rel2", "B", "TRUE")

        related = self.ontology.query_by_node("A", "out")
        fact_ids = {f.fact_id for f in related}

        assert fact_ids == {fact1, fact2}
    
    def test_add_fact_invalid_parameters(self):
        """Testa adição de fato com parâmetros inválidos."""
        with pytest.raises(ValueError):
            self.ontology.add_fact("", "é", "humano")
        
        with pytest.raises(ValueError):
            self.ontology.add_fact("Sócrates", "", "humano")
        
        with pytest.raises(ValueError):
            self.ontology.add_fact("Sócrates", "é", "")
    
    def test_update_fact_state(self):
        """Testa atualização do estado de um fato."""
        fact_id = self.ontology.add_fact("hipótese", "é", "verdadeira", "TRUE")
        
        # Atualiza para FALSE
        success = self.ontology.update_fact_state(fact_id, "FALSE", emit_warning=False)
        assert success
        
        fact = self.ontology.get_fact(fact_id)
        assert fact.state.collapse() == "FALSE"
        
        # Atualiza para superposição (que pode resultar em UNDECIDABLE)
        success = self.ontology.update_fact_state(fact_id, [0.3, 0.3, 0.4], emit_warning=False)
        assert success
        
        fact = self.ontology.get_fact(fact_id)
        assert np.allclose(fact.state.state_vector, [0.3, 0.3, 0.4])
    
    def test_update_nonexistent_fact(self):
        """Testa atualização de fato inexistente."""
        with pytest.raises(KeyError):
            self.ontology.update_fact_state("fake_id", "TRUE")
    
    def test_handle_contradiction(self):
        """Testa tratamento de contradições."""
        fact_id = self.ontology.add_fact("proposição", "é", "válida", "TRUE")
        
        # Testa com warning habilitado
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            self.ontology.update_fact_state(fact_id, "UNDECIDABLE", emit_warning=True)
            
            assert len(w) == 1
            assert "Contradição detectada" in str(w[0].message)
        
        # Verifica se os metadados de contradição foram adicionados
        fact = self.ontology.get_fact(fact_id)
        assert fact.metadata.get('contradiction_detected') is True
        assert 'contradiction_timestamp' in fact.metadata
        
        # Testa sem warning (para uso em testes)
        fact_id2 = self.ontology.add_fact("C", "é", "D", "TRUE")
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            self.ontology.update_fact_state(fact_id2, "UNDECIDABLE", emit_warning=False)
            
            # Verifica que nenhum warning foi emitido
            assert len(w) == 0
        
        # Mas os metadados ainda devem ser adicionados
        fact2 = self.ontology.get_fact(fact_id2)
        assert fact2.metadata.get('contradiction_detected') is True
    
    def test_query_basic(self):
        """Testa consultas básicas."""
        # Adiciona alguns fatos
        self.ontology.add_fact("Sócrates", "é", "humano", "TRUE")
        self.ontology.add_fact("Platão", "é", "humano", "TRUE")
        self.ontology.add_fact("Sócrates", "ensina", "Platão", "TRUE")
        self.ontology.add_fact("gato", "é", "animal", "FALSE")
        
        # Consulta por sujeito
        results = self.ontology.query({"subject": "Sócrates"})
        assert len(results) == 2
        
        # Consulta por relação
        results = self.ontology.query({"relation": "é"})
        assert len(results) == 3
        
        # Consulta por objeto
        results = self.ontology.query({"object": "humano"})
        assert len(results) == 2
        
        # Consulta por tipo de estado
        results = self.ontology.query({"state_type": "FALSE"})
        assert len(results) == 1
    
    def test_query_combined_criteria(self):
        """Testa consultas com múltiplos critérios."""
        self.ontology.add_fact("Sócrates", "é", "humano", "TRUE")
        self.ontology.add_fact("Sócrates", "é", "filósofo", "TRUE")
        self.ontology.add_fact("Platão", "é", "humano", "TRUE")
        
        # Consulta combinada
        results = self.ontology.query({
            "subject": "Sócrates",
            "relation": "é",
            "state_type": "TRUE"
        })
        assert len(results) == 2
        
        # Consulta mais específica
        results = self.ontology.query({
            "subject": "Sócrates",
            "relation": "é",
            "object": "humano"
        })
        assert len(results) == 1
    
    def test_query_by_node(self):
        """Testa consultas por nó."""
        self.ontology.add_fact("Sócrates", "é", "humano", "TRUE")
        self.ontology.add_fact("Sócrates", "ensina", "Platão", "TRUE")
        self.ontology.add_fact("Aristóteles", "estuda_com", "Sócrates", "TRUE")
        
        # Consulta todas as relações
        results = self.ontology.query_by_node("Sócrates", "both")
        assert len(results) == 3
        
        # Consulta apenas saídas
        results = self.ontology.query_by_node("Sócrates", "out")
        assert len(results) == 2
        
        # Consulta apenas entradas
        results = self.ontology.query_by_node("Sócrates", "in")
        assert len(results) == 1
        
        # Consulta nó inexistente
        results = self.ontology.query_by_node("Inexistente", "both")
        assert len(results) == 0
    
    def test_get_contradictory_facts(self):
        """Testa recuperação de fatos contraditórios."""
        self.ontology.add_fact("fato1", "é", "verdadeiro", "TRUE")
        self.ontology.add_fact("fato2", "é", "falso", "FALSE")
        fact_id3 = self.ontology.add_fact("fato3", "é", "incerto", "UNDECIDABLE")
        
        contradictory = self.ontology.get_contradictory_facts()
        assert len(contradictory) == 1
        assert contradictory[0].fact_id == fact_id3
    
    def test_get_statistics(self):
        """Testa geração de estatísticas."""
        self.ontology.add_fact("A", "é", "B", "TRUE")
        self.ontology.add_fact("C", "é", "D", "FALSE")
        self.ontology.add_fact("E", "relaciona", "F", "UNDECIDABLE")
        self.ontology.add_fact("G", "é", "H", "TRUE")
        
        stats = self.ontology.get_statistics()
        
        assert stats['total_facts'] == 4
        assert stats['total_nodes'] == 8  # A, B, C, D, E, F, G, H
        assert stats['total_edges'] == 4
        assert stats['state_distribution']['TRUE'] == 2
        assert stats['state_distribution']['FALSE'] == 1
        assert stats['state_distribution']['UNDECIDABLE'] == 1
        assert stats['relation_distribution']['é'] == 3
        assert stats['relation_distribution']['relaciona'] == 1
        assert stats['contradictory_facts'] == 1
    
    def test_export_to_dict(self):
        """Testa exportação para dicionário."""
        fact_id = self.ontology.add_fact("teste", "é", "exemplo", [0.8, 0.1, 0.1])
        
        export_data = self.ontology.export_to_dict()
        
        assert 'facts' in export_data
        assert 'nodes' in export_data
        assert 'statistics' in export_data
        
        assert len(export_data['facts']) == 1
        fact_data = export_data['facts'][0]
        assert fact_data['fact_id'] == fact_id
        assert fact_data['subject'] == "teste"
        assert fact_data['relation'] == "é"
        assert fact_data['object'] == "exemplo"
        assert np.allclose(fact_data['state'], [0.8, 0.1, 0.1])
    
    def test_clear(self):
        """Testa limpeza da ontologia."""
        self.ontology.add_fact("A", "é", "B", "TRUE")
        self.ontology.add_fact("C", "é", "D", "FALSE")
        
        assert len(self.ontology) == 2
        
        self.ontology.clear()
        
        assert len(self.ontology) == 0
        assert self.ontology.graph.number_of_nodes() == 0
        assert self.ontology.graph.number_of_edges() == 0
        assert self.ontology._fact_counter == 0
    
    def test_magic_methods(self):
        """Testa métodos mágicos da classe."""
        fact_id = self.ontology.add_fact("A", "é", "B", "TRUE")
        
        # Teste __len__
        assert len(self.ontology) == 1
        
        # Teste __contains__
        assert fact_id in self.ontology
        assert "fake_id" not in self.ontology
        
        # Teste __repr__
        repr_str = repr(self.ontology)
        assert "KnowledgeOntology" in repr_str
        assert "facts=1" in repr_str
        assert "nodes=2" in repr_str
        assert "contradictions=0" in repr_str


class TestUtilityFunctions:
    """Testes para funções utilitárias."""
    
    def test_create_simple_ontology(self):
        """Testa criação de ontologia simples."""
        ontology = create_simple_ontology()
        
        assert len(ontology) > 0
        assert ontology.graph.number_of_nodes() > 0
        
        # Verifica se contém fatos esperados
        socrates_facts = ontology.query({"subject": "Sócrates"})
        assert len(socrates_facts) > 0
        
        human_facts = ontology.query({"subject": "humano"})
        assert len(human_facts) > 0
    
    def test_create_medical_ontology(self):
        """Testa criação de ontologia médica."""
        ontology = create_medical_ontology()
        
        assert len(ontology) > 0
        
        # Verifica se contém fatos médicos esperados
        fever_facts = ontology.query({"subject": "febre"})
        assert len(fever_facts) > 0
        
        flu_facts = ontology.query({"object": "gripe"})
        assert len(flu_facts) > 0
        
        # Verifica se há fatos com estados probabilísticos
        all_facts = list(ontology.facts.values())
        probabilistic_facts = [f for f in all_facts if not f.state.is_pure()]
        assert len(probabilistic_facts) > 0


class TestIntegrationScenarios:
    """Testes de cenários de integração mais complexos."""
    
    def setup_method(self):
        """Configuração para testes de integração."""
        self.ontology = KnowledgeOntology()
    
    def test_medical_diagnosis_scenario(self):
        """Testa cenário de diagnóstico médico."""
        # Adiciona conhecimento médico
        self.ontology.add_fact("febre", "indica", "infecção", [0.7, 0.2, 0.1])
        self.ontology.add_fact("tosse", "indica", "gripe", [0.6, 0.3, 0.1])
        self.ontology.add_fact("dor_cabeça", "indica", "enxaqueca", [0.5, 0.3, 0.2])
        
        # Adiciona observações do paciente
        self.ontology.add_fact("paciente_1", "apresenta", "febre", "TRUE")
        self.ontology.add_fact("paciente_1", "apresenta", "tosse", "TRUE")
        
        # Consulta sintomas do paciente
        patient_symptoms = self.ontology.query({"subject": "paciente_1"})
        assert len(patient_symptoms) == 2
        
        # Consulta possíveis diagnósticos
        fever_diagnoses = self.ontology.query({"subject": "febre", "relation": "indica"})
        cough_diagnoses = self.ontology.query({"subject": "tosse", "relation": "indica"})
        
        assert len(fever_diagnoses) == 1
        assert len(cough_diagnoses) == 1
        
        # Verifica estados probabilísticos
        fever_fact = fever_diagnoses[0]
        assert not fever_fact.state.is_pure()
        assert abs(fever_fact.state.get_probabilities()['TRUE'] - 0.7) < 1e-10
    
    def test_contradiction_propagation(self):
        """Testa propagação de contradições."""
        # Adiciona fatos iniciais
        self.ontology.add_fact("A", "implica", "B", "TRUE")
        self.ontology.add_fact("B", "implica", "C", "TRUE")
        fact3_id = self.ontology.add_fact("A", "implica", "não_C", "TRUE")
        
        # Simula detecção de contradição
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            self.ontology.update_fact_state(fact3_id, "UNDECIDABLE", emit_warning=False)
            
            # Não esperamos warnings nos testes
            assert len(w) == 0
        
        # Verifica se a contradição foi registrada
        contradictory_facts = self.ontology.get_contradictory_facts()
        assert len(contradictory_facts) == 1
        assert contradictory_facts[0].fact_id == fact3_id
    
    def test_knowledge_evolution(self):
        """Testa evolução do conhecimento ao longo do tempo."""
        # Estado inicial
        fact_id = self.ontology.add_fact("hipótese_X", "é", "válida", [0.3, 0.5, 0.2])
        
        initial_stats = self.ontology.get_statistics()
        assert initial_stats['state_distribution']['FALSE'] == 1  # Estado mais provável
        
        # Nova evidência aumenta a confiança
        self.ontology.update_fact_state(fact_id, [0.7, 0.2, 0.1], emit_warning=False)
        
        updated_stats = self.ontology.get_statistics()
        assert updated_stats['state_distribution']['TRUE'] == 1  # Agora TRUE é mais provável
        
        # Evidência contraditória gera incerteza (sem warning nos testes)
        self.ontology.update_fact_state(fact_id, [0.3, 0.3, 0.4], emit_warning=False)
        
        final_stats = self.ontology.get_statistics()
        assert final_stats['state_distribution']['UNDECIDABLE'] == 1  # Agora incerto
        assert final_stats['contradictory_facts'] == 1


if __name__ == "__main__":
    # Executa os testes se o arquivo for executado diretamente
    pytest.main([__file__, "-v"])
