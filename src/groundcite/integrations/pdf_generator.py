import io
from pathlib import Path
from typing import List, Dict, Any
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, Image, KeepTogether
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch

from groundcite.backends.exchange import convert_usd_to

class FactualPDFReportGenerator:
    """
    Gerador de Relatórios Corporativos em PDF (ReportLab) com design profissional Light Mode.
    Consolida métricas científicas, ROI financeiro multi-moedas, ablação e top claims alucinados.
    """
    
    def __init__(self, results: List[Dict[str, Any]], currency: str = "BRL", max_samples: int = 5):
        self.results = results
        self.currency = currency.upper().strip()
        self.max_samples = max_samples
        
    def _generate_plots_images(self) -> tuple:
        """
        Gera os gráficos de calibração e ROI usando matplotlib e retorna instâncias de Image do ReportLab.
        """
        import matplotlib.pyplot as plt
        import numpy as np
        
        # 1. Gráfico de Calibração (Reliability Diagram)
        confs = []
        accs = []
        for r in self.results:
            for c in r.get("claims", []):
                conf = float(c.get("confidence", 1.0))
                g = c.get("gold_label")
                p = c.get("pred_label")
                if g and p:
                    confs.append(conf)
                    accs.append(1.0 if g == p else 0.0)
                    
        calib_img = None
        if confs and accs:
            # Plota reliability diagram em matplotlib
            fig, ax = plt.subplots(figsize=(3.0, 2.0), dpi=150)
            
            # Divide em 5 bins
            bins = np.linspace(0, 1.0, 6)
            bin_ids = np.digitize(confs, bins) - 1
            
            bin_confs = []
            bin_accs = []
            
            for j in range(5):
                mask = bin_ids == j
                size = np.sum(mask)
                if size > 0:
                    bin_confs.append(np.mean(np.array(confs)[mask]))
                    bin_accs.append(np.mean(np.array(accs)[mask]))
                else:
                    bin_confs.append(0.0)
                    bin_accs.append(0.0)
            
            # Reta diagonal ideal y=x
            ax.plot([0, 1], [0, 1], linestyle="--", color="gray", label="Ideal")
            # Barras reais
            x_pos = [(bins[k] + bins[k+1])/2 for k in range(5)]
            ax.bar(x_pos, bin_accs, width=0.16, color="#0f766e", alpha=0.85, edgecolor="#0d5c56", label="Acurácia")
            
            ax.set_xlim(0, 1.0)
            ax.set_ylim(0, 1.0)
            ax.set_xlabel("Confiança do Juiz", fontsize=7)
            ax.set_ylabel("Acurácia Factual", fontsize=7)
            ax.tick_params(axis='both', which='major', labelsize=6)
            ax.set_title("Diagrama de Confiabilidade (ECE)", fontsize=8, fontweight="bold", color="#1e3a8a")
            ax.legend(fontsize=6, loc="upper left")
            ax.grid(True, linestyle=":", alpha=0.5)
            
            img_buf = io.BytesIO()
            plt.savefig(img_buf, format='png', bbox_inches='tight', dpi=150)
            img_buf.seek(0)
            plt.close(fig)
            calib_img = Image(img_buf, width=2.4*inch, height=1.6*inch)
            
        # 2. Gráfico de ROI (Rosca de Custos Evitados)
        total_saved = sum(r.get("cost", {}).get("usd_saved", 0.0) if "cost" in r else r.get("usd_saved", 0.0) for r in self.results)
        total_estimate = sum(r.get("cost", {}).get("usd_estimate", 0.0) if "cost" in r else r.get("usd_estimate", 0.0) for r in self.results)
        total_cost_without = total_saved + total_estimate
        
        roi_img = None
        if total_cost_without > 0:
            fig, ax = plt.subplots(figsize=(3.0, 2.0), dpi=150)
            labels = ['Economia', 'Gasto']
            sizes = [total_saved, total_estimate]
            colors_list = ['#10b981', '#ef4444']
            
            # Plota gráfico de pizza com donut hole
            wedges, texts, autotexts = ax.pie(
                sizes, 
                labels=labels, 
                colors=colors_list, 
                autopct='%1.1f%%',
                startangle=90, 
                textprops=dict(color="#334155", fontsize=6),
                wedgeprops=dict(width=0.4, edgecolor='white', linewidth=1.5)
            )
            for autotext in autotexts:
                autotext.set_fontsize(6)
                autotext.set_weight('bold')
                
            ax.set_title("Eficiência de Custos (ROI)", fontsize=8, fontweight="bold", color="#1e3a8a")
            
            img_buf = io.BytesIO()
            plt.savefig(img_buf, format='png', bbox_inches='tight', dpi=150)
            img_buf.seek(0)
            plt.close(fig)
            roi_img = Image(img_buf, width=2.4*inch, height=1.6*inch)
            
        return calib_img, roi_img
        
    def generate_pdf_buffer(self) -> io.BytesIO:
        """
        Gera o relatório corporativo em PDF em buffer de bytes para download em memória.
        """
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=letter,
            rightMargin=36,
            leftMargin=36,
            topMargin=36,
            bottomMargin=36
        )
        
        styles = getSampleStyleSheet()
        
        # Paleta de cores corporativa clara (Light Mode)
        color_primary = colors.HexColor("#1e3a8a")     # Azul escuro corporativo
        color_secondary = colors.HexColor("#0f766e")   # Verde escuro HSL
        color_text = colors.HexColor("#334155")        # Slate escuro
        color_border = colors.HexColor("#cbd5e1")      # Slate claro
        color_bg_header = colors.HexColor("#f1f5f9")   # Slate super claro
        
        # Estilos tipográficos polidos
        title_style = ParagraphStyle(
            'DocTitle',
            parent=styles['Normal'],
            fontName='Helvetica-Bold',
            fontSize=22,
            leading=26,
            textColor=color_primary,
            spaceAfter=12
        )
        
        subtitle_style = ParagraphStyle(
            'DocSubtitle',
            parent=styles['Normal'],
            fontName='Helvetica',
            fontSize=10,
            leading=14,
            textColor=color_text,
            spaceAfter=20
        )
        
        h2_style = ParagraphStyle(
            'SectionHeader',
            parent=styles['Normal'],
            fontName='Helvetica-Bold',
            fontSize=14,
            leading=18,
            textColor=color_primary,
            spaceBefore=14,
            spaceAfter=8,
            keepWithNext=True
        )
        
        body_style = ParagraphStyle(
            'BodyStyle',
            parent=styles['Normal'],
            fontName='Helvetica',
            fontSize=9,
            leading=13,
            textColor=color_text
        )
        
        body_bold_style = ParagraphStyle(
            'BodyBoldStyle',
            parent=styles['Normal'],
            fontName='Helvetica-Bold',
            fontSize=9,
            leading=13,
            textColor=color_text
        )
        
        code_style = ParagraphStyle(
            'CodeStyle',
            parent=styles['Normal'],
            fontName='Courier',
            fontSize=8,
            leading=10,
            textColor=colors.HexColor("#475569")
        )
        
        th_style = ParagraphStyle(
            'TableHeader',
            parent=styles['Normal'],
            fontName='Helvetica-Bold',
            fontSize=9,
            leading=11,
            textColor=colors.white
        )
        
        story = []
        
        # 1. Cabeçalho Corporativo
        story.append(Paragraph("GroundCite MLOps & Factual Audit Report", title_style))
        story.append(Paragraph(
            f"Relatório executivo automatizado de calibração fática, análise de retorno de investimento (ROI) "
            f"e conformidade de alucinações para sistemas RAG. Gerado em moeda local de destino: **{self.currency}**.",
            subtitle_style
        ))
        story.append(Spacer(1, 10))
        
        # 2. Resumo de Metadados do Lote
        total_samples = len(self.results)
        total_claims = 0
        supported_claims = 0
        unsupported_claims = 0
        contradicted_claims = 0
        
        for r in self.results:
            for c in r.get("claims", []):
                total_claims += 1
                lbl = c.get("pred_label", "unsupported")
                if lbl == "supported":
                    supported_claims += 1
                elif lbl == "contradicted":
                    contradicted_claims += 1
                else:
                    unsupported_claims += 1
                    
        meta_data = [
            [Paragraph("Métrica do Lote", th_style), Paragraph("Total Encontrado", th_style)],
            [Paragraph("Total de Respostas Avaliadas", body_bold_style), Paragraph(str(total_samples), body_style)],
            [Paragraph("Total de Claims Extraídos", body_bold_style), Paragraph(str(total_claims), body_style)],
            [Paragraph("Claims Suportados (Grounded)", body_bold_style), Paragraph(f"{supported_claims} ({ (supported_claims/total_claims*100):.1f}% se total > 0 else 0.0)", body_style) if total_claims > 0 else Paragraph("0", body_style)],
            [Paragraph("Claims Não Suportados (Alucinações)", body_bold_style), Paragraph(f"{unsupported_claims} ({ (unsupported_claims/total_claims*100):.1f}% se total > 0 else 0.0)", body_style) if total_claims > 0 else Paragraph("0", body_style)],
            [Paragraph("Claims Contraditados (Erros Críticos)", body_bold_style), Paragraph(f"{contradicted_claims} ({ (contradicted_claims/total_claims*100):.1f}% se total > 0 else 0.0)", body_style) if total_claims > 0 else Paragraph("0", body_style)]
        ]
        
        meta_table = Table(meta_data, colWidths=[250, 250])
        meta_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), color_primary),
            ('ALIGN', (0,0), (-1,-1), 'LEFT'),
            ('BOTTOMPADDING', (0,0), (-1,0), 6),
            ('TOPPADDING', (0,0), (-1,0), 6),
            ('GRID', (0,0), (-1,-1), 0.5, color_border),
            ('BACKGROUND', (0,1), (-1,-1), color_bg_header),
            ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, color_bg_header]),
            ('BOTTOMPADDING', (0,1), (-1,-1), 5),
            ('TOPPADDING', (0,1), (-1,-1), 5),
        ]))
        
        story.append(Paragraph("📋 Resumo Operacional do Lote", h2_style))
        story.append(meta_table)
        story.append(Spacer(1, 15))
        
        # 3. Métricas Científicas & Calibração
        # Computa F1, Kappa e ECE dinâmicos
        confs = []
        accs = []
        y_g = []
        y_p = []
        
        for r in self.results:
            for c in r.get("claims", []):
                conf = float(c.get("confidence", 1.0))
                g = c.get("gold_label")
                p = c.get("pred_label")
                if g and p:
                    confs.append(conf)
                    accs.append(1.0 if g == p else 0.0)
                    y_g.append(g)
                    y_p.append(p)
                    
        f1_val = 0.0
        kappa_val = 0.0
        ece_val = 0.0
        
        if y_g and y_p:
            from sklearn.metrics import f1_score, cohen_kappa_score
            from groundcite.integrations.visuals import calculate_ece_and_bins
            f1_val = f1_score(y_g, y_p, average="macro", zero_division=0)
            kappa_val = cohen_kappa_score(y_g, y_p)
            _, ece_val = calculate_ece_and_bins(confs, accs)
            
        scientific_data = [
            [Paragraph("Métrica Científica", th_style), Paragraph("Pontuação / Score", th_style), Paragraph("Classificação Factual (Landis & Koch)", th_style)],
            [Paragraph("Macro F1-Score (Acurácia Global)", body_bold_style), Paragraph(f"{f1_val:.4f}", body_style), Paragraph("N/A (Métrica de Classificação)", body_style)],
            [Paragraph("Cohen's Kappa (Inter-Annotator Agreement)", body_bold_style), Paragraph(f"{kappa_val:.4f}", body_style), Paragraph(
                "Acordo Quase Perfeito" if kappa_val > 0.80 else ("Acordo Substancial" if kappa_val > 0.60 else "Acordo Moderado/Baixo"), body_style
            )],
            [Paragraph("Expected Calibration Error (ECE)", body_bold_style), Paragraph(f"{ece_val:.4f}", body_style), Paragraph(
                "Alta Calibração (Incerteza Mínima)" if ece_val < 0.12 else "Descalibração Moderada", body_style
            )]
        ]
        
        sci_table = Table(scientific_data, colWidths=[200, 120, 180])
        sci_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), color_secondary),
            ('ALIGN', (0,0), (-1,-1), 'LEFT'),
            ('BOTTOMPADDING', (0,0), (-1,0), 6),
            ('TOPPADDING', (0,0), (-1,0), 6),
            ('GRID', (0,0), (-1,-1), 0.5, color_border),
            ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, color_bg_header]),
            ('BOTTOMPADDING', (0,1), (-1,-1), 5),
            ('TOPPADDING', (0,1), (-1,-1), 5),
        ]))
        
        story.append(Paragraph("🎯 Desempenho Estatístico & Validade Científica", h2_style))
        story.append(sci_table)
        story.append(Spacer(1, 15))
        
        # 4. Análise Financeira & Retorno de Investimento (ROI)
        total_saved = sum(r.get("cost", {}).get("usd_saved", 0.0) if "cost" in r else r.get("usd_saved", 0.0) for r in self.results)
        total_estimate = sum(r.get("cost", {}).get("usd_estimate", 0.0) if "cost" in r else r.get("usd_estimate", 0.0) for r in self.results)
        total_cost_without = total_saved + total_estimate
        roi_percent = (total_saved / total_cost_without * 100.0) if total_cost_without > 0 else 0.0
        
        converted_saved = convert_usd_to(total_saved, self.currency)
        converted_estimate = convert_usd_to(total_estimate, self.currency)
        converted_without = convert_usd_to(total_cost_without, self.currency)
        
        financial_data = [
            [Paragraph("Métrica Financeira", th_style), Paragraph("Dólar (Universal USD)", th_style), Paragraph(f"Moeda Local de Destino ({self.currency})", th_style)],
            [Paragraph("Custo Real de API (Gastos Efetuados)", body_bold_style), Paragraph(f"USD {total_estimate:.5f}", body_style), Paragraph(f"{self.currency} {converted_estimate:.5f}", body_style)],
            [Paragraph("Custo Evitado (Economia no Fast-Path)", body_bold_style), Paragraph(f"USD {total_saved:.5f}", body_style), Paragraph(f"{self.currency} {converted_saved:.5f}", body_style)],
            [Paragraph("Custo Equivalente Sem GroundCite", body_bold_style), Paragraph(f"USD {total_cost_without:.5f}", body_style), Paragraph(f"{self.currency} {converted_without:.5f}", body_style)],
            [Paragraph("Eficiência de ROI (Fração Economizada)", body_bold_style), Paragraph(f"{roi_percent:.1f}%", body_bold_style), Paragraph(f"{roi_percent:.1f}%", body_bold_style)]
        ]
        
        fin_table = Table(financial_data, colWidths=[200, 150, 150])
        fin_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), color_primary),
            ('ALIGN', (0,0), (-1,-1), 'LEFT'),
            ('BOTTOMPADDING', (0,0), (-1,0), 6),
            ('TOPPADDING', (0,0), (-1,0), 6),
            ('GRID', (0,0), (-1,-1), 0.5, color_border),
            ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, color_bg_header]),
            ('BOTTOMPADDING', (0,1), (-1,-1), 5),
            ('TOPPADDING', (0,1), (-1,-1), 5),
            ('BACKGROUND', (0,4), (-1,4), colors.HexColor("#ecfdf5")), # Realce verde claro no ROI
        ]))
        
        story.append(Paragraph("💰 Retorno de Investimento (ROI) & Eficiência de Custos", h2_style))
        story.append(financial_data_p := Paragraph(
            f"Graças ao motor híbrido do GroundCite que intercepta termos deterministicamente sem chamadas caras na nuvem, "
            f"este lote obteve **{roi_percent:.1f}%** de economia real!", body_style
        ))
        story.append(Spacer(1, 5))
        story.append(fin_table)
        story.append(Spacer(1, 10))
        
        # Adiciona gráficos analíticos lado a lado em uma tabela (Fase 17)
        calib_img, roi_img = self._generate_plots_images()
        if calib_img or roi_img:
            story.append(Paragraph("📊 Visualização Gráfica Analítica", h2_style))
            charts_data = [[calib_img or "", roi_img or ""]]
            charts_table = Table(charts_data, colWidths=[250, 250])
            charts_table.setStyle(TableStyle([
                ('ALIGN', (0,0), (-1,-1), 'CENTER'),
                ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
                ('BOTTOMPADDING', (0,0), (-1,-1), 0),
                ('TOPPADDING', (0,0), (-1,-1), 0),
            ]))
            story.append(charts_table)
        
        # 5. Top Amostras e Detalhamento de Alucinações (Top Falhas com falhas)
        story.append(PageBreak()) # Quebra de página para relatórios longos
        
        story.append(Paragraph("🔍 Auditoria de Qualidade: Top Falhas Fácticas (Alucinações)", h2_style))
        story.append(Paragraph(
            "Detalhamento das amostras que apresentaram falhas de conformidade fáctica "
            "(claims não suportados ou explicitamente contraditados nas fontes evidenciadas). "
            "Abaixo de cada tabela, é renderizada a árvore de dependências e decomposição lógica de claims.", body_style
        ))
        story.append(Spacer(1, 10))
        
        count_fails = 0
        for r in self.results:
            claims = r.get("claims", [])
            unsupported = [c for c in claims if c.get("pred_label") in ("unsupported", "contradicted")]
            
            if unsupported:
                count_fails += 1
                sample_id = r.get("id", "N/A")
                lang = r.get("lang", "N/A")
                
                story.append(Paragraph(f"<b>Amostra ID: {sample_id} ({lang})</b>", body_bold_style))
                story.append(Spacer(1, 3))
                
                fail_data = [
                    [Paragraph("ID", th_style), Paragraph("Fato / Claim Decomposto", th_style), Paragraph("Status Fáctico", th_style), Paragraph("Confiança", th_style)]
                ]
                
                for idx, c in enumerate(claims):
                    lbl = c.get("pred_label", "unsupported").upper()
                    if lbl in ("UNSUPPORTED", "CONTRADICTED"):
                        lbl_color = "#ef4444" if lbl == "CONTRADICTED" else "#f97316"
                        lbl_str = f"<font color='{lbl_color}'><b>{lbl}</b></font>"
                    else:
                        lbl_str = "<font color='#10b981'><b>SUPPORTED</b></font>"
                    
                    fail_data.append([
                        Paragraph(f"c{idx+1}", code_style),
                        Paragraph(c.get("text", ""), body_style),
                        Paragraph(lbl_str, body_style),
                        Paragraph(f"{c.get('confidence', 0.0):.3f}", body_style)
                    ])
                    
                fail_table = Table(fail_data, colWidths=[40, 310, 90, 60])
                fail_table.setStyle(TableStyle([
                    ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#475569")),
                    ('ALIGN', (0,0), (-1,-1), 'LEFT'),
                    ('GRID', (0,0), (-1,-1), 0.5, color_border),
                    ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, color_bg_header]),
                    ('BOTTOMPADDING', (0,0), (-1,-1), 4),
                    ('TOPPADDING', (0,0), (-1,-1), 4),
                ]))
                
                story.append(fail_table)
                story.append(Spacer(1, 6))
                
                # Representação estruturada com recuos da árvore de dependência do grafo (Árvore de Falhas)
                mermaid_code = r.get("cost", {}).get("entailment_mermaid", "")
                adj = {}
                in_degree = {}
                for idx, c in enumerate(claims):
                    c_idx = c.get("id") or f"c{idx+1}"
                    adj[c_idx] = []
                    in_degree[c_idx] = 0
                
                # Procura por arestas ex: c1 --> c2 ou c1 -->c2
                import re
                if mermaid_code:
                    edges = re.findall(r"(\w+)\s*-->\s*(\w+)", mermaid_code)
                    for src, tgt in edges:
                        if src in adj and tgt in adj:
                            adj[src].append(tgt)
                            in_degree[tgt] += 1
                
                roots = [node for node, deg in in_degree.items() if deg == 0]
                if not roots and claims:
                    roots = [f"c{idx+1}" for idx in range(len(claims))]
                
                story.append(Paragraph("<b>Hierarquia e Dependência Factual de Claims (Árvore de Falhas):</b>", body_bold_style))
                story.append(Spacer(1, 2))
                
                def render_tree(node_id, prefix=""):
                    claim_obj = None
                    try:
                        c_num = int(node_id[1:]) - 1
                        if 0 <= c_num < len(claims):
                            claim_obj = claims[c_num]
                    except Exception:
                        pass
                    
                    if not claim_obj:
                        return []
                        
                    lbl = claim_obj.get("pred_label", "unsupported").upper()
                    lbl_color = "#ef4444" if lbl == "CONTRADICTED" else ("#f97316" if lbl == "UNSUPPORTED" else "#10b981")
                    text = claim_obj.get("text", "")
                    
                    line = f"{prefix}└─ <b>{node_id}</b> [<font color='{lbl_color}'><b>{lbl}</b></font>]: {text}"
                    res_paragraphs = [Paragraph(line, body_style), Spacer(1, 2)]
                    
                    children = adj.get(node_id, [])
                    for child in children:
                        res_paragraphs.extend(render_tree(child, prefix + "&nbsp;&nbsp;&nbsp;&nbsp;"))
                    return res_paragraphs
                
                for r_node in roots:
                    story.extend(render_tree(r_node))
                
                story.append(Spacer(1, 10))
                
                if count_fails >= self.max_samples:
                    break
                    
        if count_fails == 0:
            story.append(Paragraph("✨ <i>Excelente! Nenhuma resposta alucinada ou contraditória foi encontrada neste lote.</i>", body_style))
            
        # 6. Top Amostras com Calibração Factual Perfeita (Top Grounded)
        story.append(Spacer(1, 10))
        story.append(Paragraph("✨ Conformidade Factual Exemplar (Top Grounded)", h2_style))
        story.append(Paragraph(
            "Listagem das principais amostras que demonstraram 100% de precisão de groundedness "
            "sem nenhuma alucinação ou contradição fáctica detectada pelas fontes.", body_style
        ))
        story.append(Spacer(1, 10))
        
        count_success = 0
        for r in self.results:
            claims = r.get("claims", [])
            unsupported = [c for c in claims if c.get("pred_label") in ("unsupported", "contradicted")]
            
            if not unsupported and claims:
                count_success += 1
                sample_id = r.get("id", "N/A")
                lang = r.get("lang", "N/A")
                
                story.append(Paragraph(f"<b>Amostra ID: {sample_id} ({lang})</b>", body_bold_style))
                story.append(Spacer(1, 3))
                
                success_data = [
                    [Paragraph("ID", th_style), Paragraph("Fato / Claim Suportado pelas Fontes", th_style), Paragraph("Status", th_style), Paragraph("Confiança", th_style)]
                ]
                
                for idx, c in enumerate(claims):
                    success_data.append([
                        Paragraph(f"c{idx+1}", code_style),
                        Paragraph(c.get("text", ""), body_style),
                        Paragraph("<font color='#10b981'><b>SUPPORTED</b></font>", body_style),
                        Paragraph(f"{c.get('confidence', 1.0):.3f}", body_style)
                    ])
                    
                success_table = Table(success_data, colWidths=[40, 310, 90, 60])
                success_table.setStyle(TableStyle([
                    ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#0f766e")),
                    ('ALIGN', (0,0), (-1,-1), 'LEFT'),
                    ('GRID', (0,0), (-1,-1), 0.5, color_border),
                    ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, color_bg_header]),
                    ('BOTTOMPADDING', (0,0), (-1,-1), 4),
                    ('TOPPADDING', (0,0), (-1,-1), 4),
                ]))
                
                story.append(success_table)
                story.append(Spacer(1, 10))
                
                if count_success >= self.max_samples:
                    break
                    
        if count_success == 0:
            story.append(Paragraph("<i>Nenhuma amostra com 100% de conformidade factual foi encontrada neste lote.</i>", body_style))
            
        doc.build(story)
        buffer.seek(0)
        return buffer
        
    def export_pdf_file(self, file_path: str) -> None:
        """
        Gera e salva o PDF físico diretamente em arquivo.
        """
        p = Path(file_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        buffer = self.generate_pdf_buffer()
        with open(p, "wb") as f:
            f.write(buffer.read())
