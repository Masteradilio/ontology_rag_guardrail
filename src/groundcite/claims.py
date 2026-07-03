import re
import os
import json
import logging
from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Tuple

logger = logging.getLogger(__name__)

try:
    import litellm
    litellm.drop_params = True
except ImportError:
    litellm = None

# Mapeamento de abreviações comuns para placeholders para evitar quebras falsas de sentença.
# Ordenado do maior para o menor para evitar substituições parciais (ex: U.S.A. antes de U.S.).
MAP_ABBREVIATIONS = {
    "U.S.A.": "___USA_PLACEHOLDER___",
    "p.ex.": "___PEX_PLACEHOLDER___",
    "Prof.": "___PROF_PLACEHOLDER___",
    "Apto.": "___APTO_PLACEHOLDER___",
    "Ltda.": "___LTDA_PLACEHOLDER___",
    "e.g.": "___EG_PLACEHOLDER___",
    "i.e.": "___IE_PLACEHOLDER___",
    "U.S.": "___US_PLACEHOLDER___",
    "Sra.": "___SRA_PLACEHOLDER___",
    "Dra.": "___DRA_PLACEHOLDER___",
    "Rua.": "___RUA_PLACEHOLDER___",
    "Ltd.": "___LTD_PLACEHOLDER___",
    "Inc.": "___INC_PLACEHOLDER___",
    "Dez.": "___DEZ_PLACEHOLDER___",
    "Feb.": "___FEB_PLACEHOLDER___",
    "Mar.": "___MAR_PLACEHOLDER___",
    "Apr.": "___APR_PLACEHOLDER___",
    "Jun.": "___JUN_PLACEHOLDER___",
    "Jul.": "___JUL_PLACEHOLDER___",
    "Aug.": "___AUG_PLACEHOLDER___",
    "Sep.": "___SEP_PLACEHOLDER___",
    "Oct.": "___OCT_PLACEHOLDER___",
    "Nov.": "___NOV_PLACEHOLDER___",
    "Dec.": "___DEC_PLACEHOLDER___",
    "Jan.": "___JAN_PLACEHOLDER___",
    "Mrs.": "___MRS_PLACEHOLDER___",
    "Mr.": "___MR_PLACEHOLDER___",
    "Sr.": "___SR_PLACEHOLDER___",
    "Dr.": "___DR_PLACEHOLDER___",
    "Av.": "___AV_PLACEHOLDER___",
    "Co.": "___CO_PLACEHOLDER___",
}

# Cache sob demanda leve para tokenizer e modelo de embeddings opcionais
_EMBEDDING_TOKENIZER = None
_EMBEDDING_MODEL = None

def _calculate_embedding_similarity(text1: str, text2: str, model_name: str = "sentence-transformers/all-MiniLM-L6-v2") -> Optional[float]:
    """
    Calcula a similaridade por cosseno entre embeddings de dois textos de forma opcional e preguiçosa.
    Retorna None se as dependências (torch/transformers) não estiverem instaladas ou se houver erro de rede/carregamento.
    """
    global _EMBEDDING_TOKENIZER, _EMBEDDING_MODEL
    try:
        import torch
        from transformers import AutoTokenizer, AutoModel
        
        # Inicializa o modelo de forma preguiçosa (lazy load)
        if _EMBEDDING_TOKENIZER is None or _EMBEDDING_MODEL is None:
            _EMBEDDING_TOKENIZER = AutoTokenizer.from_pretrained(model_name)
            _EMBEDDING_MODEL = AutoModel.from_pretrained(model_name)
            
        def get_embedding(text: str):
            inputs = _EMBEDDING_TOKENIZER(text, padding=True, truncation=True, max_length=128, return_tensors="pt")
            with torch.no_grad():
                outputs = _EMBEDDING_MODEL(**inputs)
                # Mean pooling
                attention_mask = inputs['attention_mask']
                token_embeddings = outputs[0]
                input_mask_expanded = attention_mask.unsqueeze(-1).expand(token_embeddings.size()).float()
                sum_embeddings = torch.sum(token_embeddings * input_mask_expanded, 1)
                sum_mask = torch.clamp(input_mask_expanded.sum(1), min=1e-9)
                return sum_embeddings / sum_mask
                
        emb1 = get_embedding(text1)
        emb2 = get_embedding(text2)
        
        # Similaridade de cosseno
        cos = torch.nn.CosineSimilarity(dim=1, eps=1e-6)
        similarity = cos(emb1, emb2).item()
        return float(similarity)
    except Exception:
        # Fallback silencioso em caso de ausência de dependências, erro de timeout ou rede
        return None

class ClaimDependencyGraph:
    """
    Grafo direcionado de dependências lógicas e semânticas entre claims decompostos.
    Habilita propagação de incertezas e contradições estruturadas com ponderação de confiança (Fase 12).
    """
    def __init__(self):
        self.nodes: Dict[str, str] = {}  # claim_id -> text
        self.labels: Dict[str, str] = {} # claim_id -> label ("supported", "unsupported", "contradicted")
        self.confidences: Dict[str, float] = {} # claim_id -> confidence
        # dependencies[filho] = lista de pais (seus pressupostos dos quais depende)
        self.dependencies: Dict[str, List[str]] = {} 

    def add_node(self, node_id: str, text: str, label: str = "unsupported", confidence: float = 1.0):
        self.nodes[node_id] = text
        self.labels[node_id] = label
        self.confidences[node_id] = confidence
        if node_id not in self.dependencies:
            self.dependencies[node_id] = []

    def add_dependency(self, source_id: str, target_id: str):
        """Informa que target_id depende logicamente de source_id."""
        if target_id in self.nodes and source_id in self.nodes:
            if source_id not in self.dependencies[target_id]:
                self.dependencies[target_id].append(source_id)

    def propagate(self) -> Tuple[Dict[str, str], Dict[str, float]]:
        """
        Propaga o status de suporte e pondera as confianças pelas relações de dependência no grafo.
        Se um nó ancestral (pai) for 'contradicted', os dependentes (filhos) tornam-se 'contradicted'.
        Se for 'unsupported', os dependentes tornam-se 'unsupported'.
        A confiança do filho é multiplicada pela confiança acumulada do pai para refletir a incerteza lógica.
        Retorna uma tupla contendo (labels_atualizados, confianças_atualizadas).
        """
        updated_labels = dict(self.labels)
        updated_confidences = dict(self.confidences)
        
        # Propagação iterativa robusta
        changed = True
        iterations = 0
        max_iter = len(self.nodes) * 2
        
        while changed and iterations < max_iter:
            changed = False
            iterations += 1
            
            for child_id, parents in self.dependencies.items():
                if not parents:
                    continue
                
                for parent_id in parents:
                    parent_label = updated_labels.get(parent_id, "unsupported")
                    child_label = updated_labels.get(child_id, "unsupported")
                    
                    parent_conf = updated_confidences.get(parent_id, 1.0)
                    original_child_conf = self.confidences.get(child_id, 1.0)
                    
                    # 1. Propagação de incerteza/rótulo
                    if parent_label == "contradicted" and child_label != "contradicted":
                        updated_labels[child_id] = "contradicted"
                        changed = True
                        
                    elif parent_label == "unsupported" and child_label == "supported":
                        updated_labels[child_id] = "unsupported"
                        changed = True
                        
                    # 2. Ponderação de confiança: a confiança do filho sofre degradação baseada na confiança da premissa.
                    # Aplicamos um fator de amortecimento (damping factor) de 0.15 para suavizar e evitar quedas
                    # catastróficas em dependências fracas (reduzindo falsos negativos lógicos).
                    new_conf = original_child_conf * (0.15 + 0.85 * parent_conf)
                    if abs(updated_confidences.get(child_id, 0.0) - new_conf) > 1e-5:
                        updated_confidences[child_id] = new_conf
                        changed = True
                        
        self.labels = updated_labels
        self.confidences = updated_confidences
        return updated_labels, updated_confidences

    def adjudicate_semantic_dependencies(self, threshold_similarity: float = 72.0, use_embeddings: bool = True):
        """
        Adjudicação Semântica Dinâmica de dependências para claims órfãos (Fase 16 Aprimorada).
        Mapeia nós órfãos para nós pais lógicos se compartilharem alta similaridade de tokens ou vetorial.
        """
        from rapidfuzz import fuzz
        
        # Encontra nós que não possuem arestas de dependência de entrada e que ninguém depende deles
        orphan_nodes = []
        for node_id in self.nodes:
            has_parents = bool(self.dependencies.get(node_id))
            has_children = any(node_id in parents for parents in self.dependencies.values())
            if not has_parents and not has_children:
                orphan_nodes.append(node_id)
        
        for orphan_id in orphan_nodes:
            orphan_text = self.nodes[orphan_id]
            best_parent_id = None
            best_score = -1.0
            used_method = "lexical"
            
            for potential_id, potential_text in self.nodes.items():
                if orphan_id == potential_id:
                    continue
                
                # Tenta cálculo de similaridade vetorial densa opcional
                score = None
                if use_embeddings:
                    emb_sim = _calculate_embedding_similarity(orphan_text, potential_text)
                    if emb_sim is not None:
                        score = emb_sim * 100.0
                        used_method = "dense"
                        
                # Fallback para fuzzy lexical token sorted
                if score is None:
                    score = fuzz.token_sort_ratio(orphan_text.lower(), potential_text.lower())
                    used_method = "lexical"
                
                if score > best_score:
                    best_score = score
                    best_parent_id = potential_id
            
            # Ajusta limite para similaridade densa se for o método utilizado (embeddings de cosseno costumam ser mais restritos, 0.70+ e excelente)
            cutoff = threshold_similarity if used_method == "lexical" else (threshold_similarity - 2.0)
            
            if best_parent_id and best_score >= cutoff:
                logger.info(
                    f"Adjudicação Semântica ({used_method}): Conectando claim órfão '{orphan_id}' "
                    f"ao claim pai '{best_parent_id}' com score: {best_score:.1f}%"
                )
                self.add_dependency(best_parent_id, orphan_id)

    def to_mermaid(self) -> str:
        """Exporta o grafo de dependências no formato Mermaid.js para dashboards visuais."""
        lines = ["graph TD"]
        for node_id, text in self.nodes.items():
            label = self.labels.get(node_id, "unsupported")
            conf = self.confidences.get(node_id, 1.0)
            escaped_text = text.replace('"', '\\"')
            lines.append(f'    {node_id}["{node_id}: {escaped_text} ({label}, conf: {conf:.2f})"]')
            
        for child_id, parents in self.dependencies.items():
            for parent_id in parents:
                lines.append(f"    {parent_id} --> {child_id}")
        return "\n".join(lines)

    def to_dot(self) -> str:
        """Exporta o grafo no formato DOT do Graphviz."""
        lines = ["digraph G {", "    node [shape=box];"]
        for node_id, text in self.nodes.items():
            label = self.labels.get(node_id, "unsupported")
            conf = self.confidences.get(node_id, 1.0)
            escaped_text = text.replace('"', '\\"')
            lines.append(f'    {node_id} [label="{node_id}: {escaped_text}\\n({label}, conf: {conf:.2f})"];')
            
        for child_id, parents in self.dependencies.items():
            for parent_id in parents:
                lines.append(f"    {parent_id} -> {child_id};")
        lines.append("}")
        return "\n".join(lines)


class BaseClaimDecomposer(ABC):
    """Interface base para decompositores de claims do RAG."""
    
    @abstractmethod
    def decompose(self, text: str, lang: str = "pt-BR") -> List[str]:
        """Decompõe um texto em claims atômicos verificáveis."""
        pass

    @abstractmethod
    def decompose_to_graph(self, text: str, lang: str = "pt-BR") -> ClaimDependencyGraph:
        """Decompõe um texto retornando um grafo direcionado de dependências semânticas."""
        pass

class RegexClaimDecomposer(BaseClaimDecomposer):
    """Decompositor rápido local baseado em regex e fronteiras de sentenças (Sentence Boundary)."""
    
    def decompose(self, text: str, lang: str = "pt-BR") -> List[str]:
        if not text:
            return []
            
        normalized_text = re.sub(r'\s+', ' ', text).strip()
        processed_text = normalized_text
        for abbr, placeholder in MAP_ABBREVIATIONS.items():
            escaped_abbr = re.escape(abbr)
            processed_text = re.sub(escaped_abbr, placeholder, processed_text, flags=re.IGNORECASE)
            
        sentence_boundary_regex = re.compile(
            r"(?<![A-Z])"                         
            r"([.!?])"                            
            r"(?=\s|$)"                           
        )
        
        placeholder_boundary = " [SENTENCE_BOUNDARY] "
        marked_text = sentence_boundary_regex.sub(r"\1" + placeholder_boundary, processed_text)
        
        raw_claims = marked_text.split(placeholder_boundary)
        claims: List[str] = []
        
        for claim in raw_claims:
            cleaned = claim.strip()
            if not cleaned:
                continue
                
            restored = cleaned
            for abbr, placeholder in MAP_ABBREVIATIONS.items():
                restored = restored.replace(placeholder, abbr)
                
            if len(restored) >= 5:
                claims.append(restored)
                
        return claims

    def decompose_to_graph(self, text: str, lang: str = "pt-BR") -> ClaimDependencyGraph:
        claims = self.decompose(text, lang)
        graph = ClaimDependencyGraph()
        
        for i, c_text in enumerate(claims):
            node_id = f"c{i+1}"
            graph.add_node(node_id, c_text)
            
        # Heurística de acoplamento linguístico: conecta c_{i+1} a c_i se houver pronomes ou conectores
        pronouns_connectors = [
            "ele", "ela", "eles", "elas", "este", "esta", "isso", "esse", "essa",
            "he", "she", "it", "they", "this", "that", "these", "those",
            "além disso", "contudo", "então", "portanto", "assim", "mas",
            "furthermore", "however", "therefore", "thus", "also", "besides"
        ]
        
        for i in range(1, len(claims)):
            current_text = claims[i].lower()
            prev_id = f"c{i}"
            curr_id = f"c{i+1}"
            
            # Se começar com pronome/conector ou contiver algum nos primeiros termos
            first_words = [w.strip(".,;:?!") for w in current_text.split()[:3]]
            if any(pw in pronouns_connectors for pw in first_words):
                graph.add_dependency(prev_id, curr_id)
                
        graph.adjudicate_semantic_dependencies()
        return graph

class LLMClaimDecomposer(BaseClaimDecomposer):
    """
    Decompositor atômico baseado em LLM.
    Quebra sentenças complexas em fatos atômicos únicos e independentes, 
    resolvendo pronomes quando possível, mapeando dependências lógicas.
    """
    
    def __init__(self, model: Optional[str] = None):
        if not litellm:
            raise ImportError("litellm é necessário para o LLMClaimDecomposer. Instale com `pip install litellm`")
        
        self.model = model or os.environ.get("GROUNDCITE_DECOMPOSER_MODEL", "gpt-4o-mini")

    def decompose_to_graph(self, text: str, lang: str = "pt-BR") -> ClaimDependencyGraph:
        if not text:
            return ClaimDependencyGraph()
            
        language = "Portuguese (pt-BR)" if "pt" in lang.lower() else "English"
        prompt = f"""Break down the following text into atomic, independent claims and identify logical dependencies.
An atomic claim is a short sentence containing a single verifiable fact.
Resolve pronouns to their explicit subjects.
Identify if a claim logically depends on another (e.g., if claim B is a detail about an entity introduced in claim A, then claim B depends on claim A).

Language of output: {language}.
Respond ONLY with a JSON object containing:
1. "claims": an array of objects, each with "id" (e.g. "c1", "c2") and "text" (the atomic claim).
2. "dependencies": an array of objects representing directed edges, each with "source" (the id of the prerequisite claim) and "target" (the id of the dependent claim).

Text:
{text}
"""
        try:
            api_key = os.environ.get("LLM_API_OPENAI_KEY") or os.environ.get("LLM_API_OPENROUTER_KEY") or os.environ.get("LLM_API_NVIDIA_KEY")
            
            kwargs = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": "You are a precise linguistic decomposer."},
                    {"role": "user", "content": prompt}
                ],
                "response_format": {"type": "json_object"}
            }
            
            if api_key:
                kwargs["api_key"] = api_key
                
                # Injeta a chave adequadamente baseada na plataforma
                if "openrouter" in self.model:
                    os.environ["OPENROUTER_API_KEY"] = api_key
                elif "nvidia" in self.model or "minimax" in self.model:
                    os.environ["NVIDIA_API_KEY"] = api_key
                elif "gpt-" in self.model:
                    os.environ["OPENAI_API_KEY"] = api_key
                    
            response = litellm.completion(**kwargs)
            content = response.choices[0].message.content
            data = json.loads(content)
            
            graph = ClaimDependencyGraph()
            claims_data = data.get("claims", [])
            
            if isinstance(claims_data, list) and claims_data:
                if isinstance(claims_data[0], str):
                    for i, c_text in enumerate(claims_data):
                        graph.add_node(f"c{i+1}", c_text)
                else:
                    for c in claims_data:
                        node_id = str(c.get("id", ""))
                        text = str(c.get("text", ""))
                        if node_id and text:
                            graph.add_node(node_id, text)
                            
                deps = data.get("dependencies", [])
                if isinstance(deps, list):
                    for d in deps:
                        source = str(d.get("source", ""))
                        target = str(d.get("target", ""))
                        if source and target:
                            graph.add_dependency(source, target)
            else:
                logger.warning("LLM retornou JSON inválido/vazio para os claims. Usando fallback local (Regex).")
                return RegexClaimDecomposer().decompose_to_graph(text, lang)
                
            graph.adjudicate_semantic_dependencies()
            return graph
            
        except Exception as e:
            logger.warning(f"Falha ao decompor texto com LLM ({self.model}). Realizando fallback local. Erro: {str(e)}")
            return RegexClaimDecomposer().decompose_to_graph(text, lang)

    def decompose(self, text: str, lang: str = "pt-BR") -> List[str]:
        try:
            graph = self.decompose_to_graph(text, lang)
            return list(graph.nodes.values())
        except Exception:
            return RegexClaimDecomposer().decompose(text, lang)

def split_into_claims(text: str, lang: str = "pt-BR") -> List[str]:
    """Função de compatibilidade legada com a versão inicial (0.1.0). Usa Regex/Fronteira de sentença."""
    return RegexClaimDecomposer().decompose(text, lang)
