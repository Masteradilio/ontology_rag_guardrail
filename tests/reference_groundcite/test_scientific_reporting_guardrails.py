from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
REFERENCE_DOCS = ROOT / "docs" / "reference" / "groundcite_pten"

STRICT_DOCS = [
    REFERENCE_DOCS / "README.md",
    REFERENCE_DOCS / "CHANGELOG.md",
    REFERENCE_DOCS / "docs_benchmark_card.md",
    REFERENCE_DOCS / "docs_dataset_card.md",
    REFERENCE_DOCS / "docs_gold_label_audit.md",
    REFERENCE_DOCS / "docs_paper_readiness_checklist.md",
    REFERENCE_DOCS / "docs_reproducibility_report.md",
    REFERENCE_DOCS / "docs_scientific_claims_ledger.md",
]

FORBIDDEN_TERMS = [
    "SOTA",
    "100% de confiança",
    "superioridade científica",
    "prova formal",
    "garante factualidade",
    "benchmark definitivo",
    "concordância quase perfeita",
    "framework de ponta",
    "Dependency Killer",
    "confiança matemática formal",
]


def test_active_scientific_docs_do_not_use_forbidden_overclaim_terms():
    offenders = []
    for path in STRICT_DOCS:
        text = path.read_text(encoding="utf-8")
        for term in FORBIDDEN_TERMS:
            if term in text:
                offenders.append(f"{path.relative_to(ROOT)}: {term}")
    assert offenders == []


def test_claims_ledger_blocks_unsafe_abstract_claims():
    ledger = (REFERENCE_DOCS / "docs_scientific_claims_ledger.md").read_text(encoding="utf-8")
    for line in ledger.splitlines():
        if "| yes |" in line:
            assert "| blocked |" not in line
            assert "| remove |" not in line
            assert "| engineering_only |" not in line


def test_paper_outline_names_kappa_correctly():
    outline = (REFERENCE_DOCS / "docs_paper_readiness_checklist.md").read_text(encoding="utf-8")
    assert "model-gold agreement" in outline
    assert "human-human IAA" in outline
