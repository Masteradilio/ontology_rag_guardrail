import os
import asyncio
import logging
from typing import List, Dict, Any
from pathlib import Path

import requests

from groundcite.schema import Sample

logger = logging.getLogger(__name__)

try:
    from dotenv import find_dotenv, load_dotenv

    env_path = find_dotenv(usecwd=True)
    if env_path:
        load_dotenv(env_path)
    else:
        root_env = Path(__file__).resolve().parents[3] / ".env"
        if root_env.exists():
            load_dotenv(root_env)
except ImportError:
    pass


def _clean_env_value(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip().strip('"\'')
    return cleaned or None


def _ollama_base_url() -> str:
    return os.environ.get("OLLAMA_HOST", "http://localhost:11434")


class _OllamaDeepEvalModel:
    def __new__(cls, *args, **kwargs):
        from deepeval.models import DeepEvalBaseLLM

        class OllamaDeepEvalModel(DeepEvalBaseLLM):
            def __init__(self, model: str, base_url: str):
                self.base_url = base_url.rstrip("/")
                super().__init__(model=model)

            def load_model(self, *args, **kwargs):
                return self

            def generate(self, prompt: str, *args, **kwargs) -> str:
                response = requests.post(
                    f"{self.base_url}/api/generate",
                    json={
                        "model": self.name,
                        "prompt": prompt,
                        "stream": False,
                        "options": {"temperature": 0},
                    },
                    timeout=15,
                )
                response.raise_for_status()
                return response.json().get("response", "")

            async def a_generate(self, prompt: str, *args, **kwargs) -> str:
                return await asyncio.to_thread(self.generate, prompt, *args, **kwargs)

            def get_model_name(self, *args, **kwargs) -> str:
                return f"ollama/{self.name}"

        return OllamaDeepEvalModel(*args, **kwargs)


def _build_ollama_model() -> Any:
    model = _clean_env_value(os.environ.get("LLM_LOCAL_MODEL"))
    if not model:
        return None
    return _OllamaDeepEvalModel(model=model, base_url=_ollama_base_url())


class _NvidiaDeepEvalModel:
    def __new__(cls, *args, **kwargs):
        from deepeval.models import DeepEvalBaseLLM

        class NvidiaDeepEvalModel(DeepEvalBaseLLM):
            def __init__(self, model: str, api_key: str):
                self.api_key = api_key
                super().__init__(model=model)

            def load_model(self, *args, **kwargs):
                return self

            def generate(self, prompt: str, *args, **kwargs) -> str:
                response = requests.post(
                    "https://integrate.api.nvidia.com/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": self.name,
                        "messages": [{"role": "user", "content": prompt}],
                        "temperature": 0,
                    },
                    timeout=15,
                )
                response.raise_for_status()
                data = response.json()
                return data["choices"][0]["message"]["content"]

            async def a_generate(self, prompt: str, *args, **kwargs) -> str:
                return await asyncio.to_thread(self.generate, prompt, *args, **kwargs)

            def get_model_name(self, *args, **kwargs) -> str:
                return f"nvidia/{self.name}"

        return NvidiaDeepEvalModel(*args, **kwargs)


def _build_nvidia_model() -> Any:
    api_key = _clean_env_value(os.environ.get("LLM_API_NVIDIA_KEY"))
    if not api_key:
        return None

    free_source = _clean_env_value(os.environ.get("LLM_API_FREE_SOURCE"))
    if free_source and free_source.lower() == "nvidia":
        model = _clean_env_value(os.environ.get("LLM_API_FREE_MODEL"))
        if model:
            return _NvidiaDeepEvalModel(model=model, api_key=api_key)

    model = _clean_env_value(os.environ.get("LLM_API_FREE_NVIDIA_MODEL"))
    if not model:
        model = _clean_env_value(os.environ.get("LLM_API_PAID_NVIDIA_MODEL"))
    if not model:
        return None
    return _NvidiaDeepEvalModel(model=model, api_key=api_key)


class _RestFallbackDeepEvalModel:
    def __new__(cls, *args, **kwargs):
        from deepeval.models import DeepEvalBaseLLM

        class RestFallbackDeepEvalModel(DeepEvalBaseLLM):
            def __init__(self, providers: list[dict[str, str]]):
                self.providers = providers
                super().__init__(model=providers[0]["model"])

            def load_model(self, *args, **kwargs):
                return self

            def _endpoint(self, source: str) -> str | None:
                source = source.lower()
                if source == "nvidia":
                    return "https://integrate.api.nvidia.com/v1/chat/completions"
                if source == "openrouter":
                    return "https://openrouter.ai/api/v1/chat/completions"
                if source == "openai":
                    return "https://api.openai.com/v1/chat/completions"
                return None

            def generate(self, prompt: str, *args, **kwargs) -> str:
                last_error: Exception | None = None
                for provider in self.providers:
                    endpoint = self._endpoint(provider["source"])
                    if not endpoint:
                        continue
                    headers = {
                        "Authorization": f"Bearer {provider['api_key']}",
                        "Content-Type": "application/json",
                    }
                    if provider["source"].lower() == "openrouter":
                        headers["HTTP-Referer"] = "https://github.com/groundcite"
                    try:
                        response = requests.post(
                            endpoint,
                            headers=headers,
                            json={
                                "model": provider["model"],
                                "messages": [{"role": "user", "content": prompt}],
                                "temperature": 0,
                            },
                            timeout=15,
                        )
                        response.raise_for_status()
                        data = response.json()
                        return data["choices"][0]["message"]["content"]
                    except Exception as exc:
                        last_error = exc
                        logger.warning("DeepEval provider %s/%s failed: %s", provider["source"], provider["model"], exc)
                        continue
                raise RuntimeError(f"All DeepEval REST providers failed. Last error: {last_error}")

            async def a_generate(self, prompt: str, *args, **kwargs) -> str:
                return await asyncio.to_thread(self.generate, prompt, *args, **kwargs)

            def get_model_name(self, *args, **kwargs) -> str:
                names = ",".join(f"{item['source']}/{item['model']}" for item in self.providers)
                return f"fallback({names})"

        return RestFallbackDeepEvalModel(*args, **kwargs)


def _append_provider(providers: list[dict[str, str]], seen: set[tuple[str, str]], source: str | None, model: str | None) -> None:
    source = _clean_env_value(source)
    model = _clean_env_value(model)
    if not source or not model:
        return
    key_name = f"LLM_API_{source.upper()}_KEY"
    api_key = _clean_env_value(os.environ.get(key_name))
    if not api_key:
        return
    key = (source.lower(), model)
    if key in seen:
        return
    seen.add(key)
    providers.append({"source": source, "model": model, "api_key": api_key})


def _configured_rest_providers() -> list[dict[str, str]]:
    providers: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()

    free_source = _clean_env_value(os.environ.get("LLM_API_FREE_SOURCE"))
    if free_source and free_source.lower() != "openrouter":
        _append_provider(providers, seen, free_source, os.environ.get("LLM_API_FREE_MODEL"))

    for i in range(1, 10):
        source = _clean_env_value(os.environ.get(f"LLM_API_FREE_SOURCE_{i}"))
        if not source:
            break
        if source.lower() == "openrouter":
            continue
        _append_provider(providers, seen, source, os.environ.get(f"LLM_API_FREE_{source.upper()}_MODEL"))

    for i in range(1, 10):
        source = _clean_env_value(os.environ.get(f"LLM_API_PAID_SOURCE_{i}"))
        if not source:
            break
        _append_provider(providers, seen, source, os.environ.get(f"LLM_API_PAID_{source.upper()}_MODEL"))

    return providers


def _build_rest_fallback_model() -> Any:
    providers = _configured_rest_providers()
    if not providers:
        return None
    return _RestFallbackDeepEvalModel(providers=providers)

class DeepEvalRealAdapter:
    """
    Adapter que orquestra a biblioteca DeepEval REAL para avaliação,
    mas cuida da formatação do GroundCite (JSONL -> DeepEval -> JSONL).
    Dessa forma a meta-avaliação do benchmark roda na biblioteca concorrente verdadeira.
    """
    
    def __init__(self, threshold: float = 0.5):
        try:
            from deepeval.metrics import HallucinationMetric

            provider_model = _build_rest_fallback_model() or _build_ollama_model()
            self.metric = HallucinationMetric(threshold=threshold, model=provider_model)
            self.threshold = threshold
        except ImportError:
            raise ImportError("DeepEval não está instalado. Instale com `pip install deepeval`")
            
    def evaluate_sample(self, sample: Sample) -> Dict[str, Any]:
        from deepeval.test_case import LLMTestCase
        
        test_case = LLMTestCase(
            input=sample.question,
            actual_output=sample.answer,
            context=[c.text for c in sample.contexts]
        )
        
        try:
            self.metric.measure(test_case)
            score = self.metric.score
            reason = self.metric.reason
            is_successful = self.metric.is_successful()
        except Exception as e:
            logger.error(f"Erro ao processar DeepEval real (Amostra {sample.id}): {e}")
            score = 1.0 # Penalidade máxima em caso de erro da lib
            reason = str(e)
            is_successful = False
            
        return {
            "id": sample.id,
            "deepeval_hallucination_score": score,
            "deepeval_reason": reason,
            "is_successful": is_successful,
            "adapter_error": None if is_successful else reason,
        }

# Mantendo os nomes emuladores antigos expostos por compatibilidade
class LLMTestCase:
    pass
class HallucinationMetric:
    pass
