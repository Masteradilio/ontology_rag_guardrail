from __future__ import annotations
from typing import Dict, List
from pathlib import Path
from pypdf import PdfReader

from .tenant_ontology import OntologyEntry, FactConfidence


FRAMEWORK_FILES = {
    "LGPD": "LGPD.pdf",
    "GDPR": "GDPR.pdf",
    "AI_ACT": "AI_act.pdf",
}


KEYWORDS = {
    "LGPD": {
        "consentimento": [
            "consentimento",
            "consent",
            "consentir",
            "consentimento explícito",
            "consentimento inequívoco",
            "opt-in",
            "opt out",
        ],
        "base_legal": [
            "base legal",
            "lawful basis",
            "legitimidade",
            "interesse legítimo",
            "execução de contrato",
        ],
        "minimizacao": [
            "minimização",
            "data minimization",
            "minimize",
            "coletar o mínimo",
            "restrição de finalidade",
        ],
        "direitos_titular": [
            "direitos do titular",
            "direitos do consumidor",
            "data subject rights",
            "acesso",
            "retificação",
            "exclusão",
            "portabilidade",
            "oposição",
        ],
        "retencao": [
            "retenção",
            "armazenamento",
            "retention",
            "prazo de retenção",
            "eliminação",
        ],
        "seguranca": [
            "segurança",
            "security",
            "medidas de segurança",
            "medidas técnicas",
            "medidas organizacionais",
        ],
        "transferencia_internacional": [
            "transferência internacional",
            "international transfer",
            "país terceiro",
            "transferência transfronteiriça",
        ],
    },
    "GDPR": {
        "lawful_basis": [
            "lawful basis",
            "base legal",
            "legality",
            "legitimate interest",
            "contractual necessity",
        ],
        "data_minimization": [
            "data minimization",
            "minimização",
            "minimize",
            "purpose limitation",
        ],
        "right_to_erasure": [
            "right to erasure",
            "direito de exclusão",
            "right to be forgotten",
            "article 17",
        ],
        "security": [
            "security",
            "segurança",
            "technical and organizational measures",
            "tom",
        ],
        "portability": [
            "portability",
            "portabilidade",
            "data portability",
            "article 20",
        ],
        "transfers": [
            "international transfers",
            "third country",
            "adequacy decision",
            "standard contractual clauses",
        ],
    },
    "AI_ACT": {
        "high_risk": [
            "high-risk",
            "alto risco",
            "risk management",
            "classificação de risco",
        ],
        "transparency": [
            "transparency",
            "transparência",
            "disclosure",
            "informar uso de ia",
        ],
        "data_governance": [
            "data governance",
            "governança de dados",
            "dataset documentation",
            "qualidade de dados",
        ],
        "registration": [
            "registry",
            "registro",
            "conformity assessment",
            "avaliação de conformidade",
        ],
        "post_monitoring": [
            "post-market monitoring",
            "monitoramento",
            "incident reporting",
            "monitoramento pós-implantação",
        ],
    },
}

ARTICLE_MAP = {
    "LGPD": {
        "consentimento": ["Art. 7", "Art. 8"],
        "base_legal": ["Art. 7"],
        "direitos_titular": ["Art. 18"],
        "retencao": ["Art. 16"],
        "seguranca": ["Art. 46"],
        "transferencia_internacional": ["Art. 33", "Art. 34"],
    },
    "GDPR": {
        "lawful_basis": ["Art. 6"],
        "data_minimization": ["Art. 5(1)(c)"],
        "right_to_erasure": ["Art. 17"],
        "security": ["Art. 32"],
        "portability": ["Art. 20"],
        "transfers": ["Art. 44-49"],
    },
    "AI_ACT": {
        "high_risk": ["Title III, Chapter 1"],
        "transparency": ["Art. 52"],
        "data_governance": ["Art. 10"],
        "registration": ["Art. 51"],
        "post_monitoring": ["Art. 61"],
    },
}


def read_pdf_text(path: Path) -> str:
    if not path.exists():
        return ""
    reader = PdfReader(str(path))
    parts: List[str] = []
    for page in reader.pages:
        try:
            parts.append(page.extract_text() or "")
        except Exception:
            continue
    return "\n".join(parts)


def split_sentences(text: str) -> List[str]:
    text = text.replace("\r", " ")
    for sep in [". ", "\n", "; "]:
        text = text.replace(sep, ". ")
    return [s.strip() for s in text.split(".") if s.strip()]

def _normalize(s: str) -> str:
    s = s.lower()
    s = s.replace("\t", " ")
    s = s.replace("\n", " ")
    while "  " in s:
        s = s.replace(" ", " ")
    return s.strip()


def extract_entries(framework: str, text: str) -> List[OntologyEntry]:
    kws = KEYWORDS.get(framework, {})
    sents = split_sentences(text)
    entries: List[OntologyEntry] = []
    for concept, terms in kws.items():
        facts: List[str] = []
        constraints: List[str] = []
        for s in sents:
            lower = _normalize(s)
            if any(_normalize(t) in lower for t in terms):
                if any(x in lower for x in ["não", "vedado", "proibido", "sem ", "ban", "deny", "sem transparência", "no disclosure"]):
                    constraints.append(s)
                else:
                    facts.append(s)
        if facts or constraints:
            src = framework
            arts = ARTICLE_MAP.get(framework, {}).get(concept, [])
            if arts:
                src = f"{framework}:{','.join(arts)}"
            entries.append(OntologyEntry(
                concept=concept,
                definition=concept.replace("_", " "),
                facts=list(dict.fromkeys(facts))[:10],
                constraints=list(dict.fromkeys(constraints))[:10],
                synonyms=terms,
                source=src,
                confidence=FactConfidence.PROBABLE,
            ))
    return entries


def extract_from_pdfs(project_root: Path, frameworks: List[str]) -> Dict[str, List[OntologyEntry]]:
    docs_dir = project_root / "docs" / "compliance"
    result: Dict[str, List[OntologyEntry]] = {}
    for fw in frameworks:
        fname = FRAMEWORK_FILES.get(fw.upper())
        if not fname:
            result[fw] = []
            continue
        text = read_pdf_text(docs_dir / fname)
        result[fw] = extract_entries(fw.upper(), text)
    return result
