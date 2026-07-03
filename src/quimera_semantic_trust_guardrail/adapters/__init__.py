# -*- coding: utf-8 -*-
"""
Adapters para integração com bases de conhecimento externas.

Adapters Disponíveis:
- CustomFileSearchAdapter: Para sistema File Search próprio (PostgreSQL + pgvector)
- OntologySync: Sincronização automática de ontologias a partir dos documentos
- GoogleFileSearchAdapter: Para Google File Search (Gemini API) - LEGADO
- SimpleKnowledgeAdapter: Para testes/mock com fatos em memória
"""

# Adapter principal - Sistema File Search customizado (EAO)
from .custom_file_search import (
    KnowledgeAdapter,
    KnowledgeFact,
    CustomFileSearchAdapter,
    SimpleKnowledgeAdapter,
    FactCache,
    create_file_search_adapter,
    create_adapter_from_env,
)

# Sincronização automática de ontologias
from .ontology_sync import (
    OntologySync,
    FactExtractor,
    PatternBasedExtractor,
    LLMBasedExtractor,
    ExtractedFact,
    FactType,
    DomainTerminology,
    create_ontology_sync,
)

# Adapter legado - Google File Search (opcional)
try:
    from .google_file_search import (
        GoogleFileSearchAdapter,
        create_knowledge_adapter,
    )
    HAS_GOOGLE_ADAPTER = True
except ImportError:
    HAS_GOOGLE_ADAPTER = False
    GoogleFileSearchAdapter = None
    create_knowledge_adapter = None

__all__ = [
    # Interfaces
    "KnowledgeAdapter",
    "KnowledgeFact",
    "FactCache",
    # Adapter principal (Custom File Search)
    "CustomFileSearchAdapter",
    "SimpleKnowledgeAdapter",
    "create_file_search_adapter",
    "create_adapter_from_env",
    # Sincronização de Ontologia
    "OntologySync",
    "FactExtractor",
    "PatternBasedExtractor",
    "LLMBasedExtractor",
    "ExtractedFact",
    "FactType",
    "DomainTerminology",
    "create_ontology_sync",
    # Adapter legado (Google)
    "GoogleFileSearchAdapter",
    "create_knowledge_adapter",
    "HAS_GOOGLE_ADAPTER",
]
