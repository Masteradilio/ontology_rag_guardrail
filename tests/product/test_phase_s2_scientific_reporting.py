from pathlib import Path


DOCS = [
    Path("docs/scientific_claims_ledger_quimera.md"),
    Path("docs/scientific_technical_report.md"),
    Path("docs/scientific_external_research_decision.md"),
]

FORBIDDEN_TERMS = [
    "eliminates hallucinations",
    "proves real-world truth",
    "legal compliance certification",
    "production accuracy",
    "superiority over other guardrail systems",
]


def test_scientific_reporting_documents_exist():
    for path in DOCS:
        assert path.exists(), path
        assert path.read_text(encoding="utf-8").strip()


def test_quimera_claims_ledger_has_required_statuses_and_forbidden_claims():
    text = Path("docs/scientific_claims_ledger_quimera.md").read_text(encoding="utf-8")

    for status in ["supported", "preliminary", "blocked", "engineering_only", "remove"]:
        assert status in text
    assert "Ontology RAG Guardrail proves real-world truth. | remove" in text
    assert "Ontology RAG Guardrail eliminates hallucinations. | remove" in text
    assert "Ontology RAG Guardrail provides legal compliance certification. | remove" in text


def test_technical_report_records_seed_metrics_and_failure():
    text = Path("docs/scientific_technical_report.md").read_text(encoding="utf-8")

    assert "Samples: 12" in text
    assert "Correct decisions: 11" in text
    assert "False allow rate: 0.0833" in text
    assert "policy-undecidable-001" in text
    assert "does not establish production hallucination reduction" in text


def test_external_research_decision_is_conservative():
    text = Path("docs/scientific_external_research_decision.md").read_text(encoding="utf-8")

    assert "do not submit a formal paper yet" in text
    assert "technical whitepaper or blog post" in text
    assert "not a comparative benchmark" in text


def test_scientific_docs_do_not_assert_forbidden_claims_as_facts():
    offenders = []
    for path in DOCS:
        text = path.read_text(encoding="utf-8")
        for term in FORBIDDEN_TERMS:
            if term in text and "Do not claim" not in text and "Do not use" not in text:
                offenders.append(f"{path}: {term}")
    assert offenders == []
