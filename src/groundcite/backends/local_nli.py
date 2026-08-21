from typing import List, Dict, Any, Optional

from groundcite.backends.base import BaseBackend

class LocalNLIBackend(BaseBackend):
    """
    Backend de inferência local baseado em modelos de Natural Language Inference (NLI) multilíngues.
    Carrega sob demanda as bibliotecas pesadas (torch e transformers) para manter o core leve.
    """
    
    def __init__(self, model_name: str = "MoritzLaurer/mDeBERTa-v3-base-xnli-multilingual-nli-2mil7"):
        """
        Args:
            model_name: Nome do modelo de NLI no Hugging Face Hub.
        """
        self.model_name = model_name
        self._tokenizer = None
        self._model = None
        self._device = None
        
    def _lazy_init(self):
        """Inicializa as dependências do torch/transformers sob demanda e com tratamento amigável de erros."""
        if self._tokenizer is not None and self._model is not None:
            return
            
        try:
            import torch
            from transformers import AutoTokenizer, AutoModelForSequenceClassification
        except ImportError:
            raise ImportError(
                "As dependências para execução de modelos locais NLI não foram encontradas.\n"
                "Por favor, instale-as executando: pip install \"groundcite[local]\""
            )
            
        self._device = "cuda" if torch.cuda.is_available() else "cpu"
        self._tokenizer = AutoTokenizer.from_pretrained(self.model_name)
        self._model = AutoModelForSequenceClassification.from_pretrained(self.model_name).to(self._device)
        self._model.eval()
        
    def predict_support(
        self, 
        claim: str, 
        contexts: List[str], 
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        self._lazy_init()
        
        # Importação local segura
        import torch
        
        if not contexts:
            return {"label": "unsupported", "confidence": 0.0, "evidence_doc_idx": None, "evidence_span": None}
            
        # Para NLI local, concatenamos todos os contextos para servir de premissa principal,
        # ou avaliamos contra cada contexto individualmente e pegamos o de maior suporte (melhor para atribuição).
        # Avaliar individualmente permite identificar EXATAMENTE qual contexto (evidence_doc_idx) deu suporte ao claim!
        best_label = "unsupported"
        best_confidence = 0.0
        best_idx = None
        
        # Mapeamento padrão dos índices de saída de modelos de NLI (XNLI):
        # 0: entailment (suporte), 1: neutral (neutro), 2: contradiction (contradição)
        # Atenção: Dependendo do modelo, essa ordem pode mudar, mas o mDeBERTa/XLM-RoBERTa XNLI usam o padrão XNLI:
        # Index 0: Entailment, Index 1: Neutral, Index 2: Contradiction
        
        for idx, ctx in enumerate(contexts):
            # Tokenização do par de sentenças (Premissa, Hipótese)
            inputs = self._tokenizer(
                ctx, 
                claim, 
                truncation=True, 
                max_length=512, 
                return_tensors="pt"
            ).to(self._device)
            
            with torch.no_grad():
                outputs = self._model(**inputs)
                probs = torch.softmax(outputs.logits, dim=-1)[0]
                
            probs_list = probs.cpu().tolist()
            
            entail_prob = probs_list[0]
            neutral_prob = probs_list[1]
            contradict_prob = probs_list[2]
            
            # Encontra a probabilidade máxima para determinar a classificação deste contexto
            max_prob = max(entail_prob, neutral_prob, contradict_prob)
            
            if entail_prob == max_prob and entail_prob > best_confidence:
                best_confidence = entail_prob
                best_label = "supported"
                best_idx = idx
            elif contradict_prob == max_prob and contradict_prob > best_confidence:
                best_confidence = contradict_prob
                best_label = "contradicted"
                best_idx = idx
            elif neutral_prob == max_prob and neutral_prob > best_confidence:
                # Se neutro for o maior, mas já tivermos um suporte parcial de outro contexto, preservamos
                if best_label != "supported":
                    best_confidence = neutral_prob
                    best_label = "unsupported"
                    best_idx = idx
                    
        # Se nenhum contexto deu suporte ou contradição clara, retorna o índice de maior neutralidade
        if best_idx is None:
            best_idx = 0
            
        # Estimamos o span de evidência localmente usando a heurística de alinhamento fuzzy do rapidfuzz
        # (já que o modelo NLI sequencial não emite spans de caracteres nativamente)
        from rapidfuzz import fuzz
        align = fuzz.partial_ratio_alignment(claim.lower(), contexts[best_idx].lower())
        evidence_span = (align.dest_start, align.dest_end) if align.score > 40.0 else None
        
        return {
            "label": best_label,
            "confidence": float(best_confidence),
            "evidence_doc_idx": best_idx,
            "evidence_span": evidence_span
        }
