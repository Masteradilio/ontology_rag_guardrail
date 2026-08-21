from typing import List, Dict, Any, Tuple
from groundcite.schema import Sample
from groundcite.backends.base import BaseBackend

class ConflictingSourceAdjudication:
    """
    Eixo Metodológico CSA (Conflicting Source Adjudication).
    Identifica contradições factuais cruzadas nas fontes de contexto (ex: Doc A diverge de Doc B)
    e penaliza severamente respostas RAG que escolham arbitrariamente um lado sem relatar 
    esta divergência explicitamente ao usuário final.
    """
    
    def __init__(self, name: str = "csa_adjudication"):
        self.name = name
        # Marcadores linguísticos comuns em português e inglês de reconhecimento de contradições/divergências
        self.contradiction_markers = [
            "diverg", "conflit", "contrad", "opost", "embora", "no entanto", 
            "por outro lado", "diverge", "diferem", "diferente", "discorda", 
            "entretanto", "contudo", "porem", "porém", "discrep",
            "conflict", "contradict", "however", "on the other hand", "differ", 
            "although", "nevertheless", "yet"
        ]

    def _contains_divergence_warning(self, text: str) -> bool:
        """Verifica se a resposta RAG ou claim explicita a contradição/divergência."""
        normalized = text.lower()
        # Remove acentos básicos para robustez
        import unicodedata
        normalized = "".join(
            c for c in unicodedata.normalize("NFD", normalized)
            if unicodedata.category(c) != "Mn"
        )
        return any(marker in normalized for marker in self.contradiction_markers)

    def evaluate(self, sample: Sample, backend: BaseBackend, claims: List[Dict[str, Any]]) -> Tuple[Dict[str, float], List[Dict[str, Any]]]:
        """
        Avalia se claims da resposta RAG sofrem de contradição de fontes e se foram adjudicados devidamente.
        
        Args:
            sample: O exemplo contendo os dados originais do RAG e contextos.
            backend: O backend de inferência (Lexical ou NLI).
            claims: Lista de claims analisados previamente (gerados pelo ClaimSupport).
            
        Returns:
            Um par contendo:
                - Dicionário de scores consolidados de CSA.
                - Lista de claims com metadados CSA enriquecidos.
        """
        csa_claims = []
        conflicting_claims_count = 0
        arbitrary_choices_count = 0
        penalized_claims_count = 0
        
        ctx_texts = [ctx.text for ctx in sample.contexts]
        
        for cl in claims:
            cl_copy = dict(cl)
            claim_text = cl_copy["text"]
            
            # Se já temos poucos contextos, não há conflito cruzado possível
            if len(ctx_texts) < 2:
                cl_copy["csa_status"] = "no_conflict_possible"
                csa_claims.append(cl_copy)
                continue
                
            # Avalia o claim contra cada documento de contexto individualmente
            supports = []
            contradictions = []
            
            # Agrupa metadados básicos para o backend
            sample_meta = {
                "sample_metadata": getattr(sample, "metadata", None),
                "contexts_metadata": [getattr(ctx, "metadata", None) for ctx in sample.contexts]
            }
            
            for idx, ctx_text in enumerate(ctx_texts):
                pred = backend.predict_support(claim_text, [ctx_text], metadata=sample_meta)
                label = pred["label"]
                if label == "supported":
                    supports.append(idx)
                elif label == "contradicted":
                    contradictions.append(idx)
            
            # Se o claim é suportado por algum doc E contradito por outro, temos um conflito nas fontes!
            if supports and contradictions:
                conflicting_claims_count += 1
                cl_copy["csa_conflict_detected"] = True
                cl_copy["csa_supporting_docs"] = [sample.contexts[i].doc_id for i in supports]
                cl_copy["csa_contradicting_docs"] = [sample.contexts[i].doc_id for i in contradictions]
                
                # Verifica se a resposta ou o claim alerta sobre o conflito
                has_warning = self._contains_divergence_warning(sample.answer) or self._contains_divergence_warning(claim_text)
                
                if not has_warning:
                    # Escolha unilateral arbitrária detectada! Penaliza o label e a confiança.
                    arbitrary_choices_count += 1
                    cl_copy["csa_status"] = "arbitrary_unilateral_choice"
                    cl_copy["pred_label"] = "contradicted"  # Penalização severa: força label contradicted!
                    cl_copy["confidence"] = max(0.1, cl_copy.get("confidence", 1.0) - 0.5)  # Penaliza confiança
                    
                    if "metadata" not in cl_copy or cl_copy["metadata"] is None:
                        cl_copy["metadata"] = {}
                    cl_copy["metadata"]["csa_penalized"] = True
                    cl_copy["metadata"]["csa_reason"] = "A resposta escolheu de forma arbitrária uma versão sem reportar a divergência das fontes."
                    penalized_claims_count += 1
                else:
                    cl_copy["csa_status"] = "adjudicated_correctly"
                    if "metadata" not in cl_copy or cl_copy["metadata"] is None:
                        cl_copy["metadata"] = {}
                    cl_copy["metadata"]["csa_adjudicated"] = True
            else:
                cl_copy["csa_status"] = "consistent_sources"
                
            csa_claims.append(cl_copy)
            
        csa_score = 1.0
        if conflicting_claims_count > 0:
            csa_score = (conflicting_claims_count - arbitrary_choices_count) / conflicting_claims_count
            
        scores = {
            f"{self.name}_score": csa_score,
            f"{self.name}_conflicting_claims": float(conflicting_claims_count),
            f"{self.name}_arbitrary_choices": float(arbitrary_choices_count),
            f"{self.name}_penalized_claims": float(penalized_claims_count)
        }
        
        return scores, csa_claims
