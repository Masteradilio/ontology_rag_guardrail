#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MÃ³dulo: symbolic_inference.py
PropÃ³sito: Motor de InferÃªncia SimbÃ³lica com Forward Chaining

Este mÃ³dulo implementa o motor de inferÃªncia central do Projeto Quimera,
responsÃ¡vel pelo raciocÃ­nio simbÃ³lico usando lÃ³gica trivalente QGSL.

Classes principais:
- Rule: Representa uma regra de inferÃªncia (H :- B1, B2, ...)
- InferenceEngine: Motor de encadeamento para frente

Autor: Projeto Quimera
Data: 2024
"""

import re
import copy
import time
import os
import numpy as np
from typing import List, Dict, Any, Optional, Tuple, Set
from dataclasses import dataclass, field
from collections import defaultdict
import logging

# ImportaÃ§Ãµes condicionais para compatibilidade
try:
    from .qgsl_core import LogicalQubit, logical_and, logical_or, apply_gate, get_logical_gate
    from .qgsl_core import create_quantum_superposition, apply_quantum_gate, quantum_logical_and, quantum_logical_or
    from .knowledge_ontology import KnowledgeOntology, Fact
    from .bounded_reasoning import BoundedReasoning, ConstraintViolation
except ImportError:
    from qgsl_core import LogicalQubit, logical_and, logical_or, apply_gate, get_logical_gate
    from qgsl_core import create_quantum_superposition, apply_quantum_gate, quantum_logical_and, quantum_logical_or
    from knowledge_ontology import KnowledgeOntology, Fact
    from bounded_reasoning import BoundedReasoning, ConstraintViolation

# VerificaÃ§Ã£o de disponibilidade quÃ¢ntica baseada no Qiskit
try:
    import qiskit
    QUANTUM_AVAILABLE = True
except ImportError:
    QUANTUM_AVAILABLE = False


# --- Qutrit oracle integration ---
# Usa orÃ¡culos ternÃ¡rios quando habilitado
_QUTRIT_ENV = os.getenv("QUIMERA_QUTRIT_ENABLED", "auto").strip().lower()
QUTRIT_FLAG = _QUTRIT_ENV in ("true", "1", "yes", "on", "force")
try:  # pragma: no cover - import opcional
    from .qutrit_bridge import make_ternary_oracle_2in, run_example
    QUTRIT_AVAILABLE = True
except Exception:  # pragma: no cover - fallback se nÃ£o disponÃ­vel
    try:
        from qutrit_bridge import make_ternary_oracle_2in, run_example
        QUTRIT_AVAILABLE = True
    except Exception:  # pragma: no cover
        QUTRIT_AVAILABLE = False

USE_QUTRIT_ORACLES = QUTRIT_FLAG and QUTRIT_AVAILABLE

def set_qutrit_oracles_enabled(value: Optional[bool] = None) -> None:
    """Define habilitação dos oráculos qutrit em tempo de execução.

    Args:
        value: True/False para forçar; None para recalcular a partir da env var.
    """
    global USE_QUTRIT_ORACLES
    try:
        if value is None:
            env = os.getenv("QUIMERA_QUTRIT_ENABLED", "auto").strip().lower()
            flag = env in ("true", "1", "yes", "on", "force")
        else:
            flag = bool(value)
        USE_QUTRIT_ORACLES = flag and QUTRIT_AVAILABLE
    except Exception:
        # Mantém estado atual em caso de erro
        pass

if USE_QUTRIT_ORACLES:
    def _kleene_and(a: int, b: int) -> int:
        table = [[0, 0, 0], [0, 1, 2], [0, 2, 2]]
        return table[a][b]

    def _kleene_or(a: int, b: int) -> int:
        table = [[0, 1, 2], [1, 1, 1], [2, 1, 2]]
        return table[a][b]

    def _kleene_not(a: int, _b: int = 0) -> int:
        return [1, 0, 2][a]

    ORACLE_AND = make_ternary_oracle_2in(_kleene_and)
    ORACLE_OR = make_ternary_oracle_2in(_kleene_or)
    ORACLE_NOT = make_ternary_oracle_2in(_kleene_not)

    def _run_oracle(oracle, a: int, b: int) -> int:
        return run_example(oracle, a, b)

    def _qubit_to_qutrit_index(qubit: LogicalQubit) -> int:
        try:
            from .truth_mapping import qubit_index_of
        except ImportError:
            from truth_mapping import qubit_index_of
        
        probs = qubit.get_probabilities()
        key = max(probs, key=probs.get)
        return qubit_index_of(key)

    def _qutrit_index_to_qubit(idx: int) -> LogicalQubit:
        try:
            from .truth_mapping import index_to_truth
        except ImportError:
            from truth_mapping import index_to_truth
        
        truth_str = index_to_truth(idx)
        return LogicalQubit(truth_str)

    def _oracle_and_qubits(q1: LogicalQubit, q2: LogicalQubit) -> LogicalQubit:
        if USE_QUTRIT_ORACLES and q1.is_pure() and q2.is_pure():
            try:
                a = _qubit_to_qutrit_index(q1)
                b = _qubit_to_qutrit_index(q2)
                res = _run_oracle(ORACLE_AND, a, b)
                return _qutrit_index_to_qubit(res)
            except Exception:
                # Fallback para caminho simbÃ³lico quando Cirq nÃ£o estÃ¡ disponÃ­vel
                pass
        return logical_and(q1, q2)

    def _oracle_or_qubits(q1: LogicalQubit, q2: LogicalQubit) -> LogicalQubit:
        if USE_QUTRIT_ORACLES and q1.is_pure() and q2.is_pure():
            try:
                a = _qubit_to_qutrit_index(q1)
                b = _qubit_to_qutrit_index(q2)
                res = _run_oracle(ORACLE_OR, a, b)
                return _qutrit_index_to_qubit(res)
            except Exception:
                pass
        return logical_or(q1, q2)

    def _oracle_not_qubit(q: LogicalQubit) -> LogicalQubit:
        if USE_QUTRIT_ORACLES and q.is_pure():
            try:
                a = _qubit_to_qutrit_index(q)
                res = _run_oracle(ORACLE_NOT, a, 0)
                return _qutrit_index_to_qubit(res)
            except Exception:
                pass
        # Fallback clÃ¡ssico
        not_gate = get_logical_gate('NOT')
        return apply_gate(q, not_gate)


def logical_not(qubit: LogicalQubit) -> LogicalQubit:
    """
    OperaÃ§Ã£o NOT lÃ³gica para um qubit.
    
    Args:
        qubit (LogicalQubit): Qubit de entrada
    
    Returns:
        LogicalQubit: Resultado da operaÃ§Ã£o NOT
    """
    if USE_QUTRIT_ORACLES and '_oracle_not_qubit' in globals():
        result = _oracle_not_qubit(qubit)
        if result is not None:
            return result
    not_gate = get_logical_gate('NOT')
    return apply_gate(qubit, not_gate)

# ConfiguraÃ§Ã£o de logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class Pattern:
    """
    Representa um padrÃ£o para matching de fatos.
    
    Attributes:
        subject: Sujeito do padrÃ£o (pode ser variÃ¡vel como ?x)
        relation: RelaÃ§Ã£o do padrÃ£o
        object: Objeto do padrÃ£o (pode ser variÃ¡vel como ?y)
    """
    subject: str
    relation: str
    object: str
    
    def __post_init__(self):
        """Valida o padrÃ£o apÃ³s inicializaÃ§Ã£o."""
        if not all([self.subject, self.relation, self.object]):
            raise ValueError("Todos os campos do padrÃ£o devem ser preenchidos")
    
    def is_variable(self, term: str) -> bool:
        """Verifica se um termo Ã© uma variÃ¡vel (comeÃ§a com ?)."""
        return term.startswith('?')
    
    def get_variables(self) -> Set[str]:
        """Retorna todas as variÃ¡veis no padrÃ£o."""
        variables = set()
        for term in [self.subject, self.relation, self.object]:
            if self.is_variable(term):
                variables.add(term)
        return variables
    
    def matches(self, fact: Fact, bindings: Dict[str, str] = None) -> Tuple[bool, Dict[str, str]]:
        """
        Verifica se o padrÃ£o faz match com um fato.
        
        Args:
            fact: Fato a ser testado
            bindings: Bindings de variÃ¡veis existentes
            
        Returns:
            Tuple (match_success, new_bindings)
        """
        if bindings is None:
            bindings = {}
        
        new_bindings = bindings.copy()
        
        # Testa cada componente do padrÃ£o
        for pattern_term, fact_term in [
            (self.subject, fact.subject),
            (self.relation, fact.relation),
            (self.object, fact.object)
        ]:
            if self.is_variable(pattern_term):
                # Ã‰ uma variÃ¡vel
                if pattern_term in new_bindings:
                    # VariÃ¡vel jÃ¡ tem binding, deve ser consistente
                    if new_bindings[pattern_term] != fact_term:
                        return False, {}
                else:
                    # Nova variÃ¡vel, cria binding
                    new_bindings[pattern_term] = fact_term
            else:
                # Ã‰ um termo concreto, deve ser igual
                if pattern_term != fact_term:
                    return False, {}
        
        return True, new_bindings
    
    def substitute(self, bindings: Dict[str, str]) -> 'Pattern':
        """Substitui variÃ¡veis pelos seus bindings."""
        new_subject = bindings.get(self.subject, self.subject)
        new_relation = bindings.get(self.relation, self.relation)
        new_object = bindings.get(self.object, self.object)
        
        return Pattern(new_subject, new_relation, new_object)
    
    def __str__(self) -> str:
        return f"{self.subject} {self.relation} {self.object}"


@dataclass
class Rule:
    """
    Representa uma regra de inferÃªncia no formato: head :- body1, body2, ...
    
    Attributes:
        name: Nome identificador da regra
        head: PadrÃ£o da conclusÃ£o (consequente)
        body: Lista de padrÃµes das premissas (antecedentes)
        confidence: ConfianÃ§a na regra (0.0 a 1.0)
        description: DescriÃ§Ã£o textual da regra
    """
    name: str
    head: Pattern
    body: List[Pattern]
    confidence: float = 1.0
    description: str = ""
    
    def __post_init__(self):
        """Valida a regra apÃ³s inicializaÃ§Ã£o."""
        if not self.name:
            raise ValueError("Nome da regra Ã© obrigatÃ³rio")
        if not isinstance(self.head, Pattern):
            raise ValueError("Head deve ser um Pattern")
        if not self.body or not all(isinstance(p, Pattern) for p in self.body):
            raise ValueError("Body deve ser uma lista nÃ£o-vazia de Patterns")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("Confidence deve estar entre 0.0 e 1.0")
    
    def get_all_variables(self) -> Set[str]:
        """Retorna todas as variÃ¡veis na regra."""
        variables = self.head.get_variables()
        for pattern in self.body:
            variables.update(pattern.get_variables())
        return variables
    
    def is_applicable(self, ontology: KnowledgeOntology, bindings: Dict[str, str] = None) -> List[Dict[str, str]]:
        """
        Verifica se a regra Ã© aplicÃ¡vel dado o estado atual da ontologia.
        
        Args:
            ontology: Ontologia de conhecimento
            bindings: Bindings parciais de variÃ¡veis
            
        Returns:
            Lista de bindings completos que tornam a regra aplicÃ¡vel
        """
        if bindings is None:
            bindings = {}
        
        return self._find_bindings(ontology, self.body, 0, bindings)
    
    def _find_bindings(self, ontology: KnowledgeOntology, patterns: List[Pattern], 
                      pattern_index: int, current_bindings: Dict[str, str]) -> List[Dict[str, str]]:
        """
        Encontra recursivamente todos os bindings que satisfazem os padrÃµes.
        """
        if pattern_index >= len(patterns):
            # Todos os padrÃµes foram satisfeitos
            return [current_bindings.copy()]
        
        current_pattern = patterns[pattern_index]
        all_bindings = []
        
        # Busca fatos que fazem match com o padrÃ£o atual
        for fact in list(ontology.get_all_facts()):
            # SÃ³ considera fatos com estado TRUE ou probabilidade alta
            if fact.state.collapse() == 'FALSE':
                continue
                
            match_success, new_bindings = current_pattern.matches(fact, current_bindings)
            if match_success:
                # Recursivamente processa o prÃ³ximo padrÃ£o
                recursive_bindings = self._find_bindings(
                    ontology, patterns, pattern_index + 1, new_bindings
                )
                all_bindings.extend(recursive_bindings)
        
        return all_bindings
    
    def apply(self, bindings: Dict[str, str]) -> Pattern:
        """
        Aplica os bindings Ã  regra para gerar uma nova conclusÃ£o.
        
        Args:
            bindings: Mapeamento de variÃ¡veis para valores
            
        Returns:
            PadrÃ£o da conclusÃ£o com variÃ¡veis substituÃ­das
        """
        return self.head.substitute(bindings)
    
    def calculate_conclusion_state(self, ontology: KnowledgeOntology, 
                                 bindings: Dict[str, str], use_quantum: bool = False) -> LogicalQubit:
        """
        Calcula o estado lÃ³gico da conclusÃ£o baseado nas premissas.
        
        Args:
            ontology: Ontologia de conhecimento
            bindings: Bindings das variÃ¡veis
            use_quantum: Se deve usar simulaÃ§Ã£o quÃ¢ntica
            
        Returns:
            Estado lÃ³gico da conclusÃ£o
        """
        premise_states = []
        
        # Coleta os estados das premissas
        for pattern in self.body:
            concrete_pattern = pattern.substitute(bindings)
            
            # Busca o fato correspondente na ontologia
            matching_facts = []
            for fact in list(ontology.get_all_facts()):
                if (fact.subject == concrete_pattern.subject and
                    fact.relation == concrete_pattern.relation and
                    fact.object == concrete_pattern.object):
                    matching_facts.append(fact)
            
            if matching_facts:
                # Usa o fato mais recente ou com maior confianÃ§a
                best_fact = max(matching_facts, 
                              key=lambda f: f.state.get_probabilities()['TRUE'])
                premise_states.append(best_fact.state)
            else:
                # Se nÃ£o encontrar o fato, assume UNDECIDABLE
                premise_states.append(LogicalQubit('UNDECIDABLE'))
        
        # Combina os estados das premissas usando AND lÃ³gico
        if not premise_states:
            return LogicalQubit('UNDECIDABLE')
        
        # Escolhe entre implementaÃ§Ã£o clÃ¡ssica ou quÃ¢ntica
        if use_quantum and QUANTUM_AVAILABLE:
            result_state = self._quantum_combine_premises(premise_states)
        else:
            result_state = self._classical_combine_premises(premise_states)
        
        # Aplica a confianÃ§a da regra
        if self.confidence < 1.0:
            probs = result_state.get_probabilities()
            # Reduz a probabilidade de TRUE pela confianÃ§a
            new_true_prob = probs['TRUE'] * self.confidence
            remaining = 1.0 - new_true_prob
            
            # Evita divisÃ£o por zero
            denominator = probs['FALSE'] + probs['UNDECIDABLE']
            if denominator > 0:
                new_false_prob = probs['FALSE'] * (remaining / denominator)
                new_undecidable_prob = 1.0 - new_true_prob - new_false_prob
            else:
                # Se FALSE + UNDECIDABLE = 0, distribui o remaining igualmente
                new_false_prob = remaining / 2.0
                new_undecidable_prob = remaining / 2.0
            
            result_state = LogicalQubit([new_true_prob, new_false_prob, new_undecidable_prob])
        
        return result_state
    
    def _classical_combine_premises(self, premise_states: List[LogicalQubit]) -> LogicalQubit:
        """
        Combina premissas usando lÃ³gica clÃ¡ssica.
        
        Args:
            premise_states: Lista de estados das premissas
            
        Returns:
            Estado combinado
        """
        result_state = premise_states[0]
        for state in premise_states[1:]:
            if USE_QUTRIT_ORACLES and '_oracle_and_qubits' in globals():
                result_state = _oracle_and_qubits(result_state, state)
            else:
                result_state = logical_and(result_state, state)
        return result_state
    
    def _quantum_combine_premises(self, premise_states: List[LogicalQubit]) -> LogicalQubit:
        """
        Combina premissas usando simulaÃ§Ã£o quÃ¢ntica.
        
        Args:
            premise_states: Lista de estados das premissas
            
        Returns:
            Estado combinado usando simulaÃ§Ã£o quÃ¢ntica
        """
        try:
            result_state = premise_states[0]
            for state in premise_states[1:]:
                if USE_QUTRIT_ORACLES and '_oracle_and_qubits' in globals() and result_state.is_pure() and state.is_pure():
                    result_state = _oracle_and_qubits(result_state, state)
                else:
                    result_state = quantum_logical_and(result_state, state)
            return result_state
        except Exception as e:
            logger.warning(f"Erro na simulaÃ§Ã£o quÃ¢ntica, usando fallback clÃ¡ssico: {e}")
            return self._classical_combine_premises(premise_states)
    
    def get_quantum_info(self) -> Dict[str, Any]:
        """
        Retorna informaÃ§Ãµes sobre capacidades quÃ¢nticas da regra.
        
        Returns:
            DicionÃ¡rio com informaÃ§Ãµes quÃ¢nticas
        """
        return {
            'quantum_available': QUANTUM_AVAILABLE,
            'rule_name': self.name,
            'premise_count': len(self.body),
            'confidence': self.confidence,
            'supports_quantum_inference': QUANTUM_AVAILABLE and len(self.body) > 0
        }
    
    def __str__(self) -> str:
        body_str = ", ".join(str(pattern) for pattern in self.body)
        return f"{self.name}: {self.head} :- {body_str} (conf: {self.confidence})"


class InferenceEngine:
    """
    Motor de inferÃªncia simbÃ³lica com forward chaining.
    
    Implementa o LaÃ§o 1 do sistema Quimera, aplicando regras iterativamente
    para derivar novos conhecimentos da ontologia com suporte a:
    - LÃ³gica trivalente (TRUE, FALSE, UNDECIDABLE)
    - Estados probabilÃ­sticos
    - Regras com mÃºltiplas premissas
    - ExplicaÃ§Ãµes de inferÃªncia
    - Busca por objetivos
    - RestriÃ§Ãµes Ã©ticas e de seguranÃ§a (Bounded Reasoning)
    """
    
    def __init__(self, ontology: KnowledgeOntology, rules: List[Rule] = None, 
                 enable_bounded_reasoning: bool = True, enable_quantum: bool = True):
        """
        Inicializa o motor de inferÃªncia.
        
        Args:
            ontology: Ontologia de conhecimento
            rules: Lista de regras de inferÃªncia
            enable_bounded_reasoning: Se deve habilitar verificaÃ§Ãµes de restriÃ§Ãµes
            enable_quantum: Se deve habilitar simulaÃ§Ã£o quÃ¢ntica
        """
        self.ontology = ontology
        self.rules = rules or []
        self.inference_history = []
        self.max_iterations = 100
        self.min_confidence_threshold = 0.1
        
        # ConfiguraÃ§Ãµes quÃ¢nticas
        self.enable_quantum = enable_quantum and QUANTUM_AVAILABLE
        # QuantumBridge removido - substituÃ­do por qutrit_bridge
        self.quantum_bridge = None
        
        # Inicializa sistema de raciocÃ­nio delimitado
        self.bounded_reasoning = BoundedReasoning() if enable_bounded_reasoning else None
        self.enable_bounded_reasoning = enable_bounded_reasoning
        
        logger.info(f"InferenceEngine inicializado com {len(self.rules)} regras")
        if enable_bounded_reasoning:
            logger.info(f"RaciocÃ­nio delimitado habilitado com {len(self.bounded_reasoning.constraints)} restriÃ§Ãµes")
        if self.enable_quantum:
            logger.info("SimulaÃ§Ã£o quÃ¢ntica habilitada")
        elif enable_quantum and not QUANTUM_AVAILABLE:
            # Suprime warning durante testes
            import os
            if not os.environ.get('PYTEST_CURRENT_TEST'):
                logger.warning("SimulaÃ§Ã£o quÃ¢ntica solicitada mas nÃ£o disponÃ­vel (instale qiskit e qiskit-aer)")
    
    def add_rule(self, rule: Rule) -> None:
        """Adiciona uma nova regra ao motor."""
        if not isinstance(rule, Rule):
            raise ValueError("Deve ser uma instÃ¢ncia de Rule")
        
        self.rules.append(rule)
        logger.info(f"Regra adicionada: {rule.name}")
    
    def remove_rule(self, rule_name: str) -> bool:
        """Remove uma regra pelo nome."""
        initial_count = len(self.rules)
        self.rules = [r for r in self.rules if r.name != rule_name]
        removed = len(self.rules) < initial_count
        
        if removed:
            logger.info(f"Regra removida: {rule_name}")
        
        return removed
    
    def forward_chain(self, goal_pattern: Pattern = None, max_iterations: int = None) -> List[Fact]:
        """
        Executa forward chaining para derivar novos fatos.
        
        Args:
            goal_pattern: PadrÃ£o objetivo (opcional)
            max_iterations: MÃ¡ximo de iteraÃ§Ãµes (opcional)
            
        Returns:
            Lista de novos fatos derivados
        """
        try:
            if max_iterations is None:
                max_iterations = self.max_iterations
            
            logger.info(f"Iniciando forward chaining (max_iter: {max_iterations})")
            if goal_pattern:
                logger.info(f"Objetivo: {goal_pattern}")
            
            new_facts = []
            iteration = 0
            start_time = time.time()
            
            while iteration < max_iterations:
                iteration += 1
                iteration_start = time.time()
                logger.debug(f"IteraÃ§Ã£o {iteration}/{max_iterations}")
                
                iteration_new_facts = []
                rules_applied = 0
                
                try:
                    # Aplica cada regra - cria cÃ³pia da lista para evitar "dictionary changed size during iteration"
                    for rule in list(self.rules):
                        try:
                            rule_new_facts = self._apply_rule(rule)
                            iteration_new_facts.extend(rule_new_facts)
                            if rule_new_facts:
                                rules_applied += 1
                                logger.debug(f"Regra '{rule.name}' derivou {len(rule_new_facts)} novos fatos")
                        except Exception as e:
                            logger.error(f"Erro ao aplicar regra '{rule.name}': {e}")
                            continue  # Continua com prÃ³xima regra
                    
                    iteration_time = time.time() - iteration_start
                    logger.debug(f"IteraÃ§Ã£o {iteration} concluÃ­da em {iteration_time:.3f}s: "
                               f"{len(iteration_new_facts)} novos fatos, {rules_applied} regras aplicadas")
                    
                except Exception as e:
                    logger.error(f"Erro crÃ­tico na iteraÃ§Ã£o {iteration}: {e}")
                    break  # Para o forward chaining em caso de erro crÃ­tico
                
                # Se nÃ£o derivou novos fatos, para
                if not iteration_new_facts:
                    logger.info(f"ConvergÃªncia alcanÃ§ada na iteraÃ§Ã£o {iteration}")
                    break
                
                new_facts.extend(iteration_new_facts)
                
                # Se tem objetivo especÃ­fico, verifica se foi alcanÃ§ado
                if goal_pattern:
                    try:
                        if self._goal_achieved(goal_pattern):
                            logger.info(f"Objetivo alcanÃ§ado na iteraÃ§Ã£o {iteration}")
                            break
                    except Exception as e:
                        logger.warning(f"Erro ao verificar objetivo: {e}")
                        # Continua mesmo com erro na verificaÃ§Ã£o do objetivo
            
            total_time = time.time() - start_time
            logger.info(f"Forward chaining concluÃ­do em {total_time:.3f}s: "
                       f"{len(new_facts)} novos fatos em {iteration} iteraÃ§Ãµes")
            return new_facts
            
        except Exception as e:
            logger.error(f"Erro fatal no forward chaining: {e}")
            return []  # Retorna lista vazia em caso de erro fatal
    
    def _apply_rule(self, rule: Rule) -> List[Fact]:
        """
        Aplica uma regra especÃ­fica Ã  ontologia atual.
        
        Args:
            rule: Regra a ser aplicada
            
        Returns:
            Lista de novos fatos derivados
        """
        new_facts = []
        
        # Encontra todos os bindings que tornam a regra aplicÃ¡vel
        applicable_bindings = rule.is_applicable(self.ontology)
        
        for bindings in applicable_bindings:
            # Gera a conclusÃ£o
            conclusion_pattern = rule.apply(bindings)
            
            # Verifica se a conclusÃ£o jÃ¡ existe
            existing_fact = self._find_existing_fact(conclusion_pattern)
            
            if existing_fact:
                # Atualiza o estado do fato existente
                new_state = rule.calculate_conclusion_state(self.ontology, bindings)
                
                # Combina com o estado existente usando OR lÃ³gico
                if USE_QUTRIT_ORACLES and '_oracle_or_qubits' in globals():
                    combined_state = _oracle_or_qubits(existing_fact.state, new_state)
                else:
                    combined_state = logical_or(existing_fact.state, new_state)
                
                if not existing_fact.state.__eq__(combined_state):
                    self.ontology.update_fact_state(existing_fact.fact_id, combined_state, emit_warning=False)
                    logger.debug(f"Fato atualizado: {existing_fact.fact_id}")
            else:
                # Cria novo fato usando simulaÃ§Ã£o quÃ¢ntica se habilitada
                new_state = rule.calculate_conclusion_state(self.ontology, bindings, use_quantum=self.enable_quantum)
                
                # SÃ³ adiciona se a confianÃ§a for suficiente ou se hÃ¡ incerteza significativa
                probs = new_state.get_probabilities()
                confidence_check = (probs['TRUE'] >= self.min_confidence_threshold or 
                                  probs['UNDECIDABLE'] >= self.min_confidence_threshold)
                
                if confidence_check:
                    # Verifica restriÃ§Ãµes antes de adicionar o fato
                    should_add_fact = True
                    if self.enable_bounded_reasoning:
                        try:
                            # Cria um fato temporÃ¡rio para verificaÃ§Ã£o
                            temp_fact = Fact(
                                fact_id="temp",
                                subject=conclusion_pattern.subject,
                                relation=conclusion_pattern.relation,
                                object=conclusion_pattern.object,
                                state=new_state
                            )
                            
                            # Verifica se o fato viola alguma restriÃ§Ã£o
                            violations = self.bounded_reasoning.check_constraints(temp_fact)
                            
                            # Verifica se hÃ¡ violaÃ§Ãµes que devem bloquear o fato
                            blocking_violations = [v for v in violations if v.constraint.action == "block"]
                            
                            if blocking_violations:
                                logger.warning(f"Fato rejeitado por violar restriÃ§Ãµes: {blocking_violations[0].message}")
                                # Registra a violaÃ§Ã£o no histÃ³rico
                                self.inference_history.append({
                                    'rule': rule.name,
                                    'bindings': bindings,
                                    'conclusion': str(conclusion_pattern),
                                    'fact_id': None,
                                    'state': str(new_state),
                                    'violation': blocking_violations[0].message,
                                    'constraint': blocking_violations[0].constraint_name
                                })
                                should_add_fact = False  # Marca para nÃ£o adicionar o fato
                            elif violations:
                                # Registra violaÃ§Ãµes nÃ£o-bloqueantes (warn, log) mas permite o fato
                                for violation in violations:
                                    if violation.constraint.action in ["warn", "log"]:
                                        logger.warning(f"ViolaÃ§Ã£o detectada (nÃ£o-bloqueante): {violation.message}")
                                        self.inference_history.append({
                                            'rule': rule.name,
                                            'bindings': bindings,
                                            'conclusion': str(conclusion_pattern),
                                            'fact_id': None,
                                            'state': str(new_state),
                                            'violation': violation.message,
                                            'constraint': violation.constraint_name,
                                            'action': violation.constraint.action
                                        })
                        except Exception as e:
                            logger.error(f"Erro ao verificar restriÃ§Ãµes: {e}")
                            # Em caso de erro, permite a adiÃ§Ã£o do fato
                    
                    # SÃ³ adiciona o fato se nÃ£o houver violaÃ§Ãµes
                    if should_add_fact:
                        # Adiciona o fato Ã  ontologia
                        new_fact_id = self.ontology.add_fact(
                            conclusion_pattern.subject,
                            conclusion_pattern.relation,
                            conclusion_pattern.object,
                            new_state
                        )
                        
                        # Busca o fato criado
                        new_fact = self.ontology.get_fact(new_fact_id)
                        new_facts.append(new_fact)
                        
                        # Registra na histÃ³ria
                        self.inference_history.append({
                            'rule': rule.name,
                            'bindings': bindings,
                            'conclusion': str(conclusion_pattern),
                            'fact_id': new_fact_id,
                            'state': str(new_state)
                        })
                        
                        logger.debug(f"Novo fato derivado: {new_fact}")
        
        return new_facts
    
    def _find_existing_fact(self, pattern: Pattern) -> Optional[Fact]:
        """Encontra um fato existente que corresponde ao padrÃ£o."""
        for fact in list(self.ontology.get_all_facts()):
            if (fact.subject == pattern.subject and
                fact.relation == pattern.relation and
                fact.object == pattern.object):
                return fact
        return None
    
    def _goal_achieved(self, goal_pattern: Pattern) -> bool:
        """Verifica se o objetivo foi alcanÃ§ado."""
        for fact in list(self.ontology.get_all_facts()):
            match_success, _ = goal_pattern.matches(fact)
            if match_success and fact.state.collapse() == 'TRUE':
                return True
        return False
    
    def query(self, pattern: Pattern) -> List[Tuple[Fact, Dict[str, str]]]:
        """
        Consulta a ontologia por fatos que fazem match com o padrÃ£o.
        
        Args:
            pattern: PadrÃ£o de busca
            
        Returns:
            Lista de tuplas (fato, bindings)
        """
        results = []
        
        for fact in list(self.ontology.get_all_facts()):
            match_success, bindings = pattern.matches(fact)
            if match_success:
                results.append((fact, bindings))
        
        return results
    
    def explain_inference(self, fact_id: str) -> List[Dict[str, Any]]:
        """
        Explica como um fato foi derivado.
        
        Args:
            fact_id: ID do fato a ser explicado
            
        Returns:
            Lista de passos de inferÃªncia
        """
        explanation = []
        
        for step in self.inference_history:
            if step['fact_id'] == fact_id:
                explanation.append(step)
        
        return explanation
    
    def get_statistics(self) -> Dict[str, Any]:
        """Retorna estatÃ­sticas do motor de inferÃªncia."""
        stats = {
            'total_rules': len(self.rules),
            'total_inferences': len(self.inference_history),
            'ontology_facts': len(self.ontology.get_all_facts()),
            'rules_by_name': [rule.name for rule in self.rules],
            'quantum_enabled': self.enable_quantum,
            'quantum_available': QUANTUM_AVAILABLE
        }
        
        # Adiciona estatÃ­sticas quÃ¢nticas se disponÃ­vel
        if self.enable_quantum and self.quantum_bridge:
            quantum_stats = self.get_quantum_statistics()
            stats.update(quantum_stats)
        
        return stats
    
    def reset_history(self) -> None:
        """Limpa o histÃ³rico de inferÃªncias."""
        self.inference_history.clear()
        logger.info("HistÃ³rico de inferÃªncias limpo")
    
    def add_constraint(self, constraint_rule) -> None:
        """Adiciona uma nova restriÃ§Ã£o ao sistema de raciocÃ­nio delimitado."""
        if self.bounded_reasoning:
            self.bounded_reasoning.add_constraint(constraint_rule)
            logger.info(f"Nova restriÃ§Ã£o adicionada: {constraint_rule.name}")
        else:
            logger.warning("Tentativa de adicionar restriÃ§Ã£o com bounded_reasoning desabilitado")
    
    def remove_constraint(self, constraint_name: str) -> bool:
        """Remove uma restriÃ§Ã£o do sistema de raciocÃ­nio delimitado."""
        if self.bounded_reasoning:
            success = self.bounded_reasoning.remove_constraint(constraint_name)
            if success:
                logger.info(f"RestriÃ§Ã£o removida: {constraint_name}")
            else:
                logger.warning(f"RestriÃ§Ã£o nÃ£o encontrada: {constraint_name}")
            return success
        else:
            logger.warning("Tentativa de remover restriÃ§Ã£o com bounded_reasoning desabilitado")
            return False
    
    def get_constraints(self) -> List:
        """Retorna a lista de restriÃ§Ãµes ativas."""
        if self.bounded_reasoning:
            return self.bounded_reasoning.constraints
        return []
    
    def get_violations_history(self) -> List[Dict[str, Any]]:
        """Retorna o histÃ³rico de violaÃ§Ãµes de restriÃ§Ãµes."""
        violations = []
        for step in self.inference_history:
            if 'violation' in step:
                violations.append(step)
        return violations
    
    def get_quantum_statistics(self) -> Dict[str, Any]:
        """
        Retorna estatÃ­sticas especÃ­ficas da simulaÃ§Ã£o quÃ¢ntica.
        
        Returns:
            DicionÃ¡rio com estatÃ­sticas quÃ¢nticas
        """
        if not self.enable_quantum:
            return {
                'quantum_inferences': 0,
                'quantum_bridge_available': False,
                'quantum_rules_count': 0,
                'quantum_stats': 'not_available'
            }
        
        quantum_inferences = sum(1 for step in self.inference_history 
                               if step.get('quantum_used', False))
        
        return {
            'quantum_inferences': quantum_inferences,
            'quantum_bridge_available': QUANTUM_AVAILABLE,
            'quantum_rules_count': sum(1 for rule in self.rules 
                                     if rule.get_quantum_info()['supports_quantum_inference'])
        }
    
    def quantum_forward_chain(self, goal_pattern: Pattern = None, max_iterations: int = None) -> List[Fact]:
        """
        Executa forward chaining com Ãªnfase em simulaÃ§Ã£o quÃ¢ntica.
        
        Args:
            goal_pattern: PadrÃ£o objetivo (opcional)
            max_iterations: MÃ¡ximo de iteraÃ§Ãµes (opcional)
            
        Returns:
            Lista de novos fatos derivados usando simulaÃ§Ã£o quÃ¢ntica
        """
        if not self.enable_quantum:
            logger.warning("SimulaÃ§Ã£o quÃ¢ntica nÃ£o habilitada, usando forward chaining clÃ¡ssico")
            return self.forward_chain(goal_pattern, max_iterations)
        
        logger.info("Iniciando forward chaining com simulaÃ§Ã£o quÃ¢ntica")
        
        # Temporariamente forÃ§a o uso de quantum para todas as regras
        original_quantum_state = self.enable_quantum
        self.enable_quantum = True
        
        try:
            new_facts = self.forward_chain(goal_pattern, max_iterations)
            
            # Marca os fatos como derivados quanticamente
            for step in self.inference_history[-len(new_facts):]:
                step['quantum_used'] = True
            
            return new_facts
        finally:
            self.enable_quantum = original_quantum_state
    
    def create_quantum_superposition_fact(self, subject: str, relation: str, object: str) -> str:
        """
        Cria um fato em superposiÃ§Ã£o quÃ¢ntica.
        
        Args:
            subject: Sujeito do fato
            relation: RelaÃ§Ã£o do fato
            object: Objeto do fato
            
        Returns:
            ID do fato criado
        """
        if not self.enable_quantum:
            logger.warning("SimulaÃ§Ã£o quÃ¢ntica nÃ£o habilitada, criando fato clÃ¡ssico UNDECIDABLE")
            superposition_state = LogicalQubit('UNDECIDABLE')
        else:
            try:
                superposition_state = create_quantum_superposition()
                logger.info(f"Fato em superposiÃ§Ã£o quÃ¢ntica criado: {subject} {relation} {object}")
            except Exception as e:
                logger.warning(f"Erro ao criar superposiÃ§Ã£o quÃ¢ntica: {e}, usando fallback")
                superposition_state = LogicalQubit('UNDECIDABLE')
        
        return self.ontology.add_fact(subject, relation, object, superposition_state)
    
    def apply_quantum_gate_to_fact(self, fact_id: str, gate_name: str) -> bool:
        """
        Aplica uma porta quÃ¢ntica a um fato especÃ­fico.
        
        Args:
            fact_id: ID do fato
            gate_name: Nome da porta quÃ¢ntica ('NOT', 'HADAMARD', etc.)
            
        Returns:
            True se a operaÃ§Ã£o foi bem-sucedida
        """
        if not self.enable_quantum:
            logger.warning("SimulaÃ§Ã£o quÃ¢ntica nÃ£o habilitada")
            return False
        
        try:
            fact = self.ontology.get_fact(fact_id)
            if not fact:
                logger.error(f"Fato nÃ£o encontrado: {fact_id}")
                return False
            
            if gate_name.upper() == 'HADAMARD':
                new_state = fact.state.quantum_hadamard(use_quantum=QUANTUM_AVAILABLE)
            elif gate_name.upper() == 'NOT':
                new_state = fact.state.quantum_not(use_quantum=QUANTUM_AVAILABLE)
            else:
                logger.error(f"Porta quÃ¢ntica nÃ£o suportada: {gate_name}")
                return False
            
            self.ontology.update_fact_state(fact_id, new_state, emit_warning=False)
            logger.info(f"Porta {gate_name} aplicada ao fato {fact_id}")
            return True
            
        except Exception as e:
            logger.error(f"Erro ao aplicar porta quÃ¢ntica: {e}")
            return False
    
    def backward_chain(self, goal_pattern: Pattern, max_depth: int = 10) -> List[Tuple[bool, List[Fact], Dict[str, str]]]:
        """
        Executa backward chaining para verificar se um objetivo pode ser provado.
        
        O backward chaining trabalha de forma goal-driven, partindo do objetivo
        e tentando encontrar regras e fatos que o suportem.
        
        Args:
            goal_pattern: PadrÃ£o objetivo a ser provado
            max_depth: Profundidade mÃ¡xima de busca
            
        Returns:
            Lista de tuplas (provado, fatos_usados, bindings) para cada prova encontrada
        """
        logger.info(f"Iniciando backward chaining para objetivo: {goal_pattern}")
        
        proofs = []
        visited_goals = set()  # Evita loops infinitos
        
        def _backward_search(current_goal: Pattern, current_bindings: Dict[str, str], 
                           depth: int, proof_path: List[Fact]) -> List[Tuple[bool, List[Fact], Dict[str, str]]]:
            """
            Busca recursiva backward.
            """
            if depth > max_depth:
                return []
            
            # Evita loops infinitos
            bindings_str = "_".join([f"{k}:{v}" for k, v in sorted(current_bindings.items())])
            goal_key = f"{current_goal}_{bindings_str}"
            if goal_key in visited_goals:
                return []
            visited_goals.add(goal_key)
            
            results = []
            
            # 1. Verifica se o objetivo jÃ¡ existe como fato na ontologia
            for fact in list(self.ontology.get_all_facts()):
                if fact.state.collapse() == 'FALSE':
                    continue
                    
                match_success, new_bindings = current_goal.matches(fact, current_bindings)
                if match_success:
                    # Objetivo encontrado diretamente
                    logger.debug(f"Objetivo encontrado como fato: {fact}")
                    results.append((True, proof_path + [fact], new_bindings))
            
            # 2. Busca regras que podem provar o objetivo - cria cÃ³pia da lista para evitar "dictionary changed size during iteration"
            for rule in list(self.rules):
                # Verifica se a cabeÃ§a da regra pode unificar com o objetivo
                match_success, rule_bindings = rule.head.matches(current_goal, current_bindings)
                if not match_success:
                    continue
                
                logger.debug(f"Tentando regra: {rule.name} para objetivo: {current_goal}")
                
                # Tenta provar todas as premissas da regra
                if self._prove_premises(rule.body, rule_bindings, depth + 1, proof_path, results):
                    logger.debug(f"Regra {rule.name} provou objetivo com sucesso")
            
            visited_goals.remove(goal_key)
            return results
        
        try:
            proofs = _backward_search(goal_pattern, {}, 0, [])
            
            logger.info(f"Backward chaining concluÃ­do. Encontradas {len(proofs)} provas")
            return proofs
            
        except Exception as e:
            logger.error(f"Erro durante backward chaining: {e}")
            return []
    
    def _prove_premises(self, premises: List[Pattern], bindings: Dict[str, str], 
                       depth: int, proof_path: List[Fact], results: List) -> bool:
        """
        Tenta provar todas as premissas de uma regra recursivamente.
        
        Args:
            premises: Lista de padrÃµes que devem ser provados
            bindings: Bindings atuais
            depth: Profundidade atual
            proof_path: Caminho de prova atual
            results: Lista para armazenar resultados
            
        Returns:
            True se todas as premissas foram provadas
        """
        if not premises:
            # Todas as premissas foram provadas
            results.append((True, proof_path.copy(), bindings.copy()))
            return True
        
        # Pega a primeira premissa
        first_premise = premises[0]
        remaining_premises = premises[1:]
        
        # Substitui variÃ¡veis jÃ¡ ligadas na premissa
        instantiated_premise = first_premise.substitute(bindings)
        
        # Tenta provar a primeira premissa
        premise_proofs = self.backward_chain(instantiated_premise, max_depth=10-depth)
        
        success = False
        for proved, premise_facts, premise_bindings in premise_proofs:
            if proved:
                # Combina bindings
                combined_bindings = {**bindings, **premise_bindings}
                
                # Tenta provar as premissas restantes
                if self._prove_premises(remaining_premises, combined_bindings, 
                                      depth, proof_path + premise_facts, results):
                    success = True
        
        return success
    
    def goal_driven_inference(self, goal_pattern: Pattern, use_backward: bool = True, 
                            use_forward: bool = True) -> Dict[str, Any]:
        """
        Executa inferÃªncia dirigida por objetivo combinando forward e backward chaining.
        
        Args:
            goal_pattern: Objetivo a ser alcanÃ§ado
            use_backward: Se deve usar backward chaining
            use_forward: Se deve usar forward chaining
            
        Returns:
            DicionÃ¡rio com resultados da inferÃªncia
        """
        logger.info(f"Iniciando inferÃªncia dirigida por objetivo: {goal_pattern}")
        
        results = {
            'goal': str(goal_pattern),
            'backward_proofs': [],
            'forward_facts': [],
            'goal_achieved': False,
            'total_proofs': 0
        }
        
        # 1. Tenta backward chaining primeiro (mais eficiente para objetivos especÃ­ficos)
        if use_backward:
            logger.info("Executando backward chaining...")
            backward_proofs = self.backward_chain(goal_pattern)
            results['backward_proofs'] = backward_proofs
            
            if backward_proofs and any(proof[0] for proof in backward_proofs):
                results['goal_achieved'] = True
                results['total_proofs'] = len([p for p in backward_proofs if p[0]])
                logger.info(f"Objetivo alcanÃ§ado via backward chaining ({results['total_proofs']} provas)")
        
        # 2. Se backward nÃ£o conseguiu ou forward tambÃ©m foi solicitado
        if use_forward and (not results['goal_achieved'] or use_forward):
            logger.info("Executando forward chaining...")
            initial_facts_count = len(self.ontology.get_all_facts())
            
            # Executa forward chaining com o objetivo
            forward_facts = self.forward_chain(goal_pattern)
            results['forward_facts'] = forward_facts
            
            # Verifica se o objetivo foi alcanÃ§ado apÃ³s forward chaining
            if not results['goal_achieved']:
                for fact in list(self.ontology.get_all_facts()):
                    if fact.state.collapse() != 'FALSE':
                        match_success, _ = goal_pattern.matches(fact)
                        if match_success:
                            results['goal_achieved'] = True
                            logger.info("Objetivo alcanÃ§ado via forward chaining")
                            break
        
        logger.info(f"InferÃªncia dirigida por objetivo concluÃ­da. Objetivo alcanÃ§ado: {results['goal_achieved']}")
        return results


def prove(hypotheses, ontology):
    """Avalia hipÃ³teses contra a ontologia utilizando encadeamento simbÃ³lico."""
    # Permite entrada como lista simples ou dicionÃ¡rio com chaves 'facts'/'rules'
    rules_data = hypotheses.get("rules", []) if isinstance(hypotheses, dict) else []
    fact_data = hypotheses.get("facts", hypotheses) if isinstance(hypotheses, dict) else hypotheses

    # Converte regras em objetos Rule
    rules = []
    for r in rules_data:
        try:
            head = r.get("head", {})
            body = r.get("body", [])
            head_pat = Pattern(head["subject"], head["relation"], head["object"])
            body_pats = [Pattern(p["subject"], p["relation"], p["object"]) for p in body]
            rules.append(Rule(
                name=r.get("name", "rule"),
                head=head_pat,
                body=body_pats,
                confidence=r.get("confidence", 1.0),
                description=r.get("description", "")
            ))
        except Exception as exc:  # pragma: no cover
            logger.warning(f"Erro ao converter regra: {exc}")

    engine = InferenceEngine(ontology, rules=rules)

    result = {"proved": [], "rejected": [], "undecidable": [], "trace": [], "score": 0.0}
    scores = []

    for hyp in fact_data:
        hyp_struct = {
            "subject": hyp.get("subject"),
            "relation": hyp.get("relation"),
            "object": hyp.get("object")
        }
        pattern = Pattern(hyp_struct["subject"], hyp_struct["relation"], hyp_struct["object"])
        info = engine.goal_driven_inference(pattern)

        if info.get("goal_achieved"):
            result["proved"].append(hyp_struct)
            proof_steps = []
            if info.get("backward_proofs"):
                proof = info["backward_proofs"][0][1]
                proof_steps = [f"{f.subject} {f.relation} {f.object}" for f in proof]
            result["trace"].append({"hypothesis": hyp_struct, "proof": proof_steps})
            scores.append(1.0 / (1 + len(proof_steps)))
        else:
            contradict = None
            for fact in list(ontology.get_all_facts()):
                if (fact.subject == hyp_struct["subject"] and
                        fact.relation == hyp_struct["relation"] and
                        fact.object == hyp_struct["object"]):
                    contradict = fact
                    break
            if contradict and contradict.state.collapse() == "FALSE":
                result["rejected"].append(hyp_struct)
                result["trace"].append({"hypothesis": hyp_struct, "proof": [], "reason": "contradiction"})
            else:
                result["undecidable"].append(hyp_struct)
                result["trace"].append({"hypothesis": hyp_struct, "proof": []})
            scores.append(0.0)

    if scores:
        result["score"] = float(sum(scores) / len(scores))
    return result


# FunÃ§Ãµes utilitÃ¡rias para criaÃ§Ã£o de regras comuns

def create_transitivity_rule(relation: str, confidence: float = 1.0) -> Rule:
    """
    Cria uma regra de transitividade para uma relaÃ§Ã£o.
    
    Args:
        relation: Nome da relaÃ§Ã£o
        confidence: ConfianÃ§a na regra
        
    Returns:
        Regra de transitividade
    """
    return Rule(
        name=f"transitivity_{relation}",
        head=Pattern("?x", relation, "?z"),
        body=[
            Pattern("?x", relation, "?y"),
            Pattern("?y", relation, "?z")
        ],
        confidence=confidence,
        description=f"Transitividade da relaÃ§Ã£o {relation}"
    )


def create_symmetry_rule(relation: str, confidence: float = 1.0) -> Rule:
    """
    Cria uma regra de simetria para uma relaÃ§Ã£o.
    
    Args:
        relation: Nome da relaÃ§Ã£o
        confidence: ConfianÃ§a na regra
        
    Returns:
        Regra de simetria
    """
    return Rule(
        name=f"symmetry_{relation}",
        head=Pattern("?y", relation, "?x"),
        body=[Pattern("?x", relation, "?y")],
        confidence=confidence,
        description=f"Simetria da relaÃ§Ã£o {relation}"
    )


def create_medical_diagnosis_rules() -> List[Rule]:
    """
    Cria um conjunto de regras para diagnÃ³stico mÃ©dico.
    
    Returns:
        Lista de regras mÃ©dicas
    """
    rules = []
    
    # Regra: Se tem febre e tosse, pode ter gripe
    rules.append(Rule(
        name="gripe_sintomas",
        head=Pattern("?paciente", "pode_ter", "gripe"),
        body=[
            Pattern("?paciente", "tem_sintoma", "febre"),
            Pattern("?paciente", "tem_sintoma", "tosse")
        ],
        confidence=0.8,
        description="DiagnÃ³stico de gripe baseado em sintomas"
    ))
    
    # Regra: Se tem febre alta e dor de cabeÃ§a, pode ter infecÃ§Ã£o
    rules.append(Rule(
        name="infeccao_sintomas",
        head=Pattern("?paciente", "pode_ter", "infeccao"),
        body=[
            Pattern("?paciente", "tem_sintoma", "febre_alta"),
            Pattern("?paciente", "tem_sintoma", "dor_cabeca")
        ],
        confidence=0.7,
        description="DiagnÃ³stico de infecÃ§Ã£o baseado em sintomas"
    ))
    
    # Regra: Se pode ter gripe, deve fazer repouso
    rules.append(Rule(
        name="tratamento_gripe",
        head=Pattern("?paciente", "deve_fazer", "repouso"),
        body=[Pattern("?paciente", "pode_ter", "gripe")],
        confidence=0.9,
        description="Tratamento recomendado para gripe"
    ))
    
    return rules


if __name__ == "__main__":
    # Exemplo bÃ¡sico de uso
    print("=== TESTE BÃSICO DO MOTOR DE INFERÃŠNCIA ===")
    
    # Cria ontologia
    ontology = KnowledgeOntology()
    
    # Adiciona fatos iniciais
    ontology.add_fact("joao", "tem_sintoma", "febre", LogicalQubit('TRUE'))
    ontology.add_fact("joao", "tem_sintoma", "tosse", LogicalQubit('TRUE'))
    
    # Cria motor de inferÃªncia com simulaÃ§Ã£o quÃ¢ntica
    engine = InferenceEngine(ontology, enable_quantum=True)
    
    # Adiciona regras mÃ©dicas
    medical_rules = create_medical_diagnosis_rules()
    for rule in medical_rules:
        engine.add_rule(rule)
    
    # Executa inferÃªncia clÃ¡ssica
    print("\n--- InferÃªncia ClÃ¡ssica ---")
    engine.enable_quantum = False
    classical_facts = engine.forward_chain()
    
    print(f"Novos fatos derivados (clÃ¡ssico): {len(classical_facts)}")
    for fact in classical_facts:
        print(f"  {fact}")
    
    # Executa inferÃªncia quÃ¢ntica se disponÃ­vel
    if QUANTUM_AVAILABLE:
        print("\n--- InferÃªncia QuÃ¢ntica ---")
        engine.enable_quantum = True
        
        # Cria um fato em superposiÃ§Ã£o
        superposition_fact_id = engine.create_quantum_superposition_fact(
            "maria", "tem_sintoma", "dor_cabeca"
        )
        
        # Executa inferÃªncia quÃ¢ntica
        quantum_facts = engine.quantum_forward_chain()
        
        print(f"Novos fatos derivados (quÃ¢ntico): {len(quantum_facts)}")
        for fact in quantum_facts:
            print(f"  {fact}")
        
        # Aplica porta quÃ¢ntica a um fato
        if superposition_fact_id:
            success = engine.apply_quantum_gate_to_fact(superposition_fact_id, "HADAMARD")
            print(f"Porta HADAMARD aplicada: {success}")
    else:
        print("\n--- SimulaÃ§Ã£o QuÃ¢ntica NÃ£o DisponÃ­vel ---")
        print("Para habilitar funcionalidades quÃ¢nticas, instale:")
        print("  pip install qiskit qiskit-aer")
    
    # Mostra estatÃ­sticas
    stats = engine.get_statistics()
    print(f"\nEstatÃ­sticas: {stats}")
    
    # Mostra informaÃ§Ãµes quÃ¢nticas das regras
    print("\n--- InformaÃ§Ãµes QuÃ¢nticas das Regras ---")
    for rule in engine.rules:
        quantum_info = rule.get_quantum_info()
        print(f"  {rule.name}: {quantum_info}")
    
    print("\n=== TESTE CONCLUÃDO ===")


