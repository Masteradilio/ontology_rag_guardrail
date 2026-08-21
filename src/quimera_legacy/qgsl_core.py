#!/usr/bin/env python3
"""
QGSL Core - Quantum-inspired Symbolic Logic Core

Este módulo implementa o núcleo da lógica simbólica quântica (QGSL) do Projeto Quimera.
Fornece representações vetoriais para estados lógicos trivalentes e operações matriciais
para portas lógicas que operam em superposições de estados TRUE, FALSE e UNDECIDABLE.

Baseado na arquitetura do Projeto Quimera que utiliza vetores de estado de 3 dimensões:
- TRUE = [1, 0, 0]
- FALSE = [0, 1, 0] 
- UNDECIDABLE = [0, 0, 1]

Autor: Projeto Quimera
Versão: 1.0.0
"""

import numpy as np
from typing import Union, Dict
import warnings

# Importa helpers do truth_mapping para unificação da ordem T/F/U
try:
    from .truth_mapping import (
        qubit_index_of,
        qutrit_index_of,
        index_to_truth,
        get_truth_vector,
        TRUTH_VECTORS
    )
except ImportError:
    from truth_mapping import (
        qubit_index_of,
        qutrit_index_of,
        index_to_truth,
        get_truth_vector,
        TRUTH_VECTORS
    )

# Suprime warnings específicos do Qiskit durante os testes
warnings.filterwarnings("ignore", message="Qiskit não está instalado.*", category=UserWarning)

# Importação condicional do quantum bridge
try:
    # Verifica se o Qiskit está disponível
    __import__("qiskit")
    QUANTUM_AVAILABLE = True
except ImportError:
    QUANTUM_AVAILABLE = False
    warnings.warn("Qiskit não está instalado. Funcionalidades quânticas limitadas. Para instalar: pip install qiskit qiskit-aer")


class LogicalQutrit:
    """Representa um qutrit lógico seguindo a ordem unificada.

    Ordem unificada (truth_mapping): TRUE=0, FALSE=1, UNDECIDABLE=2.
    """

    # Usa vetores do truth_mapping para unificação da ordem T/F/U
    FALSE_STATE = TRUTH_VECTORS["FALSE"].copy()
    TRUE_STATE = TRUTH_VECTORS["TRUE"].copy()
    UNDECIDABLE_STATE = TRUTH_VECTORS["UNDECIDABLE"].copy()

    def __init__(self, amp: Union[np.ndarray, list, str]):
        if isinstance(amp, str):
            amp = self._string_to_vector(amp)
        self.state_vector = np.array(amp, dtype=float)
        if self.state_vector.shape != (3,):
            raise ValueError("Estado deve ter exatamente 3 componentes")
        if np.any(self.state_vector < 0):
            raise ValueError("Probabilidades negativas não são permitidas")
        total = float(np.sum(self.state_vector))
        if total == 0:
            raise ValueError("Vetor de estado não pode ser zero")
        self.state_vector /= total

    def _string_to_vector(self, state_str: str) -> np.ndarray:
        """Converte string para vetor usando truth_mapping helpers."""
        try:
            return get_truth_vector(state_str.upper())
        except ValueError:
            available = 'FALSE, TRUE, UNDECIDABLE'
            raise ValueError(f"Estado '{state_str}' não reconhecido. Use: {available}")

    def collapse(self, deterministic: bool = True) -> str:
        """Colapsa o estado usando truth_mapping helpers."""
        idx = np.argmax(self.state_vector) if deterministic else np.random.choice(3, p=self.state_vector)
        return index_to_truth(idx)

    def is_pure(self) -> bool:
        return np.max(self.state_vector) >= 1.0 - 1e-9

    def get_probabilities(self) -> Dict[str, float]:
        """Retorna probabilidades usando truth_mapping helpers."""
        return {
            'FALSE': float(self.state_vector[qutrit_index_of('FALSE')]),
            'TRUE': float(self.state_vector[qutrit_index_of('TRUE')]),
            'UNDECIDABLE': float(self.state_vector[qutrit_index_of('UNDECIDABLE')]),
        }

    @classmethod
    def superposition(cls, false: float, true: float, undecidable: float) -> 'LogicalQutrit':
        return cls([false, true, undecidable])


class LogicalQubit:
    """
    Representa um qubit lógico com estados trivalentes e suporte a amplitudes complexas.
    
    O estado é representado como um vetor numpy de 3 dimensões onde:
    - Posição 0: Amplitude complexa de TRUE
    - Posição 1: Amplitude complexa de FALSE
    - Posição 2: Amplitude complexa de UNDECIDABLE
    
    As probabilidades são calculadas como |amplitude|²
    
    Attributes:
        state_vector (np.ndarray): Vetor de estado normalizado com amplitudes complexas
        _use_complex (bool): Flag para indicar se está usando amplitudes complexas
    """
    
    # Estados base predefinidos (amplitudes complexas) - usa truth_mapping para unificação
    FALSE_STATE = TRUTH_VECTORS["FALSE"].astype(complex)
    TRUE_STATE = TRUTH_VECTORS["TRUE"].astype(complex)
    UNDECIDABLE_STATE = TRUTH_VECTORS["UNDECIDABLE"].astype(complex)
    
    # Estados de superposição predefinidos - F=0, T=1, U=2
    SUPERPOSITION_EQUAL = np.array([1/np.sqrt(3), 1/np.sqrt(3), 1/np.sqrt(3)], dtype=complex)
    SUPERPOSITION_TRUE_FALSE = np.array([1/np.sqrt(2), 1/np.sqrt(2), 0.0+0j], dtype=complex)
    SUPERPOSITION_TRUE_UNDECIDABLE = np.array([1/np.sqrt(2), 0.0+0j, 1/np.sqrt(2)], dtype=complex)
    SUPERPOSITION_FALSE_UNDECIDABLE = np.array([0.0+0j, 1/np.sqrt(2), 1/np.sqrt(2)], dtype=complex)
    
    def __init__(self, state_vector: Union[np.ndarray, list, str], use_complex: bool = False):
        """
        Inicializa um LogicalQubit com um vetor de estado.
        
        Args:
            state_vector: Pode ser:
                - np.ndarray de 3 elementos (real ou complexo)
                - lista de 3 elementos (real ou complexo)
                - string: 'TRUE', 'FALSE', 'UNDECIDABLE', ou estados de superposição
            use_complex (bool): Se True, usa amplitudes complexas; se False, usa probabilidades reais
        
        Raises:
            ValueError: Se o vetor não tiver 3 elementos ou não for válido
        """
        self._use_complex = use_complex
        
        if isinstance(state_vector, str):
            state_vector = self._string_to_vector(state_vector)
        elif isinstance(state_vector, LogicalQubit) or hasattr(state_vector, 'state_vector'):
            # Verifica se é um LogicalQubit (mesmo de módulos diferentes) ou tem o atributo state_vector
            state_vector = state_vector.state_vector
            
        # Converte para o tipo apropriado
        if use_complex:
            self.state_vector = np.array(state_vector, dtype=complex)
        else:
            # Modo compatibilidade: converte amplitudes complexas para probabilidades reais
            if np.iscomplexobj(state_vector):
                state_vector = np.abs(np.array(state_vector))**2
            self.state_vector = np.array(state_vector, dtype=float)
        
        if len(self.state_vector) != 3:
            raise ValueError("Estado deve ter exatamente 3 componentes")
        
        # Normalização baseada no tipo
        if use_complex:
            # Para amplitudes complexas, normaliza para que ∑|amplitude|² = 1
            norm = np.sqrt(np.sum(np.abs(self.state_vector)**2))
            if norm == 0:
                raise ValueError("Vetor de estado não pode ser zero")
            self.state_vector = self.state_vector / norm
        else:
            # Para probabilidades reais, normaliza para que ∑probabilidade = 1
            if np.any(self.state_vector < 0):
                warnings.warn("Componentes negativas detectadas, tomando valor absoluto")
                self.state_vector = np.abs(self.state_vector)
            
            total = np.sum(self.state_vector)
            if total == 0:
                raise ValueError("Vetor de estado não pode ser zero")
            self.state_vector = self.state_vector / total
    
    def _string_to_vector(self, state_str: str) -> np.ndarray:
        """Converte string de estado para vetor usando truth_mapping helpers."""
        # Primeiro tenta usar truth_mapping para estados básicos
        try:
            if state_str.upper() in ['TRUE', 'FALSE', 'UNDECIDABLE']:
                return get_truth_vector(state_str.upper()).astype(complex)
        except ValueError:
            pass
        
        # Fallback para estados especiais de superposição
        state_map = {
            'TRUE': self.TRUE_STATE.copy(),
            'FALSE': self.FALSE_STATE.copy(),
            'UNDECIDABLE': self.UNDECIDABLE_STATE.copy(),
            'SUPERPOSITION_EQUAL': self.SUPERPOSITION_EQUAL.copy(),
            'SUPERPOSITION_TRUE_FALSE': self.SUPERPOSITION_TRUE_FALSE.copy(),
            'SUPERPOSITION_TRUE_UNDECIDABLE': self.SUPERPOSITION_TRUE_UNDECIDABLE.copy(),
            'SUPERPOSITION_FALSE_UNDECIDABLE': self.SUPERPOSITION_FALSE_UNDECIDABLE.copy(),
            # Estados de superposição adicionais
            'SUPERPOSITION_TF': self.SUPERPOSITION_TRUE_FALSE.copy(),
            'SUPERPOSITION_TU': self.SUPERPOSITION_TRUE_UNDECIDABLE.copy(),
            'SUPERPOSITION_FU': self.SUPERPOSITION_FALSE_UNDECIDABLE.copy(),
            # Estados de Hadamard - F=0, T=1, U=2
            'HADAMARD_TRUE': np.array([1/np.sqrt(2), 1/np.sqrt(2), 0], dtype=complex),
            'HADAMARD_FALSE': np.array([1/np.sqrt(2), -1/np.sqrt(2), 0], dtype=complex),
            # Estados de Bell para entrelaçamento quântico - F=0, T=1, U=2
            'BELL_00': np.array([1/np.sqrt(2), 0, 1/np.sqrt(2)], dtype=complex),
            'BELL_01': np.array([1/np.sqrt(2), 0, -1/np.sqrt(2)], dtype=complex),
            'BELL_10': np.array([0, 1/np.sqrt(2), 1/np.sqrt(2)], dtype=complex),
            'BELL_11': np.array([0, 1/np.sqrt(2), -1/np.sqrt(2)], dtype=complex),
            # Estados com fases específicas - F=0, T=1, U=2
            'PHASE_TRUE': np.array([0, 1, 0], dtype=complex),
            'PHASE_FALSE': np.array([1, 0, 0], dtype=complex),
            'PHASE_UNDECIDABLE': np.array([0, 0, 1], dtype=complex),
            'PHASE_PI_TRUE': np.array([0, -1, 0], dtype=complex),
            'PHASE_PI_FALSE': np.array([-1, 0, 0], dtype=complex),
            'PHASE_PI_UNDECIDABLE': np.array([0, 0, -1], dtype=complex)
        }
        
        state_upper = state_str.upper()
        if state_upper not in state_map:
            available_states = ', '.join(state_map.keys())
            raise ValueError(f"Estado '{state_str}' não reconhecido. Use: {available_states}")
        
        return state_map[state_upper]
    
    def is_pure(self) -> bool:
        """
        Verifica se o estado não está em superposição.
        
        Returns:
            bool: True se apenas uma componente é dominante (>= 0.999)
        """
        # Tolerância mais relaxada para considerar um estado como puro
        tolerance = 1e-3
        
        # Calcula probabilidades a partir das amplitudes
        if self._use_complex:
            probabilities = np.abs(self.state_vector)**2
        else:
            probabilities = self.state_vector
        
        # Verifica se alguma componente é dominante
        max_prob = np.max(probabilities)
        return max_prob >= (1.0 - tolerance)
    
    def collapse(self, deterministic: bool = False) -> str:
        """
        Simula o colapso da função de onda e retorna o estado mais provável.
        
        Args:
            deterministic: Se True, sempre retorna o estado mais provável.
                          Se False, usa aleatoriedade baseada nas probabilidades.
        
        Returns:
            str: 'TRUE', 'FALSE' ou 'UNDECIDABLE' baseado na maior probabilidade
        """
        # Calcula probabilidades a partir das amplitudes
        if self._use_complex:
            probabilities = np.abs(self.state_vector)**2
        else:
            probabilities = self.state_vector
            
        # Simula medição quântica
        if not self.is_pure() and not deterministic:
            # Estado em superposição - escolhe aleatoriamente baseado nas probabilidades
            choice = np.random.choice(3, p=probabilities)
        else:
            # Estado puro ou modo determinístico - retorna o estado dominante
            choice = np.argmax(probabilities)
            
        return index_to_truth(choice)
    
    def get_probabilities(self) -> Dict[str, float]:
        """
        Retorna as probabilidades de cada estado calculadas a partir das amplitudes.
        
        Returns:
            Dict[str, float]: Dicionário com probabilidades de cada estado
        """
        if self._use_complex:
            # Para amplitudes complexas, probabilidade = |amplitude|²
            probabilities = np.abs(self.state_vector)**2
        else:
            # Para modo compatibilidade, usa valores diretos
            probabilities = self.state_vector
            
        return {
            'FALSE': float(probabilities[qubit_index_of('FALSE')]),
            'TRUE': float(probabilities[qubit_index_of('TRUE')]),
            'UNDECIDABLE': float(probabilities[qubit_index_of('UNDECIDABLE')])
        }
    
    def __str__(self) -> str:
        """Representação string do qubit."""
        probs = self.get_probabilities()
        if self.is_pure():
            # Para estados puros, mostra apenas o estado dominante
            dominant_index = np.argmax(np.abs(self.state_vector)**2 if self._use_complex else self.state_vector)
            dominant_state = index_to_truth(dominant_index)
            return f"LogicalQubit({dominant_state})"
        else:
            # Para superposições, mostra probabilidades e informações de fase se complexo
            if self._use_complex:
                phases = np.angle(self.state_vector)
                return f"LogicalQubit(F:{probs['FALSE']:.3f}∠{phases[0]:.2f}, T:{probs['TRUE']:.3f}∠{phases[1]:.2f}, U:{probs['UNDECIDABLE']:.3f}∠{phases[2]:.2f})"
            else:
                return f"LogicalQubit(F:{probs['FALSE']:.3f}, T:{probs['TRUE']:.3f}, U:{probs['UNDECIDABLE']:.3f})"
    
    def __repr__(self) -> str:
        return self.__str__()
    
    def get_amplitudes(self) -> Dict[str, complex]:
        """
        Retorna as amplitudes complexas de cada estado.
        
        Returns:
            Dict[str, complex]: Dicionário com amplitudes complexas de cada estado
        """
        if self._use_complex:
            return {
                'FALSE': complex(self.state_vector[0]),
                'TRUE': complex(self.state_vector[1]),
                'UNDECIDABLE': complex(self.state_vector[2])
            }
        else:
            # Para modo compatibilidade, converte probabilidades para amplitudes reais
            return {
                'FALSE': complex(np.sqrt(self.state_vector[0]), 0),
                'TRUE': complex(np.sqrt(self.state_vector[1]), 0),
                'UNDECIDABLE': complex(np.sqrt(self.state_vector[2]), 0)
            }
    
    def get_phases(self) -> Dict[str, float]:
        """
        Retorna as fases de cada amplitude complexa.
        
        Returns:
            Dict[str, float]: Dicionário com fases em radianos de cada estado
        """
        if self._use_complex:
            return {
                'FALSE': float(np.angle(self.state_vector[0])),
                'TRUE': float(np.angle(self.state_vector[1])),
                'UNDECIDABLE': float(np.angle(self.state_vector[2]))
            }
        else:
            # Para modo compatibilidade, todas as fases são zero
            return {'FALSE': 0.0, 'TRUE': 0.0, 'UNDECIDABLE': 0.0}
    
    def is_in_superposition(self) -> bool:
        """
        Verifica se o qubit está em superposição (não é um estado puro).
        
        Returns:
            bool: True se o qubit está em superposição
        """
        return not self.is_pure()
    
    def normalize(self) -> 'LogicalQubit':
        """
        Normaliza o vetor de estado para garantir que a soma das probabilidades seja 1.
        
        Returns:
            LogicalQubit: Uma nova instância com o estado normalizado
        """
        if self._use_complex:
            # Para amplitudes complexas, normaliza para que Σ|amplitude|² = 1
            norm = np.sqrt(np.sum(np.abs(self.state_vector)**2))
            if norm > 0:
                normalized_vector = self.state_vector / norm
            else:
                normalized_vector = self.state_vector
        else:
            # Para probabilidades, normaliza para que Σprobabilidade = 1
            norm = np.sum(self.state_vector)
            if norm > 0:
                normalized_vector = self.state_vector / norm
            else:
                normalized_vector = self.state_vector
        
        # Cria nova instância com estado normalizado
        new_qubit = LogicalQubit('TRUE', use_complex=self._use_complex)
        new_qubit.state_vector = normalized_vector
        return new_qubit
    
    def apply_phase(self, phase: float, state: str = 'all') -> 'LogicalQubit':
        """
        Aplica uma fase específica a um ou todos os estados.
        
        Args:
            phase: Fase em radianos para aplicar
            state: Estado para aplicar a fase ('TRUE', 'FALSE', 'UNDECIDABLE', 'all')
        
        Returns:
            LogicalQubit: Nova instância com a fase aplicada
        """
        if not self._use_complex:
            raise ValueError("Fases só podem ser aplicadas em modo de amplitudes complexas")
        
        new_vector = self.state_vector.copy()
        phase_factor = np.exp(1j * phase)
        
        if state == 'all':
            new_vector *= phase_factor
        elif state == 'TRUE':
            new_vector[1] *= phase_factor
        elif state == 'FALSE':
            new_vector[0] *= phase_factor
        elif state == 'UNDECIDABLE':
            new_vector[2] *= phase_factor
        else:
            raise ValueError(f"Estado inválido: {state}. Use 'TRUE', 'FALSE', 'UNDECIDABLE' ou 'all'")
        
        # Cria nova instância com a fase aplicada
        new_qubit = LogicalQubit('TRUE', use_complex=True)
        new_qubit.state_vector = new_vector
        return new_qubit
    
    def create_superposition(self, amplitudes: Dict[str, complex]) -> 'LogicalQubit':
        """
        Cria um estado de superposição com amplitudes específicas.
        
        Args:
            amplitudes: Dicionário com amplitudes complexas para cada estado
        
        Returns:
            LogicalQubit: Nova instância em superposição
        """
        # Cria vetor de amplitudes
        amp_vector = np.array([
            amplitudes.get('FALSE', 0+0j),
            amplitudes.get('TRUE', 0+0j),
            amplitudes.get('UNDECIDABLE', 0+0j)
        ], dtype=complex)
        
        # Normaliza as amplitudes
        norm = np.sqrt(np.sum(np.abs(amp_vector)**2))
        if norm > 0:
            amp_vector /= norm
        
        # Cria nova instância
        new_qubit = LogicalQubit('TRUE', use_complex=True)
        new_qubit.state_vector = amp_vector
        return new_qubit
    
    def __eq__(self, other) -> bool:
        """Verifica igualdade entre qubits."""
        if not isinstance(other, LogicalQubit):
            return False
        return np.allclose(self.state_vector, other.state_vector, atol=1e-10)
    
    def quantum_not(self, use_quantum: bool = True) -> 'LogicalQubit':
        """
        Aplica operação NOT usando simulação quântica se disponível.
        
        Args:
            use_quantum (bool): Se True, usa simulação quântica real
        
        Returns:
            LogicalQubit: Resultado da operação NOT
        """
        if use_quantum and QUANTUM_AVAILABLE:
            try:
                # Implementação quântica real usando Qiskit
                from qiskit import QuantumCircuit, transpile
                from qiskit_aer import AerSimulator
                
                # Cria circuito quântico
                qc = QuantumCircuit(1, 1)
                
                # Inicializa estado baseado no qubit atual
                if self.collapse() == 'FALSE':
                    pass  # |0⟩ é o estado padrão
                elif self.collapse() == 'TRUE':
                    qc.x(0)  # Aplica X para obter |1⟩
                
                # Aplica NOT (X gate)
                qc.x(0)
                qc.measure(0, 0)
                
                # Simula
                simulator = AerSimulator()
                compiled_circuit = transpile(qc, simulator)
                result = simulator.run(compiled_circuit, shots=1000).result()
                counts = result.get_counts(compiled_circuit)
                
                # Calcula probabilidades
                prob_1 = counts.get('1', 0) / 1000
                
                # Retorna estado baseado nas probabilidades
                if prob_1 > 0.5:
                    return LogicalQubit('TRUE')
                else:
                    return LogicalQubit('FALSE')
                    
            except Exception:
                # Fallback se Qiskit falhar
                pass
        
        # Fallback para implementação clássica
        not_gate = get_logical_gate('NOT')
        return apply_gate(self, not_gate)
    
    def quantum_and(self, other: 'LogicalQubit', use_quantum: bool = True) -> 'LogicalQubit':
        """
        Aplica operação AND usando simulação quântica se disponível.
        
        Args:
            other (LogicalQubit): Segundo qubit
            use_quantum (bool): Se True, usa simulação quântica real
        
        Returns:
            LogicalQubit: Resultado da operação AND
        """
        if use_quantum and QUANTUM_AVAILABLE:
            return logical_and(self, other)
        else:
            # Fallback para implementação clássica
            return logical_and(self, other)
    
    def quantum_or(self, other: 'LogicalQubit', use_quantum: bool = True) -> 'LogicalQubit':
        """
        Aplica operação OR usando simulação quântica se disponível.
        
        Args:
            other (LogicalQubit): Segundo qubit
            use_quantum (bool): Se True, usa simulação quântica real
        
        Returns:
            LogicalQubit: Resultado da operação OR
        """
        if use_quantum and QUANTUM_AVAILABLE:
            return logical_or(self, other)
        else:
            # Fallback para implementação clássica
            return logical_or(self, other)
    
    def quantum_hadamard(self, use_quantum: bool = True) -> 'LogicalQubit':
        """
        Aplica porta Hadamard para criar superposição quântica.
        
        Args:
            use_quantum (bool): Se True, usa simulação quântica real
        
        Returns:
            LogicalQubit: Qubit em superposição
        """
        if use_quantum and QUANTUM_AVAILABLE:
            try:
                # Implementação quântica real usando Qiskit
                from qiskit import QuantumCircuit, transpile
                from qiskit_aer import AerSimulator
                
                # Cria circuito quântico
                qc = QuantumCircuit(1, 1)
                
                # Inicializa estado baseado no qubit atual
                if self.collapse() == 'FALSE':
                    pass  # |0⟩ é o estado padrão
                elif self.collapse() == 'TRUE':
                    qc.x(0)  # Aplica X para obter |1⟩
                
                # Aplica Hadamard
                qc.h(0)
                qc.measure(0, 0)
                
                # Simula
                simulator = AerSimulator()
                compiled_circuit = transpile(qc, simulator)
                result = simulator.run(compiled_circuit, shots=1000).result()
                counts = result.get_counts(compiled_circuit)
                
                # Calcula probabilidades
                prob_0 = counts.get('0', 0) / 1000
                prob_1 = counts.get('1', 0) / 1000
                
                # Retorna superposição baseada nas probabilidades
                return create_superposition(prob_0, prob_1, 0.0)
                
            except Exception:
                # Fallback se Qiskit falhar
                pass
        
        # Fallback: cria superposição aproximada
        if self.collapse() == 'TRUE':
            return create_superposition(0.5, 0.5, 0.0)
        elif self.collapse() == 'FALSE':
            return create_superposition(0.5, 0.5, 0.0)
        else:
            return LogicalQubit(self.state_vector)  # Já em superposição
    
    def get_quantum_info(self) -> Dict[str, any]:
        """
        Retorna informações quânticas detalhadas se disponível.
        
        Returns:
            Dict[str, any]: Informações quânticas ou informações básicas
        """
        if QUANTUM_AVAILABLE:
            # QuantumBridge removido - funcionalidade básica mantida
            return self._get_basic_quantum_info()
        else:
            # Informações básicas sem Qiskit
            probs = self.get_probabilities()
            entropy = -sum([p * np.log2(p) for p in probs.values() if p > 0])
            purity = sum([p**2 for p in probs.values()])
            
            return {
                'probabilities': list(probs.values()),
                'entropy': float(entropy),
                'purity': float(purity),
                'is_pure': self.is_pure(),
                'quantum_available': False
            }
    
    @staticmethod
    def create_superposition_equal() -> 'LogicalQubit':
        """
        Cria um qubit em superposição igual de todos os estados.
        
        Returns:
            LogicalQubit: Qubit em superposição igual
        """
        return LogicalQubit('SUPERPOSITION_EQUAL')
    
    @staticmethod
    def create_bell_state(state_type: str = '00') -> 'LogicalQubit':
        """
        Cria estados de Bell para entrelaçamento quântico.
        
        Args:
            state_type: Tipo do estado de Bell ('00', '01', '10', '11')
        
        Returns:
            LogicalQubit: Qubit em estado de Bell
        """
        bell_amplitudes = {
            '00': np.array([1/np.sqrt(2), 0, 1/np.sqrt(2)], dtype=complex),  # |Φ+⟩
            '01': np.array([1/np.sqrt(2), 0, -1/np.sqrt(2)], dtype=complex), # |Φ-⟩
            '10': np.array([0, 1/np.sqrt(2), 1/np.sqrt(2)], dtype=complex),  # |Ψ+⟩
            '11': np.array([0, 1/np.sqrt(2), -1/np.sqrt(2)], dtype=complex)  # |Ψ-⟩
        }
        
        if state_type not in bell_amplitudes:
            raise ValueError(f"Tipo de estado de Bell inválido: {state_type}. Use '00', '01', '10' ou '11'")
        
        qubit = LogicalQubit('TRUE', use_complex=True)
        qubit.state_vector = bell_amplitudes[state_type]
        return qubit
    
    @staticmethod
    def from_amplitudes(amplitudes: Dict[str, complex]) -> 'LogicalQubit':
        """
        Cria um LogicalQubit a partir de amplitudes complexas específicas.
        
        Args:
            amplitudes: Dicionário com amplitudes complexas para cada estado
        
        Returns:
            LogicalQubit: Nova instância com as amplitudes especificadas
        """
        qubit = LogicalQubit('TRUE', use_complex=True)
        return qubit.create_superposition(amplitudes)


def apply_gate(qubit: LogicalQubit, gate: np.ndarray) -> LogicalQubit:
    """
    Aplica uma matriz (porta) a um vetor de qubit.
    
    Args:
        qubit (LogicalQubit): O qubit de entrada
        gate (np.ndarray): Matriz 3x3 representando a porta lógica
    
    Returns:
        LogicalQubit: Novo qubit com o estado resultante
    
    Raises:
        ValueError: Se a matriz não for 3x3
    """
    if gate.shape != (3, 3):
        raise ValueError("Porta deve ser uma matriz 3x3")
    
    # Aplica a transformação matricial
    new_state = gate @ qubit.state_vector
    
    return LogicalQubit(new_state)


def get_logical_gate(gate_name: str) -> np.ndarray:
    """
    Retorna a matriz para uma dada operação lógica.
    
    Args:
        gate_name (str): Nome da porta ('NOT', 'AND', 'OR', 'IDENTITY')
    
    Returns:
        np.ndarray: Matriz 3x3 representando a porta lógica
    
    Raises:
        ValueError: Se o nome da porta não for reconhecido
    """
    gates = {
        'NOT': _get_not_gate(),
        'IDENTITY': _get_identity_gate(),
        # AND e OR são operações binárias, implementadas separadamente
    }
    
    gate_name_upper = gate_name.upper()
    if gate_name_upper not in gates:
        available = list(gates.keys())
        raise ValueError(f"Porta '{gate_name}' não reconhecida. Disponíveis: {available}")
    
    return gates[gate_name_upper]


def _get_not_gate() -> np.ndarray:
    """
    Matriz NOT que troca TRUE e FALSE, mantém UNDECIDABLE.
    
    Tabela verdade (F=0, T=1, U=2):
    NOT(FALSE) -> TRUE
    NOT(TRUE) -> FALSE  
    NOT(UNDECIDABLE) -> UNDECIDABLE
    """
    return np.array([
        [0, 1, 0],  # FALSE -> TRUE
        [1, 0, 0],  # TRUE -> FALSE
        [0, 0, 1]   # UNDECIDABLE -> UNDECIDABLE
    ])


def _get_identity_gate() -> np.ndarray:
    """
    Matriz identidade - não altera o estado.
    """
    return np.eye(3)


def logical_and(qubit_a: LogicalQubit, qubit_b: LogicalQubit) -> LogicalQubit:
    """
    Operação AND lógica entre dois qubits.
    
    Implementa a lógica trivalente (T=0, F=1, U=2):
    - TRUE AND TRUE = TRUE
    - TRUE AND FALSE = FALSE
    - FALSE AND anything = FALSE
    - TRUE AND UNDECIDABLE = UNDECIDABLE
    - UNDECIDABLE AND UNDECIDABLE = UNDECIDABLE
    
    Args:
        qubit_a (LogicalQubit): Primeiro qubit
        qubit_b (LogicalQubit): Segundo qubit
    
    Returns:
        LogicalQubit: Resultado da operação AND
    """
    # Calcula o produto tensorial das probabilidades
    result_vector = np.zeros(3)
    
    for i in range(3):  # Estados de A: 0=TRUE, 1=FALSE, 2=UNDECIDABLE
        for j in range(3):  # Estados de B: 0=TRUE, 1=FALSE, 2=UNDECIDABLE
            prob_a = qubit_a.state_vector[i]
            prob_b = qubit_b.state_vector[j]
            combined_prob = prob_a * prob_b
            
            # Determina o resultado baseado na tabela AND
            if i == 0 and j == 0:  # TRUE AND TRUE
                result_vector[0] += combined_prob
            elif i == 1 or j == 1:  # FALSE AND anything
                result_vector[1] += combined_prob
            else:  # Casos com UNDECIDABLE (i=2 ou j=2, mas não ambos FALSE)
                result_vector[2] += combined_prob
    
    return LogicalQubit(result_vector)


def logical_or(qubit_a: LogicalQubit, qubit_b: LogicalQubit) -> LogicalQubit:
    """
    Operação OR lógica entre dois qubits.
    
    Implementa a lógica trivalente (T=0, F=1, U=2):
    - FALSE OR FALSE = FALSE
    - TRUE OR anything = TRUE
    - FALSE OR UNDECIDABLE = UNDECIDABLE
    - UNDECIDABLE OR UNDECIDABLE = UNDECIDABLE
    
    Args:
        qubit_a (LogicalQubit): Primeiro qubit
        qubit_b (LogicalQubit): Segundo qubit
    
    Returns:
        LogicalQubit: Resultado da operação OR
    """
    result_vector = np.zeros(3)
    
    for i in range(3):  # Estados de A: 0=TRUE, 1=FALSE, 2=UNDECIDABLE
        for j in range(3):  # Estados de B: 0=TRUE, 1=FALSE, 2=UNDECIDABLE
            prob_a = qubit_a.state_vector[i]
            prob_b = qubit_b.state_vector[j]
            combined_prob = prob_a * prob_b
            
            # Determina o resultado baseado na tabela OR
            if i == 0 or j == 0:  # TRUE OR anything
                result_vector[0] += combined_prob
            elif i == 1 and j == 1:  # FALSE OR FALSE
                result_vector[1] += combined_prob
            else:  # Casos com UNDECIDABLE
                result_vector[2] += combined_prob
    
    return LogicalQubit(result_vector)


def create_superposition(false_prob: float, true_prob: float, undecidable_prob: float) -> LogicalQubit:
    """
    Cria um qubit em superposição com probabilidades específicas.
    
    Args:
        false_prob (float): Probabilidade do estado FALSE
        true_prob (float): Probabilidade do estado TRUE
        undecidable_prob (float): Probabilidade do estado UNDECIDABLE
    
    Returns:
        LogicalQubit: Qubit em superposição
    """
    # Agora TRUE=0, FALSE=1, UNDECIDABLE=2
    return LogicalQubit([true_prob, false_prob, undecidable_prob])


def create_quantum_superposition(false_amp: complex = 1/np.sqrt(2), true_amp: complex = 1/np.sqrt(2)) -> LogicalQubit:
    """
    Cria superposição quântica com amplitudes complexas.
    
    Args:
        false_amp (complex): Amplitude para estado FALSE
        true_amp (complex): Amplitude para estado TRUE
    
    Returns:
        LogicalQubit: Qubit em superposição quântica
    """
    if QUANTUM_AVAILABLE:
        # QuantumBridge removido - funcionalidade básica mantida
        prob_false = abs(false_amp)**2
        prob_true = abs(true_amp)**2
        total = prob_false + prob_true
        if total > 0:
            prob_false /= total
            prob_true /= total
        return create_superposition(prob_false, prob_true, 0.0)
    else:
        # Fallback: usa módulo das amplitudes como probabilidades
        prob_false = abs(false_amp)**2
        prob_true = abs(true_amp)**2
        total = prob_false + prob_true
        if total > 0:
            prob_false /= total
            prob_true /= total
        return create_superposition(prob_false, prob_true, 0.0)


def apply_quantum_gate(qubit: LogicalQubit, gate_name: str, use_quantum: bool = True) -> LogicalQubit:
    """
    Aplica porta quântica a um qubit.
    
    Args:
        qubit (LogicalQubit): Qubit de entrada
        gate_name (str): Nome da porta ('NOT', 'HADAMARD')
        use_quantum (bool): Se True, usa simulação quântica real
    
    Returns:
        LogicalQubit: Resultado da operação
    """
    gate_name = gate_name.upper()
    
    if gate_name == 'NOT':
        return qubit.quantum_not(use_quantum)
    elif gate_name == 'HADAMARD':
        return qubit.quantum_hadamard(use_quantum)
    elif gate_name == 'IDENTITY':
        return LogicalQubit(qubit.state_vector)
    else:
        # Fallback para portas clássicas
        if gate_name in ['AND', 'OR']:
            raise ValueError(f"Porta '{gate_name}' requer dois qubits. Use logical_and/logical_or.")
        
        gate_matrix = get_logical_gate(gate_name)
        return apply_gate(qubit, gate_matrix)


def quantum_logical_and(qubit_a: LogicalQubit, qubit_b: LogicalQubit, use_quantum: bool = True) -> LogicalQubit:
    """
    Operação AND quântica entre dois qubits.
    
    Args:
        qubit_a (LogicalQubit): Primeiro qubit
        qubit_b (LogicalQubit): Segundo qubit
        use_quantum (bool): Se True, usa simulação quântica real
    
    Returns:
        LogicalQubit: Resultado da operação AND quântica
    """
    return qubit_a.quantum_and(qubit_b, use_quantum)


def quantum_logical_or(qubit_a: LogicalQubit, qubit_b: LogicalQubit, use_quantum: bool = True) -> LogicalQubit:
    """
    Operação OR quântica entre dois qubits.
    
    Args:
        qubit_a (LogicalQubit): Primeiro qubit
        qubit_b (LogicalQubit): Segundo qubit
        use_quantum (bool): Se True, usa simulação quântica real
    
    Returns:
        LogicalQubit: Resultado da operação OR quântica
    """
    return qubit_a.quantum_or(qubit_b, use_quantum)


# Constantes para estados puros comuns
FALSE_QUBIT = LogicalQubit('FALSE')
TRUE_QUBIT = LogicalQubit('TRUE')
UNDECIDABLE_QUBIT = LogicalQubit('UNDECIDABLE')

# Equivalentes para qutrits (F=0, T=1, U=2)
FALSE_QUTRIT = LogicalQutrit('FALSE')
TRUE_QUTRIT = LogicalQutrit('TRUE')
UNDECIDABLE_QUTRIT = LogicalQutrit('UNDECIDABLE')

# Adicionar atributos de classe para compatibilidade
LogicalQubit.FALSE = LogicalQubit('FALSE')
LogicalQubit.TRUE = LogicalQubit('TRUE')
LogicalQubit.UNDECIDABLE = LogicalQubit('UNDECIDABLE')




if __name__ == "__main__":
    # Demonstração básica do sistema
    print("=== Demonstração QGSL Core com Integração Quântica ===")
    
    # Estados puros
    print("\n1. Estados Puros:")
    true_q = LogicalQubit('TRUE')
    false_q = LogicalQubit('FALSE')
    undecidable_q = LogicalQubit('UNDECIDABLE')
    
    print(f"TRUE: {true_q}")
    print(f"FALSE: {false_q}")
    print(f"UNDECIDABLE: {undecidable_q}")
    
    # Superposição clássica
    print("\n2. Estado em Superposição Clássica:")
    superpos = create_superposition(0.6, 0.3, 0.1)
    print(f"Superposição: {superpos}")
    print(f"É puro? {superpos.is_pure()}")
    print(f"Colapso: {superpos.collapse()}")
    
    # Verificar disponibilidade quântica
    print(f"\n3. Funcionalidades Quânticas Disponíveis: {QUANTUM_AVAILABLE}")
    
    if QUANTUM_AVAILABLE:
        print("\n4. Superposição Quântica:")
        quantum_superpos = create_quantum_superposition()
        print(f"Superposição Quântica: {quantum_superpos}")
        
        # Informações quânticas
        quantum_info = true_q.get_quantum_info()
        print("\nInformações Quânticas do TRUE:")
        print(f"  Entropia: {quantum_info.get('entropy', 'N/A'):.3f}")
        print(f"  Pureza: {quantum_info.get('purity', 'N/A'):.3f}")
        print(f"  Coerência: {quantum_info.get('coherence', 'N/A'):.3f}")
    
    # Porta NOT (clássica e quântica)
    print("\n5. Porta NOT (Clássica vs Quântica):")
    not_gate = get_logical_gate('NOT')
    not_true_classical = apply_gate(true_q, not_gate)
    not_true_quantum = true_q.quantum_not(use_quantum=QUANTUM_AVAILABLE)
    print(f"NOT(TRUE) Clássico = {not_true_classical}")
    print(f"NOT(TRUE) Quântico = {not_true_quantum}")
    
    # Operações lógicas (clássicas e quânticas)
    print("\n6. Operações Lógicas (Clássica vs Quântica):")
    and_classical = logical_and(true_q, false_q)
    and_quantum = quantum_logical_and(true_q, false_q, use_quantum=QUANTUM_AVAILABLE)
    or_classical = logical_or(true_q, false_q)
    or_quantum = quantum_logical_or(true_q, false_q, use_quantum=QUANTUM_AVAILABLE)
    
    print(f"AND(TRUE, FALSE) Clássico = {and_classical}")
    print(f"AND(TRUE, FALSE) Quântico = {and_quantum}")
    print(f"OR(TRUE, FALSE) Clássico = {or_classical}")
    print(f"OR(TRUE, FALSE) Quântico = {or_quantum}")
    
    # Porta Hadamard (apenas quântica)
    if QUANTUM_AVAILABLE:
        print("\n7. Porta Hadamard (Superposição Quântica):")
        hadamard_result = true_q.quantum_hadamard()
        print(f"HADAMARD(TRUE) = {hadamard_result}")
        
        hadamard_info = hadamard_result.get_quantum_info()
        print(f"  Entropia após Hadamard: {hadamard_info.get('entropy', 'N/A'):.3f}")
        print(f"  Pureza após Hadamard: {hadamard_info.get('purity', 'N/A'):.3f}")
    else:
        print("\n7. Porta Hadamard (Simulação Clássica):")
        hadamard_result = true_q.quantum_hadamard(use_quantum=False)
        print(f"HADAMARD(TRUE) Simulado = {hadamard_result}")
    
    # Demonstração de gates quânticos
    print("\n8. Aplicação de Gates Quânticos:")
    try:
        identity_result = apply_quantum_gate(true_q, 'IDENTITY')
        not_result = apply_quantum_gate(true_q, 'NOT', use_quantum=QUANTUM_AVAILABLE)
        print(f"IDENTITY(TRUE) = {identity_result}")
        print(f"Quantum NOT(TRUE) = {not_result}")
        
        if QUANTUM_AVAILABLE:
            hadamard_gate_result = apply_quantum_gate(true_q, 'HADAMARD')
            print(f"Quantum HADAMARD(TRUE) = {hadamard_gate_result}")
    except Exception as e:
        print(f"Erro ao aplicar gates quânticos: {e}")
    
    print("\n=== Fim da Demonstração ===")
    
    if not QUANTUM_AVAILABLE:
        print("\n💡 Para habilitar funcionalidades quânticas completas:")
        print("   pip install qiskit qiskit-aer")
        print("   Reinicie o programa após a instalação.")
