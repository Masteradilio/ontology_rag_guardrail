from __future__ import annotations

import json
from dataclasses import dataclass

import pytest

from quimera_semantic_trust_guardrail.evaluation import (
    EvaluationRunMetadata,
    EvaluationSampleResult,
    FallbackLLMClient,
    LLMFailure,
    LLMRequest,
    LLMResponse,
    NVIDIAProvider,
    OpenRouterProvider,
    ProviderTrace,
    SummaryMetrics,
    create_evaluation_run,
    load_dataset_manifest,
    load_env_file,
    load_jsonl_records,
    redact_secrets,
    write_jsonl,
)


@dataclass
class FakeProvider:
    provider_name: str
    model_name: str
    response_text: str = "ok"
    failure: LLMFailure | None = None

    def generate(self, request: LLMRequest) -> LLMResponse:
        if self.failure:
            raise self.failure
        return LLMResponse(
            text=self.response_text,
            provider_name=self.provider_name,
            model_name=self.model_name,
            latency_ms=3,
            usage={"total_tokens": 4},
            request_id=f"{self.provider_name}-req",
        )


def test_fallback_uses_nvidia_first_without_openrouter():
    nvidia = FakeProvider("nvidia", "minimax-m3", response_text="primary")
    openrouter = FakeProvider("openrouter", "minimax-m3", response_text="fallback")

    client = FallbackLLMClient([nvidia, openrouter])
    response = client.generate(LLMRequest(prompt="test"))

    assert response.text == "primary"
    assert response.provider_name == "nvidia"
    assert client.last_failures == []


def test_fallback_uses_openrouter_when_nvidia_fails():
    nvidia = FakeProvider(
        "nvidia",
        "minimax-m3",
        failure=LLMFailure("quota exhausted", provider_name="nvidia", status_code=429),
    )
    openrouter = FakeProvider("openrouter", "minimax-m3", response_text="paid fallback")

    client = FallbackLLMClient([nvidia, openrouter])
    response = client.generate(LLMRequest(prompt="test"))

    assert response.text == "paid fallback"
    assert response.provider_name == "openrouter"
    assert client.last_failures == [
        {
            "provider_name": "nvidia",
            "message": "quota exhausted",
            "retryable": True,
            "status_code": 429,
        }
    ]


def test_fallback_raises_when_all_providers_fail():
    client = FallbackLLMClient(
        [
            FakeProvider("nvidia", "minimax-m3", failure=LLMFailure("down", provider_name="nvidia")),
            FakeProvider("openrouter", "minimax-m3", failure=LLMFailure("paid disabled", provider_name="openrouter")),
        ]
    )

    with pytest.raises(LLMFailure, match="all providers failed"):
        client.generate(LLMRequest(prompt="test"))

    assert [failure["provider_name"] for failure in client.last_failures] == ["nvidia", "openrouter"]


def test_provider_configs_read_expected_env_names():
    env = {
        "NVIDIA_LLM_MODEL": "minimax/m3",
        "NVIDIA_URL_REFERENCE_MODEL": "https://integrate.api.nvidia.com/v1/chat/completions",
        "NVIDIA_API_KEY": "nv-secret",
        "OPENROUTER_LLM_MODEL": "minimax/minimax-m3",
        "OPENROUTER_API_KEY": "or-secret",
    }

    nvidia = NVIDIAProvider(env=env)
    openrouter = OpenRouterProvider(env=env)

    assert nvidia.provider_name == "nvidia"
    assert nvidia.model_name == "minimax/m3"
    assert nvidia.config.base_url == env["NVIDIA_URL_REFERENCE_MODEL"]
    assert openrouter.provider_name == "openrouter"
    assert openrouter.model_name == "minimax/minimax-m3"
    assert "openrouter.ai" in openrouter.config.base_url


def test_env_file_loader_and_redaction(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(
            [
                "# local secrets",
                "NVIDIA_API_KEY='abc123'",
                'OPENROUTER_API_KEY="def456"',
                "EMPTY=",
            ]
        ),
        encoding="utf-8",
    )

    values = load_env_file(env_file)

    assert values["NVIDIA_API_KEY"] == "abc123"
    assert values["OPENROUTER_API_KEY"] == "def456"
    assert redact_secrets("abc123 and def456", values.values()) == "[REDACTED] and [REDACTED]"


def test_evaluation_run_artifacts_are_schema_valid(tmp_path):
    metadata = EvaluationRunMetadata(
        run_id="run-test",
        dataset_id="quimera_scientific_seed",
        dataset_version="2026-07-04-v1",
        ontology_version="ontology-v1",
        policy_version="policy-v1",
        runtime_config={"temperature": 0},
        providers=[ProviderTrace(provider_name="nvidia", model_name="minimax/m3", status="ok")],
    )

    run_dir = create_evaluation_run(base_dir=tmp_path, metadata=metadata)

    loaded = EvaluationRunMetadata.model_validate_json((run_dir / "metadata.json").read_text(encoding="utf-8"))
    assert loaded.run_id == "run-test"
    assert loaded.dataset_id == "quimera_scientific_seed"


def test_write_jsonl_for_results_and_summary(tmp_path):
    result = EvaluationSampleResult(
        sample_id="sample-1",
        task="claim_check",
        expected_label="supported",
        observed_decision="TRUE",
        recommended_action="allow",
        correct=True,
    )
    summary = SummaryMetrics(run_id="run-test", sample_count=1, metrics={"accuracy": 1.0})

    path = tmp_path / "results.jsonl"
    write_jsonl(path, [result, summary])

    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    assert rows[0]["sample_id"] == "sample-1"
    assert rows[1]["metrics"]["accuracy"] == 1.0


def test_scientific_seed_manifest_and_records_load():
    manifest = load_dataset_manifest("data/evaluation/scientific_seed/manifest.json")

    assert manifest.package_id == "quimera_scientific_seed"
    assert {dataset.task for dataset in manifest.datasets} == {
        "claim_answer_validation",
        "agent_action_authorization",
        "policy_compliance",
    }
    for dataset in manifest.datasets:
        records = load_jsonl_records(dataset.path)
        assert len(records) == dataset.sample_count
        assert dataset.label_distribution


def test_scientific_seed_covers_critical_trivalent_labels():
    claim_records = load_jsonl_records("data/evaluation/scientific_seed/claim_answer_seed.jsonl")
    action_records = load_jsonl_records("data/evaluation/scientific_seed/agent_action_seed.jsonl")

    assert {record["expected_decision"] for record in claim_records} == {"TRUE", "FALSE", "UNDECIDABLE"}
    assert any(record["expected_label"] == "partially_unsupported" for record in claim_records)
    assert any(record["expected_label"] == "missing_authorization" for record in action_records)
