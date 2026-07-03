import re
import random
import logging
from typing import List, Optional, Dict, Any
from groundcite.schema import Sample, GoldSchema, GoldClaim, EvidenceSpan

logger = logging.getLogger(__name__)

class PerturbationEngine:
    """
    Motor para corromper respostas RAG suportadas automaticamente.
    Usado para gerar datasets sintéticos de teste de estresse (RAGStress v2) com consistência de Gold labels.
    """

    @staticmethod
    def _negate_text(text: str) -> str:
        """Heurística simples que adiciona 'não' após o primeiro verbo/auxiliar encontrado."""
        words = text.split()
        if len(words) > 1:
            words.insert(1, "não")
        return " ".join(words)

    @staticmethod
    def _swap_numbers(text: str) -> str:
        """Encontra números na resposta e os altera para criar contradições numéricas factuais."""
        def repl(match):
            val_str = match.group(0)
            try:
                val = int(val_str)
                noise = random.randint(10, 100)
                return str(val + noise)
            except ValueError:
                return val_str
                
        return re.sub(r'\b\d+\b', repl, text)
        
    @staticmethod
    def _inject_hallucination(text: str) -> str:
        """
        Retorna uma alucinação dinâmica e contextualmente pareada com o próprio texto da resposta.
        Extrai palavras-chave do texto (como palavras capitalizadas ou maiores de 5 caracteres)
        para gerar uma injeção de alucinação sintética que soe muito mais realista e acoplada.
        """
        # Extrai palavras candidatas a entidades (palavras capitalizadas ou maiores que 5 caracteres)
        words = [w.strip(".,;:?!()") for w in text.split()]
        candidates = [w for w in words if len(w) > 5 and w[0].isupper()]
        
        # Fallback se não achar palavras capitalizadas longas: pega as maiores palavras
        if not candidates:
            candidates = [w for w in words if len(w) > 6]
            
        entity = random.choice(candidates) if candidates else "o projeto"
        
        hallucinations = [
            f" Além disso, foi confirmado que o impacto direto de {entity} foi integralmente cancelado no Brasil.",
            f" No entanto, documentos recentes provam que a eficácia real sobre {entity} é nula.",
            f" Embora o autor de {entity} negue publicamente, a auditoria externa suspendeu esta operação.",
            f" Contudo, relatórios fiscais mostram que os investimentos em {entity} geraram prejuízo acumulado."
        ]
        return random.choice(hallucinations)

    @staticmethod
    def _apply_pt_telemarketing(text: str) -> str:
        """Substitui expressões verbais por gerúndio prolixo redundante/estilo telemarketing."""
        replacements = {
            r'\bvou enviar\b': "vou estar enviando",
            r'\bvamos fazer\b': "estaremos executando",
            r'\bvou analisar\b': "vou estar analisando",
            r'\bvai ajudar\b': "estará ajudando",
            r'\benviarei\b': "vou estar enviando",
            r'\banalisarei\b': "vou estar analisando",
            r'\bgarante\b': "estará garantindo"
        }
        perturbed = text
        for pat, rep in replacements.items():
            perturbed = re.sub(pat, rep, perturbed, flags=re.IGNORECASE)
            
        if perturbed == text:
            # Se não bateu nenhum padrão, injeta uma prolixidade típica no início
            perturbed = "Estaremos providenciando a informação de que " + text[0].lower() + text[1:]
            
        return perturbed

    @staticmethod
    def _apply_language_hallucination(text: str) -> str:
        """
        Substitui palavras e expressões corretas em português por falsos cognatos induzidos pelo inglês (EN->PT).
        Distorce o sentido factual de forma sutil, gerando contradições difíceis de detectar por LLMs EN-centric.
        """
        replacements = {
            r'\bpercebeu o erro\b': "realizou o erro",
            r'\bpercebeu que\b': "realizou que",
            r'\bfingiu ser\b': "pretendeu ser",
            r'\bfingiu estar\b': "pretendeu estar",
            r'\benviou as alterações\b': "puxou as alterações",
            r'\benviou o código\b': "puxou o código",
            r'\bNa verdade\b': "Atualmente",
            r'\bna verdade\b': "atualmente",
            r'\boriginalidade do\b': "novidade do",
            r'\bapoia o uso\b': "suporta o uso",
            r'\bapoia a decisão\b': "suporta a decisão",
        }
        perturbed = text
        for pat, rep in replacements.items():
            perturbed = re.sub(pat, rep, perturbed, flags=re.IGNORECASE)
            
        if perturbed == text:
            word_replacements = {
                r'\bpercebeu\b': "realizou",
                r'\bfingiu\b': "pretendeu",
                r'\benviou\b': "puxou",
                r'\bna verdade\b': "atualmente",
                r'\bapoia\b': "suporta"
            }
            for pat, rep in word_replacements.items():
                perturbed = re.sub(pat, rep, perturbed, flags=re.IGNORECASE)
                
        return perturbed

    @classmethod
    def perturb(cls, sample: Sample, strategy: str = "number_swap") -> Sample:
        """
        Recebe um Sample suportado e gera uma versão corrompida preservando/reconstruindo o GoldSchema.
        
        Estratégias:
        - 'number_swap': Altera os números da resposta (Contradicted)
        - 'negation': Inverte a semântica da resposta (Contradicted)
        - 'injection': Insere text irrelevante no fim (Unsupported)
        - 'pt_telemarketing': Insere gerúndio redundante prolixo (Supported/Style stress)
        - 'language_induced_hallucination': Tradução latente com falsos cognatos cross-lingua EN->PT (Contradicted)
        - 'conflicting_context': Gera contradição interna nas fontes contextuais e resposta unilateral (CSA Contradicted)
        """
        new_sample = sample.model_copy(deep=True)
        new_sample.id = f"{sample.id}_perturb_{strategy}"
        
        hallucination_text = ""
        
        # Estratégia de conflito de contexto precisa reestruturar os contextos
        if strategy == "conflicting_context":
            # Criamos dois contextos mutuamente contraditórios
            if not sample.contexts:
                logger.warning("Sample sem contextos para aplicar 'conflicting_context'.")
                return new_sample
                
            base_ctx = sample.contexts[0]
            ctx_a = base_ctx.model_copy(deep=True)
            ctx_a.doc_id = "doc_conflicting_a"
            ctx_a.text = "De acordo com o relatório anual corporativo de 2023, o lucro líquido consolidado do grupo foi de exatamente 10 milhões de reais."
            ctx_a.title = "Relatório Corporativo A"
            
            ctx_b = base_ctx.model_copy(deep=True)
            ctx_b.doc_id = "doc_conflicting_b"
            ctx_b.text = "O relatório de auditoria fiscal independente declarou expressamente que o lucro líquido consolidado do grupo em 2023 foi de 5 milhões de reais."
            ctx_b.title = "Relatório Auditoria B"
            
            new_sample.contexts = [ctx_a, ctx_b]
            # Resposta escolhe arbitrariamente o lado A sem relatar conflito
            new_sample.answer = "O lucro líquido consolidado da empresa em 2023 foi de 10 milhões de reais."
            
            # Anota no Gold como contradicted sob adjudicação CSA
            new_sample.gold = GoldSchema(
                claims=[
                    GoldClaim(
                        claim_id=f"{new_sample.id}_c1",
                        text="O lucro líquido consolidado da empresa em 2023 foi de 10 milhões de reais.",
                        label="contradicted",  # É contradito pelo doc B nas fontes conflitantes
                        evidence=[
                            EvidenceSpan(doc_id="doc_conflicting_a", start=0, end=len(ctx_a.text))
                        ]
                    )
                ],
                unsupported_spans=[]
            )
            
            if new_sample.metadata is None:
                new_sample.metadata = {}
            new_sample.metadata["perturbation_strategy"] = strategy
            new_sample.metadata["is_synthetic"] = True
            new_sample.metadata["has_conflicting_sources"] = True
            return new_sample

        # 1. Executa a perturbação no texto da resposta
        if strategy == "number_swap":
            new_sample.answer = cls._swap_numbers(sample.answer)
        elif strategy == "negation":
            new_sample.answer = cls._negate_text(sample.answer)
        elif strategy == "injection":
            hallucination_text = cls._inject_hallucination(sample.answer)
            new_sample.answer = sample.answer + hallucination_text
        elif strategy == "pt_telemarketing":
            new_sample.answer = cls._apply_pt_telemarketing(sample.answer)
        elif strategy == "language_induced_hallucination":
            new_sample.answer = cls._apply_language_hallucination(sample.answer)
        else:
            logger.warning(f"Estratégia '{strategy}' desconhecida. Retornando inalterado.")
            return new_sample

        # 2. Reconstrói o GoldSchema preservando a compatibilidade metodológica
        if sample.gold is not None:
            new_claims = []
            new_unsupported_spans = list(sample.gold.unsupported_spans)
            
            for gc in sample.gold.claims:
                gc_copy = gc.model_copy(deep=True)
                
                if strategy == "number_swap":
                    perturbed_text = cls._swap_numbers(gc.text)
                    if perturbed_text != gc.text:
                        gc_copy.text = perturbed_text
                        gc_copy.label = "contradicted"
                elif strategy == "negation":
                    gc_copy.text = cls._negate_text(gc.text)
                    gc_copy.label = "contradicted"
                elif strategy == "pt_telemarketing":
                    gc_copy.text = cls._apply_pt_telemarketing(gc.text)
                elif strategy == "language_induced_hallucination":
                    perturbed_text = cls._apply_language_hallucination(gc.text)
                    gc_copy.text = perturbed_text
                    gc_copy.label = "contradicted"
                    
                new_claims.append(gc_copy)
                
            if strategy == "injection" and hallucination_text:
                h_clean = hallucination_text.strip()
                new_claims.append(GoldClaim(
                    claim_id=f"{sample.id}_c_perturb_inj",
                    text=h_clean,
                    label="unsupported",
                    evidence=[]
                ))
                
                start_pos = len(sample.answer)
                end_pos = len(new_sample.answer)
                new_unsupported_spans.append({
                    "start": start_pos,
                    "end": end_pos,
                    "text": h_clean
                })
                
            new_sample.gold = GoldSchema(
                claims=new_claims,
                unsupported_spans=new_unsupported_spans
            )

        if new_sample.metadata is None:
            new_sample.metadata = {}
        new_sample.metadata["perturbation_strategy"] = strategy
        new_sample.metadata["is_synthetic"] = True
        
        return new_sample

    @classmethod
    def generate_stress_dataset(cls, original_samples: List[Sample], output_path: str):
        """
        Aplica todas as estratégias destrutivas/estilísticas em lote e escreve o JSONL.
        """
        strategies = ["number_swap", "negation", "injection", "pt_telemarketing", "language_induced_hallucination", "conflicting_context"]
        corrupted_samples = []
        
        for sample in original_samples:
            for strategy in strategies:
                corrupt = cls.perturb(sample, strategy)
                corrupted_samples.append(corrupt)
                
        import json
        from pathlib import Path
        
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(path, "w", encoding="utf-8") as f:
            for s in corrupted_samples:
                f.write(s.model_dump_json() + "\n")
                
        logger.info(f"RAGStress v2: Gerado dataset sintético com {len(corrupted_samples)} exemplos perturbados em {path}")
