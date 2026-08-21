# RAG Evaluation Seed

This small deterministic dataset exercises the three-stage RAG evaluation path:

- pre-RAG: rank candidate documents for a query;
- during RAG: inspect the assembled context and its evidence coverage;
- post-RAG: compare the answer's trivalent decision with the controlled expected outcome.

The records are synthetic and intentionally compact. They are suitable for regression and architecture demonstration, not for production retrieval accuracy or claims about a language model.

The benchmark uses a local Sentence Transformers model for query/document embeddings. No LLM API key is required because answer decisions are supplied by a deterministic controlled evaluator for the seed cases.
