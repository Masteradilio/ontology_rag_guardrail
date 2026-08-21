from __future__ import annotations

import json

from quimera_semantic_trust_guardrail.decision_model import TrivalentDecision
from quimera_semantic_trust_guardrail.evaluation.llm_providers import (
    FallbackLLMClient,
    LLMFailure,
    LLMRequest,
    LLMResponse,
)
from quimera_semantic_trust_guardrail.evaluation.llm_rag_benchmark import (
    parse_llm_output,
    run_llm_rag_benchmark,
)


class FakeEmbedding:
    model_name = "fake-embedding"

    def encode(self, texts):
        vectors = []
        for text in texts:
            value = text.lower()
            if "refund" in value:
                vectors.append([1.0, 0.0, 0.0])
            elif "export" in value or "contractor" in value:
                vectors.append([0.0, 1.0, 0.0])
            else:
                vectors.append([0.0, 0.0, 1.0])
        return vectors


class FakeLLMClient:
    provider_name = "fake"
    model_name = "fake-model"

    def __init__(self, responses):
        self.responses = iter(responses)
        self.requests = []

    def generate(self, request: LLMRequest) -> LLMResponse:
        self.requests.append(request)
        return LLMResponse(
            text=next(self.responses),
            provider_name=self.provider_name,
            model_name=self.model_name,
            latency_ms=7,
            request_id="request-1",
        )


class RecordingProvider:
    def __init__(self, provider_name, response=None, failure=None):
        self.provider_name = provider_name
        self.model_name = f"{provider_name}-model"
        self.response = response
        self.failure = failure
        self.calls = 0

    def generate(self, request: LLMRequest) -> LLMResponse:
        self.calls += 1
        if self.failure:
            raise self.failure
        return self.response


def _cases():
    return [
        {
            "case_id": "refund-case",
            "query": "What is the refund window?",
            "documents": [
                {"document_id": "refund-policy", "text": "Refunds are available within 30 days."},
                {"document_id": "export-policy", "text": "Contractors may not export customer data."},
            ],
            "relevant_document_ids": ["refund-policy"],
            "answer": "",
            "expected_decision": "TRUE",
        }
    ]


def test_parse_fenced_and_noisy_json():
    parsed = parse_llm_output(
        'Model note: ```json\n{"answer":"Refunds are available.","decision":"true"}\n```'
    )

    assert parsed.parse_status == "valid"
    assert parsed.decision is TrivalentDecision.TRUE
    assert parsed.answer == "Refunds are available."


def test_malformed_output_becomes_undecidable_and_writes_artifacts(tmp_path):
    client = FakeLLMClient(["not JSON at all"])
    run_dir = run_llm_rag_benchmark(
        cases=_cases(),
        output_dir=tmp_path,
        run_id="malformed",
        embedder=FakeEmbedding(),
        llm_client=client,
    )

    report = json.loads((run_dir / "report.json").read_text(encoding="utf-8"))
    metadata = json.loads((run_dir / "metadata.json").read_text(encoding="utf-8"))
    assert report["cases"][0]["post_rag"]["observed_decision"] == "UNDECIDABLE"
    assert report["provider_trace"][0]["parse_status"] == "malformed"
    assert metadata["llm_api_key_required"] is True
    assert metadata["status"] == "partial"
    assert (run_dir / "summary.md").exists()
    assert (run_dir / "provider_trace.jsonl").exists()
    assert len(
        [json.loads(line) for line in (run_dir / "provider_trace.jsonl").read_text(encoding="utf-8").splitlines()]
    ) == 1
    assert "What is the refund window?" in client.requests[0].prompt
    assert "Refunds are available within 30 days." in client.requests[0].prompt


def test_injected_fallback_attempts_nvidia_before_openrouter(tmp_path):
    nvidia = RecordingProvider(
        "nvidia",
        failure=LLMFailure(
            "temporary outage", provider_name="nvidia", retryable=True
        ),
    )
    openrouter = RecordingProvider(
        "openrouter",
        response=LLMResponse(
            text='{"answer":"Refunds are available within 30 days.","decision":"TRUE"}',
            provider_name="openrouter",
            model_name="openrouter-model",
            latency_ms=11,
            request_id="fallback-request",
        ),
    )
    client = FallbackLLMClient([nvidia, openrouter])

    run_dir = run_llm_rag_benchmark(
        cases=_cases(),
        output_dir=tmp_path,
        run_id="fallback",
        embedder=FakeEmbedding(),
        llm_client=client,
    )

    assert nvidia.calls == 1
    assert openrouter.calls == 1
    trace = json.loads((run_dir / "report.json").read_text(encoding="utf-8"))["provider_trace"][0]
    assert trace["provider_name"] == "openrouter"
    assert trace["fallback_failures"][0]["provider_name"] == "nvidia"


def test_evidence_guardrail_corrects_explicit_prohibition(tmp_path):
    cases = [
        {
            "case_id": "prohibited",
            "query": "Can a contractor export customer data?",
            "documents": [
                {
                    "document_id": "policy",
                    "text": "Contractors must not export customer data.",
                }
            ],
            "relevant_document_ids": ["policy"],
            "answer": "",
            "expected_decision": "FALSE",
        }
    ]
    client = FakeLLMClient(
        ['{"answer":"The action is allowed.","decision":"TRUE"}']
    )

    run_dir = run_llm_rag_benchmark(
        cases=cases,
        output_dir=tmp_path,
        run_id="guardrail",
        embedder=FakeEmbedding(),
        llm_client=client,
    )

    report = json.loads((run_dir / "report.json").read_text(encoding="utf-8"))
    assert report["llm_cases"][0]["raw_decision"] == "TRUE"
    assert report["llm_cases"][0]["decision"] == "FALSE"
    assert report["llm_cases"][0]["guardrail_applied"] is True
    assert report["llm_raw_decision_accuracy"] == 0.0
    assert report["llm_guardrailed_decision_accuracy"] == 1.0


def test_default_policy_can_disable_paid_fallback(monkeypatch):
    import quimera_semantic_trust_guardrail.evaluation.llm_rag_benchmark as benchmark

    nvidia = RecordingProvider("nvidia")
    openrouter = RecordingProvider("openrouter")
    monkeypatch.setattr(benchmark, "NVIDIAProvider", lambda: nvidia)
    monkeypatch.setattr(benchmark, "OpenRouterProvider", lambda: openrouter)

    client = benchmark._build_default_llm_client(allow_paid_fallback=False)

    assert [provider.provider_name for provider in client.providers] == ["nvidia"]


def test_secret_in_response_is_not_persisted(tmp_path):
    secret = "NVIDIA-API-KEY-SHOULD-NOT-APPEAR"
    client = FakeLLMClient(
        [json.dumps({"answer": secret, "decision": "TRUE"})]
    )
    run_dir = run_llm_rag_benchmark(
        cases=_cases(),
        output_dir=tmp_path,
        run_id="redacted",
        embedder=FakeEmbedding(),
        llm_client=client,
    )

    artifact_text = "".join(
        path.read_text(encoding="utf-8")
        for path in run_dir.iterdir()
        if path.is_file()
    )
    assert secret not in artifact_text
