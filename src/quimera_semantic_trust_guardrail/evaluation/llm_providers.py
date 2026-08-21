"""LLM provider clients used by opt-in evaluation runs.

The scientific regression suite uses mocks for these clients. Real provider
calls are intentionally explicit so normal tests do not consume API budget or
leak secrets into logs.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Mapping, Optional, Protocol, Sequence
from urllib.parse import urlparse

import requests


NVIDIA_DEFAULT_BASE_URL = "https://integrate.api.nvidia.com/v1/chat/completions"


def _nvidia_base_url(configured_url: str) -> str:
    """Resolve an NVIDIA model-card reference to its inference endpoint."""

    url = configured_url.strip()
    parsed = urlparse(url)
    if parsed.netloc == "build.nvidia.com" and parsed.path.rstrip("/").endswith("/modelcard"):
        return NVIDIA_DEFAULT_BASE_URL
    return url or NVIDIA_DEFAULT_BASE_URL


class LLMFailure(RuntimeError):
    """Provider failure that can be recorded without exposing secrets."""

    def __init__(
        self,
        message: str,
        *,
        provider_name: str,
        retryable: bool = True,
        status_code: Optional[int] = None,
    ) -> None:
        super().__init__(message)
        self.provider_name = provider_name
        self.retryable = retryable
        self.status_code = status_code


@dataclass(frozen=True)
class LLMRequest:
    """Provider-neutral text generation request."""

    prompt: str
    system: Optional[str] = None
    temperature: float = 0.0
    max_tokens: int = 512
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class LLMResponse:
    """Provider-neutral response with audit metadata."""

    text: str
    provider_name: str
    model_name: str
    latency_ms: int
    usage: Dict[str, Any] = field(default_factory=dict)
    request_id: Optional[str] = None
    raw: Dict[str, Any] = field(default_factory=dict)


class LLMClient(Protocol):
    """Minimal contract for evaluation LLM clients."""

    provider_name: str
    model_name: str

    def generate(self, request: LLMRequest) -> LLMResponse:
        """Generate a response or raise ``LLMFailure``."""


@dataclass(frozen=True)
class ProviderConfig:
    """Configuration for OpenAI-compatible chat completion providers."""

    provider_name: str
    model_name: str
    api_key: str
    base_url: str
    timeout_seconds: float = 60.0
    extra_headers: Dict[str, str] = field(default_factory=dict)


def load_env_file(path: str | Path = ".env") -> Dict[str, str]:
    """Load simple KEY=VALUE entries from a local env file.

    Existing environment variables take precedence when callers merge this
    result with ``os.environ``. The function does not mutate the process env.
    """

    env_path = Path(path)
    values: Dict[str, str] = {}
    if not env_path.exists():
        return values
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def _merged_env(env: Optional[Mapping[str, str]] = None) -> Mapping[str, str]:
    if env is not None:
        return env
    file_env = load_env_file()
    return {**file_env, **os.environ}


def redact_secrets(text: str, secrets: Sequence[str]) -> str:
    """Redact configured secret values from a string."""

    redacted = text
    for secret in secrets:
        if secret:
            redacted = redacted.replace(secret, "[REDACTED]")
    return redacted


class OpenAICompatibleProvider:
    """Small client for chat-completions-compatible providers."""

    provider_name: str
    model_name: str

    def __init__(self, config: ProviderConfig) -> None:
        self.config = config
        self.provider_name = config.provider_name
        self.model_name = config.model_name

    def generate(self, request: LLMRequest) -> LLMResponse:
        if not self.config.api_key:
            raise LLMFailure("missing API key", provider_name=self.provider_name, retryable=False)
        if not self.config.base_url:
            raise LLMFailure("missing base URL", provider_name=self.provider_name, retryable=False)

        messages = []
        if request.system:
            messages.append({"role": "system", "content": request.system})
        messages.append({"role": "user", "content": request.prompt})
        payload = {
            "model": self.config.model_name,
            "messages": messages,
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
        }
        headers = {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json",
            **self.config.extra_headers,
        }

        started = time.perf_counter()
        try:
            response = requests.post(
                self.config.base_url,
                headers=headers,
                json=payload,
                timeout=self.config.timeout_seconds,
            )
        except requests.RequestException as exc:
            message = redact_secrets(str(exc), [self.config.api_key])
            raise LLMFailure(message, provider_name=self.provider_name, retryable=True) from exc

        latency_ms = int((time.perf_counter() - started) * 1000)
        request_id = response.headers.get("x-request-id") or response.headers.get("cf-ray")
        if response.status_code >= 400:
            body = redact_secrets(response.text[:500], [self.config.api_key])
            raise LLMFailure(
                f"HTTP {response.status_code}: {body}",
                provider_name=self.provider_name,
                retryable=response.status_code >= 500 or response.status_code == 429,
                status_code=response.status_code,
            )

        try:
            data = response.json()
        except (ValueError, requests.RequestException) as exc:
            raise LLMFailure(
                "provider response was not valid JSON",
                provider_name=self.provider_name,
                retryable=response.status_code >= 500,
                status_code=response.status_code,
            ) from exc
        try:
            text = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMFailure(
                "provider response did not include choices[0].message.content",
                provider_name=self.provider_name,
                retryable=False,
            ) from exc

        return LLMResponse(
            text=text,
            provider_name=self.provider_name,
            model_name=self.config.model_name,
            latency_ms=latency_ms,
            usage=data.get("usage", {}),
            request_id=request_id,
            raw={"id": data.get("id"), "object": data.get("object")},
        )


class NVIDIAProvider(OpenAICompatibleProvider):
    """MiniMax M3 provider through NVIDIA API."""

    def __init__(self, env: Optional[Mapping[str, str]] = None, timeout_seconds: float = 60.0) -> None:
        values = _merged_env(env)
        super().__init__(
            ProviderConfig(
                provider_name="nvidia",
                model_name=values.get("NVIDIA_LLM_MODEL", ""),
                api_key=values.get("NVIDIA_API_KEY", ""),
                base_url=_nvidia_base_url(values.get("NVIDIA_URL_REFERENCE_MODEL", "")),
                timeout_seconds=timeout_seconds,
            )
        )


class OpenRouterProvider(OpenAICompatibleProvider):
    """MiniMax M3 provider through OpenRouter fallback."""

    DEFAULT_BASE_URL = "https://openrouter.ai/api/v1/chat/completions"

    def __init__(self, env: Optional[Mapping[str, str]] = None, timeout_seconds: float = 60.0) -> None:
        values = _merged_env(env)
        super().__init__(
            ProviderConfig(
                provider_name="openrouter",
                model_name=values.get("OPENROUTER_LLM_MODEL", ""),
                api_key=values.get("OPENROUTER_API_KEY", ""),
                base_url=values.get("OPENROUTER_URL", self.DEFAULT_BASE_URL),
                timeout_seconds=timeout_seconds,
                extra_headers={
                    "HTTP-Referer": "https://github.com/Masteradilio/quimera_semantic_trust_guardrail",
                    "X-Title": "Ontology RAG Guardrail Evaluation",
                },
            )
        )


class FallbackLLMClient:
    """Try providers in priority order and keep a trace of failures."""

    provider_name = "fallback"

    def __init__(self, providers: Sequence[LLMClient]) -> None:
        if not providers:
            raise ValueError("at least one provider is required")
        self.providers = list(providers)
        self.model_name = " -> ".join(provider.model_name for provider in providers)
        self.last_failures: list[Dict[str, Any]] = []

    def generate(self, request: LLMRequest) -> LLMResponse:
        self.last_failures = []
        for provider in self.providers:
            try:
                return provider.generate(request)
            except LLMFailure as exc:
                self.last_failures.append(
                    {
                        "provider_name": exc.provider_name,
                        "message": str(exc),
                        "retryable": exc.retryable,
                        "status_code": exc.status_code,
                    }
                )
                continue
        raise LLMFailure("all providers failed", provider_name=self.provider_name, retryable=True)
