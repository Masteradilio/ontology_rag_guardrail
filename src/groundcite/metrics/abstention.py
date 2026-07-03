from typing import Dict, List, Any

from groundcite.schema import Sample

class AbstentionRisk:
    """
    Métrica que estima o risco de abstenção (abstention risk) com base na taxa de
    suporte de claims, detecção de contradições factuais e taxas de spans não suportados.
    Recomenda se a resposta deve ser retida/bloqueada para evitar alucinações confiantes.
    """
    
    def __init__(self, name: str = "abstention_risk", risk_threshold: float = 0.40):
        """
        Args:
            name: Nome da métrica.
            risk_threshold: Limite acima do qual a abstenção é recomendada (0.0 a 1.0).
        """
        self.name = name
        self.risk_threshold = risk_threshold
        
    def evaluate(self, sample: Sample, scores: Dict[str, float]) -> Dict[str, Any]:
        """
        Calcula o risco de abstenção com base nos scores parciais coletados.
        
        Args:
            sample: Exemplo RAG original.
            scores: Scores coletados das métricas de claim_support e span_support.
            
        Returns:
            Dicionário com o score de risco (0.0 a 1.0) e a decisão binária de recomendação.
        """
        # Extrai métricas auxiliares calculadas
        support_rate = scores.get("claim_support_rate", 1.0)
        contradicted_count = scores.get("claim_support_contradicted_count", 0.0)
        unsupported_rate = scores.get("span_support_unsupported_rate", 0.0)
        
        # Fórmula calibrada para cálculo de risco (data-driven):
        # 1. Se houver qualquer contradição factual direta detectada pelo backend,
        #    o risco é imediatamente forçado para o máximo (1.0).
        if contradicted_count > 0:
            risk = 1.0
        else:
            # 2. Risco ponderado: 70% pela fração de claims sem suporte + 30% pela proporção de caracteres alucinados
            unsupported_claims_fraction = 1.0 - support_rate
            risk = (unsupported_claims_fraction * 0.7) + (unsupported_rate * 0.3)
            
        # Garante limites válidos [0.0, 1.0]
        risk = max(0.0, min(1.0, risk))
        
        recommend_abstain = risk >= self.risk_threshold
        
        return {
            f"{self.name}": risk,
            "recommend_abstention": recommend_abstain
        }

    @staticmethod
    def calculate_ece(predictions: List[float], labels: List[int], n_bins: int = 10) -> float:
        """
        Calcula o Expected Calibration Error (ECE) para um conjunto de predições de risco.
        O ECE mede o quão bem calibrado está o risco de abstenção previsto em relação 
        aos erros reais (labels).
        
        Args:
            predictions: Lista de probabilidades/riscos previstos (0.0 a 1.0).
            labels: Lista de ground truth binário onde 1 significa erro factual/alucinação 
                    (onde deveria ter se abstido).
            n_bins: Número de compartimentos para agrupar as probabilidades.
            
        Returns:
            O valor de ECE computado. Quanto mais próximo de 0.0, mais bem calibrado.
        """
        if not predictions or not labels or len(predictions) != len(labels):
            return 0.0
            
        import numpy as np
        preds = np.array(predictions)
        trues = np.array(labels)
        
        bin_boundaries = np.linspace(0.0, 1.0, n_bins + 1)
        ece = 0.0
        n_total = len(preds)
        
        for i in range(n_bins):
            # Identifica as amostras que caem neste bin (compartimento)
            in_bin = (preds >= bin_boundaries[i]) & (preds < bin_boundaries[i+1])
            # A última caixa inclui o limite superior de 1.0
            if i == n_bins - 1:
                in_bin = (preds >= bin_boundaries[i]) & (preds <= bin_boundaries[i+1])
                
            n_in_bin = np.sum(in_bin)
            
            if n_in_bin > 0:
                # Confiança média do modelo para este bin
                avg_confidence_in_bin = np.mean(preds[in_bin])
                # Proporção real de falhas/alucinações neste bin (Acurácia empírica)
                avg_accuracy_in_bin = np.mean(trues[in_bin])
                
                # Diferença absoluta ponderada pelo tamanho do bin
                ece += (n_in_bin / n_total) * np.abs(avg_accuracy_in_bin - avg_confidence_in_bin)
                
        return float(ece)
