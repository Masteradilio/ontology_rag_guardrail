from typing import List, Dict, Any, Optional

from groundcite.backends.base import BaseBackend
from groundcite.backends.lexical import LexicalBackend

class HybridBackend(BaseBackend):
    """
    Backend Híbrido que funciona como um gateway inteligente de avaliação.
    Aplica um "fast-path" determinístico de primeiro nível (LexicalBackend) para interceptar
    correspondências exatas e contradições numéricas factuais imediatas.
    Se o atalho for acionado, calcula dinamicamente o custo de tokens economizado (usd_saved)
    com base no modelo de LLM de referência especificado.
    """
    
    def __init__(
        self,
        primary_backend: BaseBackend,
        fast_path_backend: Optional[BaseBackend] = None,
        exact_match_threshold: Optional[float] = None,
        fast_path_contradiction: bool = True,
        pricing_model: str = "gpt-4o"
    ):
        """
        Args:
            primary_backend: Backend semântico principal pesado (ex: LocalNLIBackend, OpenAIBackend).
            fast_path_backend: Backend leve determinístico para o fast-path. Se None, inicializa o LexicalBackend.
            exact_match_threshold: Limiar de confiança (0.0 a 1.0) acima do qual um suporte lexical exato 
                                  é aceito sem chamar o backend primário. Se None, tenta carregar automaticamente.
            fast_path_contradiction: Se True, intercepta e retorna contradições numéricas factuais instantaneamente.
            pricing_model: Nome do modelo de referência de LLM para estimativa de ROI (ex: 'gpt-4o', 'gemini-1.5-pro').
        """
        self.primary_backend = primary_backend
        self.fast_path_backend = fast_path_backend if fast_path_backend is not None else LexicalBackend()
        self.fast_path_contradiction = fast_path_contradiction
        self.pricing_model = pricing_model
        
        # Carregamento Automático da Otimização de Pareto (Fase 13)
        if exact_match_threshold is None:
            import json
            import os
            config_file = "hybrid_tuned_config.json"
            if os.path.exists(config_file):
                try:
                    with open(config_file, "r", encoding="utf-8") as f:
                        cfg = json.load(f)
                    self.exact_match_threshold = cfg.get("exact_match_threshold", 0.98)
                    self.pricing_model = cfg.get("pricing_model", self.pricing_model)
                    self.fast_path_contradiction = cfg.get("fast_path_contradiction", self.fast_path_contradiction)
                except Exception:
                    self.exact_match_threshold = 0.98
            else:
                self.exact_match_threshold = 0.98
        else:
            self.exact_match_threshold = exact_match_threshold
            
    @classmethod
    def from_tuned_config(
        cls, 
        config_path: str, 
        primary_backend: BaseBackend, 
        fast_path_backend: Optional[BaseBackend] = None,
        **kwargs
    ) -> 'HybridBackend':
        """
        Cria uma instância do HybridBackend carregando a calibração ótima diretamente de um arquivo de configuração JSON.
        """
        import json
        with open(config_path, "r", encoding="utf-8") as f:
            cfg = json.load(f)
            
        exact_match_threshold = cfg.get("exact_match_threshold", 0.98)
        fast_path_contradiction = cfg.get("fast_path_contradiction", True)
        pricing_model = cfg.get("pricing_model", "gpt-4o")
        
        return cls(
            primary_backend=primary_backend,
            fast_path_backend=fast_path_backend,
            exact_match_threshold=exact_match_threshold,
            fast_path_contradiction=fast_path_contradiction,
            pricing_model=pricing_model,
            **kwargs
        )

        
    def predict_support(
        self, 
        claim: str, 
        contexts: List[str], 
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        if not contexts:
            return {
                "label": "unsupported", 
                "confidence": 0.0, 
                "evidence_doc_idx": None, 
                "evidence_span": None,
                "usd_saved": 0.0,
                "usd_estimate": 0.0
            }
            
        # 1. Executa a análise ultra rápida no fast-path determinístico de primeiro nível
        fast_result = self.fast_path_backend.predict_support(claim, contexts, metadata)
        
        label = fast_result["label"]
        confidence = fast_result["confidence"]
        
        # Função auxiliar interna para calcular o custo estimado de tokens
        def _calculate_cost() -> float:
            # Prompt de input simulado enviado para a API do LLM Judge
            prompt_input = (
                f"Analise o seguinte claim contra as fontes fornecidas:\n"
                f"Claim: {claim}\n"
                f"Fontes:\n" + "\n".join(contexts)
            )
            # Resposta média curta gerada pelo LLM Judge (ex: classificação + explicação de 100 caracteres)
            simulated_output = "O claim está suportado pelo contexto fornecido."
            
            from groundcite.backends.pricing import estimate_tokens, estimate_image_tokens, PRICING_MODELS
            
            text_tokens = estimate_tokens(prompt_input)
            image_tokens = 0
            
            # Computa tokens de imagens se houver metadados multimodal
            if metadata:
                # A) Metadados do Sample global
                sample_meta = metadata.get("sample_metadata") or {}
                if isinstance(sample_meta, dict) and "images" in sample_meta:
                    for img in sample_meta["images"]:
                        if isinstance(img, dict):
                            w = img.get("width", 512)
                            h = img.get("height", 512)
                            det = img.get("detail", "low")
                            image_tokens += estimate_image_tokens(w, h, det)
                            
                # B) Metadados dos Contextos
                ctx_meta_list = metadata.get("contexts_metadata") or []
                for c_meta in ctx_meta_list:
                    if isinstance(c_meta, dict) and "images" in c_meta:
                        for img in c_meta["images"]:
                            if isinstance(img, dict):
                                w = img.get("width", 512)
                                h = img.get("height", 512)
                                det = img.get("detail", "low")
                                image_tokens += estimate_image_tokens(w, h, det)
                                
            input_tokens = text_tokens + image_tokens
            output_tokens = estimate_tokens(simulated_output)
            
            pricing = PRICING_MODELS.get(self.pricing_model.lower())
            if not pricing:
                clean_name = self.pricing_model.split("/")[-1].lower() if "/" in self.pricing_model else self.pricing_model.lower()
                pricing = PRICING_MODELS.get(clean_name, {"input": 0.15, "output": 0.60})
                
            cost_input = (input_tokens / 1_000_000.0) * pricing["input"]
            cost_output = (output_tokens / 1_000_000.0) * pricing["output"]
            
            return cost_input + cost_output
            
        # A) Intercepção por Contradição Numérica
        if self.fast_path_contradiction and label == "contradicted":
            fast_result["optimized_by"] = "hybrid_fast_path_contradiction"
            fast_result["usd_saved"] = _calculate_cost()
            fast_result["usd_estimate"] = 0.0
            return fast_result
            
        # B) Intercepção por Match Exato / Confiança Lexical Extrema
        if label == "supported" and confidence >= self.exact_match_threshold:
            fast_result["optimized_by"] = "hybrid_fast_path_exact_match"
            fast_result["usd_saved"] = _calculate_cost()
            fast_result["usd_estimate"] = 0.0
            return fast_result
            
        # 2. Se não atendeu aos critérios de atalho, faz o fallback para o backend primário semântico
        semantic_result = self.primary_backend.predict_support(claim, contexts, metadata)
        semantic_result["optimized_by"] = "fallback_semantic_evaluation"
        semantic_result["usd_saved"] = 0.0  # Sem economia, pois a inferência primária de fato ocorreu
        semantic_result["usd_estimate"] = _calculate_cost()  # Custo real estimado incorrido
        
        return semantic_result
