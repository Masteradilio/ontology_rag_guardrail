# Quimera Guardrails

> Sistema Avançado de Proteção para Agentes de IA baseado em Lógica Simbólica Quântica (QGSL)

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: AGPLv3+](https://img.shields.io/badge/License-AGPLv3%2B-blue.svg)](../LICENSE)

## 📋 Índice

- [Visão Geral](#-visão-geral)
- [Características](#-características)
- [Arquitetura](#-arquitetura)
- [Instalação](#-instalação)
- [Uso Rápido](#-uso-rápido)
- [Integração com Orquestrador](#-integração-com-orquestrador-de-agentes)
- [Componentes](#-componentes)
- [Configuração](#-configuração)
- [API Reference](#-api-reference)
- [Exemplos](#-exemplos)

## 🎯 Visão Geral

O **Quimera Guardrails** é um sistema de proteção avançado para agentes de IA que combina:

- **Lógica Trivalente QGSL**: TRUE/FALSE/UNDECIDABLE para decisões mais nuançadas
- **Input Shield**: Proteção contra PII, injeções, jailbreaks e ameaças
- **Output Validator**: Validação de relevância, alucinações e compliance
- **Multi-Tenant**: Isolamento completo entre clientes
- **Compliance Multi-Regulatório**: LGPD, GDPR, HIPAA, SOX, PCI-DSS, CCPA
- **Auditoria Criptográfica**: Blockchain-like para rastreabilidade

## ✨ Características

### Input Shield (Proteção de Entrada)
- ✅ Detecção de PII (CPF, Email, Telefone, Cartão, etc.)
- ✅ Prevenção de SQL/Script Injection
- ✅ Detecção de Jailbreak/Prompt Injection
- ✅ Rate Limiting por usuário/tenant
- ✅ Análise de intenção maliciosa
- ✅ Detecção de spam e abuso
- ✅ Sanitização automática

### Output Validator (Validação de Saída)
- ✅ Verificação de relevância semântica
- ✅ Detecção de alucinações contra ontologia
- ✅ Verificação de compliance regulatório
- ✅ Análise de consistência interna
- ✅ Score de qualidade multidimensional
- ✅ Guidance para retry automático

### Diferenciais Únicos
- 🔮 **Lógica QGSL**: Suporta "incerteza" como estado válido
- 🏢 **Multi-Tenant**: Cada cliente tem ontologia isolada
- 📜 **Proof Ledger**: Auditoria imutável tipo blockchain
- 🌍 **Compliance**: 6 regulamentações suportadas
- 🚀 **Performance**: Validação em <100ms por mensagem

## 🏗 Arquitetura

```
┌─────────────────────────────────────────────────────────────────┐
│                    QUIMERA GUARDRAILS                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│   ┌─────────────┐    ┌─────────────┐    ┌─────────────┐        │
│   │   Input     │    │    Agent    │    │   Output    │        │
│   │   Shield    │───>│   (LLM)     │───>│  Validator  │        │
│   └─────────────┘    └─────────────┘    └─────────────┘        │
│         │                                      │                │
│         v                                      v                │
│   ┌─────────────────────────────────────────────────────────┐  │
│   │              QGSL Logic Engine                          │  │
│   │         TRUE | FALSE | UNDECIDABLE                      │  │
│   └─────────────────────────────────────────────────────────┘  │
│         │                                      │                │
│         v                                      v                │
│   ┌─────────────┐    ┌─────────────┐    ┌─────────────┐        │
│   │  Compliance │    │   Tenant    │    │    Proof    │        │
│   │   Engine    │    │  Ontology   │    │   Ledger    │        │
│   └─────────────┘    └─────────────┘    └─────────────┘        │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## 📦 Instalação

```bash
# Copiar a pasta quimera_guardrails para seu projeto
cp -r quimera_guardrails /seu/projeto/

# Ou adicionar ao PYTHONPATH
export PYTHONPATH="${PYTHONPATH}:/caminho/para/quimera"

# Dependências básicas (escolha uma)
pip install httpx     # Recomendado para async
# ou
pip install aiohttp   # Alternativa async
# ou
pip install requests  # Fallback síncrono
```

### Dependências Mínimas
```
python >= 3.10
hashlib (stdlib)
dataclasses (stdlib)
asyncio (stdlib)
typing (stdlib)
```

### Dependências Opcionais
```
httpx               # Cliente HTTP async recomendado
aiohttp             # Cliente HTTP async alternativo
requests            # Cliente HTTP síncrono (fallback)
numpy               # Para operações QGSL avançadas
google-generativeai # Para integração com Google File Search (legado)
```

## 🚀 Uso Rápido

```python
from quimera_guardrails import (
    QuimeraGuardrails,
    GuardrailsConfig,
    create_guardrails,
    ComplianceStandard
)

# 1. Configuração
config = GuardrailsConfig(
    tenant_id="meu_saas_001",
    enable_pii_detection=True,
    enable_injection_detection=True,
    enable_jailbreak_detection=True,
    enable_compliance_check=True,
    compliance_standards=[
        ComplianceStandard.LGPD,
        ComplianceStandard.GDPR
    ]
)

# 2. Criar instância
guardrails = create_guardrails(config)

# 3. Validar input do usuário
async def process_message(user_input: str):
    # Shield de entrada
    input_result = await guardrails.shield_input(user_input)
    
    if not input_result.allowed:
        return {
            "error": "Mensagem bloqueada",
            "reason": input_result.reasoning,
            "threats": [t.threat_type.value for t in input_result.threats]
        }
    
    # Usar texto sanitizado se disponível
    safe_input = input_result.sanitized_input or user_input
    
    # ... Processar com seu agente LLM ...
    agent_response = await call_your_agent(safe_input)
    
    # Validar output
    output_result = await guardrails.validate_output(
        original_query=safe_input,
        agent_response=agent_response
    )
    
    if not output_result.is_valid:
        if output_result.should_retry:
            # Refazer com guidance
            agent_response = await call_your_agent(
                safe_input,
                guidance=output_result.retry_guidance
            )
        else:
            return {"error": "Resposta inválida", "issues": output_result.issues}
    
    return {"response": agent_response}
```

## 🔌 Integração com Orquestrador de Agentes

### Estrutura Recomendada

```
orquestrador/
├── guardrails/
│   └── quimera_guardrails/     # Copiar esta pasta
├── agents/
│   ├── base_agent.py
│   └── specialized_agent.py
├── core/
│   └── message_handler.py
└── main.py
```

### Exemplo de Integração

```python
# orquestrador/core/message_handler.py

from typing import Optional, Dict, Any
from quimera_guardrails import (
    QuimeraGuardrails,
    GuardrailsConfig,
    create_guardrails,
    ComplianceStandard,
    ShieldResult,
    ValidationResult
)

class SecureMessageHandler:
    """Handler de mensagens com proteção Quimera integrada"""
    
    def __init__(
        self,
        tenant_id: str,
        compliance_standards: list = None
    ):
        self.guardrails = create_guardrails(
            GuardrailsConfig(
                tenant_id=tenant_id,
                enable_pii_detection=True,
                enable_injection_detection=True,
                enable_jailbreak_detection=True,
                enable_hallucination_detection=True,
                enable_compliance_check=True,
                compliance_standards=compliance_standards or [
                    ComplianceStandard.LGPD
                ]
            )
        )
        
    async def process(
        self,
        message: str,
        agent_callback,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Processa mensagem com proteção completa
        
        Args:
            message: Mensagem do usuário
            agent_callback: Função async do agente que processa a mensagem
            context: Contexto adicional (histórico, etc)
            
        Returns:
            Dict com resposta ou erro
        """
        # === FASE 1: INPUT SHIELD ===
        input_result = await self.guardrails.shield_input(
            message,
            context=context
        )
        
        if not input_result.allowed:
            return {
                "success": False,
                "error_type": "input_blocked",
                "message": input_result.reasoning,
                "threats": [
                    {
                        "type": t.threat_type.value,
                        "severity": t.severity,
                        "details": t.details
                    }
                    for t in input_result.threats
                ],
                "proof_id": input_result.proof_id
            }
        
        # Usar texto sanitizado
        safe_message = input_result.sanitized_input or message
        
        # === FASE 2: PROCESSAMENTO DO AGENTE ===
        try:
            agent_response = await agent_callback(safe_message, context)
        except Exception as e:
            return {
                "success": False,
                "error_type": "agent_error",
                "message": str(e)
            }
        
        # === FASE 3: OUTPUT VALIDATION ===
        output_result = await self.guardrails.validate_output(
            original_query=safe_message,
            agent_response=agent_response,
            context=context
        )
        
        if not output_result.is_valid:
            if output_result.should_retry:
                # Tentar novamente com guidance
                try:
                    agent_response = await agent_callback(
                        safe_message,
                        context={
                            **(context or {}),
                            "retry_guidance": output_result.retry_guidance
                        }
                    )
                    # Re-validar
                    output_result = await self.guardrails.validate_output(
                        original_query=safe_message,
                        agent_response=agent_response,
                        context=context
                    )
                except Exception:
                    pass
            
            if not output_result.is_valid:
                return {
                    "success": False,
                    "error_type": "output_invalid",
                    "message": "Resposta não passou na validação",
                    "issues": [
                        {
                            "type": i.issue_type.value,
                            "severity": i.severity,
                            "description": i.description
                        }
                        for i in output_result.issues
                    ],
                    "quality_metrics": output_result.quality_metrics.to_dict(),
                    "proof_id": output_result.proof_id
                }
        
        # === SUCESSO ===
        return {
            "success": True,
            "response": agent_response,
            "quality_score": output_result.quality_metrics.overall_score,
            "proof_id": output_result.proof_id
        }
```

### Uso no Orquestrador

```python
# orquestrador/main.py

from core.message_handler import SecureMessageHandler
from agents.specialized_agent import SpecializedAgent

class AgentOrchestrator:
    def __init__(self, tenant_id: str):
        self.handler = SecureMessageHandler(tenant_id)
        self.agent = SpecializedAgent()
    
    async def chat(self, message: str, session_id: str) -> dict:
        context = {
            "session_id": session_id,
            "history": await self.get_history(session_id)
        }
        
        return await self.handler.process(
            message=message,
            agent_callback=self.agent.generate,
            context=context
        )
```

### Integração com FastAPI

```python
# orquestrador/api/routes.py

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from core.message_handler import SecureMessageHandler

router = APIRouter()

class ChatRequest(BaseModel):
    message: str
    session_id: str

class ChatResponse(BaseModel):
    success: bool
    response: str = None
    error_type: str = None
    error_message: str = None
    quality_score: float = None
    proof_id: str = None

@router.post("/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    handler: SecureMessageHandler = Depends(get_handler)
):
    result = await handler.process(
        message=request.message,
        agent_callback=process_with_agent,
        context={"session_id": request.session_id}
    )
    
    if not result["success"]:
        return ChatResponse(
            success=False,
            error_type=result.get("error_type"),
            error_message=result.get("message")
        )
    
    return ChatResponse(
        success=True,
        response=result["response"],
        quality_score=result.get("quality_score"),
        proof_id=result.get("proof_id")
    )
```

## 📦 Componentes

### Input Shield

```python
from quimera_guardrails import QuimeraInputShield, ThreatType

shield = QuimeraInputShield(
    tenant_id="meu_tenant",
    config={
        "pii_detection_enabled": True,
        "injection_detection_enabled": True,
        "jailbreak_detection_enabled": True,
        "rate_limiting_enabled": True,
        "max_requests_per_minute": 60
    }
)

result = await shield.analyze("Meu CPF é 123.456.789-00")

print(f"Permitido: {result.allowed}")
print(f"Risk Score: {result.risk_score}")
print(f"Ameaças: {[t.threat_type.value for t in result.threats]}")
print(f"Texto Sanitizado: {result.sanitized_input}")
```

### Output Validator

```python
from quimera_guardrails import QuimeraOutputValidator

validator = QuimeraOutputValidator(
    tenant_id="meu_tenant",
    config={
        "min_relevance_score": 0.6,
        "min_overall_quality": 0.5,
        "hallucination_check_enabled": True,
        "compliance_check_enabled": True
    }
)

result = await validator.validate(
    original_query="Qual o prazo de entrega?",
    agent_response="O prazo é de 3 a 5 dias úteis."
)

print(f"Válido: {result.is_valid}")
print(f"Qualidade: {result.quality_metrics.overall_score}")
print(f"Deve Retry: {result.should_retry}")
```

### Compliance Engine

```python
from quimera_guardrails import ComplianceEngine, ComplianceStandard

engine = ComplianceEngine()

violations = engine.check(
    "O CPF do cliente é 123.456.789-00",
    context={"standards": [ComplianceStandard.LGPD]}
)

for v in violations:
    print(f"Violação: {v.rule.standard.value}")
    print(f"Severidade: {v.rule.severity.value}")
    print(f"Descrição: {v.rule.description}")

# Mascarar dados sensíveis
masked = engine.mask_pii("CPF: 123.456.789-00")
print(masked)  # "CPF: ***.***.***-**"
```

### Tenant Ontology

```python
from quimera_guardrails import TenantOntologyManager, OntologyEntry

manager = TenantOntologyManager()

# Criar tenant
manager.create_tenant("empresa_xyz")
manager.create_ontology("empresa_xyz", "conhecimento_interno")

# Adicionar conhecimento
manager.add_entry(
    tenant_id="empresa_xyz",
    ontology_id="conhecimento_interno",
    entry=OntologyEntry(
        concept="politica_devolucao",
        definition="Devoluções são aceitas em até 30 dias após a compra",
        confidence=1.0,
        source="manual_interno"
    )
)

# Verificar contra ontologia (usado para detecção de alucinações)
entries = manager.get_entries("empresa_xyz", "conhecimento_interno", "devolucao")
```

### Proof Recorder

```python
from quimera_guardrails import ProofRecorder
from quimera_guardrails.proof_recorder import ProofType

recorder = ProofRecorder()

# Registrar decisão
entry = recorder.record(
    proof_type=ProofType.INPUT_VALIDATION,
    tenant_id="empresa_xyz",
    input_data="mensagem do usuário",
    decision="ALLOWED",
    confidence=0.95,
    context={"session_id": "abc123"}
)

print(f"Proof ID: {entry.proof_id}")
print(f"Hash: {entry.hash}")

# Verificar integridade da cadeia
is_valid = recorder.verify_chain()
print(f"Cadeia íntegra: {is_valid}")

# Exportar para auditoria
audit_log = recorder.export()
```

## ⚙️ Configuração

### GuardrailsConfig

```python
@dataclass
class GuardrailsConfig:
    tenant_id: str
    
    # Input Shield
    enable_pii_detection: bool = True
    enable_injection_detection: bool = True
    enable_jailbreak_detection: bool = True
    enable_rate_limiting: bool = False
    max_requests_per_minute: int = 60
    max_input_length: int = 10000
    
    # Output Validator
    enable_hallucination_detection: bool = True
    enable_compliance_check: bool = True
    min_relevance_score: float = 0.6
    min_quality_score: float = 0.5
    max_output_length: int = 50000
    
    # Compliance
    compliance_standards: List[ComplianceStandard] = field(
        default_factory=lambda: [ComplianceStandard.LGPD]
    )
    
    # Logging
    log_level: str = "INFO"
    enable_proof_recording: bool = True
```

### Variáveis de Ambiente

```bash
# Logging
QUIMERA_LOG_LEVEL=INFO

# Rate Limiting
QUIMERA_RATE_LIMIT_ENABLED=true
QUIMERA_RATE_LIMIT_PER_MINUTE=60

# Compliance
QUIMERA_DEFAULT_STANDARDS=LGPD,GDPR
```

## 📚 API Reference

### QuimeraGuardrails

| Método | Descrição |
|--------|-----------|
| `shield_input(message, context?)` | Valida entrada do usuário |
| `validate_output(query, response, context?)` | Valida saída do agente |
| `add_knowledge(concept, definition, confidence?)` | Adiciona ao ontologia |
| `get_audit_trail(limit?)` | Retorna histórico de auditoria |
| `export_proofs(format?)` | Exporta provas para auditoria |

### ShieldResult

| Atributo | Tipo | Descrição |
|----------|------|-----------|
| `allowed` | bool | Se a entrada é permitida |
| `risk_score` | float | Score de risco (0-1) |
| `threats` | List[ThreatDetail] | Ameaças detectadas |
| `sanitized_input` | str | Texto com dados sensíveis mascarados |
| `reasoning` | str | Explicação da decisão |
| `proof_id` | str | ID da prova para auditoria |

### ValidationResult

| Atributo | Tipo | Descrição |
|----------|------|-----------|
| `is_valid` | bool | Se a saída é válida |
| `quality_metrics` | QualityMetrics | Métricas de qualidade |
| `issues` | List[IssueDetail] | Problemas detectados |
| `should_retry` | bool | Se deve pedir retry |
| `retry_guidance` | str | Orientações para retry |
| `hallucinations` | List | Alucinações detectadas |
| `proof_id` | str | ID da prova para auditoria |

### QualityMetrics

| Atributo | Tipo | Descrição |
|----------|------|-----------|
| `relevance_score` | float | Relevância à pergunta (0-1) |
| `completeness_score` | float | Completude da resposta (0-1) |
| `clarity_score` | float | Clareza/legibilidade (0-1) |
| `factuality_score` | float | Factualidade (0-1) |
| `consistency_score` | float | Consistência interna (0-1) |
| `overall_score` | float | Score geral ponderado (0-1) |

## 📖 Exemplos

### Exemplo 1: Chatbot Seguro

```python
async def secure_chatbot(user_message: str):
    # Criar guardrails
    g = create_guardrails(GuardrailsConfig(tenant_id="chatbot"))
    
    # Validar input
    input_check = await g.shield_input(user_message)
    if not input_check.allowed:
        return f"❌ Mensagem bloqueada: {input_check.reasoning}"
    
    # Processar com LLM
    response = await my_llm.generate(input_check.sanitized_input)
    
    # Validar output
    output_check = await g.validate_output(user_message, response)
    if not output_check.is_valid:
        return f"⚠️ Resposta com problemas: {output_check.suggestions[0]}"
    
    return f"✅ {response} (Qualidade: {output_check.quality_metrics.overall_score:.0%})"
```

### Exemplo 2: API com Compliance

```python
@app.post("/api/v1/process")
async def process_request(req: Request):
    guardrails = create_guardrails(
        GuardrailsConfig(
            tenant_id=req.tenant_id,
            compliance_standards=[
                ComplianceStandard.LGPD,
                ComplianceStandard.HIPAA
            ]
        )
    )
    
    # O resto do processamento...
```

### Exemplo 3: Detecção de Alucinações

```python
# Adicionar conhecimento do domínio
guardrails.add_knowledge(
    concept="horario_funcionamento",
    definition="Funcionamos de segunda a sexta, das 9h às 18h",
    confidence=1.0
)

# Agora, se o agente disser "Funcionamos 24 horas",
# será detectado como alucinação
result = await guardrails.validate_output(
    original_query="Qual o horário de funcionamento?",
    agent_response="Funcionamos 24 horas por dia, 7 dias por semana."
)

print(result.hallucinations)  # Detectará a inconsistência
```

## 🔗 Integração com File Search Customizado (EAO)

O Quimera pode usar a **mesma base de conhecimento** do seu agente principal para validar alucinações, sem duplicar dados. Esta integração é feita através do `CustomFileSearchAdapter` que conecta ao sistema File Search Híbrido do Enterprise Agent Orchestrator (EAO).

### Características do Sistema File Search

- **PostgreSQL + pgvector**: Armazenamento vetorial eficiente
- **Busca Híbrida**: Vetor + Keyword com RRF (Reciprocal Rank Fusion)
- **Reranking**: FlashRank com ms-marco-MiniLM-L-12-v2
- **Multi-tenant**: Isolamento por tenant via RLS
- **Chunking Otimizado**: 1500 tokens com 200 overlap

### Arquitetura Integrada

```
┌─────────────────────────────────────────────────────────────────┐
│                    SEU ORQUESTRADOR (EAO)                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│   ┌─────────────────────────────────────────────────────────┐  │
│   │           CUSTOM FILE SEARCH (PostgreSQL)               │  │
│   │    pgvector + Full-Text + RRF + FlashRank Reranking     │  │
│   └──────────────────────┬──────────────────────────────────┘  │
│                          │                                      │
│              ┌───────────┴───────────┐                         │
│              │                       │                         │
│              ▼                       ▼                         │
│   ┌─────────────────┐     ┌─────────────────┐                  │
│   │  AGENTE (LLM)   │     │ QUIMERA (lazy)  │                  │
│   │  Usa para RAG   │     │ Valida outputs  │                  │
│   └─────────────────┘     └─────────────────┘                  │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Configuração Básica

```python
from quimera_guardrails import (
    QuimeraGuardrails,
    CustomFileSearchAdapter,
    create_file_search_adapter
)

# 1. Criar adapter para o File Search customizado
adapter = CustomFileSearchAdapter(
    base_url="http://localhost:8000",      # URL do seu backend EAO
    tenant_id="meu_tenant",                 # ID do tenant para RLS
    agent_id="agente_financeiro",           # (Opcional) Filtrar por agente
    cache_enabled=True,                     # Cache local de fatos
    cache_ttl_minutes=30,                   # TTL do cache
    use_reranking=True,                     # Usar FlashRank
    search_mode="hybrid"                    # "hybrid", "vector", "keyword"
)

# 2. Pré-carregar fatos críticos (opcional, melhora performance)
adapter.cache.preload_critical({
    "taxa selic": "A taxa SELIC atual é 12.25% ao ano (Nov/2024)",
    "horario atendimento": "Atendimento de segunda a sexta, 9h às 18h",
    "pix limite": "O limite de PIX noturno é R$ 1.000"
})

# 3. Criar guardrails com o adapter
guardrails = QuimeraGuardrails(
    tenant_id="meu_saas",
    knowledge_adapter=adapter  # Usa File Search para validar alucinações
)

# 4. Usar normalmente
result = await guardrails.validate_output(
    original_query="Qual a taxa SELIC?",
    agent_response="A taxa SELIC é 5% ao ano."  # ERRADO!
)

# O Quimera detectará a alucinação via File Search
print(result.hallucinations)  # Mostrará a inconsistência
```

### Configuração via Variáveis de Ambiente

```python
from quimera_guardrails.adapters import create_adapter_from_env

# Usa variáveis de ambiente automaticamente
adapter = create_adapter_from_env()

# Variáveis esperadas:
# FILE_SEARCH_BASE_URL=http://localhost:8000
# FILE_SEARCH_TENANT_ID=meu_tenant
# FILE_SEARCH_AGENT_ID=agente_financeiro (opcional)
# FILE_SEARCH_API_KEY=sua_api_key (opcional)
# FILE_SEARCH_CACHE_ENABLED=true
# FILE_SEARCH_CACHE_TTL=30
# FILE_SEARCH_USE_RERANKING=true
```

### Verificação de Claims em Batch

```python
# Verificar múltiplas afirmações de uma vez
claims = [
    "A taxa SELIC é 12.25%",
    "O horário de atendimento é 9h às 18h",
    "O limite de PIX é R$ 5.000"
]

results = await adapter.batch_verify(
    claims=claims,
    context="pergunta sobre serviços bancários"
)

for claim, result in zip(claims, results):
    print(f"{claim}: {result['status']} (confiança: {result['confidence']:.2f})")
```

### Estratégias de Performance

```python
# MODO 1: Lazy (default) - Só consulta quando suspeita de alucinação
#         Latência: ~10-50ms para maioria, ~200ms quando verifica
adapter = CustomFileSearchAdapter(
    base_url="http://localhost:8000",
    tenant_id="meu_tenant",
    cache_enabled=True  # Importante para performance
)

# MODO 2: Pré-cache de fatos críticos
#         Latência: ~10-50ms sempre
adapter.cache.preload_critical({
    "fato1": "valor1",
    "fato2": "valor2"
}, tenant_id="meu_tenant")

# MODO 3: Validação assíncrona (background)
#         Latência: 0ms (responde imediatamente, valida depois)
result = await guardrails.validate_output(
    query, response,
    async_hallucination_check=True  # Valida em background
)
```

### Para Agentes Financeiros

```python
# Exemplo: Agente de investimentos
adapter = CustomFileSearchAdapter(
    base_url=os.environ["EAO_BASE_URL"],
    tenant_id="banco_xpto",
    agent_id="consultor_investimentos",
    use_reranking=True,
    min_relevance_score=0.5  # Mais rigoroso para dados financeiros
)

# Fatos que NUNCA devem ser alucinados
adapter.cache.preload_critical({
    "taxa selic": "A taxa SELIC vigente é 12.25% ao ano",
    "cdi": "O CDI acompanha a SELIC, atualmente ~12.15% ao ano",
    "ibovespa": "O Ibovespa é o principal índice da B3",
    "poupanca": "Rendimento da poupança: 70% da SELIC quando SELIC > 8.5%",
    "fgc": "O FGC garante até R$ 250.000 por CPF por instituição"
})

guardrails = QuimeraGuardrails(
    tenant_id="agente_financeiro",
    knowledge_adapter=adapter,
    compliance_standards=["lgpd", "bacen"]  # Compliance bancário
)
```

### Monitoramento e Estatísticas

```python
# Estatísticas do adapter
stats = adapter.get_adapter_stats()
print(f"Cache hit rate: {stats['cache_hit_rate']:.1%}")
print(f"API calls: {stats['api_calls']}")
print(f"Latência média: {stats['avg_latency_ms']:.2f}ms")

# Estatísticas do File Search (via API)
full_stats = await adapter.get_stats()
print(f"Documentos indexados: {full_stats['file_search']['total_documents']}")
```

### Quando NÃO Precisa de Ontologia

O Quimera funciona **muito bem** sem ontologia para:

- ✅ Bloquear PII (CPF, cartão, etc.)
- ✅ Detectar injection/jailbreak
- ✅ Compliance regulatório (LGPD)
- ✅ Métricas de qualidade básicas

Use ontologia/File Search quando precisar:

- 🔮 Detectar alucinações específicas do domínio
- 🔮 Verificar informações factuais
- 🔮 Garantir consistência com dados internos

## 🧠 Auto-Alimentação de Ontologias (OntologySync)

Como seu SaaS é um orquestrador genérico onde **o cliente cria seus próprios agentes** para qualquer área de conhecimento (RH, Financeiro, Jurídico, Saúde, etc.), o Quimera precisa se adaptar automaticamente ao domínio.

O `OntologySync` resolve isso **extraindo automaticamente fatos e ontologias** dos mesmos documentos que o cliente envia ao File Search!

### Como Funciona

```
┌─────────────────────────────────────────────────────────────────┐
│                    FLUXO DE AUTO-ALIMENTAÇÃO                    │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│   ┌─────────────────┐                                          │
│   │ Cliente faz     │                                          │
│   │ upload de docs  │                                          │
│   └────────┬────────┘                                          │
│            │                                                    │
│            ▼                                                    │
│   ┌─────────────────┐       ┌─────────────────┐                │
│   │   File Search   │──────>│  OntologySync   │                │
│   │   (indexação)   │       │  extrai fatos   │                │
│   └────────┬────────┘       └────────┬────────┘                │
│            │                         │                          │
│            ▼                         ▼                          │
│   ┌─────────────────┐       ┌─────────────────┐                │
│   │  Agente usa     │       │ Quimera Ontology│                │
│   │  para RAG       │       │ valida outputs  │                │
│   └─────────────────┘       └─────────────────┘                │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Tipos de Fatos Extraídos Automaticamente

| Tipo | Exemplo | Padrão Detectado |
|------|---------|------------------|
| **DEFINITION** | "CLT é a Consolidação das Leis do Trabalho" | "X é Y", "X significa Y" |
| **NUMERIC** | "Taxa SELIC: 12.25% ao ano" | Percentuais, valores em R$ |
| **RULE** | "É obrigatório aviso prévio de 30 dias" | "É obrigatório X", "Não é permitido Y" |
| **TEMPORAL** | "Atendimento de 9h às 18h" | Horários, prazos, datas |
| **CONSTRAINT** | "Férias só podem ser divididas em 3 períodos" | Restrições e condições |

### Configuração Básica

```python
from quimera_guardrails import (
    QuimeraGuardrails,
    CustomFileSearchAdapter,
    OntologySync,
    create_ontology_sync
)

# 1. Criar adapter do File Search
file_search = CustomFileSearchAdapter(
    base_url="http://localhost:8000",
    tenant_id="cliente_abc"
)

# 2. Criar guardrails
guardrails = QuimeraGuardrails(
    tenant_id="cliente_abc",
    knowledge_adapter=file_search
)

# 3. Criar sincronizador de ontologia
sync = OntologySync(
    file_search_adapter=file_search,
    ontology_manager=guardrails.ontology_manager,
    min_facts_confidence=0.6,      # Confiança mínima
    max_facts_per_document=50      # Limite por documento
)

# 4. Sincronizar ontologia dos documentos existentes
stats = await sync.sync_from_documents()
print(f"Fatos extraídos: {stats['facts_extracted']}")
print(f"Fatos adicionados à ontologia: {stats['facts_added']}")
```

### Sincronização Automática em Uploads

Configure um hook para sincronizar automaticamente quando o cliente faz upload:

```python
# No seu endpoint de upload de documentos:

async def upload_document(file: UploadFile, tenant_id: str):
    # 1. Processa upload para File Search
    content = await file.read()
    text_content = extract_text(content)  # Seu extrator de texto
    
    await file_search.upload(
        content=text_content,
        filename=file.filename,
        tenant_id=tenant_id
    )
    
    # 2. Sincroniza ontologia automaticamente
    upload_hook = sync.create_upload_hook()
    sync_result = await upload_hook(
        content=text_content,
        filename=file.filename
    )
    
    return {
        "message": "Upload concluído",
        "facts_extracted": sync_result["facts_extracted"],
        "facts_added": sync_result["facts_added"]
    }
```

### Webhook FastAPI para Sincronização

Registre endpoints automáticos no seu FastAPI:

```python
from fastapi import FastAPI

app = FastAPI()

# Registra endpoints de sincronização
sync.register_fastapi_webhook(app, endpoint="/api/guardrails/sync")

# Endpoints disponíveis:
# POST /api/guardrails/sync         - Sincroniza um documento
# POST /api/guardrails/sync/all     - Sincroniza todos os documentos
# GET  /api/guardrails/sync/stats   - Estatísticas de sincronização
```

### Extração via LLM (Opcional)

Para extração mais sofisticada, use um LLM:

```python
from quimera_guardrails import create_ontology_sync

# Função que chama seu LLM
async def call_llm(prompt: str) -> str:
    # Sua implementação de chamada ao LLM
    response = await your_llm_client.generate(prompt)
    return response.text

# Criar sync com extração via LLM
sync = create_ontology_sync(
    file_search_adapter=file_search,
    ontology_manager=guardrails.ontology_manager,
    use_llm_extractor=True,
    llm_caller=call_llm
)
```

### Exemplo: Agente de RH Auto-Configurado

```python
# Cliente faz upload de documentos de RH:
# - CLT.pdf
# - Acordo_Coletivo_2024.pdf
# - Manual_Beneficios.pdf

# O OntologySync extrai automaticamente:
facts_extracted = [
    "Férias: mínimo de 30 dias após 12 meses de trabalho",
    "Aviso prévio: 30 dias, acrescido de 3 dias por ano trabalhado",
    "13º salário: pago em duas parcelas, até novembro e dezembro",
    "Vale-refeição: R$ 35,00 por dia trabalhado",
    "Horário de trabalho: 8h às 17h com 1h de almoço",
    "Banco de horas: máximo de 2 horas extras por dia"
]

# Agora, se o agente responder:
# "Suas férias são de 15 dias após 6 meses de trabalho"
# 
# O Quimera detectará como ALUCINAÇÃO porque contradiz
# o fato extraído automaticamente do documento!
```

### Monitoramento

```python
# Estatísticas da sincronização
stats = sync.get_stats()
print(f"Documentos processados: {stats['documents_processed']}")
print(f"Fatos extraídos: {stats['facts_extracted']}")
print(f"Fatos na ontologia: {stats['facts_added_to_ontology']}")
print(f"Última sincronização: {stats['last_sync']}")
```

## 🔗 Integração com Google File Search (Legado)

> ⚠️ **Nota**: O `GoogleFileSearchAdapter` está disponível para compatibilidade,
> mas recomendamos usar o `CustomFileSearchAdapter` integrado ao seu sistema.

```python
from quimera_guardrails.adapters import GoogleFileSearchAdapter, HAS_GOOGLE_ADAPTER

if HAS_GOOGLE_ADAPTER:
    adapter = GoogleFileSearchAdapter(
        api_key="sua_api_key_gemini",
        corpus_name="corpora/seu-corpus"
    )
```

## 🔒 Segurança

- Todas as decisões são registradas com hash SHA-256
- Cadeia de provas tipo blockchain para auditoria
- Dados sensíveis são automaticamente mascarados
- Isolamento completo entre tenants
- Sem dependências externas para core security

## 📝 Licença

O código original deste repositório é licenciado sob a GNU Affero General Public License v3 ou posterior (AGPLv3+). Consulte a [licença na raiz do repositório](../LICENSE). Uso proprietário ou fora dos termos da AGPLv3+ exige autorização escrita separada do titular dos direitos autorais.

## 🤝 Contribuição

Contribuições são bem-vindas! Por favor, abra uma issue primeiro para discutir mudanças propostas.

---

**Desenvolvido com 🔬 pelo Projeto Quimera**
