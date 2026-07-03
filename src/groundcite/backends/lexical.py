import re
from typing import List, Dict, Any, Optional
from rapidfuzz import fuzz

from groundcite.backends.base import BaseBackend

class LexicalBackend(BaseBackend):
    """
    Backend heurístico/lexical ultrarrápido baseado em alinhamento fuzzy de strings com RapidFuzz.
    Focado em execuções locais leves de baixo custo para CI/CD.
    """
    
    def __init__(self, threshold_support: float = 75.0, threshold_contradiction_numeric: bool = True):
        """
        Args:
            threshold_support: Score de similaridade parcial mínima (0-100) para classificar como 'supported'.
            threshold_contradiction_numeric: Se True, identifica contradições factuais numéricas baseadas em grandezas.
        """
        self.threshold_support = threshold_support
        self.threshold_contradiction_numeric = threshold_contradiction_numeric
        
    def _extract_numeric_entities(self, text: str) -> List[Dict[str, Any]]:
        """
        Extrai números e suas respectivas unidades ou palavras substantivas adjacentes à direita
        (janela de contexto da grandeza) para correlacionar medidas com exatidão.
        """
        # Captura um número e até duas palavras adjacentes à direita contendo letras ou ideogramas CJK/Árabe
        matches = re.finditer(
            r'\b(\d+(?:[.,]\d+)?)\b\s*([a-zA-Z\u00C0-\u00FF\u4e00-\u9fff\u3040-\u309f\u30a0-\u30ff\u0600-\u06ff\-_]+(?:\s+[a-zA-Z\u00C0-\u00FF\u4e00-\u9fff\u3040-\u309f\u30a0-\u30ff\u0600-\u06ff\-_]+)?)?', 
            text
        )
        entities = []
        stop_words = {
            # Português
            "de", "e", "o", "a", "do", "da", "em", "um", "uma", "sendo", "como", "para", "com", "ao", "no", "na", "os", "as", "por", "dos", "das",
            # Inglês
            "the", "and", "of", "to", "in", "for", "with", "on", "at", "by", "from", "as", "an", "is", "it", "that", "this",
            # Espanhol
            "el", "la", "los", "las", "un", "una", "en", "y", "o", "de", "con", "por", "para", "como",
            # Francês
            "le", "la", "les", "un", "une", "en", "et", "ou", "de", "avec", "par", "pour", "dans",
            # Alemão
            "der", "die", "das", "ein", "eine", "in", "und", "oder", "von", "mit", "fur", "auf",
            # Mandarim (Chinês)
            "的", "和", "在", "有", "个", "与", "为", "之", "于", "以", "及",
            # Japonês
            "の", "と", "に", "は", "g", "を", "た", "で", "も", "な",
            # Árabe
            "من", "في", "و", "على", "أن", "إلى", "مع", "عن", "هذا", "هذه"
        }
        
        for m in matches:
            num = m.group(1)
            # Normaliza o valor numérico removendo pontuações de milhar/decimal comuns em PT/EN
            normalized_val = num.replace(".", "").replace(",", "")
            
            raw_unit = m.group(2).lower() if m.group(2) else ""
            # Filtra stop words e retém as unidades substantivas ou medidas reais
            words = [w for w in raw_unit.split() if len(w) > 2 and w not in stop_words]
            clean_unit = " ".join(words).strip()
            
            entities.append({
                "raw_value": num,
                "normalized_value": normalized_val,
                "context": clean_unit
            })
        return entities

    def predict_support(
        self, 
        claim: str, 
        contexts: List[str], 
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        if not contexts:
            return {"label": "unsupported", "confidence": 0.0, "evidence_doc_idx": None, "evidence_span": None}
            
        best_score = -1.0
        best_idx = None
        best_alignment = None
        
        # Encontra o contexto com a melhor correspondência parcial de string
        for idx, ctx in enumerate(contexts):
            align = fuzz.partial_ratio_alignment(claim.lower(), ctx.lower())
            score = align.score
            
            if score > best_score:
                best_score = score
                best_idx = idx
                best_alignment = align
                
        if best_idx is None or best_alignment is None:
            return {"label": "unsupported", "confidence": 0.0, "evidence_doc_idx": None, "evidence_span": None}
            
        dest_start = best_alignment.dest_start
        dest_end = best_alignment.dest_end
        
        confidence = best_score / 100.0
        
        # Heurística avançada para detecção de contradição numérica baseada em grandezas/unidades
        if self.threshold_contradiction_numeric and best_score >= 40.0:
            claim_entities = self._extract_numeric_entities(claim)
            ctx_entities = self._extract_numeric_entities(contexts[best_idx])
            
            for c_ent in claim_entities:
                c_val = c_ent["normalized_value"]
                c_ctx = c_ent["context"]
                
                # Só executa correlação de grandeza se o claim tiver uma unidade substantiva associada (ex: "quilômetros")
                if c_ctx:
                    for ctx_ent in ctx_entities:
                        ctx_val = ctx_ent["normalized_value"]
                        ctx_ctx = ctx_ent["context"]
                        
                        # Verifica se a grandeza correlacionada é semanticamente correspondente
                        # (Suporta correspondência parcial direta ou score fuzzy alto entre contextos de grandeza)
                        if ctx_ctx and (c_ctx in ctx_ctx or ctx_ctx in c_ctx or fuzz.ratio(c_ctx, ctx_ctx) >= 80.0):
                            # Se os valores normalizados divergem, há uma contradição de grandeza direta!
                            if c_val != ctx_val:
                                return {
                                    "label": "contradicted",
                                    "confidence": confidence,
                                    "evidence_doc_idx": best_idx,
                                    "evidence_span": (dest_start, dest_end)
                                }
                                
        # Classificação do rótulo padrão com base nos limiares de similaridade
        if best_score >= self.threshold_support:
            label = "supported"
        elif best_score >= 45.0:
            label = "unsupported"
        else:
            label = "unsupported"
            
        return {
            "label": label,
            "confidence": confidence,
            "evidence_doc_idx": best_idx,
            "evidence_span": (dest_start, dest_end)
        }
