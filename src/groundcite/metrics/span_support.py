from typing import List, Dict, Any, Tuple
from rapidfuzz import fuzz

from groundcite.schema import Sample

class SpanSupport:
    """
    Métrica que identifica, a nível de caractere, quais partes da resposta gerada 
    carecem de suporte das fontes de contexto (unsupported content spans).
    """
    
    def __init__(self, name: str = "span_support"):
        self.name = name
        
    def evaluate(self, sample: Sample, analyzed_claims: List[Dict[str, Any]]) -> Tuple[Dict[str, float], List[Dict[str, Any]]]:
        """
        Mapeia os spans de caracteres sem suporte a partir dos claims classificados como
        unsupported ou contradicted.
        
        Args:
            sample: Exemplo RAG avaliado.
            analyzed_claims: Resultados de análise individual de claims gerados pela métrica ClaimSupport.
            
        Returns:
            Par contendo dicionário de scores e lista de spans não suportados detectados.
        """
        answer = sample.answer
        if not answer:
            return {f"{self.name}_unsupported_rate": 0.0}, []
            
        unsupported_spans: List[Dict[str, Any]] = []
        raw_intervals: List[Tuple[int, int]] = []
        
        for claim in analyzed_claims:
            if claim["pred_label"] in ("unsupported", "contradicted"):
                claim_text = claim["text"]
                
                # Localiza a posição exata (fuzzy match) do claim inválido dentro da resposta original
                align = fuzz.partial_ratio_alignment(claim_text.lower(), answer.lower())
                
                if align.score >= 50.0:
                    start, end = align.dest_start, align.dest_end
                    raw_intervals.append((start, end))
                    
        # Ordena e mescla intervalos sobrepostos para evitar dupla contagem de caracteres
        merged_intervals = self._merge_intervals(raw_intervals)
        
        # Calcula a taxa de caracteres sem suporte
        unsupported_chars_count = sum(end - start for start, end in merged_intervals)
        unsupported_rate = unsupported_chars_count / len(answer)
        
        for start, end in merged_intervals:
            unsupported_spans.append({
                "text": answer[start:end],
                "start": start,
                "end": end
            })
            
        scores = {
            f"{self.name}_unsupported_rate": unsupported_rate,
            f"{self.name}_unsupported_chars": float(unsupported_chars_count),
            f"{self.name}_total_chars": float(len(answer))
        }
        
        # Se houver gold, calcula F1 de sobreposição de spans (a nível de caractere)
        if sample.gold and sample.gold.unsupported_spans:
            # Conjunto de índices de caracteres previstos como unsupported
            pred_indices = set()
            for start, end in merged_intervals:
                pred_indices.update(range(start, end))
                
            # Conjunto de índices de caracteres anotados (gold) como unsupported
            gold_indices = set()
            for gs in sample.gold.unsupported_spans:
                gs_start = gs.get("start")
                gs_end = gs.get("end")
                if gs_start is not None and gs_end is not None:
                    gold_indices.update(range(gs_start, gs_end))
                    
            if not gold_indices and not pred_indices:
                span_f1 = 1.0
            elif not gold_indices or not pred_indices:
                span_f1 = 0.0
            else:
                intersection = pred_indices.intersection(gold_indices)
                precision = len(intersection) / len(pred_indices)
                recall = len(intersection) / len(gold_indices)
                span_f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0
                
            scores[f"{self.name}_f1"] = span_f1
            
        return scores, unsupported_spans
        
    def _merge_intervals(self, intervals: List[Tuple[int, int]]) -> List[Tuple[int, int]]:
        """Mescla intervalos numéricos de coordenadas de caracteres que se sobrepõem."""
        if not intervals:
            return []
            
        # Ordena por início de intervalo
        sorted_intervals = sorted(intervals, key=lambda x: x[0])
        merged = [sorted_intervals[0]]
        
        for current in sorted_intervals[1:]:
            prev_start, prev_end = merged[-1]
            curr_start, curr_end = current
            
            if curr_start <= prev_end:
                # Há sobreposição: estende o intervalo anterior se necessário
                merged[-1] = (prev_start, max(prev_end, curr_end))
            else:
                # Sem sobreposição: adiciona novo intervalo
                merged.append(current)
                
        return merged
