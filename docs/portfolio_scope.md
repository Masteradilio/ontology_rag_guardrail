# Portfolio Scope

Quimera Semantic Trust Guardrail is an experimental technical portfolio project for demonstrating senior-level engineering across RAG, guardrails, evaluation, observability, SDK design, and ontology-grounded reasoning.

The project is not positioned as a commercial product, a production security boundary, or a scientific paper contribution. Its purpose is to make the engineering decisions and trade-offs visible in a runnable repository.

## Demonstration Thesis

An AI system can expose a more useful trust boundary when it keeps three concerns separate:

- semantic state: `TRUE`, `FALSE`, or `UNDECIDABLE`;
- operational action: allow, warn, retry, abstain, block, or escalate;
- audit evidence: sources, ontology/policy versions, proof ids, and decision paths.

The portfolio implementation combines those concerns with:

- ontology and semantic-fact modeling;
- claim-level and answer-level RAG validation;
- agent action authorization;
- deterministic and embedding-based EVALs;
- structured proof and observability records;
- replayable failure analysis.

## What The Project Demonstrates

- Typed Python SDK contracts and compatibility-preserving adapters.
- RAG evaluation before retrieval, during context assembly, and after answer generation.
- Explicit abstention and contradiction handling instead of binary allow/block only.
- Versioned ontology state with provenance and rollback linkage.
- Provider-independent evaluation with optional LLM-assisted runs.
- Reproducible offline benchmarks that do not require API keys.
- Honest reporting of known limitations and false decisions.

## Boundaries

The runtime estimates support, contradiction, authorization, and insufficient evidence under configured evidence, ontology, and policy. It does not prove real-world truth, certify legal compliance, guarantee production safety, or eliminate hallucinations.

The known policy uncertainty case remains in the benchmark as a visible failure mode. It is useful for demonstrating how EVALs expose a guardrail limitation; it is not presented as solved behavior.

## Portfolio Success Criteria

The repository is portfolio-ready when a reviewer can:

1. install the project in a clean environment;
2. run one offline showcase command;
3. inspect a RAG decision with evidence and a proof id;
4. run the three-stage EVAL pipeline;
5. reproduce benchmark metrics without an LLM API key;
6. understand the architecture, limitations, and next engineering decisions from the documentation.
