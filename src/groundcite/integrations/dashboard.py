import os
import json
import logging
from pathlib import Path
from typing import Dict, Any, List

logger = logging.getLogger(__name__)

# Este módulo é o front-end Streamlit oficial do GroundCite-PTEN.
# Ele consome lógicas visuais do módulo modular visuals.py para manter alta coesão e legibilidade.

def run_app():
    try:
        import streamlit as st
    except ImportError:
        print("Erro: Streamlit não está instalado. Por favor, instale executando: pip install streamlit")
        return

    st.set_page_config(
        page_title="GroundCite MLOps & Factual Dashboard",
        page_icon="🧠",
        layout="wide",
        initial_sidebar_state="expanded"
    )

    # Design customizado responsive premium com suporte a Dark e Light Mode nativos
    st.markdown("""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=Outfit:wght@400;600;800&display=swap');
        
        .main-title {
            font-family: 'Outfit', sans-serif;
            font-size: 2.6rem;
            font-weight: 800;
            background: linear-gradient(135deg, #10b981, #3b82f6);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin-bottom: 0.5rem;
        }
        .subtitle {
            font-family: 'Inter', sans-serif;
            font-size: 1.05rem;
            color: #94a3b8;
            margin-bottom: 2rem;
        }
        .glass-card {
            background: rgba(30, 41, 59, 0.45);
            backdrop-filter: blur(12px);
            border: 1px solid rgba(255, 255, 255, 0.08);
            border-radius: 12px;
            padding: 1.6rem;
            margin-bottom: 1.5rem;
        }
        .metric-title {
            font-family: 'Outfit', sans-serif;
            font-size: 1.2rem;
            font-weight: 600;
            color: #f8fafc;
            margin-bottom: 1rem;
        }
        </style>
    """, unsafe_allow_html=True)

    st.markdown('<div class="main-title">🧠 GroundCite MLOps & Factual Dashboard</div>', unsafe_allow_html=True)
    st.markdown('<div class="subtitle">Análise premium de calibração, visualização lógica de grafos de claims e playground interativo de groundedness</div>', unsafe_allow_html=True)

    # Sidebar
    st.sidebar.markdown("### ⚙️ Configurações do Dashboard")
    uploaded_file = st.sidebar.file_uploader("Carregar arquivo de resultados JSONL (opcional)", type=["jsonl"])
    
    # Seletor dinâmico de moeda de ROI
    currency_option = st.sidebar.selectbox(
        "Moeda do Relatório MLOps:",
        ["BRL", "USD", "EUR", "GBP"],
        index=0,
        help="Herda dinamicamente o código ISO de moeda para o cálculo de ROI fático."
    )
    
    max_samples_option = st.sidebar.number_input(
        "Máx Amostras no PDF:",
        min_value=1,
        max_value=100,
        value=5,
        step=1,
        help="Limite máximo de amostras com falhas ou sucessos a detalhar no PDF."
    )
    
    # Aba de navegação principal (Três abas de observabilidade consolidada)
    tab1, tab2, tab3 = st.tabs([
        "📊 Analytics de Calibração & ROI", 
        "⚡ Interactive Playground & Grafos",
        "🔍 Calibração de Pareto & Ablação de Claims"
    ])

    # Importa utilitários visuais
    from groundcite.integrations.visuals import (
        generate_cohens_kappa_gauge,
        generate_reliability_diagram_svg,
        generate_mcnemar_wilcoxon_card,
        generate_pareto_curve_svg_from_config,
        generate_claim_ablation_panel
    )

    # Carrega dados padrão ou enviados pelo usuário
    results_data = []
    if uploaded_file is not None:
        for line in uploaded_file:
            if line.strip():
                results_data.append(json.loads(line))
        st.sidebar.success(f"Carregado: {len(results_data)} registros.")
    else:
        # Tenta carregar os resultados locais do Hybrid exp07 por padrão
        default_path = Path("experiments/exp07_meta_evaluation/results/meta_res_hybrid.jsonl")
        if default_path.exists():
            with open(default_path, "r", encoding="utf-8") as f:
                results_data = [json.loads(line) for line in f if line.strip()]
            st.sidebar.info("Carregado exp07_meta_evaluation por padrão.")
        else:
            st.sidebar.warning("Nenhum arquivo JSONL local encontrado. Envie um arquivo na barra lateral.")

    # Botão corporativo de download de PDF Light Mode
    if results_data:
        st.sidebar.markdown("---")
        st.sidebar.markdown("### 📥 Exportação Executiva")
        from groundcite.integrations.pdf_generator import FactualPDFReportGenerator
        try:
            pdf_gen = FactualPDFReportGenerator(results_data, currency=currency_option, max_samples=int(max_samples_option))
            pdf_buffer = pdf_gen.generate_pdf_buffer()
            st.sidebar.download_button(
                label="📥 Baixar Relatório MLOps em PDF",
                data=pdf_buffer.getvalue(),
                file_name=f"factual_mlops_report_{currency_option.lower()}.pdf",
                mime="application/pdf",
                help="Gera e baixa instantaneamente um relatório em PDF Light Mode elegante e corporativo do lote atual."
            )
        except Exception as e_pdf:
            st.sidebar.error(f"Erro ao preparar exportador PDF: {e_pdf}")

    with tab1:
        st.markdown('<div class="glass-card"><h4>📈 Leaderboard de Calibração & ROI Financeiro</h4>', unsafe_allow_html=True)
        
        if results_data:
            # Métricas agregadas de orçamento
            total_samples = len(results_data)
            total_saved = sum(r.get("cost", {}).get("usd_saved", 0.0) if "cost" in r else r.get("usd_saved", 0.0) for r in results_data)
            total_latency = sum(r.get("cost", {}).get("latency_ms", 0) if "cost" in r else r.get("latency_ms", 0) for r in results_data)
            
            from groundcite.backends.exchange import convert_usd_to
            converted_saved = convert_usd_to(total_saved, currency_option)
            
            c1, c2, c3 = st.columns(3)
            with c1:
                st.metric("Total de Amostras Avaliadas", f"{total_samples} RAG Samples")
            with c2:
                st.metric(
                    f"Orçamento Economizado ({currency_option})",
                    f"{currency_option} {converted_saved:.4f}",
                    delta=f"USD {total_saved:.4f} salvo",
                    delta_color="normal"
                )
            with c3:
                st.metric("Latência Acumulada do Lote", f"{total_latency / 1000:.1f} segundos")

            st.write("---")
            
            # Coleta dados para Cohen's Kappa, ECE e Reliability Diagram
            confs = []
            accs = []
            
            for r in results_data:
                for c in r.get("claims", []):
                    conf = float(c.get("confidence", 1.0))
                    gold = c.get("gold_label")
                    pred = c.get("pred_label")
                    if gold and pred:
                        confs.append(conf)
                        accs.append(1.0 if gold == pred else 0.0)
            
            col_l, col_m, col_r = st.columns([1.1, 0.9, 1.0])
            
            with col_l:
                st.markdown('<div class="metric-title">🎯 Expected Calibration Error (ECE)</div>', unsafe_allow_html=True)
                if confs and accs:
                    svg_rel, ece_val = generate_reliability_diagram_svg(confs, accs)
                    st.components.v1.html(svg_rel, height=300)
                    st.caption(f"**Expected Calibration Error (ECE):** {ece_val:.4f}")
                else:
                    st.caption("Sem dados de gold labels suficientes para diagramar confiabilidade.")
                    
            with col_m:
                st.markdown('<div class="metric-title">Cohen\'s Kappa model-gold</div>', unsafe_allow_html=True)
                if confs and accs:
                    # Computa Kappa de forma simples
                    from sklearn.metrics import cohen_kappa_score
                    y_g = []
                    y_p = []
                    for r in results_data:
                        for c in r.get("claims", []):
                            g = c.get("gold_label")
                            p = c.get("pred_label")
                            if g and p:
                                y_g.append(g)
                                y_p.append(p)
                    if y_g and y_p:
                        kappa = cohen_kappa_score(y_g, y_p)
                        st.components.v1.html(generate_cohens_kappa_gauge(kappa), height=200)
                    else:
                        st.caption("Falta vetor de predição/gabarito.")
                else:
                    st.caption("Aguardando carregamento de gold labels.")
                    
            with col_r:
                st.markdown('<div class="metric-title">📊 Distribuição de Labels</div>', unsafe_allow_html=True)
                labels_count = {"supported": 0, "unsupported": 0, "contradicted": 0}
                for r in results_data:
                    for c in r.get("claims", []):
                        lbl = c.get("pred_label", "unsupported")
                        labels_count[lbl] = labels_count.get(lbl, 0) + 1
                st.bar_chart(labels_count)

            # Injeta o card premium Glassmorphism de McNemar e Wilcoxon
            st.markdown(generate_mcnemar_wilcoxon_card(results_data), unsafe_allow_html=True)
            
        else:
            st.warning("Nenhum dado ativo no momento. Por favor, utilize a barra lateral para carregar um lote JSONL.")
            
        st.markdown('</div>', unsafe_allow_html=True)

    with tab2:
        st.markdown('<div class="glass-card"><h4>⚡ Teste de Groundedness & Grafo de Claims Interativo</h4>', unsafe_allow_html=True)
        st.write("Insira uma premissa (contexto) e uma hipótese (resposta) para realizar a decomposição atômica e ver o grafo semântico ao vivo.")

        ctx_input = st.text_area(
            "Fontes de Contexto / Evidências Fácticas:",
            "O Rio Amazonas desagua no Oceano Atlântico. Ele é o maior rio em volume de água do mundo, nascendo na cordilheira dos Andes.",
            height=100
        )
        
        answer_input = st.text_area(
            "Resposta Gerada pelo RAG (Answer):",
            "O Rio Amazonas desagua no Oceano Pacífico. Ele é o maior rio em volume de água do mundo.",
            height=100
        )
        
        lang_option = st.selectbox("Idioma do Texto:", ["pt-BR", "en"])
        backend_option = st.selectbox("Backend de Avaliação:", ["lexical", "local-nli", "hybrid"])

        if st.button("🚀 Avaliar Groundedness & Gerar Grafo"):
            with st.spinner("Decompondo claims, avaliando faticidade e executando adjudicação semântica vetorial..."):
                from groundcite.schema import Sample, Context
                from groundcite.evaluator import Evaluator
                from groundcite.backends.lexical import LexicalBackend
                from groundcite.backends.local_nli import LocalNLIBackend
                from groundcite.backends.hybrid import HybridBackend
                
                if backend_option == "lexical":
                    backend = LexicalBackend()
                elif backend_option == "local-nli":
                    backend = LocalNLIBackend()
                else:
                    from groundcite.backends.judge_llm import JudgeBackend
                    has_api_key = any(k.startswith("LLM_API_") and k.endswith("_KEY") for k in os.environ)
                    primary = JudgeBackend() if has_api_key else LocalNLIBackend()
                    backend = HybridBackend(primary_backend=primary, pricing_model="gpt-4o")
                    
                evaluator = Evaluator(backend=backend)
                sample = Sample(
                    id="streamlit_live_sample",
                    lang=lang_option,
                    question="Streamlit Live Query",
                    contexts=[Context(doc_id="ctx_1", text=ctx_input)],
                    answer=answer_input
                )
                
                res = evaluator.evaluate(sample)
                
                st.write("---")
                st.markdown("##### 📊 Resumo Factual do RAG")
                
                s1, s2, s3 = st.columns(3)
                with s1:
                    st.metric("Claim Support F1", f"{res.scores.get('claim_support_f1', 0.0):.4f}")
                with s2:
                    st.metric("Span Support F1", f"{res.scores.get('span_support_f1', 0.0):.4f}")
                with s3:
                    st.metric("Abstention Risk Score", f"{res.scores.get('abstention_risk', 0.0):.4f}")

                st.markdown("##### Claims Decompostos & Avaliados:")
                for c in res.claims:
                    lbl = c.get("pred_label", "unsupported")
                    color = "#10b981" if lbl == "supported" else ("#ef4444" if lbl == "contradicted" else "#f59e0b")
                    st.markdown(
                        f"<div style='border-left: 5px solid {color}; padding: 0.5rem 1rem; margin-bottom: 0.5rem; background-color: rgba(30, 41, 59, 0.2);'>"
                        f"<strong>Claim:</strong> {c.get('text')}<br>"
                        f"<strong>Label:</strong> <span style='color:{color}; font-weight:bold;'>{lbl.upper()}</span> (Confiança: {c.get('confidence', 0.0):.3f})"
                        f"</div>",
                        unsafe_allow_html=True
                    )

                mermaid_code = res.cost.get("entailment_mermaid")
                if mermaid_code:
                    st.markdown("##### 🧠 Grafo Lógico de Claims & Adjudicação Semântica (Mermaid.js)")
                    html_code = f"""
                    <div class="mermaid" style="background-color: #0f172a; padding: 1.5rem; border-radius: 8px; border: 1px solid #334155; display: flex; justify-content: center;">
                    {mermaid_code}
                    </div>
                    <script type="module">
                        import mermaid from 'https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.esm.min.mjs';
                        mermaid.initialize({{ startOnLoad: true, theme: 'dark' }});
                    </script>
                    """
                    st.components.v1.html(html_code, height=350, scrolling=True)

        st.markdown('</div>', unsafe_allow_html=True)

    with tab3:
        st.markdown('<div class="glass-card"><h4>🔍 Otimização de Pareto & Painel de Ablação (RQ2 & RQ3)</h4>', unsafe_allow_html=True)
        st.write("Analise a eficiência de calibração paramétrica de custos e a validade científica de claim decomposition contra predições holísticas.")
        
        # 1. Pareto Frontier
        st.markdown(generate_pareto_curve_svg_from_config(), unsafe_allow_html=True)
        
        # 2. Ablação de Claims Regex vs LLM
        if results_data:
            st.markdown(generate_claim_ablation_panel(results_data), unsafe_allow_html=True)
        else:
            st.warning("Envie dados de resultados JSONL para recalcular as estatísticas de ablação.")
            
        st.markdown('</div>', unsafe_allow_html=True)

if __name__ == "__main__":
    run_app()
