import pytest
from typing import List, Dict, Any, Optional

from groundcite import Sample, Context
from groundcite.backends import BaseBackend, LexicalBackend, HybridBackend

class MockSemanticBackend(BaseBackend):
    """Backend Mock semântico para contar invocações e validar o fallback."""
    def __init__(self, return_label: str = "supported", return_confidence: float = 0.90):
        self.return_label = return_label
        self.return_confidence = return_confidence
        self.call_count = 0
        
    def predict_support(
        self, 
        claim: str, 
        contexts: List[str], 
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        self.call_count += 1
        return {
            "label": self.return_label,
            "confidence": self.return_confidence,
            "evidence_doc_idx": 0,
            "evidence_span": (0, len(contexts[0])) if contexts else None
        }

def test_hybrid_fast_path_exact_match():
    """Garante que correspondências idênticas (exact match) usem o fast-path sem chamar o backend primário."""
    primary = MockSemanticBackend()
    # threshold de 0.98. O LexicalBackend dará confiança 1.0 para match exato.
    hybrid = HybridBackend(primary_backend=primary, exact_match_threshold=0.95)
    
    claim = "Dom Casmurro foi escrito por Machado de Assis."
    contexts = ["Dom Casmurro foi escrito por Machado de Assis."]
    
    res = hybrid.predict_support(claim, contexts)
    
    # O resultado deve vir do fast-path
    assert res["label"] == "supported"
    assert res["confidence"] == 1.0
    assert res["optimized_by"] == "hybrid_fast_path_exact_match"
    # O backend primário NÃO deve ter sido invocado!
    assert primary.call_count == 0

def test_hybrid_fast_path_contradiction():
    """Garante que contradições numéricas usem o fast-path sem chamar o backend primário."""
    primary = MockSemanticBackend(return_label="supported")
    hybrid = HybridBackend(primary_backend=primary, fast_path_contradiction=True)
    
    claim = "O Rio Amazonas possui 7.500 quilômetros de extensão."
    contexts = ["O Rio Amazonas possui cerca de 6.992 quilômetros de extensão."]
    
    res = hybrid.predict_support(claim, contexts)
    
    assert res["label"] == "contradicted"
    assert res["optimized_by"] == "hybrid_fast_path_contradiction"
    # O backend primário NÃO deve ter sido invocado!
    assert primary.call_count == 0

def test_hybrid_fallback_to_primary():
    """Garante que casos normais (sutis ou com menor confiança) invoquem o backend primário semântico."""
    primary = MockSemanticBackend(return_label="supported_semantic", return_confidence=0.88)
    # Threshold de 0.98. O match parcial dará confiança menor (ex: 0.85).
    hybrid = HybridBackend(primary_backend=primary, exact_match_threshold=0.98)
    
    # Texto parcialmente diferente que não atinge match exato
    claim = "Machado de Assis fundou a Academia de Letras."
    contexts = ["Machado de Assis foi um dos fundadores da Academia Brasileira de Letras."]
    
    res = hybrid.predict_support(claim, contexts)
    
    # O resultado deve vir do fallback semântico
    assert res["label"] == "supported_semantic"
    assert res["confidence"] == 0.88
    assert res["optimized_by"] == "fallback_semantic_evaluation"
    # O backend primário DEVE ter sido invocado exatamente 1 vez!
    assert primary.call_count == 1
