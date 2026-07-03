import json
import math
from pathlib import Path
from typing import List, Dict, Any, Optional
from rapidfuzz import process, fuzz
from sklearn.metrics import f1_score

from groundcite.schema import Sample
from groundcite.backends.lexical import LexicalBackend
from groundcite.backends.pricing import estimate_tokens, PRICING_MODELS, update_prices_cache
from groundcite.claims import RegexClaimDecomposer

class ParetoOptimizer:
    """
    Otimizador de Pareto Inteligente e Dinâmico para o HybridBackend.
    Realiza busca paramétrica na grade de thresholds lexicais para maximizar o F1-Score
    sob uma restrição rígida de orçamento em USD, incorporando simulações realistas e
    precificação atualizada via API.
    """
    
    def __init__(
        self,
        pricing_model: str = "gpt-4o",
        llm_accuracy: float = 0.92,
        lang_filter: str = "all"
    ):
        """
        Args:
            pricing_model: Nome do modelo líder de referência de API para estimativa de ROI.
            llm_accuracy: Fator de acurácia da LLM Judge (0.0 a 1.0) para simular um erro realista.
            lang_filter: Idioma para filtrar os samples ('pt-BR', 'en' ou 'all').
        """
        self.pricing_model = pricing_model
        self.llm_accuracy = llm_accuracy
        self.lang_filter = lang_filter
        self.lexical = LexicalBackend()
        self.decomposer = RegexClaimDecomposer()
        
        # Garante que os preços das LLMs estejam atualizados via cache/rede
        update_prices_cache()
        
    def estimate_claim_llm_cost(self, claim_text: str, contexts: List[str]) -> float:
        """
        Estima o custo teórico em USD para avaliar um único claim contra contextos usando o modelo de referência.
        """
        prompt_input = (
            f"Analise o seguinte claim contra as fontes fornecidas:\n"
            f"Claim: {claim_text}\n"
            f"Fontes:\n" + "\n".join(contexts)
        )
        simulated_output = "O claim está suportado pelo contexto fornecido."
        
        input_tokens = estimate_tokens(prompt_input)
        output_tokens = estimate_tokens(simulated_output)
        
        pricing = PRICING_MODELS.get(self.pricing_model.lower())
        if not pricing:
            clean_name = self.pricing_model.split("/")[-1].lower() if "/" in self.pricing_model else self.pricing_model.lower()
            pricing = PRICING_MODELS.get(clean_name, {"input": 0.15, "output": 0.60})
            
        cost_input = (input_tokens / 1_000_000.0) * pricing["input"]
        cost_output = (output_tokens / 1_000_000.0) * pricing["output"]
        
        return cost_input + cost_output

    def prepare_claim_runs(self, samples: List[Sample]) -> List[Dict[str, Any]]:
        """
        Decompõe e prepara a lista de execuções de claims, pareando-os com gold labels de forma determinística.
        """
        claim_runs = []
        
        # Filtra por idioma se necessário
        filtered_samples = samples
        if self.lang_filter != "all":
            target_lang = self.lang_filter.lower().strip()
            filtered_samples = [s for s in samples if s.lang.lower().strip() == target_lang]
            
        for sample in filtered_samples:
            ctx_texts = [ctx.text for ctx in sample.contexts]
            claims = self.decomposer.decompose(sample.answer, lang=sample.lang)
            
            for c_text in claims:
                lex_res = self.lexical.predict_support(c_text, ctx_texts)
                llm_cost = self.estimate_claim_llm_cost(c_text, ctx_texts)
                
                # Mapeamento do gold label correspondente via busca fuzzy de string
                gold_label = "unsupported"
                if sample.gold and sample.gold.claims:
                    gold_claims = sample.gold.claims
                    gold_texts = [gc.text for gc in gold_claims]
                    match = process.extractOne(c_text, gold_texts, scorer=fuzz.ratio)
                    if match and match[1] > 60.0:
                        gold_idx = gold_texts.index(match[0])
                        gold_label = gold_claims[gold_idx].label
                        
                claim_runs.append({
                    "text": c_text,
                    "lex_label": lex_res["label"],
                    "lex_conf": lex_res["confidence"],
                    "llm_cost": llm_cost,
                    "gold_label": gold_label
                })
                
        return claim_runs

    def run_optimization(self, samples: List[Sample], max_budget_usd: float) -> Dict[str, Any]:
        """
        Executa a busca paramétrica na grade de thresholds sob a restrição de orçamento USD,
        introduzindo o ruído realista simulado da LLM Judge.
        """
        claim_runs = self.prepare_claim_runs(samples)
        
        if not claim_runs:
            return {
                "grid_results": [],
                "best_run": None,
                "max_llm_cost": 0.0,
                "total_claims": 0
            }
            
        grid_results = []
        
        # Varredura da grade de thresholds [0.0, 1.0] com passo de 0.01 (101 iterações)
        for t_idx in range(101):
            threshold = t_idx / 100.0
            
            sim_preds = []
            sim_golds = []
            total_cost = 0.0
            
            for idx, run in enumerate(claim_runs):
                lex_label = run["lex_label"]
                lex_conf = run["lex_conf"]
                gold_label = run["gold_label"]
                
                # Lógica Híbrida de Decisão:
                if lex_label == "contradicted":
                    # Contradição numérica intercepta instantaneamente (custo zero)
                    pred_label = "contradicted"
                    cost = 0.0
                elif lex_label == "supported" and lex_conf >= threshold:
                    # Match exato acima do threshold intercepta (custo zero)
                    pred_label = "supported"
                    cost = 0.0
                else:
                    # Fallback semântico (custo real incorrido)
                    cost = run["llm_cost"]
                    
                    # Simulação realista: se claim_hash violar a acurácia configurada,
                    # a LLM simula um erro e inverte a predição contra a gold label.
                    claim_hash = abs(hash(run["text"] + gold_label + str(idx))) % 100
                    if claim_hash >= int(self.llm_accuracy * 100):
                        # Simula um erro na LLM (inverte a label)
                        pred_label = "unsupported" if gold_label == "supported" else "supported"
                    else:
                        pred_label = gold_label
                        
                sim_preds.append(pred_label)
                sim_golds.append(gold_label)
                total_cost += cost
                
            try:
                macro_f1 = f1_score(sim_golds, sim_preds, average="macro", zero_division=0)
            except Exception:
                macro_f1 = 0.0
                
            grid_results.append({
                "threshold": threshold,
                "cost_usd": total_cost,
                "f1_score": macro_f1
            })
            
        # Filtra os limiares que atendem a restrição financeira
        feasible_runs = [r for r in grid_results if r["cost_usd"] <= max_budget_usd]
        
        # Encontra o melhor limiar de Pareto
        if not feasible_runs:
            best_run = min(grid_results, key=lambda x: x["cost_usd"])
            is_feasible = False
        else:
            best_run = max(feasible_runs, key=lambda x: (x["f1_score"], -x["cost_usd"]))
            is_feasible = True
            
        max_llm_cost = next((r["cost_usd"] for r in grid_results if abs(r["threshold"] - 1.0) < 1e-5), 0.0)
        
        return {
            "grid_results": grid_results,
            "best_run": best_run,
            "is_feasible": is_feasible,
            "max_llm_cost": max_llm_cost,
            "total_claims": len(claim_runs)
        }

    def generate_html_dashboard(
        self,
        grid_results: List[Dict[str, Any]],
        tuned_threshold: float,
        pricing_model: str,
        max_budget_usd: float,
        best_run: Dict[str, Any]
    ) -> str:
        """
        Gera um dashboard HTML premium interativo desenhando a Fronteira de Pareto.
        """
        # Formata dados para injeção no gráfico SVG
        best_cost = best_run["cost_usd"]
        best_f1 = best_run["f1_score"]
        
        # Computa coordenadas para desenho SVG da curva de Pareto
        costs = [r["cost_usd"] for r in grid_results]
        f1s = [r["f1_score"] for r in grid_results]
        
        min_cost = min(costs) if costs else 0.0
        max_cost = max(costs) if costs else 1.0
        cost_range = (max_cost - min_cost) if (max_cost - min_cost) > 0 else 1.0
        
        points_svg = []
        tuned_x, tuned_y = 0.0, 0.0
        
        # Transpõe dados para uma caixa SVG de 500x300px
        for r in grid_results:
            cx = r["cost_usd"]
            cy = r["f1_score"]
            
            # Normalização X (custo) e Y (F1)
            x_val = 50 + ((cx - min_cost) / cost_range) * 400
            y_val = 250 - (cy * 200) # F1 varia de 0.0 a 1.0
            
            points_svg.append(f"{x_val:.1f},{y_val:.1f}")
            if abs(r["threshold"] - tuned_threshold) < 1e-5:
                tuned_x = x_val
                tuned_y = y_val
                
        polyline_points = " ".join(points_svg)
        
        # Gera o HTML Premium no design Glassmorphism
        html = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>GroundCite Pareto Frontier Optimizer</title>
    <style>
        :root {{
            --bg-color: #0f172a;
            --card-bg: #1e293b;
            --text-color: #f8fafc;
            --text-muted: #94a3b8;
            --primary: #10b981;
            --danger: #ef4444;
            --accent: #3b82f6;
            --border: #334155;
        }}
        body {{
            font-family: 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
            background-color: var(--bg-color);
            color: var(--text-color);
            margin: 0;
            padding: 2rem;
            display: flex;
            justify-content: center;
            align-items: center;
            min-height: 100vh;
        }}
        .dashboard {{
            width: 100%;
            max-width: 950px;
            background-color: rgba(30, 41, 59, 0.7);
            backdrop-filter: blur(10px);
            border: 1px solid var(--border);
            border-radius: 16px;
            padding: 2.5rem;
            box-shadow: 0 10px 30px rgba(0,0,0,0.5);
        }}
        header {{
            text-align: center;
            margin-bottom: 2.5rem;
        }}
        header h1 {{
            font-size: 2.5rem;
            margin: 0;
            background: linear-gradient(135deg, #10b981, #3b82f6);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            font-weight: 800;
        }}
        header p {{
            color: var(--text-muted);
            margin: 0.5rem 0 0 0;
            font-size: 1rem;
        }}
        .content {{
            display: grid;
            grid-template-columns: 1.1fr 0.9fr;
            gap: 2.5rem;
        }}
        @media (max-width: 768px) {{
            .content {{
                grid-template-columns: 1fr;
            }}
        }}
        .metrics-grid {{
            display: flex;
            flex-direction: column;
            gap: 1.2rem;
        }}
        .metric-card {{
            background-color: var(--card-bg);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 1.2rem 1.5rem;
            transition: transform 0.2s ease, box-shadow 0.2s ease;
        }}
        .metric-card:hover {{
            transform: translateY(-2px);
            box-shadow: 0 5px 15px rgba(0,0,0,0.3);
            border-color: var(--accent);
        }}
        .metric-card .label {{
            font-size: 0.85rem;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            color: var(--text-muted);
            margin-bottom: 0.4rem;
        }}
        .metric-card .value {{
            font-size: 1.6rem;
            font-weight: 700;
        }}
        .metric-card .sub-value {{
            font-size: 0.9rem;
            color: var(--primary);
            margin-top: 0.2rem;
        }}
        .chart-panel {{
            background-color: var(--card-bg);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 1.8rem;
            display: flex;
            flex-direction: column;
            align-items: center;
        }}
        .chart-title {{
            font-weight: 600;
            margin-bottom: 1.5rem;
            font-size: 1.1rem;
            color: var(--text-color);
        }}
        .svg-container {{
            width: 100%;
            max-width: 500px;
            aspect-ratio: 5/3;
        }}
        .legend {{
            margin-top: 1.2rem;
            display: flex;
            flex-direction: row;
            gap: 1.5rem;
            font-size: 0.85rem;
        }}
        .legend-item {{
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }}
        .legend-color {{
            width: 12px;
            height: 12px;
            border-radius: 3px;
        }}
        .legend-color.curve {{ background-color: var(--accent); }}
        .legend-color.selected {{ background-color: var(--primary); }}
        .legend-color.budget {{ background-color: var(--danger); }}
    </style>
</head>
<body>
    <div class="dashboard">
        <header>
            <h1>GroundCite Pareto Curve Optimizer</h1>
            <p>Varredura Paramétrica de Custo-Performance para Calibração de Limiares</p>
        </header>
        <div class="content">
            <div class="metrics-grid">
                <div class="metric-card">
                    <div class="label">Configuração de Threshold Otimizada</div>
                    <div class="value" style="color: var(--primary);">{tuned_threshold:.2f}</div>
                    <div class="sub-value">Modelo de Referência: {pricing_model}</div>
                </div>
                <div class="metric-card">
                    <div class="label">Macro-F1 Esperado (Simulado)</div>
                    <div class="value">{best_f1:.4f}</div>
                    <div class="sub-value">Simulado sob Acurácia LLM de {self.llm_accuracy * 100:.1f}%</div>
                </div>
                <div class="metric-card">
                    <div class="label">Custo Estimado sob Calibração</div>
                    <div class="value">USD {best_cost:.5f}</div>
                    <div class="sub-value">Restrição de Orçamento: USD {max_budget_usd:.5f}</div>
                </div>
                <div class="metric-card">
                    <div class="label">Idioma e Filtragem</div>
                    <div class="value" style="text-transform: uppercase;">{self.lang_filter}</div>
                    <div class="sub-value">Filtro de Amostragem do Benchmark</div>
                </div>
            </div>
            <div class="chart-panel">
                <div class="chart-title">Fronteira de Pareto: Custo x Macro-F1</div>
                <div class="svg-container">
                    <svg viewBox="0 0 500 300" width="100%" height="100%">
                        <!-- Grade de Fundo -->
                        <line x1="50" y1="50" x2="450" y2="50" stroke="#334155" stroke-dasharray="3" />
                        <line x1="50" y1="150" x2="450" y2="150" stroke="#334155" stroke-dasharray="3" />
                        <line x1="50" y1="250" x2="450" y2="250" stroke="#334155" />
                        <line x1="50" y1="50" x2="50" y2="250" stroke="#334155" />
                        <line x1="450" y1="50" x2="450" y2="250" stroke="#334155" />
                        
                        <!-- Rótulos Eixos -->
                        <text x="35" y="55" fill="#94a3b8" font-size="10" text-anchor="end">1.0</text>
                        <text x="35" y="155" fill="#94a3b8" font-size="10" text-anchor="end">0.5</text>
                        <text x="35" y="255" fill="#94a3b8" font-size="10" text-anchor="end">0.0</text>
                        <text x="250" y="280" fill="#94a3b8" font-size="11" text-anchor="middle">Custo Total da Inferência (USD)</text>
                        <text x="15" y="150" fill="#94a3b8" font-size="11" text-anchor="middle" transform="rotate(-90 15 150)">Macro-F1 Score</text>
                        
                        <!-- Linha de Orçamento Máximo (Budget Line) -->
                        <line x1="{50 + ((max_budget_usd - min_cost) / cost_range) * 400:.1f}" y1="50" x2="{50 + ((max_budget_usd - min_cost) / cost_range) * 400:.1f}" y2="250" stroke="#ef4444" stroke-width="2" stroke-dasharray="5 3" />
                        
                        <!-- Curva de Pareto -->
                        <polyline fill="none" stroke="#3b82f6" stroke-width="3" points="{polyline_points}" />
                        
                        <!-- Ponto Otimizado Selecionado -->
                        <circle cx="{tuned_x:.1f}" cy="{tuned_y:.1f}" r="7" fill="#10b981" stroke="#f8fafc" stroke-width="2" />
                    </svg>
                </div>
                <div class="legend">
                    <div class="legend-item">
                        <div class="legend-color curve"></div>
                        <span>Curva de Tradeoff</span>
                    </div>
                    <div class="legend-item">
                        <div class="legend-color selected"></div>
                        <span>Ponto Ótimo Calibrado</span>
                    </div>
                    <div class="legend-item">
                        <div class="legend-color budget"></div>
                        <span>Limite Financeiro</span>
                    </div>
                </div>
            </div>
        </div>
    </div>
</body>
</html>"""
        return html
