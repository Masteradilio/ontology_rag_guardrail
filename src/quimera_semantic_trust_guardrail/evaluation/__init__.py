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
]
