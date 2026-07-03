from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field

class Context(BaseModel):
    """Representa uma fonte de informação / documento de apoio recuperado para a resposta."""
    doc_id: str = Field(..., description="Identificador único da fonte de contexto")
    text: str = Field(..., description="Texto do conteúdo recuperado")
    title: Optional[str] = Field(None, description="Título do documento")
    source: Optional[str] = Field(None, description="Origem da informação (ex: link, tabela)")
    license: Optional[str] = Field(None, description="Licença de uso do texto")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Metadados arbitrários adicionais do contexto (ex: imagens)")

class EvidenceSpan(BaseModel):
    """Representa um intervalo exato de caracteres dentro de um contexto específico que serve de evidência."""
    doc_id: str = Field(..., description="ID do contexto de origem")
    start: int = Field(..., description="Índice de caractere inicial do span no contexto")
    end: int = Field(..., description="Índice de caractere final (exclusivo) do span no contexto")

class GoldClaim(BaseModel):
    """Representa um claim anotado manualmente (gold) para testes e avaliações."""
    claim_id: str = Field(..., description="ID único do claim")
    text: str = Field(..., description="Texto literal da afirmação (claim)")
    label: str = Field(..., description="Rótulo da anotação (ex: supported, unsupported, contradicted)")
    evidence: List[EvidenceSpan] = Field(default_factory=list, description="Lista de spans de evidência que suportam este claim")

class GoldSchema(BaseModel):
    """Representa o conjunto de gabaritos (gold labels) associados a um Sample."""
    claims: List[GoldClaim] = Field(default_factory=list, description="Claims anotados e suas classificações")
    unsupported_spans: List[Dict[str, Any]] = Field(default_factory=list, description="Trechos da resposta que não possuem suporte de contexto")

class Sample(BaseModel):
    """Estrutura principal de um exemplo de entrada para o pipeline de avaliação RAG."""
    id: str = Field(..., description="ID único do exemplo")
    lang: str = Field(..., description="Código do idioma (ex: 'pt-BR', 'en')")
    question: str = Field(..., description="Pergunta feita pelo usuário")
    contexts: List[Context] = Field(..., description="Lista de contextos de suporte associados")
    answer: str = Field(..., description="Resposta gerada pelo sistema RAG")
    reference_answer: Optional[str] = Field(None, description="Resposta de referência ideal (ground truth)")
    gold: Optional[GoldSchema] = Field(None, description="Dados padrão-ouro de anotação (opcional)")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Metadados arbitrários adicionais")

class EvalResult(BaseModel):
    """Resultado final gerado pelo pipeline de avaliação para um Sample."""
    id: str = Field(..., description="ID do exemplo avaliado")
    lang: str = Field(..., description="Idioma do exemplo")
    scores: Dict[str, float] = Field(..., description="Dicionário de métricas e suas respectivas notas")
    claims: List[Dict[str, Any]] = Field(default_factory=list, description="Lista de claims analisados pelo avaliador")
    cost: Optional[Dict[str, Any]] = Field(None, description="Metadados de custo e latência de processamento")
    warnings: List[str] = Field(default_factory=list, description="Lista de alertas gerados durante o processo")
