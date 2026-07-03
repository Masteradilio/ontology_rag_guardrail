import json
import pytest
from pydantic import ValidationError

from groundcite.schema import (
    Context,
    EvidenceSpan,
    GoldClaim,
    GoldSchema,
    Sample,
    EvalResult,
)

def test_context_validation():
    """Valida a instanciação correta do schema Context."""
    # Contexto válido completo
    ctx = Context(
        doc_id="doc_123",
        text="Este é um texto de exemplo para fins de testes.",
        title="Título do Doc",
        source="http://exemplo.com",
        license="MIT"
    )
    assert ctx.doc_id == "doc_123"
    assert ctx.text == "Este é um texto de exemplo para fins de testes."
    assert ctx.title == "Título do Doc"
    assert ctx.source == "http://exemplo.com"
    assert ctx.license == "MIT"

    # Contexto válido mínimo
    ctx_min = Context(
        doc_id="doc_456",
        text="Texto mínimo apenas."
    )
    assert ctx_min.title is None
    assert ctx_min.source is None

    # Erro por falta de campo obrigatório (text)
    with pytest.raises(ValidationError):
        Context(doc_id="doc_789")

def test_evidence_span_validation():
    """Valida a instanciação correta do schema EvidenceSpan."""
    span = EvidenceSpan(doc_id="doc_1", start=10, end=20)
    assert span.doc_id == "doc_1"
    assert span.start == 10
    assert span.end == 20

    # Erros de tipo de dados
    with pytest.raises(ValidationError):
        EvidenceSpan(doc_id="doc_1", start="dez", end=20)

def test_sample_validation_with_optionals():
    """Garante que campos opcionais de Sample funcionem perfeitamente sem erros."""
    # Mínimo de campos para instanciar um Sample
    sample = Sample(
        id="pt_001",
        lang="pt-BR",
        question="Qual o menor país do mundo?",
        contexts=[Context(doc_id="doc_1", text="O Vaticano é o menor país.")],
        answer="Vaticano."
    )
    assert sample.id == "pt_001"
    assert sample.reference_answer is None
    assert sample.gold is None
    assert sample.metadata is None

def test_sample_validation_with_gold_and_metadata():
    """Valida o schema Sample completo com dados gold e metadados."""
    gold_data = GoldSchema(
        claims=[
            GoldClaim(
                claim_id="c1",
                text="O Vaticano é o menor país.",
                label="supported",
                evidence=[EvidenceSpan(doc_id="doc_1", start=0, end=26)]
            )
        ],
        unsupported_spans=[]
    )
    
    sample = Sample(
        id="pt_001",
        lang="pt-BR",
        question="Qual o menor país?",
        contexts=[Context(doc_id="doc_1", text="O Vaticano é o menor país do mundo.")],
        answer="O Vaticano é o menor país.",
        reference_answer="Vaticano",
        gold=gold_data,
        metadata={"split": "test", "priority": 1}
    )
    
    assert sample.gold is not None
    assert sample.gold.claims[0].claim_id == "c1"
    assert sample.gold.claims[0].evidence[0].start == 0
    assert sample.metadata["split"] == "test"

def test_invalid_sample_data():
    """Valida que tipos incorretos causam ValidationError no Sample."""
    # Contexts com dados errados (não é uma lista)
    with pytest.raises(ValidationError):
        Sample(
            id="pt_001",
            lang="pt-BR",
            question="Pergunta?",
            contexts="Este contexto não é uma lista",
            answer="Resposta."
        )

def test_load_sample_from_json():
    """Valida se o carregamento a partir de uma string JSON (como lido de JSONL) funciona."""
    json_str = """
    {
        "id": "pt_machado_001",
        "lang": "pt-BR",
        "question": "Quem fundou a ABL?",
        "contexts": [
            {
                "doc_id": "doc_001",
                "text": "Machado de Assis fundou a ABL."
            }
        ],
        "answer": "Machado fundou."
    }
    """
    sample = Sample.model_validate_json(json_str)
    assert sample.id == "pt_machado_001"
    assert len(sample.contexts) == 1
    assert sample.contexts[0].doc_id == "doc_001"
