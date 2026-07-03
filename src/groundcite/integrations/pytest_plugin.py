from typing import Optional

def assert_grounded(
    dataset_path: str,
    min_claim_support: float = 0.80,
    max_unsupported_span_rate: float = 0.10,
    backend: str = "lexical",
    pricing_model: str = "gpt-4o"
) -> None:
    """
    Quality gate helper for pytest. Evaluates a JSONL dataset of RAG answers
    and asserts that they meet the minimum factuality requirements.
    
    Args:
        dataset_path: Path to the JSONL dataset.
        min_claim_support: Minimum average claim support rate (0.0 to 1.0).
        max_unsupported_span_rate: Maximum average unsupported span rate (0.0 to 1.0).
        backend: Backend to use ('lexical', 'local-nli', 'judge', 'hybrid').
        pricing_model: Pricing model reference if using the hybrid backend.
    
    Raises:
        AssertionError: If the evaluated dataset falls below the quality threshold.
    """
    import json
    from pathlib import Path
    from groundcite.schema import Sample
    from groundcite.evaluator import Evaluator
    from groundcite.backends.lexical import LexicalBackend
    from groundcite.backends.local_nli import LocalNLIBackend
    from groundcite.backends.judge_llm import JudgeBackend
    from groundcite.backends.hybrid import HybridBackend
    
    path = Path(dataset_path)
    if not path.exists():
        raise FileNotFoundError(f"Dataset não encontrado: {dataset_path}")
        
    samples = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                samples.append(Sample.model_validate_json(line))
                
    if not samples:
        raise ValueError("O dataset fornecido está vazio.")
        
    # Inicializa o backend
    if backend == "lexical":
        inference_backend = LexicalBackend()
    elif backend == "local-nli":
        inference_backend = LocalNLIBackend()
    elif backend == "judge":
        inference_backend = JudgeBackend()
    elif backend == "hybrid":
        primary = LocalNLIBackend()
        inference_backend = HybridBackend(primary_backend=primary, pricing_model=pricing_model)
    else:
        raise ValueError(f"Backend desconhecido: {backend}")
        
    evaluator = Evaluator(backend=inference_backend)
    
    results = []
    for sample in samples:
        results.append(evaluator.evaluate(sample))
        
    total = len(results)
    avg_claim_support = sum(r.scores.get("claim_support_rate", 0.0) for r in results) / total
    avg_unsupported_rate = sum(r.scores.get("span_support_unsupported_rate", 0.0) for r in results) / total
    
    assert avg_claim_support >= min_claim_support, (
        f"Groundedness (Claim Support) falhou. "
        f"Esperado >= {min_claim_support:.2f}, Obtido: {avg_claim_support:.2f}"
    )
    
    assert avg_unsupported_rate <= max_unsupported_span_rate, (
        f"Taxa de Alucinações (Unsupported Span Rate) excedeu o limite. "
        f"Esperado <= {max_unsupported_span_rate:.2f}, Obtido: {avg_unsupported_rate:.2f}"
    )
