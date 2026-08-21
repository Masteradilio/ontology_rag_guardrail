import time
from typing import List, Optional, Dict, Any

from groundcite.schema import Sample, EvalResult
from groundcite.claims import BaseClaimDecomposer, RegexClaimDecomposer
from groundcite.backends.base import BaseBackend
from groundcite.backends.lexical import LexicalBackend
from groundcite.metrics.claim_support import ClaimSupport
from groundcite.metrics.span_support import SpanSupport
from groundcite.metrics.abstention import AbstentionRisk
from groundcite.metrics.conflicting_adjudication import ConflictingSourceAdjudication
from groundcite.metrics.conformal import ConformalPredictor

class Evaluator:
    """
    Orquestrador central de avaliação de groundedness do GroundCite-PTEN.
    Combina decomposição de sentenças, alinhamento fuzzy/NLI e cálculo de métricas.
    """
    
    def __init__(self, metrics: Optional[List[Any]] = None, backend: Optional[BaseBackend] = None, decomposer: Optional[BaseClaimDecomposer] = None):
        """
        Args:
            metrics: Lista de instâncias de métricas a executar (ex: ClaimSupport, SpanSupport, AbstentionRisk).
                     Se None, carrega as métricas padrão por conveniência.
            backend: Instância de BaseBackend. Se None, inicializa o LexicalBackend padrão.
            decomposer: Instância de BaseClaimDecomposer. Se None, inicializa o RegexClaimDecomposer.
        """
        self.backend = backend if backend is not None else LexicalBackend()
        self.decomposer = decomposer if decomposer is not None else RegexClaimDecomposer()
        
        if metrics is None:
            self.metrics = [
                ClaimSupport(),
                SpanSupport(),
                AbstentionRisk(),
                ConflictingSourceAdjudication()
            ]
        else:
            self.metrics = metrics
            
    def evaluate(self, sample: Sample) -> EvalResult:
        """
        Avalia o Sample RAG fornecido e retorna os resultados estruturados.
        
        Args:
            sample: Exemplo contendo pergunta, contexto e resposta RAG.
            
        Returns:
            Um objeto EvalResult completo contendo scores e detalhes da análise.
        """
        start_time = time.perf_counter()
        
        # 1. Decomposição da resposta do Sample em claims atômicos com grafo de dependências
        if hasattr(self.decomposer, "decompose_to_graph"):
            graph = self.decomposer.decompose_to_graph(sample.answer, lang=sample.lang)
            claims = list(graph.nodes.values())
        else:
            graph = None
            claims = self.decomposer.decompose(sample.answer, lang=sample.lang)
        
        scores: Dict[str, float] = {}
        analyzed_claims: List[Dict[str, Any]] = []
        unsupported_spans: List[Dict[str, Any]] = []
        warnings: List[str] = []
        
        # Processa cada métrica de forma encadeada de acordo com as dependências lógicas:
        # A) ClaimSupport
        claim_support_metric = next((m for m in self.metrics if isinstance(m, ClaimSupport)), None)
        if claim_support_metric:
            claim_scores, analyzed_claims = claim_support_metric.evaluate(sample, self.backend, claims)
            
            # --- Fase 12: Propagação Lógica e Semântica via Claim Entailment Graph ---
            if graph and analyzed_claims:
                node_ids = list(graph.nodes.keys())
                
                # Popula os status originais e confianças no grafo
                for i, ac in enumerate(analyzed_claims):
                    if i < len(node_ids):
                        graph.labels[node_ids[i]] = ac.get("pred_label", "unsupported")
                        graph.confidences[node_ids[i]] = ac.get("confidence", 1.0)
                        
                # Executa propagação de inconsistências estruturadas e confianças
                propagated_labels, propagated_confidences = graph.propagate()
                
                # Atualiza os claims avaliados, anota metadados e ponderação de confiança
                for i, ac in enumerate(analyzed_claims):
                    if i < len(node_ids):
                        old_label = ac.get("pred_label", "unsupported")
                        new_label = propagated_labels.get(node_ids[i], "unsupported")
                        
                        old_conf = ac.get("confidence", 1.0)
                        new_conf = propagated_confidences.get(node_ids[i], 1.0)
                        
                        ac["confidence"] = new_conf
                        
                        if old_label != new_label or abs(old_conf - new_conf) > 1e-5:
                            if "metadata" not in ac or ac["metadata"] is None:
                                ac["metadata"] = {}
                            ac["metadata"]["propagated_via_entailment"] = True
                            ac["metadata"]["original_label"] = old_label
                            ac["metadata"]["original_confidence"] = old_conf
                            
                        if old_label != new_label:
                            ac["pred_label"] = new_label
                            
                # Atualiza a métrica base_claim_support recalibrada
                supported_count = sum(1 for c in analyzed_claims if c.get("pred_label") == "supported")
                total_claims = len(analyzed_claims)
                claim_scores["base_claim_support"] = supported_count / total_claims if total_claims > 0 else 1.0
                
            scores.update(claim_scores)
            
            # --- Eixo CSA: Adjudicação de Fontes Conflitantes ---
            csa_metric = next((m for m in self.metrics if isinstance(m, ConflictingSourceAdjudication)), None)
            if csa_metric:
                csa_scores, analyzed_claims = csa_metric.evaluate(sample, self.backend, analyzed_claims)
                scores.update(csa_scores)
                
                penalized = csa_scores.get("csa_adjudication_penalized_claims", 0.0)
                if penalized > 0:
                    warnings.append(f"Alerta CSA: A resposta escolheu de forma arbitrária uma versão sob conflito de fontes sobre {int(penalized)} claims sem citar a divergência.")
            
            # --- Calibração Matemática via Conformal Prediction ---
            conformal_pred = ConformalPredictor(alpha=0.1)
            for ac in analyzed_claims:
                pred_label = ac.get("pred_label", "unsupported")
                confidence = ac.get("confidence", 1.0)
                pred_set, class_probs = conformal_pred.predict_set(pred_label, confidence)
                ac["conformal_prediction_set"] = list(pred_set)
                ac["conformal_probabilities"] = class_probs
        else:
            warnings.append("Métrica ClaimSupport ausente ou ignorada.")
            
        # B) SpanSupport (depende dos claims analisados)
        span_support_metric = next((m for m in self.metrics if isinstance(m, SpanSupport)), None)
        if span_support_metric:
            span_scores, unsupported_spans = span_support_metric.evaluate(sample, analyzed_claims)
            scores.update(span_scores)
        else:
            warnings.append("Métrica SpanSupport ausente ou ignorada.")
            
        # C) AbstentionRisk (depende dos scores gerados pelas etapas anteriores)
        abstention_metric = next((m for m in self.metrics if isinstance(m, AbstentionRisk)), None)
        if abstention_metric:
            abstention_results = abstention_metric.evaluate(sample, scores)
            # recommend_abstention é booleano e vai para scores convertendo para float
            scores["abstention_risk"] = abstention_results["abstention_risk"]
            scores["recommend_abstention"] = 1.0 if abstention_results["recommend_abstention"] else 0.0
        else:
            warnings.append("Métrica AbstentionRisk ausente ou ignorada.")
            
        latency_ms = int((time.perf_counter() - start_time) * 1000)
        
        # Calcula a soma dos custos economizados e dos gastos reais estimados
        total_usd_saved = sum(c.get("usd_saved", 0.0) for c in analyzed_claims)
        total_usd_estimate = sum(c.get("usd_estimate", 0.0) for c in analyzed_claims)
        
        # Consolida custo e latência de processamento
        backend_name = self.backend.__class__.__name__
        cost_meta = {
            "backend": backend_name,
            "latency_ms": latency_ms,
            "usd_estimate": total_usd_estimate,
            "usd_saved": total_usd_saved
        }
        
        if graph:
            cost_meta["entailment_mermaid"] = graph.to_mermaid()
            cost_meta["entailment_dot"] = graph.to_dot()
        
        # Retorna o modelo EvalResult em conformidade com o Pydantic v2
        return EvalResult(
            id=sample.id,
            lang=sample.lang,
            scores=scores,
            claims=analyzed_claims,
            cost=cost_meta,
            warnings=warnings
        )
