# -*- coding: utf-8 -*-
"""
Custom File Search Adapter - Integração com Sistema RAG Próprio
================================================================

Conecta o Quimera Guardrails ao sistema File Search Híbrido do 
Enterprise Agent Orchestrator (EAO), permitindo usar a mesma base 
de conhecimento do agente para validação de alucinações.

Características do Sistema File Search do EAO:
- PostgreSQL + pgvector para armazenamento vetorial
- Busca híbrida: Vetor + Keyword com RRF (Reciprocal Rank Fusion)
- Reranking com FlashRank (ms-marco-MiniLM-L-12-v2)
- Chunking: 1500 tokens com 200 overlap
- Embedding: sentence-transformers/paraphrase-multilingual-mpnet-base-v2
- Multi-tenant com RLS no PostgreSQL

Estratégias de Performance:
1. LAZY: Só consulta quando detecta possível alucinação
2. CACHE: Mantém fatos críticos em memória (TTL configurável)
3. ASYNC: Valida em background sem bloquear resposta
4. BATCH: Agrupa múltiplas queries em uma chamada

Uso:
    from quimera_guardrails.adapters import CustomFileSearchAdapter
    
    adapter = CustomFileSearchAdapter(
        base_url="http://localhost:8000",
        tenant_id="meu_tenant",
        api_key="opcional"
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
from typing import Dict, Any, List, Optional, Union
from datetime import datetime, timedelta
import json
import logging

# HTTP clients (preferência por httpx para async, fallback para aiohttp/requests)
try:
    import httpx
    HAS_HTTPX = True
except ImportError:
    HAS_HTTPX = False

try:
    import aiohttp
    HAS_AIOHTTP = True
except ImportError:
    HAS_AIOHTTP = False

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

logger = logging.getLogger(__name__)


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
    chunk_id: Optional[str] = None
    document_id: Optional[str] = None


class KnowledgeAdapter(ABC):
    """
    Interface base para adapters de conhecimento.
    
    Permite plugar diferentes fontes:
    - Custom File Search (PostgreSQL + pgvector)
    - Google File Search
    - Pinecone
    - Weaviate
    - Qdrant
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
    - Suporte a cache por tenant
    """
    
    def __init__(
        self,
        max_size: int = 1000,
        default_ttl_minutes: int = 60
    ):
        self.max_size = max_size
        self.default_ttl = timedelta(minutes=default_ttl_minutes)
        self._cache: Dict[str, List[KnowledgeFact]] = {}
        self._access_times: Dict[str, datetime] = {}
        self._critical_keys: set = set()
    
    def _make_key(self, query: str, tenant_id: Optional[str] = None) -> str:
        """Cria chave de cache normalizada (inclui tenant para isolamento)"""
        normalized = query.lower().strip()
        if tenant_id:
            normalized = f"{tenant_id}:{normalized}"
        return hashlib.md5(normalized.encode()).hexdigest()[:16]
    
    def get(self, query: str, tenant_id: Optional[str] = None) -> Optional[List[KnowledgeFact]]:
        """Recupera do cache se válido"""
        key = self._make_key(query, tenant_id)
        
        if key not in self._cache:
            return None
        
        facts = self._cache[key]
        
        # Verifica TTL
        if facts and facts[0].cached_at:
            age = datetime.now() - facts[0].cached_at
            if age > self.default_ttl and key not in self._critical_keys:
                del self._cache[key]
                if key in self._access_times:
                    del self._access_times[key]
                return None
        
        # Atualiza tempo de acesso
        self._access_times[key] = datetime.now()
        
        return facts
    
    def set(
        self,
        query: str,
        facts: List[KnowledgeFact],
        tenant_id: Optional[str] = None,
        is_critical: bool = False
    ):
        """Armazena no cache"""
        key = self._make_key(query, tenant_id)
        
        # Eviction se necessário
        if len(self._cache) >= self.max_size:
            self._evict_oldest()
        
        # Marca timestamp
        now = datetime.now()
        for fact in facts:
            fact.cached_at = now
        
        self._cache[key] = facts
        self._access_times[key] = now
        
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
        
        # Remove os mais antigos (não críticos) - 25% do cache
        for key, _ in sorted_keys[:max(1, len(sorted_keys) // 4)]:
            if key not in self._critical_keys:
                if key in self._cache:
                    del self._cache[key]
                if key in self._access_times:
                    del self._access_times[key]
    
    def preload_critical(
        self,
        facts: Dict[str, str],
        tenant_id: Optional[str] = None
    ):
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
            key = self._make_key(query, tenant_id)
            self._cache[key] = [fact]
            self._critical_keys.add(key)
    
    def invalidate(self, query: str, tenant_id: Optional[str] = None):
        """Invalida uma entrada específica do cache"""
        key = self._make_key(query, tenant_id)
        if key in self._cache:
            del self._cache[key]
        if key in self._access_times:
            del self._access_times[key]
        self._critical_keys.discard(key)
    
    def clear(self, tenant_id: Optional[str] = None):
        """Limpa o cache (todo ou por tenant)"""
        if tenant_id:
            # Limpa apenas do tenant específico
            keys_to_remove = [
                k for k in self._cache.keys()
                if k.startswith(hashlib.md5(f"{tenant_id}:".encode()).hexdigest()[:8])
            ]
            for key in keys_to_remove:
                del self._cache[key]
                self._access_times.pop(key, None)
                self._critical_keys.discard(key)
        else:
            self._cache.clear()
            self._access_times.clear()
            self._critical_keys.clear()
    
    def stats(self) -> Dict[str, Any]:
        """Retorna estatísticas do cache"""
        return {
            "size": len(self._cache),
            "max_size": self.max_size,
            "critical_count": len(self._critical_keys),
            "ttl_minutes": self.default_ttl.total_seconds() / 60
        }


# =============================================================================
# Custom File Search Adapter (PostgreSQL + pgvector)
# =============================================================================

class CustomFileSearchAdapter(KnowledgeAdapter):
    """
    Adapter para o sistema File Search Híbrido do EAO
    
    Conecta o Quimera à mesma base de conhecimento usada pelo seu agente,
    permitindo validação de alucinações sem duplicar dados.
    
    API Endpoints do EAO:
    - POST /api/file-search/search - Busca híbrida com reranking
    - POST /api/file-search/upload - Upload de documentos
    - GET /api/file-search/stats - Estatísticas da base
    - DELETE /api/file-search/{filename} - Remover documento
    
    Uso:
        adapter = CustomFileSearchAdapter(
            base_url="http://localhost:8000",
            tenant_id="meu_tenant"
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
        base_url: str,
        tenant_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        api_key: Optional[str] = None,
        auth_token: Optional[str] = None,
        timeout_seconds: float = 30.0,
        cache_enabled: bool = True,
        cache_ttl_minutes: int = 30,
        max_cache_size: int = 500,
        use_reranking: bool = True,
        min_relevance_score: float = 0.3,
        search_mode: str = "hybrid"  # "hybrid", "vector", "keyword"
    ):
        """
        Inicializa o adapter
        
        Args:
            base_url: URL base do backend EAO (ex: http://localhost:8000)
            tenant_id: ID do tenant para multi-tenancy (RLS)
            agent_id: ID do agente para filtrar documentos específicos
            api_key: API key para autenticação (opcional)
            auth_token: Token JWT para autenticação (opcional)
            timeout_seconds: Timeout para requisições HTTP
            cache_enabled: Habilita cache local de fatos
            cache_ttl_minutes: TTL do cache em minutos
            max_cache_size: Tamanho máximo do cache
            use_reranking: Usar FlashRank para reordenar resultados
            min_relevance_score: Score mínimo para considerar um resultado
            search_mode: Modo de busca ("hybrid", "vector", "keyword")
        """
        self.base_url = base_url.rstrip('/')
        self.tenant_id = tenant_id
        self.agent_id = agent_id
        self.api_key = api_key
        self.auth_token = auth_token
        self.timeout = timeout_seconds
        self.use_reranking = use_reranking
        self.min_relevance_score = min_relevance_score
        self.search_mode = search_mode
        
        # Verifica dependências HTTP
        if not (HAS_HTTPX or HAS_AIOHTTP or HAS_REQUESTS):
            raise ImportError(
                "Nenhum cliente HTTP disponível. "
                "Instale: pip install httpx ou pip install aiohttp"
            )
        
        # Cache opcional
        self.cache_enabled = cache_enabled
        self.cache = FactCache(
            max_size=max_cache_size,
            default_ttl_minutes=cache_ttl_minutes
        ) if cache_enabled else None
        
        # Estatísticas
        self.stats: Dict[str, float] = {
            "cache_hits": 0,
            "cache_misses": 0,
            "api_calls": 0,
            "api_errors": 0,
            "avg_latency_ms": 0.0,
            "total_latency_ms": 0.0
        }
        
        # Cliente HTTP (inicializado lazy)
        self._client = None
    
    def _get_headers(self) -> Dict[str, str]:
        """Monta headers para requisições"""
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        
        if self.api_key:
            headers["X-API-Key"] = self.api_key
        
        if self.auth_token:
            headers["Authorization"] = f"Bearer {self.auth_token}"
        
        if self.tenant_id:
            headers["X-Tenant-ID"] = self.tenant_id
        
        return headers
    
    async def _make_request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict] = None,
        params: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """Faz requisição HTTP assíncrona"""
        url = f"{self.base_url}{endpoint}"
        headers = self._get_headers()
        
        start_time = time.time()
        
        try:
            if HAS_HTTPX:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    if method.upper() == "GET":
                        response = await client.get(url, headers=headers, params=params)
                    elif method.upper() == "POST":
                        response = await client.post(url, headers=headers, json=data, params=params)
                    elif method.upper() == "DELETE":
                        response = await client.delete(url, headers=headers, params=params)
                    else:
                        raise ValueError(f"Método HTTP não suportado: {method}")
                    
                    response.raise_for_status()
                    result = response.json()
            
            elif HAS_AIOHTTP:
                async with aiohttp.ClientSession() as session:
                    if method.upper() == "GET":
                        async with session.get(url, headers=headers, params=params, timeout=self.timeout) as response:
                            response.raise_for_status()
                            result = await response.json()
                    elif method.upper() == "POST":
                        async with session.post(url, headers=headers, json=data, params=params, timeout=self.timeout) as response:
                            response.raise_for_status()
                            result = await response.json()
                    elif method.upper() == "DELETE":
                        async with session.delete(url, headers=headers, params=params, timeout=self.timeout) as response:
                            response.raise_for_status()
                            result = await response.json()
                    else:
                        raise ValueError(f"Método HTTP não suportado: {method}")
            
            else:
                # Fallback síncrono com requests
                loop = asyncio.get_event_loop()
                result = await loop.run_in_executor(
                    None,
                    lambda: self._sync_request(method, url, headers, data, params)
                )
            
            # Atualiza estatísticas
            latency_ms = (time.time() - start_time) * 1000
            self.stats["api_calls"] += 1
            self.stats["total_latency_ms"] += latency_ms
            self.stats["avg_latency_ms"] = self.stats["total_latency_ms"] / self.stats["api_calls"]
            
            return result
        
        except Exception as e:
            self.stats["api_errors"] += 1
            logger.error(f"Erro na requisição {method} {url}: {e}")
            raise
    
    def _sync_request(
        self,
        method: str,
        url: str,
        headers: Dict,
        data: Optional[Dict],
        params: Optional[Dict]
    ) -> Dict[str, Any]:
        """Fallback síncrono usando requests"""
        if not HAS_REQUESTS:
            raise ImportError("requests não disponível")
        
        if method.upper() == "GET":
            response = requests.get(url, headers=headers, params=params, timeout=self.timeout)
        elif method.upper() == "POST":
            response = requests.post(url, headers=headers, json=data, params=params, timeout=self.timeout)
        elif method.upper() == "DELETE":
            response = requests.delete(url, headers=headers, params=params, timeout=self.timeout)
        else:
            raise ValueError(f"Método HTTP não suportado: {method}")
        
        response.raise_for_status()
        return response.json()
    
    async def search(
        self,
        query: str,
        max_results: int = 5,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[KnowledgeFact]:
        """
        Busca fatos na base de conhecimento usando File Search Híbrido
        
        Args:
            query: Texto para buscar
            max_results: Máximo de resultados (default: 5)
            filters: Filtros opcionais:
                - document_ids: Lista de IDs de documentos específicos
                - metadata: Filtros de metadados
                - date_from: Data mínima
                - date_to: Data máxima
                
        Returns:
            Lista de KnowledgeFact ordenados por relevância
        """
        # Tenta cache primeiro
        if self.cache_enabled and self.cache:
            cached = self.cache.get(query, self.tenant_id)
            if cached:
                self.stats["cache_hits"] += 1
                logger.debug(f"Cache hit para query: {query[:50]}...")
                return cached[:max_results]
            self.stats["cache_misses"] += 1
        
        # Monta payload para API
        payload = {
            "query": query,
            "top_k": max_results,
            "use_rerank": self.use_reranking,
            "tenant_id": self.tenant_id or "default"
        }
        
        # Adiciona filtros opcionais
        if self.agent_id:
            payload["agent_id"] = self.agent_id
        
        if filters:
            if "document_ids" in filters:
                payload["document_ids"] = filters["document_ids"]
            if "metadata" in filters:
                payload["metadata_filter"] = filters["metadata"]
        
        try:
            # Faz requisição à API
            response = await self._make_request(
                method="POST",
                endpoint="/api/file-search/search",
                data=payload
            )
            
            # Converte resposta para KnowledgeFact
            facts = self._parse_search_response(response)
            
            # Armazena no cache
            if self.cache_enabled and self.cache and facts:
                self.cache.set(query, facts, self.tenant_id)
            
            return facts[:max_results]
        
        except Exception as e:
            logger.error(f"Erro ao buscar no File Search: {e}")
            # Retorna lista vazia em caso de erro (fail-safe)
            return []
    
    def _parse_search_response(self, response: Dict[str, Any]) -> List[KnowledgeFact]:
        """Converte resposta da API para lista de KnowledgeFact"""
        facts = []
        
        # Formato esperado da resposta:
        # {
        #   "results": [
        #     {
        #       "content": "texto do chunk",
        #       "score": 0.95,
        #       "document_id": "uuid",
        #       "chunk_id": "uuid",
        #       "filename": "documento.pdf",
        #       "metadata": {...}
        #     }
        #   ],
        #   "total_found": 10,
        #   "search_mode": "hybrid"
        # }
        
        results = response.get("results", [])
        
        for result in results:
            score = result.get("score", result.get("relevance_score", 0.5))
            
            # Filtra por score mínimo
            if score < self.min_relevance_score:
                continue
            
            fact = KnowledgeFact(
                content=result.get("content", result.get("text", "")),
                source=result.get("source_file", result.get("filename", result.get("source", "unknown"))),
                relevance_score=score,
                metadata=result.get("metadata", {}),
                chunk_id=result.get("chunk_id"),
                document_id=result.get("document_id")
            )
            facts.append(fact)
        
        # Ordena por relevância decrescente
        facts.sort(key=lambda f: f.relevance_score, reverse=True)
        
        return facts
    
    async def verify_claim(
        self,
        claim: str,
        context: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Verifica se uma afirmação é suportada pela base de conhecimento
        
        Esta é a função principal para validação de alucinações!
        
        Args:
            claim: Afirmação a ser verificada
            context: Contexto adicional (pergunta do usuário, etc.)
            
        Returns:
            {
                "supported": bool,           # Se a afirmação é suportada
                "confidence": float,         # Confiança na verificação (0-1)
                "evidence": List[KnowledgeFact],  # Evidências encontradas
                "reasoning": str,            # Explicação da decisão
                "status": str               # "verified", "contradicted", "uncertain"
            }
        """
        # Combina claim com contexto para busca mais precisa
        search_query = claim
        if context:
            search_query = f"{context} {claim}"
        
        # Busca evidências
        evidence = await self.search(query=search_query, max_results=5)
        
        if not evidence:
            return {
                "supported": False,
                "confidence": 0.0,
                "evidence": [],
                "reasoning": "Nenhuma evidência encontrada na base de conhecimento",
                "status": "uncertain"
            }
        
        # Análise de suporte
        # Estratégia: verificar overlap semântico entre claim e evidências
        best_score = max(f.relevance_score for f in evidence)
        avg_score = sum(f.relevance_score for f in evidence) / len(evidence)
        
        # Regras de decisão
        if best_score >= 0.85:
            # Alta confiança - evidência forte encontrada
            return {
                "supported": True,
                "confidence": best_score,
                "evidence": evidence[:3],
                "reasoning": f"Afirmação bem suportada pela evidência (score: {best_score:.2f})",
                "status": "verified"
            }
        elif best_score >= 0.6:
            # Confiança média - evidência parcial
            return {
                "supported": True,
                "confidence": best_score * 0.9,
                "evidence": evidence[:3],
                "reasoning": f"Afirmação parcialmente suportada (score: {best_score:.2f})",
                "status": "verified"
            }
        elif best_score >= 0.4:
            # Baixa confiança - incerto
            return {
                "supported": False,
                "confidence": 0.5,
                "evidence": evidence[:3],
                "reasoning": f"Evidência insuficiente para confirmar (score: {best_score:.2f})",
                "status": "uncertain"
            }
        else:
            # Muito baixo - provavelmente não suportado
            return {
                "supported": False,
                "confidence": 1.0 - best_score,
                "evidence": evidence[:3],
                "reasoning": f"Afirmação não encontrada na base de conhecimento (score: {best_score:.2f})",
                "status": "contradicted"
            }
    
    async def batch_verify(
        self,
        claims: List[str],
        context: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Verifica múltiplas afirmações em paralelo
        
        Útil para validar uma resposta inteira de uma vez.
        
        Args:
            claims: Lista de afirmações a verificar
            context: Contexto compartilhado
            
        Returns:
            Lista de resultados de verificação
        """
        tasks = [self.verify_claim(claim, context) for claim in claims]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Trata exceções
        parsed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Erro ao verificar claim {i}: {result}")
                parsed_results.append({
                    "supported": False,
                    "confidence": 0.0,
                    "evidence": [],
                    "reasoning": f"Erro na verificação: {result}",
                    "status": "error"
                })
            else:
                parsed_results.append(result)
        
        return parsed_results
    
    async def get_stats(self) -> Dict[str, Any]:
        """
        Retorna estatísticas da base de conhecimento
        
        Chama o endpoint GET /api/file-search/stats
        """
        try:
            response = await self._make_request(
                method="GET",
                endpoint="/api/file-search/stats"
            )
            
            return {
                "file_search": response,
                "adapter": {
                    "cache": self.cache.stats() if self.cache else None,
                    "api_stats": self.stats
                }
            }
        except Exception as e:
            logger.error(f"Erro ao obter stats: {e}")
            return {"error": str(e)}
    
    def get_adapter_stats(self) -> Dict[str, Any]:
        """Retorna estatísticas do adapter (local)"""
        return {
            "cache": self.cache.stats() if self.cache else None,
            "api_calls": self.stats["api_calls"],
            "api_errors": self.stats["api_errors"],
            "cache_hits": self.stats["cache_hits"],
            "cache_misses": self.stats["cache_misses"],
            "avg_latency_ms": round(self.stats["avg_latency_ms"], 2),
            "cache_hit_rate": (
                self.stats["cache_hits"] / (self.stats["cache_hits"] + self.stats["cache_misses"])
                if (self.stats["cache_hits"] + self.stats["cache_misses"]) > 0
                else 0.0
            )
        }


# =============================================================================
# Adapter Simples para Testes/Mock
# =============================================================================

class SimpleKnowledgeAdapter(KnowledgeAdapter):
    """
    Adapter simples para testes ou quando não há File Search disponível.
    
    Mantém fatos em memória local.
    
    Uso:
        adapter = SimpleKnowledgeAdapter()
        adapter.add_fact("taxa selic", "A taxa SELIC atual é 12.25% ao ano")
        
        facts = await adapter.search("taxa selic")
    """
    
    def __init__(self):
        self._facts: List[KnowledgeFact] = []
    
    def add_fact(
        self,
        content: str,
        source: str = "local",
        keywords: Optional[List[str]] = None,
        metadata: Optional[Dict] = None
    ):
        """Adiciona um fato à base local"""
        fact = KnowledgeFact(
            content=content,
            source=source,
            relevance_score=1.0,
            metadata=metadata or {"keywords": keywords or []}
        )
        self._facts.append(fact)
    
    async def search(
        self,
        query: str,
        max_results: int = 5,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[KnowledgeFact]:
        """Busca por correspondência de texto simples"""
        query_lower = query.lower()
        results = []
        
        for fact in self._facts:
            # Calcula score simples baseado em overlap de palavras
            fact_words = set(fact.content.lower().split())
            query_words = set(query_lower.split())
            
            overlap = len(fact_words & query_words)
            if overlap > 0:
                score = overlap / max(len(fact_words), len(query_words))
                results.append((fact, score))
            
            # Também verifica keywords nos metadados
            keywords = fact.metadata.get("keywords", [])
            for kw in keywords:
                if kw.lower() in query_lower:
                    results.append((fact, 0.9))
                    break
        
        # Ordena por score
        results.sort(key=lambda x: x[1], reverse=True)
        
        # Atualiza scores nos fatos
        output = []
        for fact, score in results[:max_results]:
            fact.relevance_score = score
            output.append(fact)
        
        return output
    
    async def verify_claim(
        self,
        claim: str,
        context: Optional[str] = None
    ) -> Dict[str, Any]:
        """Verifica afirmação contra fatos locais"""
        evidence = await self.search(claim)
        
        if not evidence:
            return {
                "supported": False,
                "confidence": 0.0,
                "evidence": [],
                "reasoning": "Nenhum fato local corresponde",
                "status": "uncertain"
            }
        
        best_score = evidence[0].relevance_score
        
        return {
            "supported": best_score >= 0.5,
            "confidence": best_score,
            "evidence": evidence[:3],
            "reasoning": f"Correspondência local: {best_score:.2f}",
            "status": "verified" if best_score >= 0.5 else "uncertain"
        }


# =============================================================================
# Factory Functions
# =============================================================================

def create_file_search_adapter(
    config: Optional[Dict[str, Any]] = None,
    **kwargs
) -> KnowledgeAdapter:
    """
    Factory para criar adapter apropriado baseado na configuração
    
    Args:
        config: Dicionário de configuração ou None para usar kwargs
        **kwargs: Argumentos passados diretamente ao adapter
        
    Returns:
        KnowledgeAdapter configurado
        
    Exemplo:
        # Usando config dict
        adapter = create_file_search_adapter({
            "base_url": "http://localhost:8000",
            "tenant_id": "meu_tenant"
        })
        
        # Usando kwargs
        adapter = create_file_search_adapter(
            base_url="http://localhost:8000",
            tenant_id="meu_tenant"
        )
    """
    if config:
        kwargs.update(config)
    
    base_url = kwargs.get("base_url")
    
    if base_url:
        return CustomFileSearchAdapter(**kwargs)
    else:
        logger.warning("base_url não fornecido, usando SimpleKnowledgeAdapter")
        return SimpleKnowledgeAdapter()


def create_adapter_from_env() -> KnowledgeAdapter:
    """
    Cria adapter usando variáveis de ambiente
    
    Variáveis esperadas:
    - FILE_SEARCH_BASE_URL: URL do backend
    - FILE_SEARCH_TENANT_ID: ID do tenant
    - FILE_SEARCH_AGENT_ID: ID do agente (opcional)
    - FILE_SEARCH_API_KEY: API key (opcional)
    - FILE_SEARCH_CACHE_ENABLED: true/false
    - FILE_SEARCH_CACHE_TTL: TTL em minutos
    """
    import os
    
    base_url = os.environ.get("FILE_SEARCH_BASE_URL")
    
    if not base_url:
        logger.warning("FILE_SEARCH_BASE_URL não definido, usando SimpleKnowledgeAdapter")
        return SimpleKnowledgeAdapter()
    
    return CustomFileSearchAdapter(
        base_url=base_url,
        tenant_id=os.environ.get("FILE_SEARCH_TENANT_ID"),
        agent_id=os.environ.get("FILE_SEARCH_AGENT_ID"),
        api_key=os.environ.get("FILE_SEARCH_API_KEY"),
        cache_enabled=os.environ.get("FILE_SEARCH_CACHE_ENABLED", "true").lower() == "true",
        cache_ttl_minutes=int(os.environ.get("FILE_SEARCH_CACHE_TTL", "30")),
        use_reranking=os.environ.get("FILE_SEARCH_USE_RERANKING", "true").lower() == "true"
    )
