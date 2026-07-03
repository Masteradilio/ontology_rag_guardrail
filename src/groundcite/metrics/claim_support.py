from typing import List, Dict, Any, Tuple
from groundcite.schema import Sample
from groundcite.backends.base import BaseBackend

class ClaimSupport:
    """
    Métrica que avalia o nível de suporte (groundedness) de cada afirmação (claim) individual 
    da resposta RAG contra os contextos fornecidos.
    """
    
    def __init__(self, name: str = "claim_support"):
        self.name = name
        
    def evaluate(self, sample: Sample, backend: BaseBackend, claims: List[str]) -> Tuple[Dict[str, float], List[Dict[str, Any]]]:
        """
        Executa a avaliação de claims para um Sample específico.
        
        Args:
            sample: O exemplo contendo os dados originais do RAG.
            backend: O backend de inferência (Lexical ou NLI) a ser utilizado.
            claims: Lista de claims decompostos da resposta do Sample.
            
        Returns:
            Um par contendo:
                - Dicionário de scores calculados.
                - Lista de dicionários com a análise detalhada de cada claim.
        """
        if not claims:
            # Se a resposta for vazia ou sem claims, o score é 0.0 por definição
            return {f"{self.name}_rate": 0.0}, []
            
        ctx_texts = [ctx.text for ctx in sample.contexts]
        analyzed_claims: List[Dict[str, Any]] = []
        supported_count = 0
        contradicted_count = 0
        unsupported_count = 0
        
        # Agrupa os metadados do sample e dos contextos para o backend usar no cálculo multimodal
        sample_meta = {
            "sample_metadata": getattr(sample, "metadata", None),
            "contexts_metadata": [getattr(ctx, "metadata", None) for ctx in sample.contexts]
        }
        
        for claim_text in claims:
            prediction = backend.predict_support(claim_text, ctx_texts, metadata=sample_meta)
            
            label = prediction["label"]
            confidence = prediction["confidence"]
            doc_idx = prediction["evidence_doc_idx"]
            char_span = prediction["evidence_span"]
            
            # Coleta o doc_id correspondente
            evidence_doc_id = sample.contexts[doc_idx].doc_id if doc_idx is not None else None
            
            analyzed_claims.append({
                "text": claim_text,
                "pred_label": label,
                "confidence": confidence,
                "evidence_doc_id": evidence_doc_id,
                "evidence_char_span": char_span,
                "usd_saved": prediction.get("usd_saved", 0.0)
            })
            
            if label == "supported":
                supported_count += 1
            elif label == "contradicted":
                contradicted_count += 1
            else:
                unsupported_count += 1
                
        # Taxa de suporte: fração de claims gerados que são apoiados pelas evidências
        support_rate = supported_count / len(claims)
        
        scores: Dict[str, float] = {
            f"{self.name}_rate": support_rate,
            f"{self.name}_supported_count": float(supported_count),
            f"{self.name}_contradicted_count": float(contradicted_count),
            f"{self.name}_unsupported_count": float(unsupported_count),
        }
        
        # Se houver dados padrão-ouro (gold labels), calcula Precision, Recall e F1
        if sample.gold and sample.gold.claims:
            gold_claims = sample.gold.claims
            # Alinhamos por proximidade textual para ver a acurácia de classificação do backend
            # (Mapeamento básico simplificado para Precision/Recall)
            tp = 0  # True Positives: classificados corretamente como suportados
            fp = 0  # False Positives: previstos como suportados mas eram unsupported na verdade
            fn = 0  # False Negatives: eram suportados mas previstos como unsupported
            
            from rapidfuzz import process, fuzz
            gold_texts = [gc.text for gc in gold_claims]
            
            for analyzed in analyzed_claims:
                # Encontra o claim gold mais próximo textualmente
                match = process.extractOne(analyzed["text"], gold_texts, scorer=fuzz.ratio)
                if match and match[1] > 60.0:
                    gold_idx = gold_texts.index(match[0])
                    gold_claim = gold_claims[gold_idx]
                    
                    pred_is_supported = (analyzed["pred_label"] == "supported")
                    gold_is_supported = (gold_claim.label == "supported")
                    
                    if pred_is_supported and gold_is_supported:
                        tp += 1
                    elif pred_is_supported and not gold_is_supported:
                        fp += 1
                    elif not pred_is_supported and gold_is_supported:
                        fn += 1
                else:
                    # Sem correspondência gold direta: se dissemos supported, tratamos como FP
                    if analyzed["pred_label"] == "supported":
                        fp += 1
                        
            precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
            recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
            f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0
            
            scores[f"{self.name}_precision"] = precision
            scores[f"{self.name}_recall"] = recall
            scores[f"{self.name}_f1"] = f1
            
        return scores, analyzed_claims
