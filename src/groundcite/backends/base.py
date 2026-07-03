from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional

class BaseBackend(ABC):
    """Classe base abstrata para todos os backends de inferência do GroundCite."""
    
    @abstractmethod
    def predict_support(
        self, 
        claim: str, 
        contexts: List[str], 
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Avalia o nível de suporte lógico de um claim individual contra uma lista de contextos.
        
        Args:
            claim: Afirmação individual a ser avaliada.
            contexts: Lista de textos contendo os contextos/evidências de suporte.
            metadata: Metadados adicionais contendo informações do sample e contextos (ex: imagens).
            
        Returns:
            Dicionário contendo:
                - "label": "supported", "unsupported" ou "contradicted"
                - "confidence": float de 0.0 a 1.0
                - "evidence_doc_idx": int (índice do contexto que serviu de suporte) ou None
                - "evidence_span": tuple (start, end) de caracteres no contexto de suporte ou None
        """
        pass
