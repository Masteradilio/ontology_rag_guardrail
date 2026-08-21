"""Opt-in provider-backed RAG benchmark with redacted audit artifacts.

The runner is deliberately separate from the offline benchmark. Callers must
inject an embedding backend, and tests can inject an LLM client so no provider
call is implicit in the normal evaluation suite.
"""

from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Mapping, Optional, Sequence

from ..decision_model import TrivalentDecision
from .embeddings import EmbeddingBackend
from .llm_providers import (
    FallbackLLMClient,
    LLMClient,
    LLMFailure,
    LLMRequest,
    NVIDIAProvider,
    OpenRouterProvider,
    redact_secrets,
)
from .rag_evals import RagDocument, RagEvalCase, evaluate_rag_cases, load_rag_cases


_SCHEMA_VERSION = "quimera_llm_rag_benchmark_v1"
_SYSTEM_PROMPT = (
    "You are a conservative retrieval-grounded evaluator. Use only the supplied "
    "query and context. Return one JSON object with exactly these useful fields: "
    "answer (a concise grounded answer) and decision (one of TRUE, FALSE, "
    "UNDECIDABLE). If the context does not support a decision, choose "
    "UNDECIDABLE. TRUE means the requested action or claim is supported by "
    "the context; FALSE means the context explicitly contradicts or forbids "
    "it. Do not include markdown or commentary."
)


def _commit_sha() -> Optional[str]:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return result.stdout.strip() or None


@dataclass(frozen=True)
class ParsedLLMOutput:
    """Safe in-memory representation of the model's structured response."""

    answer: str
    decision: TrivalentDecision
    parse_status: str


@dataclass(frozen=True)
class _CaseRun:
    case_id: str
    parsed: ParsedLLMOutput
    guarded_decision: TrivalentDecision
    generation_status: str
    trace_index: int


def _malformed_output() -> ParsedLLMOutput:
    return ParsedLLMOutput(
        answer="",
        decision=TrivalentDecision.UNDECIDABLE,
        parse_status="malformed",
    )


def _json_objects(text: str) -> list[Mapping[str, Any]]:
    """Find object-shaped JSON in fenced, prefixed, or suffixed model text."""

    candidates: list[str] = [
        match.group(1)
        for match in re.finditer(
            r"```(?:json)?\s*(.*?)\s*```", text, flags=re.IGNORECASE | re.DOTALL
        )
    ]
    candidates.append(text)
    decoder = json.JSONDecoder()
    objects: list[Mapping[str, Any]] = []

    for candidate in candidates:
        try:
            payload = json.loads(candidate)
        except (TypeError, ValueError, json.JSONDecodeError):
            continue
        if isinstance(payload, Mapping):
            objects.append(payload)

    for index, character in enumerate(text):
        if character not in "{[":
            continue
        try:
            payload, _end = decoder.raw_decode(text[index:])
        except (TypeError, ValueError, json.JSONDecodeError):
            continue
        if isinstance(payload, Mapping):
            objects.append(payload)
    return objects


def parse_llm_output(text: Any) -> ParsedLLMOutput:
    """Parse conservative LLM JSON and abstain on every unknown shape."""

    if not isinstance(text, str) or not text.strip():
        return _malformed_output()
    for payload in _json_objects(text):
        answer = payload.get("answer")
        raw_decision = payload.get("decision")
        if not isinstance(answer, str) or not answer.strip():
            continue
        if isinstance(raw_decision, TrivalentDecision):
            decision = raw_decision
        elif isinstance(raw_decision, str):
            try:
                decision = TrivalentDecision(raw_decision.strip().upper())
            except ValueError:
                continue
        else:
            continue
        return ParsedLLMOutput(
            answer=answer.strip(),
            decision=decision,
            parse_status="valid",
        )
    return _malformed_output()


def _build_default_llm_client(allow_paid_fallback: bool) -> FallbackLLMClient:
    providers: list[LLMClient] = [NVIDIAProvider()]
    if allow_paid_fallback:
        providers.append(OpenRouterProvider())
    return FallbackLLMClient(providers)


def _load_cases(
    cases: Optional[Sequence[RagEvalCase | Mapping[str, Any]]],
    manifest_path: Optional[str | Path],
) -> tuple[list[RagEvalCase], Dict[str, Any]]:
    if cases is not None and manifest_path is not None:
        raise ValueError("provide cases or manifest_path, not both")
    manifest_metadata: Dict[str, Any] = {}
    loaded_cases: Sequence[RagEvalCase | Mapping[str, Any]]
    if manifest_path is not None:
        manifest_file = Path(manifest_path)
        manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
        manifest_metadata = {
            key: manifest[key]
            for key in ("package_id", "version")
            if key in manifest
        }
        manifest_case_path = Path(manifest["path"])
        if manifest_case_path.is_absolute():
            cases_file = manifest_case_path
        else:
            candidates = [manifest_case_path, manifest_file.parent / manifest_case_path]
            candidates.append(manifest_file.parent / manifest_case_path.name)
            cases_file = next(
                (candidate for candidate in candidates if candidate.exists()),
                manifest_file.parent / manifest_case_path.name,
            )
        loaded_cases = load_rag_cases(cases_file)
    elif cases is not None:
        loaded_cases = list(cases)
    else:
        raise ValueError("one of cases or manifest_path is required")

    normalized = [
        case if isinstance(case, RagEvalCase) else RagEvalCase.model_validate(case)
        for case in loaded_cases
    ]
    return normalized, manifest_metadata


def _assemble_context(case: RagEvalCase, retrieved_document_ids: Sequence[str]) -> str:
    documents_by_id = {document.document_id: document for document in case.documents}
    context_parts: list[str] = []
    for document_id in retrieved_document_ids:
        document = documents_by_id.get(document_id)
        if document is not None:
            context_parts.append(f"Document {document.document_id}:\n{document.text}")
    return "\n\n".join(context_parts) or "(no retrieved context)"


def _build_prompt(case: RagEvalCase, context: str) -> str:
    return (
        "Query:\n"
        f"{case.query}\n\n"
        "Retrieved context:\n"
        f"{context}\n\n"
        "Return JSON with this shape: "
        '{"answer":"...","decision":"TRUE|FALSE|UNDECIDABLE"}'
    )


def _guardrail_decision(
    case: RagEvalCase,
    context_documents: Sequence[RagDocument],
    parsed: ParsedLLMOutput,
) -> TrivalentDecision:
    """Apply a narrow evidence-consistency guardrail after generation.

    This is deliberately not a general truth engine. It catches two common
    RAG failure modes in the controlled seed: an explicit prohibition being
    classified as allowed, and a scoped entity in the query being absent from
    the selected evidence. The raw provider decision remains in the report.
    """

    if parsed.parse_status != "valid":
        return TrivalentDecision.UNDECIDABLE
    evidence = " ".join(document.text for document in context_documents).lower()
    query = case.query.lower()
    prohibition_markers = ("must not", "not allowed", "forbidden", "prohibited", "cannot")
    scope_markers = ("premium", "contractor", "external analytics", "archived", "retention")
    if parsed.decision == TrivalentDecision.TRUE:
        if any(marker in evidence for marker in prohibition_markers):
            return TrivalentDecision.FALSE
        for marker in scope_markers:
            if marker in query and marker not in evidence:
                return TrivalentDecision.UNDECIDABLE
    return parsed.decision


def _provider_objects(client: LLMClient) -> list[Any]:
    providers = getattr(client, "providers", None)
    if isinstance(providers, (list, tuple)):
        return list(providers)
    return [client]


def _collect_secrets(client: LLMClient) -> list[str]:
    secrets: list[str] = []
    for provider in [client, *_provider_objects(client)]:
        api_key = getattr(provider, "api_key", None)
        config = getattr(provider, "config", None)
        config_key = getattr(config, "api_key", None)
        for candidate in (api_key, config_key):
            if isinstance(candidate, str) and candidate and candidate not in secrets:
                secrets.append(candidate)
    return secrets


def _redact(value: Any, secrets: Sequence[str]) -> Optional[str]:
    if value is None:
        return None
    return redact_secrets(str(value), secrets)


def _fallback_failures(client: LLMClient, secrets: Sequence[str]) -> list[Dict[str, Any]]:
    failures = getattr(client, "last_failures", [])
    if not isinstance(failures, (list, tuple)):
        return []
    result: list[Dict[str, Any]] = []
    for failure in failures:
        if isinstance(failure, Mapping):
            result.append(
                {
                    "provider_name": _redact(failure.get("provider_name"), secrets),
                    "message": _redact(failure.get("message"), secrets),
                    "retryable": failure.get("retryable"),
                    "status_code": failure.get("status_code"),
                }
            )
    return result


def _trace_record(
    *,
    provider_name: Any,
    model_name: Any,
    latency_ms: Any,
    request_id: Any,
    fallback_failures: list[Dict[str, Any]],
    parse_status: str,
    secrets: Sequence[str],
) -> Dict[str, Any]:
    latency = latency_ms if isinstance(latency_ms, (int, float)) and not isinstance(latency_ms, bool) else None
    return {
        "provider_name": _redact(provider_name, secrets),
        "model_name": _redact(model_name, secrets),
        "latency_ms": latency,
        "request_id": _redact(request_id, secrets),
        "fallback_failures": fallback_failures,
        "parse_status": parse_status,
    }


def _client_descriptors(client: LLMClient, secrets: Sequence[str]) -> list[Dict[str, Any]]:
    return [
        {
            "provider_name": _redact(getattr(provider, "provider_name", None), secrets),
            "model_name": _redact(getattr(provider, "model_name", None), secrets),
        }
        for provider in _provider_objects(client)
    ]


def _safe_json(value: Any, secrets: Sequence[str], *, indent: Optional[int] = 2) -> str:
    return redact_secrets(
        json.dumps(value, ensure_ascii=False, indent=indent, sort_keys=True),
        secrets,
    )


def _write_json(path: Path, value: Any, secrets: Sequence[str]) -> None:
    path.write_text(_safe_json(value, secrets) + "\n", encoding="utf-8")


def run_llm_rag_benchmark(
    *,
    embedder: EmbeddingBackend,
    cases: Optional[Sequence[RagEvalCase | Mapping[str, Any]]] = None,
    manifest_path: Optional[str | Path] = None,
    output_dir: str | Path = "artifacts/evaluation",
    run_id: str = "llm-rag-benchmark",
    llm_client: Optional[LLMClient] = None,
    allow_paid_fallback: bool = True,
    top_k: int = 3,
    context_policy: str = "adaptive",
    min_similarity: float = 0.40,
    relative_score_threshold: float = 0.85,
) -> Path:
    """Run an explicit LLM-backed RAG benchmark and write redacted artifacts."""

    normalized_cases, manifest_metadata = _load_cases(cases, manifest_path)
    client = llm_client if llm_client is not None else _build_default_llm_client(allow_paid_fallback)
    secrets = _collect_secrets(client)
    run_dir = Path(output_dir) / run_id
    run_dir.mkdir(parents=True, exist_ok=False)

    retrieval_report = evaluate_rag_cases(
        normalized_cases,
        embedder,
        top_k=top_k,
        context_policy=context_policy,
        min_similarity=min_similarity,
        relative_score_threshold=relative_score_threshold,
    )
    traces: list[Dict[str, Any]] = []
    case_runs: list[_CaseRun] = []

    for index, case in enumerate(normalized_cases):
        retrieved_ids = retrieval_report.cases[index].during_rag.retrieved_document_ids
        request = LLMRequest(
            prompt=_build_prompt(case, _assemble_context(case, retrieved_ids)),
            system=_SYSTEM_PROMPT,
            temperature=0.0,
            max_tokens=512,
            metadata={"benchmark_run_id": run_id, "case_id": case.case_id},
        )
        try:
            response = client.generate(request)
        except LLMFailure as exc:
            failures = _fallback_failures(client, secrets)
            if not failures:
                failures = [
                    {
                        "provider_name": _redact(exc.provider_name, secrets),
                        "message": _redact(str(exc), secrets),
                        "retryable": exc.retryable,
                        "status_code": exc.status_code,
                    }
                ]
            traces.append(
                _trace_record(
                    provider_name=getattr(exc, "provider_name", getattr(client, "provider_name", "unknown")),
                    model_name=getattr(client, "model_name", None),
                    latency_ms=None,
                    request_id=None,
                    fallback_failures=failures,
                    parse_status="not_run",
                    secrets=secrets,
                )
            )
            case_runs.append(
                _CaseRun(
                    case_id=case.case_id,
                    parsed=_malformed_output(),
                    guarded_decision=TrivalentDecision.UNDECIDABLE,
                    generation_status="failed",
                    trace_index=len(traces) - 1,
                )
            )
            continue
        except Exception:
            traces.append(
                _trace_record(
                    provider_name=getattr(client, "provider_name", "unknown"),
                    model_name=getattr(client, "model_name", None),
                    latency_ms=None,
                    request_id=None,
                    fallback_failures=[
                        {
                            "provider_name": _redact(getattr(client, "provider_name", "unknown"), secrets),
                            "message": "unexpected provider error",
                            "retryable": True,
                            "status_code": None,
                        }
                    ],
                    parse_status="not_run",
                    secrets=secrets,
                )
            )
            case_runs.append(
                _CaseRun(
                    case_id=case.case_id,
                    parsed=_malformed_output(),
                    guarded_decision=TrivalentDecision.UNDECIDABLE,
                    generation_status="failed",
                    trace_index=len(traces) - 1,
                )
            )
            continue

        parsed = parse_llm_output(getattr(response, "text", None))
        context_documents = [
            document
            for document_id in retrieved_ids
            for document in case.documents
            if document.document_id == document_id
        ]
        guarded_decision = _guardrail_decision(case, context_documents, parsed)
        traces.append(
            _trace_record(
                provider_name=getattr(response, "provider_name", getattr(client, "provider_name", "unknown")),
                model_name=getattr(response, "model_name", getattr(client, "model_name", None)),
                latency_ms=getattr(response, "latency_ms", None),
                request_id=getattr(response, "request_id", None),
                fallback_failures=_fallback_failures(client, secrets),
                parse_status=parsed.parse_status,
                secrets=secrets,
            )
        )
        traces[-1]["raw_decision"] = parsed.decision.value
        traces[-1]["guardrail_decision"] = guarded_decision.value
        traces[-1]["guardrail_applied"] = guarded_decision != parsed.decision
        case_runs.append(
            _CaseRun(
                case_id=case.case_id,
                parsed=parsed,
                guarded_decision=guarded_decision,
                generation_status="succeeded",
                trace_index=len(traces) - 1,
            )
        )

    generated_cases = [
        case.model_copy(update={"answer": case_run.parsed.answer})
        for case, case_run in zip(normalized_cases, case_runs)
    ]
    decisions = {
        case_run.case_id: case_run.guarded_decision for case_run in case_runs
    }

    def llm_answer_evaluator(case: RagEvalCase, _context: list[RagDocument]) -> TrivalentDecision:
        return decisions.get(case.case_id, TrivalentDecision.UNDECIDABLE)

    report = evaluate_rag_cases(
        generated_cases,
        embedder,
        answer_evaluator=llm_answer_evaluator,
        top_k=top_k,
        context_policy=context_policy,
        min_similarity=min_similarity,
        relative_score_threshold=relative_score_threshold,
    )
    successful_generations = sum(
        case_run.generation_status == "succeeded" for case_run in case_runs
    )
    valid_parses = sum(case_run.parsed.parse_status == "valid" for case_run in case_runs)
    if not case_runs or (successful_generations == len(case_runs) and valid_parses == len(case_runs)):
        status = "completed"
    elif successful_generations == 0:
        status = "failed"
    else:
        status = "partial"

    llm_cases = [
        {
            "case_id": case_run.case_id,
            "generation_status": case_run.generation_status,
            "decision": rag_case.post_rag.observed_decision.value
            if rag_case.post_rag.observed_decision
            else TrivalentDecision.UNDECIDABLE.value,
            "expected_decision": rag_case.post_rag.expected_decision.value
            if rag_case.post_rag.expected_decision
            else None,
            "decision_correct": rag_case.post_rag.decision_correct,
            "raw_decision": case_run.parsed.decision.value,
            "guardrail_applied": case_run.guarded_decision != case_run.parsed.decision,
            "parse_status": traces[case_run.trace_index]["parse_status"],
            "provider_trace_index": case_run.trace_index,
        }
        for case_run, rag_case in zip(case_runs, report.cases)
    ]
    used = []
    for trace in traces:
        if trace["parse_status"] == "not_run":
            continue
        descriptor = {
            "provider_name": trace["provider_name"],
            "model_name": trace["model_name"],
        }
        if descriptor not in used:
            used.append(descriptor)
    used_names = {item["provider_name"] for item in used}
    used_models = {item["model_name"] for item in used}
    metadata: Dict[str, Any] = {
        "schema_version": _SCHEMA_VERSION,
        "run_id": run_id,
        "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "commit_sha": _commit_sha(),
        "status": status,
        "sample_count": len(normalized_cases),
        "embedding_model": getattr(embedder, "model_name", embedder.__class__.__name__),
        "top_k": top_k,
        "context_assembly_policy": context_policy,
        "context_min_similarity": min_similarity if context_policy == "adaptive" else None,
        "context_relative_score_threshold": (
            relative_score_threshold if context_policy == "adaptive" else None
        ),
        "llm_api_key_required": True,
        "provider_policy": {
            "primary": "nvidia",
            "paid_fallback": "openrouter" if allow_paid_fallback else None,
            "allow_paid_fallback": bool(allow_paid_fallback),
            "client": "injected" if llm_client is not None else "default",
        },
        "configured_providers": _client_descriptors(client, secrets),
        "providers_used": used,
        "provider_name": next(iter(used_names)) if len(used_names) == 1 else ("multiple" if used_names else None),
        "model_name": next(iter(used_models)) if len(used_models) == 1 else ("multiple" if used_models else None),
        "post_rag_evaluator": "llm_json_decision_evaluator",
        **manifest_metadata,
    }
    report_payload = report.model_dump(mode="json")
    raw_accuracy_values = [
        float(case_run.parsed.decision == case.expected_decision)
        for case_run, case in zip(case_runs, normalized_cases)
        if case.expected_decision is not None
    ]
    report_payload.update(
        {
            "schema_version": _SCHEMA_VERSION,
            "run_id": run_id,
            "status": status,
            "provider_trace": traces,
            "llm_cases": llm_cases,
            "llm_raw_decision_accuracy": (
                sum(raw_accuracy_values) / len(raw_accuracy_values) if raw_accuracy_values else 0.0
            ),
            "llm_guardrailed_decision_accuracy": report.stage_metrics["post_rag.decision_accuracy"],
        }
    )
    _write_json(run_dir / "metadata.json", metadata, secrets)
    _write_json(run_dir / "report.json", report_payload, secrets)
    (run_dir / "provider_trace.jsonl").write_text(
        "".join(_safe_json(trace, secrets, indent=None) + "\n" for trace in traces),
        encoding="utf-8",
    )

    summary_lines = [
        "# LLM RAG Benchmark",
        "",
        f"- Status: `{status}`",
        f"- Samples: `{len(normalized_cases)}`",
        f"- Embedding model: `{metadata['embedding_model']}`",
        f"- Provider policy: NVIDIA first; OpenRouter paid fallback: `{'yes' if allow_paid_fallback else 'no'}`",
        "- LLM API key required: `yes`",
        f"- Context assembly: `{context_policy}`",
        "",
        "## Retrieval And Context Metrics",
        "",
    ]
    summary_lines.extend(
        f"- `{name}`: `{value:.4f}`"
        for name, value in report.stage_metrics.items()
    )
    summary_lines.extend(
        [
            "",
            f"- `llm_raw_decision_accuracy`: `{report_payload['llm_raw_decision_accuracy']:.4f}`",
            f"- `llm_guardrailed_decision_accuracy`: `{report_payload['llm_guardrailed_decision_accuracy']:.4f}`",
        ]
    )
    summary_lines.extend(["", "## Decisions", ""])
    summary_lines.extend(
        f"- `{item['case_id']}`: `{item['decision']}` ({item['parse_status']})"
        for item in llm_cases
    )
    (run_dir / "summary.md").write_text(
        redact_secrets("\n".join(summary_lines) + "\n", secrets),
        encoding="utf-8",
    )
    return run_dir
