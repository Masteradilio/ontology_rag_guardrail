"""Evaluation infrastructure for scientific and commercial validation."""

from .artifacts import (
    EvaluationRunMetadata,
    EvaluationSampleResult,
    ProviderTrace,
    ProofTrace,
    SummaryMetrics,
    create_evaluation_run,
    write_jsonl,
)
from .datasets import (
    ControlledDataset,
    DatasetManifest,
    load_dataset_manifest,
    load_jsonl_records,
)
from .llm_providers import (
    FallbackLLMClient,
    LLMClient,
    LLMFailure,
    LLMRequest,
    LLMResponse,
    NVIDIAProvider,
    OpenAICompatibleProvider,
    OpenRouterProvider,
    ProviderConfig,
    load_env_file,
    redact_secrets,
)
from .commercial_demo import run_commercial_demo
from .commercial_pilot import (
    PilotMetrics,
    PilotReviewSample,
    PilotScope,
    compute_pilot_metrics,
    default_pilot_scopes,
    write_default_pilot_package,
)
from .scientific_baseline import ControlledClaimAdapter, run_scientific_baseline
from .embeddings import (
    DEFAULT_EMBEDDING_MODEL,
    DeterministicHashEmbedding,
    EmbeddingDependencyError,
    SentenceTransformerEmbedding,
    cosine_similarity,
)
from .rag_evals import (
    DuringRagResult,
    PostRagResult,
    PreRagResult,
    RagCaseResult,
    RagDocument,
    RagEvalCase,
    RagEvaluationReport,
    evaluate_rag_cases,
    load_rag_cases,
)
from .rag_benchmark import (
    controlled_seed_answer_evaluator,
    run_rag_benchmark,
)
from .llm_rag_benchmark import parse_llm_output, run_llm_rag_benchmark
from .observability import EvaluationTrace, TraceEvent, write_open_telemetry, write_trace_summary
from .replay import explain_proof, explain_trace, replay_proof, replay_trace
from .showcase import run_showcase

__all__ = [
    "ControlledDataset",
    "ControlledClaimAdapter",
    "DatasetManifest",
    "EvaluationRunMetadata",
    "EvaluationSampleResult",
    "FallbackLLMClient",
    "LLMClient",
    "LLMFailure",
    "LLMRequest",
    "LLMResponse",
    "NVIDIAProvider",
    "OpenAICompatibleProvider",
    "OpenRouterProvider",
    "PilotMetrics",
    "PilotReviewSample",
    "PilotScope",
    "ProviderConfig",
    "ProviderTrace",
    "ProofTrace",
    "SummaryMetrics",
    "create_evaluation_run",
    "load_dataset_manifest",
    "load_env_file",
    "load_jsonl_records",
    "redact_secrets",
    "run_commercial_demo",
    "run_scientific_baseline",
    "write_jsonl",
    "compute_pilot_metrics",
    "default_pilot_scopes",
    "write_default_pilot_package",
    "DEFAULT_EMBEDDING_MODEL",
    "DeterministicHashEmbedding",
    "EmbeddingDependencyError",
    "SentenceTransformerEmbedding",
    "cosine_similarity",
    "DuringRagResult",
    "PostRagResult",
    "PreRagResult",
    "RagCaseResult",
    "RagDocument",
    "RagEvalCase",
    "RagEvaluationReport",
    "evaluate_rag_cases",
    "load_rag_cases",
    "controlled_seed_answer_evaluator",
    "run_rag_benchmark",
    "parse_llm_output",
    "run_llm_rag_benchmark",
    "EvaluationTrace",
    "TraceEvent",
    "write_open_telemetry",
    "write_trace_summary",
    "explain_proof",
    "explain_trace",
    "replay_proof",
    "replay_trace",
    "run_showcase",
]
