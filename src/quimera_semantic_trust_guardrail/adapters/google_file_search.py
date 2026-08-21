# -*- coding: utf-8 -*-
"""
Google File Search Adapter - Integração com Ontology RAG Guardrail
==============================================================

Conecta o Ontology RAG Guardrail ao Google File Search para usar a mesma base de
conhecimento do agente principal para validação de alucinações.

Referência: https://blog.google/technology/developers/file-search-gemini-api/

Estratégias de Performance:
1. LAZY: Só consulta quando detecta possível alucinação
2. CACHE: Mantém fatos críticos em memória
3. ASYNC: Valida em background sem bloquear resposta

Uso:
    from quimera_guardrails.adapters import GoogleFileSearchAdapter
    
    adapter = GoogleFileSearchAdapter(
        api_key="sua_api_key",
        corpus_name="corpora/meu_corpus"
    )
    
    guardrails = QuimeraGuardrails(
        tenant_id="meu_tenant",
        knowledge_adapter=adapter
    )
"""

from __future__ import annotations
import asyncio
import hashlib
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import json

try:
    import google.generativeai as genai
    HAS_GOOGLE_AI = True
except ImportError:
    HAS_GOOGLE_AI = False


# =============================================================================
# Interface Base para Adapters
# =============================================================================

@dataclass
class KnowledgeFact:
    """Um fato recuperado da base de conhecimento"""
    content: str
    source: str
    relevance_score: float
    metadata: Dict[str, Any] = field(default_factory=dict)
    cached_at: Optional[datetime] = None


class KnowledgeAdapter(ABC):
    """
    Interface base para adapters de conhecimento.
    
    Permite plugar diferentes fontes:
    - Google File Search
    - Pinecone
    - Weaviate
    - Qdrant
    - Banco de dados próprio
    """
    
    @abstractmethod
    async def search(
        self,
        query: str,
        max_results: int = 5,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[KnowledgeFact]:
        """Busca fatos relevantes para a query"""
        pass
    
    @abstractmethod
    async def verify_claim(
        self,
        claim: str,
        context: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Verifica se uma afirmação é suportada pela base de conhecimento
        
        Returns:
            {
                "supported": bool,
                "confidence": float,
                "evidence": List[KnowledgeFact],
                "reasoning": str
            }
        """
        pass


# =============================================================================
# Cache de Fatos para Performance
# =============================================================================

class FactCache:
    """
    Cache inteligente de fatos para reduzir latência
    
    Features:
    - TTL configurável por categoria
    - LRU eviction
    - Pré-carregamento de fatos críticos
    """
    
    def __init__(
        self,
        max_size: int = 1000,
        default_ttl_minutes: int = 60
    ):
        self.max_size = max_size
        self.default_ttl = timedelta(minutes=default_ttl_minutes)
        self._cache: Dict[str, KnowledgeFact] = {}
        self._access_times: Dict[str, datetime] = {}
        self._critical_keys: set = set()
    
    def _make_key(self, query: str) -> str:
        """Cria chave de cache normalizada"""
        normalized = query.lower().strip()
        return hashlib.md5(normalized.encode()).hexdigest()[:16]
    
    def get(self, query: str) -> Optional[List[KnowledgeFact]]:
        """Recupera do cache se válido"""
        key = self._make_key(query)
        
        if key not in self._cache:
            return None
        
        fact = self._cache[key]
        
        # Verifica TTL
        if fact.cached_at:
            age = datetime.now() - fact.cached_at
            if age > self.default_ttl and key not in self._critical_keys:
                del self._cache[key]
                return None
        
        # Atualiza tempo de acesso
        self._access_times[key] = datetime.now()
        
        return [fact]
    
    def set(
        self,
        query: str,
        facts: List[KnowledgeFact],
        is_critical: bool = False
    ):
        """Armazena no cache"""
        key = self._make_key(query)
        
        # Eviction se necessário
        if len(self._cache) >= self.max_size:
            self._evict_oldest()
        
        # Marca timestamp
        for fact in facts:
            fact.cached_at = datetime.now()
        
        if facts:
            self._cache[key] = facts[0]  # Armazena o mais relevante
            self._access_times[key] = datetime.now()
            
            if is_critical:
                self._critical_keys.add(key)
    
    def _evict_oldest(self):
        """Remove itens menos acessados (exceto críticos)"""
        if not self._access_times:
            return
        
        # Ordena por tempo de acesso
        sorted_keys = sorted(
            self._access_times.items(),
            key=lambda x: x[1]
        )
        
        # Remove os mais antigos (não críticos)
        for key, _ in sorted_keys[:len(sorted_keys) // 4]:
            if key not in self._critical_keys:
                del self._cache[key]
                del self._access_times[key]
    
    def preload_critical(self, facts: Dict[str, str]):
        """
        Pré-carrega fatos críticos que nunca expiram
        
        Uso:
            cache.preload_critical({
                "taxa selic": "A taxa SELIC atual é 12.25% ao ano",
                "horario funcionamento": "Atendimento de 9h às 18h"
            })
        """
        for query, content in facts.items():
            fact = KnowledgeFact(
                content=content,
                source="preloaded",
                relevance_score=1.0,
                cached_at=datetime.now()
            )
            key = self._make_key(query)
            self._cache[key] = fact
            self._critical_keys.add(key)


# =============================================================================
# Google File Search Adapter
# =============================================================================

class GoogleFileSearchAdapter(KnowledgeAdapter):
    """
    Adapter para Google File Search (Gemini API)
    
    Conecta o Ontology RAG Guardrail à mesma base de conhecimento usada pelo seu agente,
    permitindo validação de alucinações sem duplicar dados.
    
    Requisitos:
        pip install google-generativeai
    
    Uso:
        adapter = GoogleFileSearchAdapter(
            api_key="AIza...",
            corpus_name="corpora/meu-corpus-financeiro"
        )
        
        # Buscar fatos
        facts = await adapter.search("taxa selic atual")
        
        # Verificar afirmação
        result = await adapter.verify_claim(
            claim="A taxa SELIC é 5%",
            context="pergunta sobre investimentos"
        )
    """
    
    def __init__(
        self,
        api_key: str,
        corpus_name: str,
        model_name: str = "gemini-2.0-flash",
        cache_enabled: bool = True,
        cache_ttl_minutes: int = 30,
        max_cache_size: int = 500
    ):
        if not HAS_GOOGLE_AI:
            raise ImportError(
                "google-generativeai não instalado. "
                "Execute: pip install google-generativeai"
            )
        
        self.corpus_name = corpus_name
        self.model_name = model_name
        
        # Configura API
        genai.configure(api_key=api_key)
        
        # Cache opcional
        self.cache_enabled = cache_enabled
        self.cache = FactCache(
            max_size=max_cache_size,
            default_ttl_minutes=cache_ttl_minutes
        ) if cache_enabled else None
        
        # Estatísticas
        self.stats = {
            "cache_hits": 0,
            "cache_misses": 0,
            "api_calls": 0,
            "avg_latency_ms": 0
        }
    
    async def search(
        self,
        query: str,
        max_results: int = 5,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[KnowledgeFact]:
        """
        Busca fatos no Google File Search
        
        Args:
            query: Texto para buscar
            max_results: Máximo de resultados
            filters: Filtros opcionais (metadata)
            
        Returns:
            Lista de fatos encontrados
        """
        # Tenta cache primeiro
        if self.cache_enabled and self.cache:
            cached = self.cache.get(query)
            if cached:
                self.stats["cache_hits"] += 1
                return cached
            self.stats["cache_misses"] += 1
        
        start_time = time.time()
        
        try:
            # Configura retrieval
            retrieval_config = {
                "source": {
                    "corpus": self.corpus_name
                },
                "max_chunks_count": max_results
            }
            
            # Adiciona filtros se fornecidos
            if filters:
                retrieval_config["metadata_filters"] = filters
            
            # Cria modelo com grounding
            model = genai.GenerativeModel(
                self.model_name,
                tools=[{
                    "retrieval": retrieval_config
                }]
            )
            
            # Faz a busca
            response = await asyncio.to_thread(
                model.generate_content,
                f"Busque informações sobre: {query}"
            )
            
            self.stats["api_calls"] += 1
            
            # Extrai chunks do grounding
            facts = []
            
            if hasattr(response, 'candidates') and response.candidates:
                candidate = response.candidates[0]
                
                # Extrai grounding chunks
                if hasattr(candidate, 'grounding_metadata'):
                    grounding = candidate.grounding_metadata
                    
                    if hasattr(grounding, 'retrieval_queries'):
                        for chunk in getattr(grounding, 'grounding_chunks', []):
                            facts.append(KnowledgeFact(
                                content=chunk.text if hasattr(chunk, 'text') else str(chunk),
                                source=self.corpus_name,
                                relevance_score=0.8,  # Estimado
                                metadata={"chunk_id": getattr(chunk, 'chunk_id', None)}
                            ))
                
                # Fallback: usa o texto da resposta
                if not facts and hasattr(candidate, 'content'):
                    facts.append(KnowledgeFact(
                        content=candidate.content.parts[0].text if candidate.content.parts else "",
                        source=self.corpus_name,
                        relevance_score=0.7
                    ))
            
            # Atualiza cache
            if self.cache_enabled and self.cache and facts:
                self.cache.set(query, facts)
            
            # Atualiza latência média
            elapsed = (time.time() - start_time) * 1000
            self.stats["avg_latency_ms"] = (
                self.stats["avg_latency_ms"] * 0.9 + elapsed * 0.1
            )
            
            return facts
            
        except Exception as e:
            # Log error mas não falha
            print(f"[GoogleFileSearch] Erro na busca: {e}")
            return []
    
    async def verify_claim(
        self,
        claim: str,
        context: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Verifica se uma afirmação é suportada pela base de conhecimento
        
        Esta é a função principal para detecção de alucinações.
        
        Args:
            claim: Afirmação a verificar (ex: "A taxa SELIC é 5%")
            context: Contexto adicional (ex: "pergunta sobre investimentos")
            
        Returns:
            {
                "supported": bool,
                "confidence": float (0-1),
                "evidence": List[KnowledgeFact],
                "reasoning": str
            }
        """
        # Busca evidências
        search_query = f"{claim} {context or ''}"
        facts = await self.search(search_query, max_results=3)
        
        if not facts:
            return {
                "supported": None,  # Indeterminado
                "confidence": 0.5,
                "evidence": [],
                "reasoning": "Nenhuma evidência encontrada na base de conhecimento"
            }
        
        try:
            # Usa Gemini para verificar consistência
            model = genai.GenerativeModel(self.model_name)
            
            evidence_text = "\n".join([f"- {f.content}" for f in facts])
            
            prompt = f"""Analise se a afirmação é suportada pelas evidências.

AFIRMAÇÃO: {claim}

EVIDÊNCIAS DA BASE DE CONHECIMENTO:
{evidence_text}

Responda em JSON:
{{
    "supported": true/false/null,
    "confidence": 0.0 a 1.0,
    "reasoning": "explicação breve"
}}

Se as evidências não forem suficientes para determinar, use null para supported."""

            response = await asyncio.to_thread(
                model.generate_content,
                prompt
            )
            
            # Parse resposta
            response_text = response.text.strip()
            
            # Remove marcadores de código se presentes
            if response_text.startswith("```"):
                response_text = response_text.split("```")[1]
                if response_text.startswith("json"):
                    response_text = response_text[4:]
            
            result = json.loads(response_text)
            result["evidence"] = facts
            
            return result
            
        except Exception as e:
            # Fallback: retorna indeterminado
            return {
                "supported": None,
                "confidence": 0.5,
                "evidence": facts,
                "reasoning": f"Erro na verificação: {str(e)}"
            }
    
    def preload_critical_facts(self, facts: Dict[str, str]):
        """
        Pré-carrega fatos críticos no cache
        
        Útil para informações que mudam raramente e são consultadas frequentemente.
        
        Exemplo:
            adapter.preload_critical_facts({
                "horario atendimento": "Atendimento de segunda a sexta, 9h às 18h",
                "taxa selic": "A taxa SELIC atual é 12.25% ao ano (Nov/2024)",
                "prazo pix": "Transferências PIX são processadas em até 10 segundos"
            })
        """
        if self.cache:
            self.cache.preload_critical(facts)
    
    def get_stats(self) -> Dict[str, Any]:
        """Retorna estatísticas de uso"""
        total_requests = self.stats["cache_hits"] + self.stats["cache_misses"]
        cache_hit_rate = (
            self.stats["cache_hits"] / total_requests * 100
            if total_requests > 0 else 0
        )
        
        return {
            **self.stats,
            "cache_hit_rate": f"{cache_hit_rate:.1f}%",
            "total_requests": total_requests
        }


# =============================================================================
# Adapter Simples (sem dependências externas)
# =============================================================================

class SimpleKnowledgeAdapter(KnowledgeAdapter):
    """
    Adapter simples baseado em dicionário.
    
    Útil para:
    - Desenvolvimento/testes
    - Bases de conhecimento pequenas
    - Fatos estáticos
    
    Uso:
        adapter = SimpleKnowledgeAdapter()
        
        adapter.add_fact("selic", "A taxa SELIC atual é 12.25% ao ano")
        adapter.add_fact("pix", "PIX funciona 24h por dia, 7 dias por semana")
        
        facts = await adapter.search("taxa selic")
    """
    
    def __init__(self):
        self._facts: Dict[str, List[KnowledgeFact]] = {}
    
    def add_fact(
        self,
        key: str,
        content: str,
        source: str = "manual",
        metadata: Optional[Dict] = None
    ):
        """Adiciona um fato à base"""
        key_lower = key.lower()
        
        fact = KnowledgeFact(
            content=content,
            source=source,
            relevance_score=1.0,
            metadata=metadata or {}
        )
        
        if key_lower not in self._facts:
            self._facts[key_lower] = []
        
        self._facts[key_lower].append(fact)
    
    def add_facts_from_dict(self, facts: Dict[str, str], source: str = "batch"):
        """Adiciona múltiplos fatos de um dicionário"""
        for key, content in facts.items():
            self.add_fact(key, content, source)
    
    async def search(
        self,
        query: str,
        max_results: int = 5,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[KnowledgeFact]:
        """Busca por keywords simples"""
        query_lower = query.lower()
        results = []
        
        for key, facts in self._facts.items():
            # Verifica se alguma palavra da query está na key
            if any(word in key for word in query_lower.split()):
                results.extend(facts)
            # Ou se a key está na query
            elif key in query_lower:
                results.extend(facts)
        
        # Ordena por relevância e limita
        results.sort(key=lambda f: f.relevance_score, reverse=True)
        return results[:max_results]
    
    async def verify_claim(
        self,
        claim: str,
        context: Optional[str] = None
    ) -> Dict[str, Any]:
        """Verificação simples por matching"""
        facts = await self.search(claim)
        
        if not facts:
            return {
                "supported": None,
                "confidence": 0.5,
                "evidence": [],
                "reasoning": "Nenhum fato relevante encontrado"
            }
        
        # Verificação simples: se encontrou fatos, assume suporte parcial
        return {
            "supported": True,
            "confidence": 0.7,
            "evidence": facts,
            "reasoning": "Fatos relacionados encontrados na base"
        }


# =============================================================================
# Factory para criar adapters
# =============================================================================

def create_knowledge_adapter(
    adapter_type: str = "simple",
    **kwargs
) -> KnowledgeAdapter:
    """
    Factory para criar adapters de conhecimento
    
    Args:
        adapter_type: "simple", "google", "pinecone", etc.
        **kwargs: Argumentos específicos do adapter
        
    Returns:
        KnowledgeAdapter configurado
    
    Exemplo:
        # Adapter simples
        adapter = create_knowledge_adapter("simple")
        
        # Google File Search
        adapter = create_knowledge_adapter(
            "google",
            api_key="...",
            corpus_name="corpora/meu-corpus"
        )
    """
    adapters = {
        "simple": SimpleKnowledgeAdapter,
        "google": GoogleFileSearchAdapter,
    }
    
    if adapter_type not in adapters:
        raise ValueError(f"Adapter desconhecido: {adapter_type}. "
                        f"Opções: {list(adapters.keys())}")
    
    adapter_class = adapters[adapter_type]
    
    # Simple não precisa de kwargs
    if adapter_type == "simple":
        return adapter_class()
    
    return adapter_class(**kwargs)
