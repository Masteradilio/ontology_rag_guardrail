import os
import logging
from typing import List, Any
from pathlib import Path

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


def _build_ollama_llm() -> Any:
    model = _clean_env_value(os.environ.get("LLM_LOCAL_MODEL"))
    if not model:
        return None

    from langchain_ollama import ChatOllama
    from ragas.llms import LangchainLLMWrapper

    return LangchainLLMWrapper(
        ChatOllama(
            model=model,
            base_url=_ollama_base_url(),
            temperature=0,
            client_kwargs={"timeout": 15},
            sync_client_kwargs={"timeout": 15},
            async_client_kwargs={"timeout": 15},
        )
    )


def _build_nvidia_llm() -> Any:
    api_key = _clean_env_value(os.environ.get("LLM_API_NVIDIA_KEY"))
    if not api_key:
        return None

    free_source = _clean_env_value(os.environ.get("LLM_API_FREE_SOURCE"))
    if free_source and free_source.lower() == "nvidia":
        model = _clean_env_value(os.environ.get("LLM_API_FREE_MODEL"))
    else:
        model = _clean_env_value(os.environ.get("LLM_API_FREE_NVIDIA_MODEL"))
    if not model:
        model = _clean_env_value(os.environ.get("LLM_API_PAID_NVIDIA_MODEL"))
    if not model:
        return None

    from langchain_openai import ChatOpenAI
    from ragas.llms import LangchainLLMWrapper

    return LangchainLLMWrapper(
        ChatOpenAI(
            model=model,
            api_key=api_key,
            base_url="https://integrate.api.nvidia.com/v1",
            temperature=0,
            timeout=15,
        )
    )


def _build_paid_openrouter_llm() -> Any:
    api_key = _clean_env_value(os.environ.get("LLM_API_OPENROUTER_KEY"))
    model = _clean_env_value(os.environ.get("LLM_API_PAID_OPENROUTER_MODEL"))
    if not api_key or not model:
        return None

    from langchain_openai import ChatOpenAI
    from ragas.llms import LangchainLLMWrapper

    return LangchainLLMWrapper(
        ChatOpenAI(
            model=model,
            api_key=api_key,
            base_url="https://openrouter.ai/api/v1",
            temperature=0,
            timeout=15,
            default_headers={"HTTP-Referer": "https://github.com/groundcite"},
        )
    )


def _build_paid_openai_llm() -> Any:
    api_key = _clean_env_value(os.environ.get("LLM_API_OPENAI_KEY") or os.environ.get("OPENAI_API_KEY"))
    model = _clean_env_value(os.environ.get("LLM_API_PAID_OPENAI_MODEL"))
    if not api_key or not model:
        return None

    from langchain_openai import ChatOpenAI
    from ragas.llms import LangchainLLMWrapper

    return LangchainLLMWrapper(
        ChatOpenAI(
            model=model,
            api_key=api_key,
            temperature=0,
            timeout=15,
        )
    )


def _llm_candidates() -> list[tuple[str, Any]]:
    candidates = [
        ("nvidia_free", _build_nvidia_llm()),
        ("openrouter_paid", _build_paid_openrouter_llm()),
        ("openai_paid", _build_paid_openai_llm()),
        ("ollama_local", _build_ollama_llm()),
    ]
    return [(name, llm) for name, llm in candidates if llm is not None]


class RagasRealAdapter:
    """
    Adapter que orquestra a biblioteca Ragas REAL para meta-avaliação.
    Faz a tradução das nossas classes para a biblioteca externa oficial.
    """
    
    def __init__(self):
        try:
            from ragas.metrics import faithfulness
            self.metric = faithfulness
        except ImportError:
            raise ImportError("Ragas não está instalado.")
            
    def evaluate_batch(self, samples: List[Sample]) -> Any:
        from ragas import evaluate
        from ragas.run_config import RunConfig
        from datasets import Dataset as HFDataset
        
        data = {
            "user_input": [],
            "response": [],
            "retrieved_contexts": [],
            "ground_truth": [] 
        }
        
        for s in samples:
            data["user_input"].append(s.question)
            data["response"].append(s.answer)
            data["retrieved_contexts"].append([c.text for c in s.contexts])
            data["ground_truth"].append(s.reference_answer or "")
            
        dataset = HFDataset.from_dict(data)
        
        logger.info(f"Executando Ragas REAL para {len(samples)} amostras...")
        last_error = None
        for candidate_name, llm in _llm_candidates():
            try:
                logger.info("Executando Ragas REAL com provider: %s", candidate_name)
                result = evaluate(
                    dataset=dataset,
                    metrics=[self.metric],
                    llm=llm,
                    run_config=RunConfig(timeout=15, max_retries=0, max_wait=15, max_workers=1),
                    show_progress=False,
                    raise_exceptions=True,
                )
                logger.info("Ragas REAL concluido com provider: %s", candidate_name)
                return result.to_pandas()
            except Exception as exc:
                last_error = exc
                logger.error("Ragas provider %s falhou: %s", candidate_name, exc)
                continue
        
        raise RuntimeError(f"Todos os providers Ragas falharam. Ultimo erro: {last_error}") from last_error

# Mantendo stubs emuladores
class Dataset:
    pass
def evaluate(*args, **kwargs):
    pass
faithfulness = None
