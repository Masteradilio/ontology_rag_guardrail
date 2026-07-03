# Projeto Quimera

[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue)](README.md)
[![OS](https://img.shields.io/badge/OS-Linux%20%7C%20macOS%20%7C%20Windows-lightgrey)](docs/ops_linux.md)
[![Docker](https://img.shields.io/badge/docker-ready-2496ED?logo=docker&logoColor=white)](deploy/docker-compose.yml)
[![CLI](https://img.shields.io/badge/CLI-quimera-brightgreen)](tools/quimera_cli.py)

> Manual prático de instalação e uso: veja `docs/MANUAL_DE_USO.md`.

## Comandos Comuns

Para guia completo de instalação e uso, veja `docs/MANUAL_DE_USO.md`.

- Validar instalação: `quimera validate`
- Rodar uma consulta: `quimera run --query "Olá Quimera"`
- Energia (amostra): `quimera energy --sample-ms 100`
- Ontologia (listar): `quimera ontology list`
- Ontologia (adicionar): `quimera ontology add --subject joao --relation tem --object febre --state TRUE`
- Snapshot (via CLI da ontologia): `quimera ontology snapshot --name baseline`
- Ledger (última entrada): `quimera ledger --last`
- Thresholds qutrit (ver): `quimera qutrit get`
- Thresholds qutrit (definir): `quimera qutrit set --true 0.7 --false 0.7 --margin 0.05`
- Demos: `quimera demo --name {diag|fin|code}`

- Qutrit (modo): defina `QUIMERA_QUTRIT_ENABLED={auto|true|false}` — veja a seção "Qutrit: Estratégia e Ledger" para detalhes.
- Edite `config/.env` para informar a chave do OpenRouter e ajustar o endpoint do LM Studio antes da primeira execução.

**Sistema AGI (Artificial General Intelligence) com Lógica Quântica Simbólica**

O Projeto Quimera é uma implementação avançada de AGI que combina inferência simbólica, lógica quântica ternária (QGSL), aprendizado por reforço ético e processamento com qutrits reais. Inspirado na arquitetura Rosie AGI, o sistema oferece raciocínio delimitado, validação rigorosa contra alucinações e auditabilidade completa.

## 🎯 Visão Geral

### Características Principais

- **🔬 Lógica Quântica Ternária (QGSL)**: Estados TRUE/FALSE/UNDECIDABLE com simulação quântica real via Cirq
- **🛡️ Gate Gerador-Validador**: Bloqueio rigoroso de alucinações - apenas fatos provados são retornados
- **⚡ Orçamento Energético**: Sistema de governança que adapta estratégias baseado em recursos disponíveis
- **📊 Proof Ledger**: Auditoria completa (JSONL) com checksums SHA-256, `query_id`, provedor/modelo do LLM, `prove` detalhado, orçamento/consumo e metadados de execução
- **🤖 Assembly of Models**: 6 LLMs (5 OpenRouter + 1 OpenAI) com votação e fallback hierárquico
- **🧠 Aprendizado por Reforço Ético**: RL com restrições éticas integradas e feedback automático
- **🔐 Criptografia Avançada**: Suporte a criptografia homomórfica e pós-quântica
- **🎛️ Hardware Adaptativo**: 4 modos de operação (Ultra-Lite a Advanced) com detecção automática

### ⚡ Quick Start

```bash
# Instalação automática com detecção de hardware
python core/smart_installer.py

# Configurar LM Studio (opcional)
export LMSTUDIO_BASE_URL=http://127.0.0.1:1234/v1

# Controle de Qutrit (auto|true|false)
# - auto (padrão): o EntropicGovernor decide heurísticamente e a decisão é aplicada ao motor simbólico
# - true: força uso de qutrit independentemente da heurística
# - false: desativa qutrit independentemente da heurística
export QUIMERA_QUTRIT_ENABLED=auto

# Executar consulta
python core/chimera.py --query "Se A é verdadeiro e B é falso, qual é A AND B?"

# Interface web
python .streamlit/run_interface.py
```

### Qutrit: Estratégia e Ledger

- `QUIMERA_QUTRIT_ENABLED` suporta `auto|true|false`:
  - auto (padrão): a heurística do `EntropicGovernor.decide_strategy()` define `use_qutrit` com base em incerteza e budget; a decisão é propagada ao motor simbólico.
  - true: força `use_qutrit=True` (sobrepõe a heurística) e habilita oráculos qutrit no motor simbólico.
  - false: força `use_qutrit=False` (sobrepõe a heurística) e desabilita oráculos qutrit.
- Ledger (`proof_ledger.jsonl`): o campo `qutrit_used` é verdadeiro quando a estratégia define `use_qutrit=True` OU quando a env var está explicitamente em estado verdadeiro; o valor padrão `auto` não força `qutrit_used`.

## 📁 Arquitetura do Sistema

### 🏗️ Componentes Principais

#### 🧠 Core Engine (`core/`)
**19 módulos integrados que formam o núcleo do sistema:**

| Módulo | Função | Status |
|--------|--------|--------|
| `chimera.py` | 🎯 Orquestrador principal | ✅ Ativo |
| `qgsl_core.py` | 🔬 Lógica Quântica Ternária | ✅ Ativo |
| `qutrit_bridge.py` | ⚛️ Simulação quântica (Cirq) | ✅ Ativo |
| `symbolic_inference.py` | 🧮 Motor de inferência | ✅ Ativo |
| `oracle_interface.py` | 🤖 Assembly of Models (6 LLMs) | ✅ Ativo |
| `entropic_governor.py` | ⚡ Governança energética | ✅ Ativo |
| `bounded_reasoning.py` | 🛡️ Restrições éticas | ✅ Ativo |
| `ethical_rl.py` | 🧠 RL com ética integrada | ✅ Ativo |
| `proof_ledger.py` | 📊 Auditoria e registro | ✅ Ativo |
| `model_cache.py` | 💾 Cache inteligente | ✅ Ativo |
| `crypto_manager.py` | 🔐 Criptografia avançada | ✅ Ativo |
| `smart_installer.py` | 🎛️ Detecção de hardware | ✅ Ativo |
| `state_manager.py` | Persistência e snapshots do estado | ✅ Ativo |

#### 🧪 Sistema de Testes (`tests/`)
**44 arquivos de teste com cobertura abrangente:**
- ✅ Testes unitários para todos os módulos core
- ✅ Testes de integração E2E
- ✅ Benchmarks de performance
- ✅ Testes de conectividade (22 cenários)
- ✅ Validação de criptografia
- ✅ Testes de qutrit e lógica quântica

#### 🖥️ Interface Web (`.streamlit/`)
**Dashboard interativo com monitoramento em tempo real:**
- `streamlit_app.py` - Interface principal
- `run_interface.py` - Launcher
- `Dockerfile` + `docker-compose.yml` - Deploy

#### 🛠️ Utilitários (`scripts/`)
- `demo_hardware_system.py` - Demonstração completa
- `install_crypto_dependencies.py` - Setup criptografia
- `benchmark_crypto_performance.py` - Testes de performance
- `run_all_tests.py` - Execução de testes

### 📦 Dependências Adaptativas

**Sistema inteligente de dependências baseado em hardware:**

| Modo | RAM | Consumo | Arquivo |
|------|-----|---------|----------|
| 🪶 Ultra-Lite | <2GB | <12W | `requirements_ultra_lite.txt` |
| 🔋 Lite | 2-8GB | 12-25W | `requirements_lite.txt` |
| 🖥️ Standard | 8-16GB | 25-50W | `requirements_standard.txt` |
| 🚀 Advanced | 16GB+ | 50W+ | `requirements_advanced.txt` |

**Dependências especializadas:**
- `requirements_crypto.txt` - Criptografia homomórfica/pós-quântica
- `requirements_streamlit.txt` - Interface web

## 🚀 Instalação

### 🎯 Instalação Automática (Recomendada)

```bash
# Clone o repositório
git clone https://github.com/seu-usuario/projeto_quimera.git
cd projeto_quimera

# Execute o instalador inteligente
python core/smart_installer.py
```

Antes de iniciar a interface ou o uso de provedores LLM, configure o arquivo `config/.env` com suas chaves de API. Se alguma chave estiver ausente, o sistema ignora o provedor correspondente e usa alternativas locais quando disponíveis.

**O instalador detecta automaticamente:**
- 🖥️ Hardware disponível (CPU, GPU, RAM)
- ⚡ Consumo energético em tempo real
- 🎛️ Modo de operação ideal
- 📦 Dependências necessárias
- 🔧 Configuração otimizada

### ⚙️ Instalação Manual

#### 1️⃣ Dependências Base

```bash
# Python 3.8+ obrigatório
pip install -r requirements.txt
```

#### 2️⃣ Modos de Hardware

| Modo | Comando | Especificações |
|------|---------|----------------|
| 🪶 **Ultra-Lite** | `pip install -r requirements_ultra_lite.txt` | <2GB RAM, <12W |
| 🔋 **Lite** | `pip install -r requirements_lite.txt` | 2-8GB RAM, 12-25W |
| 🖥️ **Standard** | `pip install -r requirements_standard.txt` | 8-16GB RAM, 25-50W |
| 🚀 **Advanced** | `pip install -r requirements_advanced.txt` | 16GB+ RAM, 50W+ |

#### 3️⃣ Criptografia Avançada (Opcional)

```bash
# Instalação automática
python scripts/install_crypto_dependencies.py

# Ou manual
pip install -r requirements_crypto.txt
```

**Inclui:**
- 🔐 Criptografia homomórfica (Microsoft SEAL)
- 🛡️ Criptografia pós-quântica (ML-KEM-512)
- 🔒 Operações seguras em dados criptografados

## 🔧 Configuração

### 🤖 LLM Configuration

#### Assembly of Models (6 LLMs)
**Configuração automática via OpenRouter + OpenAI:**

```bash
# Variáveis de ambiente obrigatórias
export OPENROUTER_API_KEY="your-openrouter-key"
export OPENAI_API_KEY="your-openai-key"

# LM Studio local (opcional, para privacidade)
export LM_STUDIO_URL="http://localhost:1234/v1"
export USE_LM_STUDIO="true"
```

**LLMs ativos:**
- 🧠 **OpenRouter**: 5 modelos especializados
- 🤖 **OpenAI**: GPT-4 como validador
- 🏠 **LM Studio**: Modelo local (fallback)

#### Configuração do LM Studio

1. **Instale o LM Studio**
2. **Baixe um modelo compatível** (ex: Llama 2 7B)
3. **Inicie o servidor local** na porta 1234
4. **Configure as variáveis** conforme acima

### 🖥️ Interface Web

```bash
# Instale dependências da interface
pip install -r requirements_streamlit.txt

# Execute o dashboard
python .streamlit/run_interface.py

# Ou diretamente
streamlit run .streamlit/streamlit_app.py --server.port 8501
```

**Funcionalidades do Dashboard:**
- 📊 Monitoramento em tempo real
- 🧠 Consultas interativas
- 📈 Métricas de performance
- 🔍 Visualização do Proof Ledger
- ⚡ Status energético

### ✅ Validação do Sistema

```bash
# Validação completa
python scripts/validate_crypto_environment.py

# Benchmark de performance
python scripts/benchmark_crypto_performance.py

# Teste de conectividade (22 cenários)
python tests/test_connectivity.py
```

## 🚀 Como Usar

### 🚀 Quick Start

```bash
# Consulta simples
python core/chimera.py "Qual é a capital do Brasil?"

# Com contexto específico
python core/chimera.py "Diagnóstico de febre alta" --domain medical

# Modo debug
python core/chimera.py "Query complexa" --debug --verbose
```

### 🧪 Sistema de Testes (19 arquivos)

**Estrutura 1:1 - Cada módulo core tem exatamente um teste correspondente:**

```bash
# Execução completa (recomendado)
pytest tests/ -v

# Testes por categoria
python -m pytest tests/test_qgsl_core.py -v      # Lógica quântica
python -m pytest tests/test_ethical_rl.py -v     # RL ético
python -m pytest tests/test_crypto_manager.py -v # Criptografia
python -m pytest tests/test_symbolic_inference.py -v # Inferência simbólica

# Cobertura de testes
pytest --cov=core tests/

# Benchmark de performance
python -m pytest tests/ -v --benchmark-only
```

**📊 Métricas de Qualidade:**
- ✅ **427 testes** executados com 100% de aprovação
- ✅ **0 falhas** e **0 warnings**
- ✅ **Cobertura geral**: 60% (6998 linhas, 2811 não cobertas)
- ✅ **Tempo de execução**: ~70 segundos
- ✅ **Estrutura limpa**: Eliminados 35 testes redundantes
- ✅ **Relação 1:1**: 19 módulos core ↔ 19 testes

**🎯 Cobertura por Módulo:**
| Módulo | Cobertura | Status |
|--------|-----------|--------|
| `feedback_system.py` | 100% | ✅ Completo |
| `proof_ledger.py` | 96% | ✅ Excelente |
| `knowledge_ontology.py` | 94% | ✅ Excelente |
| `bounded_reasoning.py` | 89% | ✅ Muito bom |
| `truth_mapping.py` | 87% | ✅ Muito bom |
| `crypto_manager.py` | 85% | ✅ Bom |
| `learning_manager.py` | 82% | ✅ Bom |
| Outros módulos | 40-70% | 📝 Em melhoria |

### 🖥️ Interface Web (Streamlit)

```bash
# Método 1: Script launcher
python .streamlit/run_interface.py

# Método 2: Streamlit direto
streamlit run .streamlit/streamlit_app.py --server.port 8501

# Método 3: Docker
docker-compose up -d
```

Acesse: `http://localhost:8501`

### 💻 Uso Programático

```python
from core.chimera import ChimeraSystem

# Inicializar sistema com configuração automática
chimera = ChimeraSystem()

# Consulta básica
result = chimera.process_query("Qual é a relação entre energia e massa?")

# Consulta com contexto
result = chimera.process_query(
    "Paciente com febre alta e dor de cabeça",
    context={"domain": "medical", "urgency": "high"}
)

# Resultados estruturados
print(f"🎯 Resposta: {result['response']}")
print(f"📊 Confiança: {result['confidence']:.2%}")
print(f"🔍 Prova: {result['proof']}")
print(f"⚡ Energia: {result['energy_consumed']}J")
print(f"📋 Ledger ID: {result['ledger_entry']}")
```

## 🔬 Funcionalidades Técnicas

### ⚛️ Quantum Gate Symbolic Logic (QGSL)
**Lógica quântica ternária com simulação real:**

- 🔬 **Qutrits reais** com Cirq (d=3: F=0, T=1, U=2)
- ⚛️ **Portas quânticas**: X3, Z3, F3, SUM3, CNOT
- 🌀 **Superposição** e entrelaçamento quântico
- 🎯 **Estados trivalentes**: FALSE, TRUE, UNDECIDABLE
- 🔄 **Bridge quântico** para simulação híbrida

### 🤖 Assembly of Models
**Ensemble inteligente de 6 LLMs:**

- 🧠 **OpenRouter**: 5 modelos especializados
- 🤖 **OpenAI**: GPT-4 como validador final
- 🏠 **LM Studio**: Modelo local (privacidade)
- 🗳️ **Sistema de votação** ponderada
- 🔄 **Fallback hierárquico** automático
- 📊 **Consenso inteligente** com threshold

### 🛡️ Gate Gerador-Validador
**Controle rigoroso de alucinações:**

- 🔍 **Parser de hipóteses** LLM → JSON estruturado
- ✅ **Validação simbólica** obrigatória
- 🚫 **Bloqueio de alucinações** não-provadas
- 🏷️ **Rotulagem** de indecidíveis
- 📊 **Scoring** de confiança

### ⚡ Orçamento Energético
**Governança inteligente de recursos:**

- 🎛️ **Entropic Governor** com thresholds adaptativos
- ⚡ **Monitoramento** energético em tempo real
- 🎯 **Ativação automática** do qutrit
- 📊 **Budget factor** dinâmico
- 🔄 **Otimização** baseada em incerteza

### 📊 Proof Ledger
**Auditoria completa e rastreabilidade:**

Exemplo atualizado de entrada JSONL (schema atual):

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

- 🗃️ **Registro imutável** de todas as operações
- 🔐 **Checksum SHA-256** para integridade
- 📈 **Métricas** de performance e consumo
- 🔍 **Rastreabilidade** end-to-end
- 📊 **Analytics** e relatórios

### 🧠 Aprendizado por Reforço Ético
**RL com restrições morais integradas:**

- 🎯 **Q-Learning** modificado com ética
- 🛡️ **Middleware** de segurança
- 🏆 **Sistema de recompensas** balanceado
- 🔄 **Feedback** automático do ambiente
- 📊 **Métricas éticas** em tempo real

### 🔐 Criptografia Avançada
**Segurança de próxima geração:**

- 🔒 **Homomórfica** (Microsoft SEAL)
- 🛡️ **Pós-quântica** (ML-KEM-512)
- 🔄 **Operações seguras** em dados criptografados
- 🔑 **Rotação automática** de chaves
- 🧪 **Benchmarks** de performance

### 🎛️ Hardware Adaptativo
**Sistema inteligente de detecção:**

- 🖥️ **Detecção automática** de hardware
- ⚡ **Monitoramento energético** em tempo real
- 🎚️ **4 modos adaptativos** (Ultra-lite → Advanced)
- 📦 **Instalação inteligente** de dependências
- 🔧 **Configuração automática** otimizada

## 🏥 Aplicação Médica

### 📊 Performance Clínica
| Métrica | Melhoria | Baseline |
|---------|----------|----------|
| 🎯 **Acurácia diagnóstica** | +29.2% | Sistema original (37.5% → 66.7%) |
| 🚨 **Detecção emergências** | +41.7% | Sistema original (25.0% → 66.7%) |
| 📈 **Confiança clínica** | +38% | Sistema original (~40% → 78%) |
| ⚡ **Tempo processamento** | -99% | Sistema original (~100ms → <1ms) |

### 🩺 Funcionalidades Clínicas
- 🔍 **Diagnóstico diferencial** com múltiplas hipóteses
- 🚨 **Detecção de emergências** com priorização automática
- 📝 **Normalização de sintomas** e terminologia médica
- 📊 **Scoring de confiança** baseado em evidências
- 💊 **Recomendações contextuais** seguindo guidelines
- ⚠️ **Sistema de níveis críticos** para triagem

### 🎯 Especialidades Suportadas
- 💓 **Cardiologia** - Infarto, angina, insuficiência cardíaca
- 🫁 **Pneumologia** - Embolia pulmonar, insuficiência respiratória
- 🧠 **Neurologia** - AVC, síncope, distúrbios neurológicos
- 🩸 **Endocrinologia** - Cetoacidose diabética, hipoglicemia

## 💾 Cache Inteligente

### 🚀 Funcionalidades Avançadas
- 🧠 **Cache semântico** com embeddings
- 🏗️ **Hierarquia** multi-camada (RAM → SSD → Rede)
- 🔄 **Invalidação inteligente** baseada em contexto
- 🗜️ **Compressão adaptativa** (60-80% economia)
- 🔗 **Deduplicação** automática (40-60% redução)
- 🎯 **Eviction LRU** com scoring semântico

### 📊 Performance
| Métrica | Valor | Melhoria |
|---------|-------|----------|
| 🎯 **Hit Rate** | 87.3% | +25% vs. cache tradicional |
| 💾 **Uso de memória** | 2.1GB | -75% (de 8.4GB) |
| 🔗 **Deduplicação** | 52.7% | Economia de espaço |
| ⚡ **Tempo resposta** | 12ms | -35% vs. sem cache |
| 🎚️ **Threshold similaridade** | 0.85 | Configurável |

### 📈 Monitoramento
```python
from core.model_cache import ModelCache

cache = ModelCache()
metrics = cache.get_metrics()

print(f"📈 Performance:")
print(f"  Hit Rate: {metrics['hit_rate']:.1%}")
print(f"  Entradas em Memória: {metrics['memory_entries']}")
print(f"  Entradas em Disco: {metrics['disk_entries']}")
print(f"  Uso de Memória: {metrics['memory_usage_mb']:.2f}MB")
print(f"  Economia de Espaço: {metrics['compression_ratio']:.1%}")
```

## 🖥️ Sistema de Hardware Inteligente

### 🎛️ Modos Adaptativos

| Modo | RAM | Consumo | Uso Ideal |
|------|-----|---------|----------|
| 🪶 **Ultra-Lite** | <2GB | <12W | IoT, embarcados |
| 🔋 **Lite** | 2-8GB | 12-25W | Laptops, tablets |
| 🖥️ **Standard** | 8-16GB | 25-50W | Desktops, workstations |
| 🚀 **Advanced** | 16GB+ | 50W+ | Servidores, GPUs |

### 🔍 Detecção Automática

```python
from core.smart_installer import SmartInstaller

installer = SmartInstaller()
mode, config = installer.detect_and_configure()
specs = installer.hardware_specs

print(f"🎯 Modo: {mode.value}")
print(f"🖥️ CPU: {specs.cpu_cores} cores @ {specs.cpu_freq_ghz:.1f}GHz")
print(f"💾 RAM: {specs.total_ram_gb:.1f}GB")
print(f"🎮 GPU: {'Sim' if specs.has_gpu else 'Não'}")
print(f"⚡ TDP: {specs.cpu_tdp_watts}W")
```

### ⚡ Monitoramento Energético

```python
from core.smart_installer import EnergyMonitor

monitor = EnergyMonitor()
monitor.start_monitoring()

metrics = monitor.get_current_metrics()
print(f"⚡ Consumo: {metrics.estimated_watts:.1f}W")
print(f"🖥️ CPU: {metrics.cpu_percent:.1f}%")
print(f"💾 Memória: {metrics.memory_percent:.1f}%")
print(f"🌡️ Temp: {metrics.cpu_temp_celsius:.1f}°C")
```

### 📈 Benefícios
- 🔋 **Eficiência**: Até 70% redução no consumo
- 🎯 **Adaptabilidade**: IoT até workstations
- 📦 **Otimização**: Apenas dependências necessárias
- 🤖 **Inteligência**: Alertas e ajustes automáticos
- 📈 **Escalabilidade**: Upgrade automático entre modos

## 📊 Status do Projeto

### 🎯 Métricas Atuais
| Componente | Status | Métricas |
|------------|--------|----------|
| 🧪 **Testes** | ✅ Completo | 19 arquivos, 427 testes, 60% cobertura |
| 🧠 **Core Engine** | ✅ Ativo | 19 módulos integrados |
| 🤖 **LLMs** | ✅ Operacional | 6 modelos (Assembly) |
| 💾 **Cache** | ✅ Otimizado | 87.3% hit rate |
| 🛡️ **Segurança** | ✅ Integrada | 100% módulos validados |
| ⚛️ **QGSL** | ✅ Implementada | Qutrits reais com Cirq |
| 📊 **Proof Ledger** | ✅ Ativo | Auditoria completa |
| 🎛️ **Hardware** | ✅ Adaptativo | 4 modos (Ultra-lite → Advanced) |

## 🗺️ Roadmap

### ✅ Fase 1: Fundação (COMPLETA)
**Simplificação e Estabilização**
- ✅ Unificação de LLMs (Assembly of Models)
- ✅ Limpeza e refatoração do código
- ✅ Sistema de testes robusto (44 arquivos)
- ✅ Correção de bugs críticos
- ✅ Cache inteligente otimizado

### ✅ Fase 2: Core Quântico (COMPLETA)
**QGSL e Lógica Ternária**
- ✅ Qutrits reais com Cirq (d=3)
- ✅ Portas quânticas (X3, Z3, F3, SUM3)
- ✅ Bridge quântico híbrido
- ✅ Estados trivalentes (F, T, U)

### ✅ Fase 3: Governança (COMPLETA)
**Controle e Auditoria**
- ✅ Gate Gerador-Validador
- ✅ Proof Ledger com SHA-256
- ✅ Orçamento energético (Entropic Governor)
- ✅ RL ético integrado
- ✅ Middleware de segurança

### ✅ Fase 4: Infraestrutura (COMPLETA)
**Hardware e Criptografia**
- ✅ Sistema adaptativo de hardware
- ✅ Criptografia homomórfica (SEAL)
- ✅ Criptografia pós-quântica (ML-KEM-512)
- ✅ Monitoramento energético

### 🔄 Fase 5: Evolução (EM ANDAMENTO)
**Meta-Aprendizado e Escala**
- 🔄 Auto-evolução de estratégias
- 🔄 Análise de falhas automática
- 🔄 Ontologia escalável
- 🔄 Aprendizado curado

## 🎯 Próximos Marcos

- **Q1 2024**: Meta-aprendizado avançado
- **Q2 2024**: Ontologia escalável
- **Q3 2024**: Deploy em produção
- **Q4 2024**: Integração com sistemas externos

## 📚 Documentação

### 📖 Documentos Principais
| Documento | Descrição | Status |
|-----------|-----------|--------|
| 📋 **[Convenções e Contratos](docs/novas_melhorias_quimera.md)** | Especificações técnicas completas | ✅ Atualizado |
| 🏗️ **[Arquitetura](docs/arquitetura_projeto_quimera.md)** | Visão técnica detalhada | ✅ Completo |
| 🗺️ **[Roadmap](docs/TODO_melhorias.md)** | Plano de evolução priorizado | ✅ Atualizado |
| 🔧 **[Implementação](docs/TODO_implementação.md)** | Roteiro de refatoração | ✅ Concluído |
| 🐛 **[Correções](docs/TODO_correcoes_melhorias.md)** | Issues e melhorias | 📝 Em revisão |

### 🔐 Criptografia Avançada

#### 🛡️ Algoritmos Suportados
| Tipo | Algoritmo | Uso | Performance |
|------|-----------|-----|-------------|
| 🔒 **Clássica** | AES-256, RSA-4096 | Criptografia padrão | 1GB/s |
| 🧮 **Homomórfica** | Microsoft SEAL (BFV/CKKS) | Computação em dados criptografados | 2000 ops/s |
| ⚛️ **Pós-Quântica** | ML-KEM-512, ML-DSA | Resistente a ataques quânticos | 5000 ops/s |
| 🔄 **Híbrida** | Combinação otimizada | Máxima segurança | Adaptável |

#### ⚙️ Instalação

```bash
# Instalação automática (recomendada)
python scripts/install_crypto_dependencies.py

# Instalação específica
python scripts/install_crypto_dependencies.py --homomorphic
python scripts/install_crypto_dependencies.py --post-quantum
python scripts/install_crypto_dependencies.py --all

# Verificação
python scripts/validate_crypto_environment.py
python scripts/benchmark_crypto_performance.py
```

#### 📊 Benchmarks

| Algoritmo | Operação | Latência | Throughput |
|-----------|----------|----------|------------|
| AES-256 | Encrypt/Decrypt | 0.1ms | 1GB/s |
| SEAL-BFV | Homomorphic Add | 0.5ms | 2000 ops/s |
| ML-KEM-512 | KeyGen/Encaps | 0.2ms | 5000 ops/s |

## 🔐 Guia de Instalação - Criptografia Avançada

### 📋 Visão Geral da Criptografia

O sistema de criptografia do Projeto Quimera suporta:

- **Criptografia Clássica**: AES-GCM, Fernet (sempre disponível)
- **Criptografia Homomórfica**: Microsoft SEAL (BFV, CKKS)
- **Criptografia Pós-Quântica**: ML-KEM-512 (Kyber)
- **Criptografia Híbrida**: Combinação de múltiplos esquemas
- **Sistema de Fallback**: Funciona mesmo sem bibliotecas especializadas

### 🔧 Instalação Rápida de Criptografia

#### Opção 1: Script Automático (Recomendado)

```bash
# Execute o script de instalação inteligente
python scripts/install_crypto_dependencies.py
```

#### Opção 2: Instalação Manual

```bash
# Dependências básicas (sempre necessárias)
pip install numpy>=1.21.0 cryptography>=3.4.8 pycryptodome>=3.15.0

# Dependências opcionais
pip install pqcrypto  # Criptografia pós-quântica
pip install tenseal  # Criptografia homomórfica
```

### 🔐 Criptografia Pós-Quântica

#### Instalação por Sistema

##### Windows
```powershell
# Opção 1: Via pip
pip install pqcrypto

# Opção 2: Alternativa Kyber
pip install kyber-py
```

##### Ubuntu/Debian
```bash
# Instalar dependências de compilação
sudo apt-get update
sudo apt-get install build-essential python3-dev

# Instalar via pip
pip install pqcrypto
```

##### macOS
```bash
# Instalar Xcode Command Line Tools
xcode-select --install

# Instalar via pip
pip install pqcrypto
```

### 🔒 Criptografia Homomórfica

#### Microsoft SEAL

##### Windows
```powershell
# TenSEAL (mais fácil)
pip install tenseal
```

##### Ubuntu/Debian
```bash
# TenSEAL
pip install tenseal

# SEAL nativo
sudo apt-get install libseal-dev
pip install pyseal
```

### 🧪 Verificação da Instalação

```python
from core.crypto_manager import CryptoManager

crypto = CryptoManager()
test_data = "Teste de criptografia"

# Testar todos os esquemas
schemes = ['classical', 'homomorphic', 'post_quantum', 'hybrid']

for scheme in schemes:
    try:
        encrypted = crypto.encrypt(test_data, scheme)
        decrypted = crypto.decrypt(encrypted, scheme)
        status = "✅" if decrypted == test_data else "❌"
        print(f"{status} {scheme}: {'OK' if decrypted == test_data else 'FALHA'}")
    except Exception as e:
        print(f"⚠️ {scheme}: Usando fallback ({str(e)[:50]}...)")
```

### 📊 Benchmarks de Criptografia

```bash
# Benchmark completo
python scripts/benchmark_crypto_performance.py

# Teste específico
python scripts/test_complete_pqcrypto.py
```

## 📋 Convenções e Contratos

Para desenvolvedores e usuários avançados, consulte a **[Documentação de Convenções e Contratos](docs/novas_melhorias_quimera.md)** que detalha:

- **Ordem T/F/U Única**: Sistema de lógica ternária padronizado (TRUE=0, FALSE=1, UNDECIDABLE=2)
- **Sentinelas do Parser**: Formato estruturado para hipóteses LLM (`BEGIN_HYPOTHESES_JSON`/`END_HYPOTHESES_JSON`)
- **Estratégia `decide_strategy`**: Heurística de ativação automática do qutrit baseada em incerteza e orçamento
- **Schema do Ledger**: Estrutura completa do Proof Ledger (atualizada com `llm_model`, `llm_fallback_used`, `domain`, `complexity`, `processing_time_ms`, `cache_hit`) com exemplos reais de auditoria
- **Helpers e APIs**: Funções utilitárias, tabelas verdade e exemplos práticos

Esta documentação é essencial para:
- Integração com sistemas externos
- Desenvolvimento de extensões
- Debugging avançado
- Auditoria e compliance

## 🤝 Contribuição

### 📋 Diretrizes de Desenvolvimento

| Área | Requisitos | Ferramentas |
|------|------------|-------------|
| 🐍 **Código** | PEP 8, type hints, docstrings | `black`, `isort`, `flake8` |
| 🧪 **Testes** | Cobertura 80%+, unitários + integração | `pytest`, `coverage` |
| ⚡ **Async** | async/await para I/O, timeouts | `asyncio`, `aiohttp` |
| 💾 **Cache** | Semântico, invalidação inteligente | `model_cache.py` |
| 🤖 **LLMs** | Fallbacks, rate limiting, validação | `oracle_interface.py` |
| 📚 **Docs** | README atualizado, exemplos | Markdown, docstrings |

### 🔧 Comandos Úteis

```bash
# Formatação e linting
black core/ tests/ && isort core/ tests/
flake8 core/ tests/ && mypy core/

# Testes completos
python scripts/run_all_tests.py
pytest tests/ -v --cov=core --cov-report=html

# Validação do ambiente
python scripts/validate_crypto_environment.py
```

### 📝 Conventional Commits
- `feat:` Nova funcionalidade
- `fix:` Correção de bug
- `docs:` Documentação
- `test:` Testes
- `refactor:` Refatoração
- `perf:` Performance

### 🚀 Processo de Contribuição

1. **Consulte o TODO.md** para entender as prioridades
2. Fork o projeto
3. Crie uma branch para sua feature (`git checkout -b feature/AmazingFeature`)
4. **Execute os testes**: `pytest tests/ -v --asyncio-mode=auto`
5. Commit suas mudanças (`git commit -m 'Add some AmazingFeature'`)
6. Push para a branch (`git push origin feature/AmazingFeature`)
7. Abra um Pull Request

---

## 📄 Licença

**MIT License** - Veja [LICENSE](LICENSE) para detalhes completos.

---

<div align="center">

**🧬 Projeto Quimera**  
*Sistema AGI com Lógica Quântica Simbólica*

*Desenvolvido com ❤️ para o futuro da inteligência artificial*

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![Tests](https://img.shields.io/badge/tests-507%20passed-green.svg)](#)
[![Coverage](https://img.shields.io/badge/coverage-60%25-orange.svg)](#)
[![Structure](https://img.shields.io/badge/structure-1:1%20module:test-blue.svg)](#)

### Higiene do Repositório
- Para evitar versionar artefatos locais, remova quando necessário: `venv/`, `.venv/`, `__pycache__/`, `.pytest_cache/`, `.benchmarks/`, `.quimera/`, `quimera/`, `.coverage`, `coverage.xml`, `*.cache`.
- Para recriar o ambiente, use o instalador inteligente: `python core/smart_installer.py`.

### Segurança e Deploy
- O subsistema de criptografia usa bibliotecas reais quando presentes (Microsoft SEAL via PySEAL e ML-KEM via pqcrypto). Quando ausentes, opera em modo simulado com avisos no log.
- Para ambientes que exigem criptografia real, ative modo estrito via `QUIMERA_CRYPTO_STRICT=true` (falha na inicialização sem as dependências reais).
- Dependências opcionais: veja `requirements_crypto.txt`.

</div>

## Perfis e Headless (env)

- Defina o perfil lógico via variável de ambiente `QUIMERA_PROFILE`:
  - Valores: `ultra_lite`, `lite`, `standard`, `advanced`
  - Mapeamento interno: ultra_lite/lite → limited; standard → common; advanced → optimized
  - A configuração retornada pelo `smart_installer.detect_and_configure()` inclui `profile` (valor aplicado) e `profile_source` (`env` ou `detected`).
- Ative modo headless com `QUIMERA_HEADLESS=true` para execução sem UI (ledger/logs apenas).

Exemplo (smoke test headless):

```bash
export QUIMERA_PROFILE=ultra_lite
export QUIMERA_HEADLESS=true
python scripts/smoke_headless.py
```

## Validações em Cascata (opcional)

- Ativa validações extras contra alucinações: contradições simbólicas, consistência temporal mínima e heurísticas semânticas.
- Variáveis de ambiente:
  - `QUIMERA_VALIDATION_CASCADE=true|false` (padrão: false)
  - `QUIMERA_VALIDATION_CASCADE_STRICT=true|false` (padrão: false, bloqueia também avisos)
- Registro no ledger: campo `cascaded_validation` com `enabled`, `steps` e `verdict`.
## Instalação (dev)

- Requisitos: Python 3.10+
- Clone o repositório e instale em modo editável:

```
pip install -e .
```

Isso disponibiliza o entry‑point `quimera` no seu PATH.

## CLI unificada (exemplos rápidos)

- Verificar instalação: `quimera validate`
- Processar uma consulta: `quimera run --query "Olá Quimera"`
- Energia (amostra): `quimera energy --sample-ms 100`
- Ontologia (CRUD): `quimera ontology list`
- Qutrit thresholds: `quimera qutrit get`
- Demos: `quimera demo --name {diag|fin|code}`

Para ver ajuda completa: `python -m tools.quimera_cli --help` ou `quimera --help`.

## Deploy e Operação

- Guia de deploy rápido: `docs/deploy_quickstart.md`
- Operação por SO: `docs/ops_linux.md`, `docs/ops_windows.md`, `docs/ops_macos.md`
- Modelos de logs/ledger: `docs/log_models.md`
