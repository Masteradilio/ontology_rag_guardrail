from groundcite.claims import split_into_claims

def test_split_into_claims_simple():
    """Garante que a quebra de sentenças básica funcione."""
    text = "Machado de Assis foi um grande escritor. Ele fundou a ABL!"
    claims = split_into_claims(text)
    assert len(claims) == 2
    assert claims[0] == "Machado de Assis foi um grande escritor."
    assert claims[1] == "Ele fundou a ABL!"

def test_split_into_claims_with_abbreviations():
    """Garante que abreviações comuns não causem quebras falsas de sentenças."""
    text_pt = "O Dr. Machado de Assis morava na Av. Paulista, etc. Ele era muito respeitado."
    claims_pt = split_into_claims(text_pt, lang="pt-BR")
    assert len(claims_pt) == 2
    assert claims_pt[0] == "O Dr. Machado de Assis morava na Av. Paulista, etc."
    assert claims_pt[1] == "Ele era muito respeitado."

    text_en = "SpaceX was founded by Mr. Elon Musk in the U.S. at 2002. They want to go to Mars."
    claims_en = split_into_claims(text_en, lang="en")
    assert len(claims_en) == 2
    assert claims_en[0] == "SpaceX was founded by Mr. Elon Musk in the U.S. at 2002."
    assert claims_en[1] == "They want to go to Mars."

def test_split_into_claims_empty_or_short():
    """Garante comportamento correto em textos vazios ou sentenças curtas demais."""
    assert split_into_claims("") == []
    assert split_into_claims("Oi.") == []  # Muito curto (menos de 5 caracteres)
