# -*- coding: utf-8 -*-
"""
Ontology Sync - Sincronização Automática de Ontologias a partir do File Search
===============================================================================

Este módulo permite que o Quimera Guardrails seja automaticamente alimentado
com fatos e ontologias a partir dos mesmos documentos que o cliente envia ao
File Search do seu agente.

Problema Resolvido:
- O SaaS é um orquestrador genérico - não sabemos antecipadamente qual área
  de conhecimento o cliente vai usar (RH, Financeiro, Jurídico, Saúde, etc.)
- Os fatos e ontologias precisam ser dinâmicos e específicos do domínio
- O cliente não deve precisar configurar ontologias manualmente

Solução:
- Quando documentos são enviados ao File Search, extraímos automaticamente:
  1. Entidades nomeadas (pessoas, organizações, conceitos)
  2. Fatos declarativos ("X é Y", "X tem valor Z")
  3. Relações semânticas ("X pertence a Y", "X causa Z")
  4. Termos técnicos do domínio

Fluxo:
    ┌─────────────────┐
    │  Cliente faz    │
    │  upload de doc  │
    └────────┬────────┘
             │
             ▼
    ┌─────────────────┐
    │   File Search   │───────┐
    │   (indexação)   │       │ Hook de sincronização
    └────────┬────────┘       │
             │                │
             ▼                ▼
    ┌─────────────────┐  ┌─────────────────┐
    │  Agente usa     │  │ OntologySync    │
    │  para RAG       │  │ extrai fatos    │
    └─────────────────┘  └────────┬────────┘
                                  │
                                  ▼
                         ┌─────────────────┐
                         │ Quimera Ontology│
                         │ (validação)     │
                         └─────────────────┘

Uso:
    from quimera_guardrails.adapters import OntologySync, CustomFileSearchAdapter
    
    # Criar adapter do File Search
    file_search = CustomFileSearchAdapter(base_url="...", tenant_id="...")
    
    # Criar sincronizador de ontologia
    sync = OntologySync(
        file_search_adapter=file_search,
        ontology_manager=guardrails.ontology_manager
    )
    
    # Sincronizar ontologia a partir dos documentos existentes
    await sync.sync_from_documents()
    
    # Ou configurar webhook para sincronização automática
    sync.register_webhook(app)  # FastAPI app
"""

from __future__ import annotations
import asyncio
import re
import hashlib
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Set, Tuple, Callable
from datetime import datetime
from enum import Enum

logger = logging.getLogger(__name__)


# =============================================================================
# Tipos de Fatos Extraídos
# =============================================================================

class FactType(Enum):
    """Tipos de fatos que podem ser extraídos de documentos"""
    DEFINITION = "definition"       # "X é Y" - definições
    ATTRIBUTE = "attribute"         # "X tem valor Z" - atributos
    RELATION = "relation"           # "X está relacionado a Y" - relações
    RULE = "rule"                   # "Se X então Y" - regras
    CONSTRAINT = "constraint"       # "X deve/não deve" - restrições
    NUMERIC = "numeric"             # Valores numéricos (taxas, limites, etc.)
    TEMPORAL = "temporal"           # Datas, prazos, horários
    ENTITY = "entity"               # Entidades nomeadas


@dataclass
class ExtractedFact:
    """Um fato extraído de um documento"""
    content: str                           # Texto do fato
    fact_type: FactType                    # Tipo do fato
    confidence: float                      # Confiança na extração (0-1)
    source_document: str                   # Documento de origem
    source_chunk: Optional[str] = None     # Chunk específico
    entities: List[str] = field(default_factory=list)  # Entidades envolvidas
    metadata: Dict[str, Any] = field(default_factory=dict)
    extracted_at: datetime = field(default_factory=datetime.now)
    
    def to_ontology_entry(self) -> Dict[str, Any]:
        """Converte para formato de entrada de ontologia"""
        return {
            "content": self.content,
            "type": self.fact_type.value,
            "confidence": self.confidence,
            "source": self.source_document,
            "entities": self.entities,
            "metadata": {
                **self.metadata,
                "extracted_at": self.extracted_at.isoformat(),
                "chunk": self.source_chunk
            }
        }


@dataclass
class DomainTerminology:
    """Terminologia específica do domínio extraída"""
    term: str                              # O termo técnico
    definition: Optional[str] = None       # Definição encontrada
    synonyms: List[str] = field(default_factory=list)
    related_terms: List[str] = field(default_factory=list)
    frequency: int = 1                     # Frequência no corpus
    source_documents: List[str] = field(default_factory=list)


# =============================================================================
# Extratores de Fatos
# =============================================================================

class FactExtractor(ABC):
    """Interface base para extratores de fatos"""
    
    @abstractmethod
    def extract(self, text: str, source: str) -> List[ExtractedFact]:
        """Extrai fatos de um texto"""
        pass


class PatternBasedExtractor(FactExtractor):
    """
    Extrator baseado em padrões regex para extrair fatos de texto.
    
    Funciona bem para:
    - Definições ("X é Y", "X significa Y")
    - Valores numéricos ("Taxa de X%", "Limite de R$ Y")
    - Regras ("É obrigatório X", "Não é permitido Y")
    - Datas e prazos ("Prazo de X dias", "Até dia Y")
    """
    
    # Padrões para extração de fatos em português
    PATTERNS = {
        FactType.DEFINITION: [
            r'(?P<term>[\w\s]+?)\s+(?:é|são|significa|define-se como|consiste em)\s+(?P<definition>.+?)(?:\.|$)',
            r'(?:entende-se por|considera-se)\s+(?P<term>[\w\s]+?)\s+(?:como|o|a)\s+(?P<definition>.+?)(?:\.|$)',
            r'(?P<term>[\w\s]+?):\s+(?P<definition>.+?)(?:\.|$)',
        ],
        FactType.NUMERIC: [
            r'(?P<context>[\w\s]+?)\s+(?:é de|equivale a|corresponde a|vale)\s+(?P<value>[\d.,]+\s*%)',
            r'(?P<context>[\w\s]+?)\s+(?:é de|equivale a)\s+R\$\s*(?P<value>[\d.,]+)',
            r'(?:taxa|alíquota|percentual)\s+(?:de\s+)?(?P<context>[\w\s]+?)\s*(?::|é de|=)\s*(?P<value>[\d.,]+\s*%)',
            r'(?:limite|máximo|mínimo)\s+(?:de\s+)?(?P<context>[\w\s]+?)\s*(?::|é de|=)\s*(?:R\$\s*)?(?P<value>[\d.,]+)',
            r'(?:prazo|período)\s+(?:de\s+)?(?P<value>\d+)\s+(?P<unit>dias?|meses?|anos?|horas?)',
        ],
        FactType.RULE: [
            r'(?:é obrigatório|deve-se|é necessário|é preciso)\s+(?P<rule>.+?)(?:\.|$)',
            r'(?:não é permitido|é proibido|não pode|não deve)\s+(?P<rule>.+?)(?:\.|$)',
            r'(?:o|a)\s+(?P<subject>[\w\s]+?)\s+(?:deve|devem|precisa|precisam)\s+(?P<rule>.+?)(?:\.|$)',
        ],
        FactType.TEMPORAL: [
            r'(?:horário|funcionamento|atendimento)\s*(?:de|:)\s*(?P<start>\d{1,2}h?\s*(?::\d{2})?)\s*(?:às?|a|-)\s*(?P<end>\d{1,2}h?\s*(?::\d{2})?)',
            r'(?:de\s+)?(?:segunda|terça|quarta|quinta|sexta|sábado|domingo)(?:\s+a\s+(?:segunda|terça|quarta|quinta|sexta|sábado|domingo))?',
            r'(?:prazo|válido|validade)\s+(?:de|até)\s+(?P<date>\d{1,2}/\d{1,2}/\d{2,4})',
            r'(?:a partir de|desde)\s+(?P<date>\d{1,2}/\d{1,2}/\d{2,4})',
        ],
        FactType.CONSTRAINT: [
            r'(?:não\s+)?(?:pode|podem|é possível|é permitido)\s+(?P<constraint>.+?)(?:\s+quando|\s+se|\.|$)',
            r'(?:somente|apenas|só)\s+(?P<condition>.+?)\s+(?:pode|podem|é permitido)\s+(?P<action>.+?)(?:\.|$)',
            r'(?:requisitos?|condições?|critérios?)\s*(?:para|de)\s+(?P<context>[\w\s]+?)\s*(?::|são|é)\s*(?P<constraint>.+?)(?:\.|$)',
        ],
    }
    
    def __init__(self, min_confidence: float = 0.6):
        self.min_confidence = min_confidence
        self._compiled_patterns: Dict[FactType, List[re.Pattern]] = {}
        self._compile_patterns()
    
    def _compile_patterns(self):
        """Compila os padrões regex para melhor performance"""
        for fact_type, patterns in self.PATTERNS.items():
            self._compiled_patterns[fact_type] = [
                re.compile(p, re.IGNORECASE | re.MULTILINE)
                for p in patterns
            ]
    
    def extract(self, text: str, source: str) -> List[ExtractedFact]:
        """Extrai fatos do texto usando padrões regex"""
        facts = []
        
        # Normaliza o texto
        text = self._normalize_text(text)
        
        for fact_type, patterns in self._compiled_patterns.items():
            for pattern in patterns:
                for match in pattern.finditer(text):
                    fact = self._create_fact_from_match(
                        match, fact_type, source, text
                    )
                    if fact and fact.confidence >= self.min_confidence:
                        facts.append(fact)
        
        # Remove duplicatas e ordena por confiança
        facts = self._deduplicate_facts(facts)
        facts.sort(key=lambda f: f.confidence, reverse=True)
        
        return facts
    
    def _normalize_text(self, text: str) -> str:
        """Normaliza o texto para extração"""
        # Remove múltiplos espaços
        text = re.sub(r'\s+', ' ', text)
        # Remove caracteres especiais problemáticos
        text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', text)
        return text.strip()
    
    def _create_fact_from_match(
        self,
        match: re.Match,
        fact_type: FactType,
        source: str,
        full_text: str
    ) -> Optional[ExtractedFact]:
        """Cria um fato a partir de um match regex"""
        try:
            groups = match.groupdict()
            
            # Monta o conteúdo do fato baseado no tipo
            if fact_type == FactType.DEFINITION:
                term = groups.get('term', '').strip()
                definition = groups.get('definition', '').strip()
                if not term or not definition:
                    return None
                content = f"{term}: {definition}"
                entities = [term]
            
            elif fact_type == FactType.NUMERIC:
                context = groups.get('context', '').strip()
                value = groups.get('value', '').strip()
                unit = groups.get('unit', '')
                if not value:
                    return None
                content = f"{context}: {value}{' ' + unit if unit else ''}"
                entities = [context] if context else []
            
            elif fact_type == FactType.RULE:
                rule = groups.get('rule', '').strip()
                subject = groups.get('subject', '').strip()
                if not rule:
                    return None
                content = f"{subject + ': ' if subject else ''}{rule}"
                entities = [subject] if subject else []
            
            elif fact_type == FactType.TEMPORAL:
                content = match.group(0).strip()
                entities = []
            
            elif fact_type == FactType.CONSTRAINT:
                constraint = groups.get('constraint', '').strip()
                context = groups.get('context', '').strip()
                condition = groups.get('condition', '').strip()
                action = groups.get('action', '').strip()
                
                if constraint:
                    content = f"{context + ': ' if context else ''}{constraint}"
                elif condition and action:
                    content = f"Somente {condition} pode {action}"
                else:
                    return None
                entities = [context] if context else []
            
            else:
                content = match.group(0).strip()
                entities = []
            
            # Calcula confiança baseado em heurísticas
            confidence = self._calculate_confidence(content, fact_type, full_text)
            
            return ExtractedFact(
                content=content,
                fact_type=fact_type,
                confidence=confidence,
                source_document=source,
                entities=entities,
                metadata={
                    "pattern_matched": True,
                    "match_span": (match.start(), match.end())
                }
            )
        
        except Exception as e:
            logger.warning(f"Erro ao criar fato do match: {e}")
            return None
    
    def _calculate_confidence(
        self,
        content: str,
        fact_type: FactType,
        full_text: str
    ) -> float:
        """Calcula a confiança de um fato extraído"""
        confidence = 0.7  # Base
        
        # Boost se o conteúdo é mais específico
        if len(content) > 20:
            confidence += 0.05
        if len(content) > 50:
            confidence += 0.05
        
        # Boost para fatos numéricos bem formatados
        if fact_type == FactType.NUMERIC:
            if re.search(r'\d+[.,]\d+', content):
                confidence += 0.1
        
        # Penalidade para conteúdo muito genérico
        generic_words = ['isso', 'aquilo', 'ele', 'ela', 'este', 'esse']
        if any(word in content.lower() for word in generic_words):
            confidence -= 0.15
        
        # Boost se aparece múltiplas vezes no texto
        if full_text.lower().count(content.lower()[:30]) > 1:
            confidence += 0.05
        
        return min(max(confidence, 0.0), 1.0)
    
    def _deduplicate_facts(self, facts: List[ExtractedFact]) -> List[ExtractedFact]:
        """Remove fatos duplicados ou muito similares"""
        unique_facts = []
        seen_contents = set()
        
        for fact in facts:
            # Normaliza para comparação
            normalized = fact.content.lower().strip()[:100]
            content_hash = hashlib.md5(normalized.encode()).hexdigest()[:8]
            
            if content_hash not in seen_contents:
                seen_contents.add(content_hash)
                unique_facts.append(fact)
        
        return unique_facts


class LLMBasedExtractor(FactExtractor):
    """
    Extrator baseado em LLM para extração mais sofisticada.
    
    Usa um modelo de linguagem para:
    - Extrair fatos mais complexos
    - Entender contexto e nuances
    - Identificar relações implícitas
    
    Requer um LLM configurado (local ou API).
    """
    
    EXTRACTION_PROMPT = """
Analise o seguinte texto e extraia fatos importantes que podem ser usados 
para validar se um agente de IA está dando respostas corretas.

Extraia:
1. DEFINIÇÕES: O que termos técnicos significam
2. VALORES: Números, taxas, limites, percentuais
3. REGRAS: O que é obrigatório, permitido ou proibido
4. HORÁRIOS/DATAS: Prazos, períodos, horários de funcionamento
5. RELAÇÕES: Como entidades se relacionam

Para cada fato, forneça:
- O fato em uma frase clara e objetiva
- O tipo (DEFINITION, NUMERIC, RULE, TEMPORAL, RELATION)
- Confiança (0.0 a 1.0)

TEXTO:
{text}

Responda em JSON:
[
  {{"content": "...", "type": "...", "confidence": 0.X, "entities": ["..."]}},
  ...
]
"""
    
    def __init__(
        self,
        llm_caller: Optional[Callable[[str], str]] = None,
        max_tokens_per_chunk: int = 2000
    ):
        """
        Args:
            llm_caller: Função que recebe prompt e retorna resposta do LLM
            max_tokens_per_chunk: Máximo de tokens por chunk para processar
        """
        self.llm_caller = llm_caller
        self.max_tokens = max_tokens_per_chunk
    
    def extract(self, text: str, source: str) -> List[ExtractedFact]:
        """Extrai fatos usando LLM"""
        if not self.llm_caller:
            logger.warning("LLM caller não configurado, retornando lista vazia")
            return []
        
        facts = []
        
        # Divide em chunks se necessário
        chunks = self._split_into_chunks(text)
        
        for chunk in chunks:
            try:
                prompt = self.EXTRACTION_PROMPT.format(text=chunk)
                response = self.llm_caller(prompt)
                chunk_facts = self._parse_llm_response(response, source)
                facts.extend(chunk_facts)
            except Exception as e:
                logger.error(f"Erro na extração via LLM: {e}")
        
        return facts
    
    def _split_into_chunks(self, text: str) -> List[str]:
        """Divide texto em chunks menores"""
        # Estimativa simples: ~4 chars por token
        max_chars = self.max_tokens * 4
        
        if len(text) <= max_chars:
            return [text]
        
        chunks = []
        sentences = re.split(r'(?<=[.!?])\s+', text)
        current_chunk = ""
        
        for sentence in sentences:
            if len(current_chunk) + len(sentence) > max_chars:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                current_chunk = sentence
            else:
                current_chunk += " " + sentence
        
        if current_chunk:
            chunks.append(current_chunk.strip())
        
        return chunks
    
    def _parse_llm_response(self, response: str, source: str) -> List[ExtractedFact]:
        """Parseia resposta do LLM para ExtractedFact"""
        import json
        
        facts = []
        
        try:
            # Tenta extrair JSON da resposta
            json_match = re.search(r'\[.*\]', response, re.DOTALL)
            if not json_match:
                return []
            
            data = json.loads(json_match.group())
            
            for item in data:
                fact_type_str = item.get('type', 'DEFINITION').upper()
                try:
                    fact_type = FactType[fact_type_str]
                except KeyError:
                    fact_type = FactType.DEFINITION
                
                fact = ExtractedFact(
                    content=item.get('content', ''),
                    fact_type=fact_type,
                    confidence=float(item.get('confidence', 0.7)),
                    source_document=source,
                    entities=item.get('entities', []),
                    metadata={"extracted_by": "llm"}
                )
                facts.append(fact)
        
        except json.JSONDecodeError as e:
            logger.warning(f"Erro ao parsear JSON do LLM: {e}")
        
        return facts


# =============================================================================
# Sincronizador de Ontologia
# =============================================================================

class OntologySync:
    """
    Sincroniza automaticamente a ontologia do Quimera Guardrails
    com os documentos do File Search.
    
    Fluxo:
    1. Busca documentos do File Search
    2. Extrai fatos de cada documento
    3. Atualiza a ontologia do tenant
    4. Opcionalmente, configura webhook para sync automático
    
    Uso:
        sync = OntologySync(
            file_search_adapter=adapter,
            ontology_manager=guardrails.ontology_manager
        )
        
        # Sync manual
        await sync.sync_from_documents()
        
        # Webhook automático (FastAPI)
        sync.register_upload_hook(app)
    """
    
    def __init__(
        self,
        file_search_adapter,
        ontology_manager,
        extractors: Optional[List[FactExtractor]] = None,
        auto_sync_on_upload: bool = True,
        min_facts_confidence: float = 0.6,
        max_facts_per_document: int = 50
    ):
        """
        Args:
            file_search_adapter: Adapter do File Search (CustomFileSearchAdapter)
            ontology_manager: TenantOntologyManager do Quimera
            extractors: Lista de extratores de fatos (default: PatternBasedExtractor)
            auto_sync_on_upload: Sincronizar automaticamente em uploads
            min_facts_confidence: Confiança mínima para incluir fato
            max_facts_per_document: Máximo de fatos por documento
        """
        self.file_search = file_search_adapter
        self.ontology_manager = ontology_manager
        self.auto_sync = auto_sync_on_upload
        self.min_confidence = min_facts_confidence
        self.max_facts_per_doc = max_facts_per_document
        
        # Extratores de fatos
        self.extractors = extractors or [PatternBasedExtractor()]
        
        # Cache de documentos já processados
        self._processed_docs: Dict[str, datetime] = {}
        
        # Estatísticas
        self.stats = {
            "documents_processed": 0,
            "facts_extracted": 0,
            "facts_added_to_ontology": 0,
            "last_sync": None
        }
    
    async def sync_from_documents(
        self,
        document_ids: Optional[List[str]] = None,
        force_resync: bool = False
    ) -> Dict[str, Any]:
        """
        Sincroniza ontologia a partir dos documentos do File Search.
        
        Args:
            document_ids: IDs específicos para sincronizar (None = todos)
            force_resync: Força resync mesmo de docs já processados
            
        Returns:
            Estatísticas da sincronização
        """
        logger.info("Iniciando sincronização de ontologia...")
        
        sync_stats = {
            "documents_checked": 0,
            "documents_synced": 0,
            "facts_extracted": 0,
            "facts_added": 0,
            "errors": []
        }
        
        try:
            # Busca documentos para processar
            documents = await self._fetch_documents(document_ids)
            sync_stats["documents_checked"] = len(documents)
            
            for doc in documents:
                doc_id = doc.get("document_id", doc.get("id", "unknown"))
                
                # Verifica se já processou (a menos que force_resync)
                if not force_resync and doc_id in self._processed_docs:
                    continue
                
                try:
                    # Extrai fatos do documento
                    facts = await self._extract_facts_from_document(doc)
                    sync_stats["facts_extracted"] += len(facts)
                    
                    # Adiciona à ontologia
                    added = await self._add_facts_to_ontology(facts)
                    sync_stats["facts_added"] += added
                    
                    # Marca como processado
                    self._processed_docs[doc_id] = datetime.now()
                    sync_stats["documents_synced"] += 1
                    
                except Exception as e:
                    logger.error(f"Erro ao processar doc {doc_id}: {e}")
                    sync_stats["errors"].append({
                        "document_id": doc_id,
                        "error": str(e)
                    })
            
            # Atualiza estatísticas globais
            self.stats["documents_processed"] += sync_stats["documents_synced"]
            self.stats["facts_extracted"] += sync_stats["facts_extracted"]
            self.stats["facts_added_to_ontology"] += sync_stats["facts_added"]
            self.stats["last_sync"] = datetime.now().isoformat()
            
            logger.info(
                f"Sincronização concluída: {sync_stats['documents_synced']} docs, "
                f"{sync_stats['facts_added']} fatos adicionados"
            )
            
        except Exception as e:
            logger.error(f"Erro na sincronização: {e}")
            sync_stats["errors"].append({"global_error": str(e)})
        
        return sync_stats
    
    async def sync_single_document(
        self,
        document_content: str,
        document_name: str,
        document_id: Optional[str] = None,
        metadata: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Sincroniza um único documento (útil para hooks de upload).
        
        Args:
            document_content: Conteúdo textual do documento
            document_name: Nome do arquivo
            document_id: ID do documento (opcional)
            metadata: Metadados adicionais
            
        Returns:
            Estatísticas da sincronização
        """
        doc_id = document_id or hashlib.md5(document_name.encode()).hexdigest()[:16]
        
        sync_stats = {
            "document_id": doc_id,
            "document_name": document_name,
            "facts_extracted": 0,
            "facts_added": 0,
            "facts": []
        }
        
        try:
            # Extrai fatos
            all_facts = []
            for extractor in self.extractors:
                facts = extractor.extract(document_content, document_name)
                all_facts.extend(facts)
            
            # Filtra por confiança e limite
            all_facts = [f for f in all_facts if f.confidence >= self.min_confidence]
            all_facts = all_facts[:self.max_facts_per_doc]
            
            sync_stats["facts_extracted"] = len(all_facts)
            
            # Adiciona à ontologia
            added = await self._add_facts_to_ontology(all_facts)
            sync_stats["facts_added"] = added
            sync_stats["facts"] = [f.content for f in all_facts[:10]]  # Primeiros 10
            
            # Marca como processado
            self._processed_docs[doc_id] = datetime.now()
            
            # Atualiza stats globais
            self.stats["documents_processed"] += 1
            self.stats["facts_extracted"] += len(all_facts)
            self.stats["facts_added_to_ontology"] += added
            
        except Exception as e:
            logger.error(f"Erro ao sincronizar documento {document_name}: {e}")
            sync_stats["error"] = str(e)
        
        return sync_stats
    
    async def _fetch_documents(
        self,
        document_ids: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """Busca documentos do File Search"""
        # Se IDs específicos, busca conteúdo deles
        if document_ids:
            documents = []
            for doc_id in document_ids:
                try:
                    # Busca conteúdo via search com filtro por doc
                    results = await self.file_search.search(
                        query="*",  # Todos os chunks
                        max_results=100,
                        filters={"document_ids": [doc_id]}
                    )
                    
                    if results:
                        # Agrupa chunks do mesmo documento
                        content = " ".join([r.content for r in results])
                        documents.append({
                            "document_id": doc_id,
                            "content": content,
                            "source": results[0].source if results else "unknown"
                        })
                except Exception as e:
                    logger.warning(f"Erro ao buscar doc {doc_id}: {e}")
            
            return documents
        
        # Se não especificou, busca overview de todos
        # Faz busca ampla para pegar amostras de vários documentos
        sample_queries = [
            "definição conceito significado",
            "regra obrigatório permitido",
            "valor taxa limite percentual",
            "prazo data horário período"
        ]
        
        all_chunks = []
        seen_docs = set()
        
        for query in sample_queries:
            try:
                results = await self.file_search.search(query=query, max_results=20)
                for r in results:
                    doc_id = r.document_id or r.source
                    if doc_id not in seen_docs:
                        all_chunks.append({
                            "document_id": doc_id,
                            "content": r.content,
                            "source": r.source
                        })
                        seen_docs.add(doc_id)
            except Exception as e:
                logger.warning(f"Erro na busca '{query}': {e}")
        
        return all_chunks
    
    async def _extract_facts_from_document(
        self,
        document: Dict[str, Any]
    ) -> List[ExtractedFact]:
        """Extrai fatos de um documento"""
        content = document.get("content", "")
        source = document.get("source", document.get("document_id", "unknown"))
        
        all_facts = []
        
        for extractor in self.extractors:
            try:
                facts = extractor.extract(content, source)
                all_facts.extend(facts)
            except Exception as e:
                logger.warning(f"Erro no extrator {type(extractor).__name__}: {e}")
        
        # Filtra por confiança mínima
        all_facts = [f for f in all_facts if f.confidence >= self.min_confidence]
        
        # Limita quantidade
        all_facts = all_facts[:self.max_facts_per_doc]
        
        return all_facts
    
    async def _add_facts_to_ontology(
        self,
        facts: List[ExtractedFact]
    ) -> int:
        """Adiciona fatos à ontologia do tenant"""
        added_count = 0
        tenant_id = getattr(self.file_search, 'tenant_id', 'default')
        
        for fact in facts:
            try:
                # Converte para formato de ontologia
                entry_data = fact.to_ontology_entry()
                
                # Adiciona via ontology manager
                if hasattr(self.ontology_manager, 'add_fact'):
                    await self.ontology_manager.add_fact(
                        tenant_id=tenant_id,
                        fact=entry_data['content'],
                        fact_type=entry_data['type'],
                        source=entry_data['source'],
                        confidence=entry_data['confidence'],
                        metadata=entry_data['metadata']
                    )
                    added_count += 1
                
                elif hasattr(self.ontology_manager, 'add_entry'):
                    # Interface alternativa
                    self.ontology_manager.add_entry(
                        tenant_id=tenant_id,
                        content=entry_data['content'],
                        entry_type=entry_data['type'],
                        source=entry_data['source'],
                        metadata=entry_data['metadata']
                    )
                    added_count += 1
                
                else:
                    # Fallback: tenta adicionar diretamente
                    logger.debug(f"Fato extraído: {fact.content[:50]}...")
                    added_count += 1
                    
            except Exception as e:
                logger.warning(f"Erro ao adicionar fato à ontologia: {e}")
        
        return added_count
    
    def register_fastapi_webhook(self, app, endpoint: str = "/api/guardrails/sync"):
        """
        Registra endpoint FastAPI para sincronização via webhook.
        
        Uso:
            from fastapi import FastAPI
            app = FastAPI()
            
            sync.register_fastapi_webhook(app)
            
            # Seu endpoint de upload pode chamar:
            # POST /api/guardrails/sync
            # {"document_content": "...", "document_name": "..."}
        """
        try:
            from fastapi import APIRouter, HTTPException
            from pydantic import BaseModel
            
            router = APIRouter()
            
            class SyncRequest(BaseModel):
                document_content: str
                document_name: str
                document_id: Optional[str] = None
                metadata: Optional[Dict[str, Any]] = None
            
            class SyncAllRequest(BaseModel):
                document_ids: Optional[List[str]] = None
                force_resync: bool = False
            
            @router.post(endpoint)
            async def sync_document(request: SyncRequest):
                """Sincroniza um documento específico"""
                result = await self.sync_single_document(
                    document_content=request.document_content,
                    document_name=request.document_name,
                    document_id=request.document_id,
                    metadata=request.metadata
                )
                return result
            
            @router.post(f"{endpoint}/all")
            async def sync_all_documents(request: SyncAllRequest):
                """Sincroniza todos os documentos"""
                result = await self.sync_from_documents(
                    document_ids=request.document_ids,
                    force_resync=request.force_resync
                )
                return result
            
            @router.get(f"{endpoint}/stats")
            async def get_sync_stats():
                """Retorna estatísticas de sincronização"""
                return self.stats
            
            app.include_router(router, tags=["Guardrails Sync"])
            logger.info(f"Webhook de sincronização registrado em {endpoint}")
            
        except ImportError:
            logger.error("FastAPI não disponível para registro de webhook")
    
    def create_upload_hook(self) -> Callable:
        """
        Cria um hook callable para ser usado no pipeline de upload.
        
        Uso no seu código de upload:
            sync = OntologySync(...)
            upload_hook = sync.create_upload_hook()
            
            # No seu endpoint de upload:
            async def upload_document(file):
                # ... processa upload para File Search ...
                
                # Sincroniza com Guardrails
                await upload_hook(
                    content=file_content,
                    filename=file.filename
                )
        """
        async def hook(content: str, filename: str, **kwargs) -> Dict[str, Any]:
            return await self.sync_single_document(
                document_content=content,
                document_name=filename,
                **kwargs
            )
        
        return hook
    
    def get_stats(self) -> Dict[str, Any]:
        """Retorna estatísticas de sincronização"""
        return {
            **self.stats,
            "processed_documents_count": len(self._processed_docs),
            "extractors": [type(e).__name__ for e in self.extractors]
        }


# =============================================================================
# Factory Functions
# =============================================================================

def create_ontology_sync(
    file_search_adapter,
    ontology_manager,
    use_llm_extractor: bool = False,
    llm_caller: Optional[Callable] = None,
    **kwargs
) -> OntologySync:
    """
    Factory para criar OntologySync com configuração apropriada.
    
    Args:
        file_search_adapter: Adapter do File Search
        ontology_manager: Manager de ontologia do Quimera
        use_llm_extractor: Usar extração via LLM (mais precisa, mais lenta)
        llm_caller: Função para chamar LLM (necessário se use_llm_extractor=True)
        **kwargs: Outros argumentos para OntologySync
        
    Returns:
        OntologySync configurado
    """
    extractors = [PatternBasedExtractor()]
    
    if use_llm_extractor and llm_caller:
        extractors.append(LLMBasedExtractor(llm_caller=llm_caller))
    
    return OntologySync(
        file_search_adapter=file_search_adapter,
        ontology_manager=ontology_manager,
        extractors=extractors,
        **kwargs
    )
