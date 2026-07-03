from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

STRICT_DOCS = [
    ROOT / "README.md",
    ROOT / "CHANGELOG.md",
    ROOT / "docs" / "paper_outline.md",
    ROOT / "docs" / "benchmark_card.md",
    ROOT / "docs" / "dataset_card.md",
    ROOT / "docs" / "gold_label_audit.md",
    ROOT / "docs" / "implementation_plan.md",
    ROOT / "docs" / "release_checklist.md",
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
    ledger = (ROOT / "docs" / "scientific_claims_ledger.md").read_text(encoding="utf-8")
    for line in ledger.splitlines():
        if "| yes |" in line:
            assert "| blocked |" not in line
            assert "| remove |" not in line
            assert "| engineering_only |" not in line


def test_paper_outline_names_kappa_correctly():
    outline = (ROOT / "docs" / "paper_outline.md").read_text(encoding="utf-8")
    assert "model-gold agreement" in outline
    assert "full IAA" in outline
