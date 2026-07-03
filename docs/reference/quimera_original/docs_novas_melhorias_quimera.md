# Documentação de Convenções e Contratos - Projeto Quimera

Este documento detalha as convenções técnicas, contratos de interface e especificações internas do Projeto Quimera, fornecendo uma referência completa para desenvolvedores e usuários avançados.

## 1. Ordem T/F/U Única e Helpers

### 1.1 Sistema de Lógica Ternária

O Projeto Quimera implementa um sistema de lógica ternária baseado na ordenação única **T/F/U** (True/False/Undecidable), definida consistentemente em todo o sistema:

```python
# Ordem padronizada: TRUE=0, FALSE=1, UNDECIDABLE=2
TRUTH_TO_INDEX = {
    "TRUE": 0,
    "FALSE": 1,
    "UNDECIDABLE": 2,
}

# Estados vetoriais correspondentes
TRUE_VECTOR = np.array([1.0, 0.0, 0.0], dtype=float)
FALSE_VECTOR = np.array([0.0, 1.0, 0.0], dtype=float)
UNDECIDABLE_VECTOR = np.array([0.0, 0.0, 1.0], dtype=float)
```

### 1.2 Helpers de Lógica Ternária

#### LogicalQubit
Classe principal para representação de estados lógicos ternários:

```python
from core.qgsl_core import LogicalQubit

# Criação de estados puros
true_state = LogicalQubit('TRUE')
false_state = LogicalQubit('FALSE')
undecidable_state = LogicalQubit('UNDECIDABLE')

# Estados probabilísticos
mixed_state = LogicalQubit([0.6, 0.3, 0.1])  # 60% TRUE, 30% FALSE, 10% UNDECIDABLE
```

#### Operações Lógicas

```python
from core.qgsl_core import logical_and, logical_or

# Operações AND e OR com lógica ternária
result_and = logical_and(true_state, false_state)  # Resultado: FALSE
result_or = logical_or(true_state, undecidable_state)  # Resultado: TRUE

# Colapso determinístico para obter valor final
final_value = result_and.collapse(deterministic=True)  # 'FALSE'
```

#### Tabelas Verdade

**Operação AND:**
| A | B | A AND B |
|---|---|---|
| T | T | T |
| T | F | F |
| T | U | U |
| F | T | F |
| F | F | F |
| F | U | F |
| U | T | U |
| U | F | F |
| U | U | U |

**Operação OR:**
| A | B | A OR B |
|---|---|---|
| T | T | T |
| T | F | T |
| T | U | T |
| F | T | T |
| F | F | F |
| F | U | U |
| U | T | T |
| U | F | U |
| U | U | U |

## 2. Sentinelas do Parser de Hipóteses

### 2.1 Sistema de Sentinelas

O parser de hipóteses utiliza sentinelas específicas para delimitar blocos JSON estruturados:

```python
# Sentinelas obrigatórias
SENTINEL_BEGIN = "BEGIN_HYPOTHESES_JSON"
SENTINEL_END = "END_HYPOTHESES_JSON"
```

### 2.2 Formatos Suportados

#### Formato com Sentinelas (Recomendado)
```
Aqui está minha análise da questão:

BEGIN_HYPOTHESES_JSON
{
    "facts": [
        {"subject": "João", "relation": "é", "object": "programador"}
    ],
    "rules": [
        {"head": "X é competente", "body": "X é programador"}
    ],
    "meta": {"confidence": 0.8}
}
END_HYPOTHESES_JSON

Essa é minha conclusão baseada nos dados.
```

#### Formato com Fenced Code Blocks
```
Resultado da análise:

```json
{
    "facts": [{"subject": "Maria", "relation": "trabalha_em", "object": "empresa"}],
    "rules": [],
    "meta": {"source": "inference"}
}
```

Análise completa.
```

### 2.3 Schema Obrigatório

Todas as hipóteses devem seguir o schema:

```json
{
    "facts": [
        {
            "subject": "string",
            "relation": "string", 
            "object": "string"
        }
    ],
    "rules": [
        {
            "head": "string",
            "body": "string"
        }
    ],
    "meta": {
        "confidence": "number (opcional)",
        "source": "string (opcional)"
    }
}
```

### 2.4 Exemplos de Uso

```python
from core.llm_hypothesis_parser import LLMHypothesisParser, parse_hypotheses

# Parser rigoroso (exige sentinelas)
strict_parser = LLMHypothesisParser(strict_sentinels=True)
result = strict_parser.parse(text_with_sentinels)

# Parser flexível (aceita JSON solto)
flexible_parser = LLMHypothesisParser(strict_sentinels=False)
result = flexible_parser.parse(text_with_json)

# Função de conveniência
try:
    hypotheses = parse_hypotheses(llm_response)
    facts = hypotheses['facts']
    rules = hypotheses['rules']
except HypothesisParseError as e:
    print(f"Erro no parsing: {e}")
```

## 3. Estratégia `decide_strategy` e Ativação do Qutrit

### 3.1 Governador Entrópico

O `EntropicGovernor` implementa a função `decide_strategy()` que determina automaticamente quando ativar o processamento qutrit baseado em heurísticas de incerteza e orçamento disponível.

### 3.2 Constantes de Limiar

```python
# Limiar mínimo de incerteza para considerar ativação do qutrit
UNDECIDABILITY_THRESHOLD = 0.35  # 35% de incerteza

# Fator mínimo de orçamento necessário para suportar qutrit
MIN_BUDGET_FACTOR_FOR_QUTRIT = 0.6  # 60% do orçamento disponível
```

### 3.3 Lógica de Ativação

O qutrit é ativado quando **ambas** as condições são atendidas:

1. **Alta Incerteza:** `difficulty >= UNDECIDABILITY_THRESHOLD`
2. **Orçamento Suficiente:** `budget_factor >= MIN_BUDGET_FACTOR_FOR_QUTRIT`

```python
# Exemplo de decisão de estratégia
budget = {
    'energy_mj': 80.0,   # 80 milijoules disponíveis
    'time_ms': 4000.0    # 4 segundos disponíveis
}
difficulty = 0.7  # 70% de incerteza

strategy = governor.decide_strategy(budget, difficulty)
print(f"Usar qutrit: {strategy['use_qutrit']}")  # True (alta incerteza + budget OK)
```

### 3.4 Cálculo do Budget Factor

```python
# Normalização baseada em valores de referência
energy_factor = min(1.0, energy_budget / 50.0)  # 50mJ como referência
time_factor = min(1.0, time_budget / 3000.0)    # 3s como referência
budget_factor = min(energy_factor, time_factor)  # Fator limitante
```

### 3.5 Cenários de Ativação

| Energia (mJ) | Tempo (ms) | Dificuldade | Budget Factor | Qutrit Ativo | Motivo |
|--------------|------------|-------------|---------------|--------------|--------|
| 100.0 | 5000 | 0.8 | 1.0 | ✅ Sim | Alta incerteza + budget alto |
| 100.0 | 5000 | 0.2 | 1.0 | ❌ Não | Baixa incerteza (query fácil) |
| 20.0 | 1000 | 0.8 | 0.33 | ❌ Não | Budget insuficiente |
| 35.0 | 2100 | 0.35 | 0.7 | ✅ Sim | No limiar exato |
| 25.0 | 1500 | 0.4 | 0.5 | ❌ Não | Budget abaixo do limiar |

### 3.6 Variável de Ambiente

O qutrit pode ser forçado via variável de ambiente:

```bash
# Força ativação do qutrit independente da heurística
export QUIMERA_QUTRIT_ENABLED=true
python core/chimera.py --query "Pergunta complexa?"
```

## 4. Schema do Ledger e Exemplos Reais

### 4.1 Atualização de Schema (2025-08)

O schema do Proof Ledger foi enriquecido para rastreabilidade completa:
- query_id: identificador estável (hash curto da consulta)
- llm_primary: provedor (ex.: openrouter_assembly, openai, local_gpt_oss)
- llm_model: modelo efetivo utilizado (ex.: deepseek/deepseek-chat-v3-0324:free)
- llm_fallback_used: se houve fallback de provedor
- hypotheses: lista/dict com hipóteses estruturadas quando disponíveis
- prove: objeto com proved/rejected/undecidable/trace
- security: objeto com status e notas (quando aplicável)
- domain, complexity, processing_time_ms, cache_hit: metadados de execução

Exemplo atualizado:
```json
{
  "ts": "2025-05-01T12:34:56.789Z",
  "version": "quimera-v1.0",
  "checksum": "a1b2c3d4e5f6a7b8",
  "query_id": "0f3e9a1b2c3d",
  "query": "Se A é verdadeiro e B é falso, qual é A AND B?",
  "llm_primary": "openrouter_assembly",
  "llm_model": "deepseek/deepseek-chat-v3-0324:free",
  "llm_fallback_used": false,
  "hypotheses": [{"subject":"A","relation":"AND","object":"B"}],
  "prove": {"proved":[],"rejected":[],"undecidable":[],"trace":[]},
  "security": {"status":"ok"},
  "budget": {"energy_mj":30.0,"time_seconds":30.0,"cpu_percent":18.0,"memory_mb":512.0},
  "consumption": {"energy_mj":12.4,"time_ms":910,"cpu_percent":15.0,"memory_mb":420.0},
  "governor": {"beam_width":5,"max_depth":10,"use_qutrit":true,"optimization_mode":"balanced"},
  "domain": "general",
  "complexity": "simple",
  "processing_time_ms": 920,
  "cache_hit": false
}
```

### 4.1 Estrutura do Proof Ledger

O Proof Ledger registra todas as consultas em formato JSONL com schema rigoroso para auditoria:

```json
{
    "query_id": "string",
    "ts": "ISO 8601 timestamp",
    "version": "string",
    "checksum": "SHA-256 hash (16 chars)",
    "llm_primary": "string",
    "fallback_used": "boolean",
    "hypotheses": "string|object",
    "prove": "string|object",
    "security": "string|object",
    "budget": {
        "energy_mj": "number",
        "time_ms": "number",
        "cpu_percent": "number",
        "memory_mb": "number"
    },
    "consumption": {
        "energy_mj": "number",
        "time_ms": "number",
        "cpu_percent": "number",
        "memory_mb": "number"
    },
    "governor": {
        "beam_width": "number",
        "max_depth": "number",
        "use_qutrit": "boolean",
        "optimization_mode": "string"
    }
}
```

### 4.2 Exemplo Real de Entrada

```json
{
    "query_id": "q_20241201_143022_001",
    "ts": "2024-12-01T14:30:22.123456Z",
    "version": "quimera-v1.0",
    "checksum": "a1b2c3d4e5f67890",
    "llm_primary": "local_gpt_oss",
    "fallback_used": false,
    "hypotheses": {
        "facts": [
            {"subject": "João", "relation": "é", "object": "programador"},
            {"subject": "programadores", "relation": "usam", "object": "computadores"}
        ],
        "rules": [
            {"head": "X é competente", "body": "X é programador"}
        ],
        "meta": {"confidence": 0.85, "source": "llm_inference"}
    },
    "prove": {
        "proved": ["João é competente"],
        "rejected": [],
        "undecidable": [],
        "trace": ["rule_application", "forward_chaining"]
    },
    "security": {
        "status": "passed",
        "checks": ["ethical_constraints", "safety_bounds"],
        "notes": []
    },
    "budget": {
        "energy_mj": 50.0,
        "time_ms": 3000,
        "cpu_percent": 25.0,
        "memory_mb": 512.0
    },
    "consumption": {
        "energy_mj": 28.5,
        "time_ms": 1850,
        "cpu_percent": 18.2,
        "memory_mb": 384.0
    },
    "governor": {
        "beam_width": 4,
        "max_depth": 8,
        "use_qutrit": true,
        "optimization_mode": "balanced"
    }
}
```

### 4.3 Exemplo com Fallback

```json
{
    "query_id": "q_20241201_143045_002",
    "ts": "2024-12-01T14:30:45.789012Z",
    "version": "quimera-v1.0",
    "checksum": "f6e5d4c3b2a19876",
    "llm_primary": "openai",
    "fallback_used": true,
    "hypotheses": "hipótese não estruturada",
    "prove": "parsing_failed",
    "security": "passed",
    "budget": {
        "energy_mj": 200.0,
        "time_ms": 10000,
        "cpu_percent": 40.0,
        "memory_mb": 1024.0
    },
    "consumption": {
        "energy_mj": 185.3,
        "time_ms": 9200,
        "cpu_percent": 38.5,
        "memory_mb": 896.0
    },
    "governor": {
        "beam_width": 6,
        "max_depth": 12,
        "use_qutrit": false,
        "optimization_mode": "full"
    }
}
```

### 4.4 Operações do Ledger

```python
from core import proof_ledger

# Registrar evento (baixo nível; o Chimera registra automaticamente)
event = {
    "query_id": "q1",
    "llm_primary": "local_gpt_oss",
    "llm_model": "gpt-oss-20b",
    "llm_fallback_used": False,
    "hypotheses": [{"subject": "X", "relation": "é", "object": "coisa"}],
    "prove": {"proved": [], "rejected": [], "undecidable": [], "trace": []},
    "security": {"status": "ok"},
    "budget": {"energy_mj": 30, "time_seconds": 1.5},
    "consumption": {"energy_mj": 15, "time_ms": 800},
    "governor": {"beam_width": 3, "use_qutrit": True, "optimization_mode": "balanced"},
    "processing_time_ms": 900,
    "cache_hit": False
}

ledger_file = proof_ledger.record(event)

# Carregar entradas
entries = proof_ledger.load_entries()
latest_entry = entries[-1] if entries else None

# Converter para DataFrame para análise
df = proof_ledger.entries_to_dataframe(entries, ["proved"])
```

### 4.5 Validação de Integridade

Cada entrada possui checksum SHA-256 para verificação de integridade:

```python
import json
from core.proof_ledger import calculate_checksum

# Verificar integridade
entry = load_entry_from_ledger()
stored_checksum = entry.pop("checksum")
expected_checksum = calculate_checksum(json.dumps(entry, sort_keys=True, ensure_ascii=False))

if stored_checksum == expected_checksum:
    print("Entrada íntegra")
else:
    print("Entrada corrompida!")
```

## 5. Quick Start e Exemplos Práticos

### 5.1 Configuração Básica

```bash
# Instalar dependências
pip install -r requirements.txt

# Configurar LM Studio (opcional)
export LMSTUDIO_BASE_URL=http://127.0.0.1:1234/v1
export LMSTUDIO_API_KEY=lm-studio

# Ativar qutrit
export QUIMERA_QUTRIT_ENABLED=true
```

### 5.2 Uso Básico

```bash
# Query simples
python core/chimera.py --query "2 + 2 = ?"

# Query com lógica
python core/chimera.py --query "Se A é verdadeiro e B é falso, qual é A AND B?"

# Query complexa (ativa qutrit automaticamente)
python core/chimera.py --query "Explique o paradoxo do mentiroso"
```

### 5.3 Interface Web

```bash
# Instalar dependências da interface
pip install -r requirements_streamlit.txt

# Executar dashboard
streamlit run .streamlit/streamlit_app.py
```

### 5.4 Testes

```bash
# Testes básicos
pytest -q

# Testes com qutrit
QUIMERA_QUTRIT_ENABLED=true pytest tests/test_qutrit_* -q

# Testes E2E do ledger
pytest tests/test_ledger_e2e.py -v
```

---

**Nota:** Esta documentação é mantida sincronizada com o código. Para atualizações, consulte os módulos correspondentes em `core/` e os testes em `tests/`.
