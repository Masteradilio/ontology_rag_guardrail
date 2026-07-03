import os
import json
import logging
import requests
from typing import List, Dict, Any, Optional
from groundcite.backends.base import BaseBackend
from pathlib import Path

try:
    from dotenv import load_dotenv, find_dotenv
    env_path = find_dotenv(usecwd=True)
    if env_path:
        load_dotenv(env_path)
    else:
        root_env = Path(__file__).parent.parent.parent.parent / ".env"
        if root_env.exists():
            load_dotenv(root_env)
except ImportError:
    pass

logger = logging.getLogger(__name__)

# Mantém um estado global dos modelos que falharam/deram timeout 
# para que nas próximas chamadas o fallback pule-os instantaneamente.
_BLACKLISTED_MODELS = set()

class JudgeBackend(BaseBackend):
    """Backend que utiliza LLM como juiz, com fallback prioritário e timeout REST estrito (15s)."""
    
    def __init__(
        self, 
        temperature: float = 0.0, 
        cache_enabled: bool = True, 
        refresh_cache: bool = False, 
        budget_usd: Optional[float] = None
    ):
        self.temperature = temperature
        self._models = self._load_model_hierarchy()
        self.cache_enabled = cache_enabled
        self.refresh_cache = refresh_cache
        self.budget_usd = budget_usd
        self.accumulated_cost = 0.0
        self.cache_file = Path.home() / ".groundcite" / "judge_cache.json"
        self._cache = self._load_cache()

    def _load_cache(self) -> Dict[str, Any]:
        if not self.cache_enabled or self.refresh_cache:
            return {}
        if self.cache_file.exists():
            try:
                with open(self.cache_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Falha ao carregar cache de judge: {e}")
        return {}

    def _save_cache(self):
        if not self.cache_enabled:
            return
        try:
            # Evita que o cache em disco cresça indefinidamente limitando a 1000 chaves (LRU)
            max_size = 1000
            if len(self._cache) > max_size:
                # Remove os itens mais antigos (primeiros inseridos)
                keys_to_remove = list(self._cache.keys())[:-max_size]
                for k in keys_to_remove:
                    self._cache.pop(k, None)
                    
            self.cache_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.cache_file, "w", encoding="utf-8") as f:
                json.dump(self._cache, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning(f"Falha ao salvar cache de judge: {e}")
    
    @staticmethod
    def _clean_env_value(value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        cleaned = value.strip().strip('"\'')
        return cleaned or None

    def _append_model(
        self,
        models: List[Dict[str, str]],
        seen: set[tuple[str, str, str]],
        source: Optional[str],
        model: Optional[str],
        model_type: str,
    ) -> None:
        source = self._clean_env_value(source)
        model = self._clean_env_value(model)
        if not source or not model:
            return
        key = (source.lower(), model, model_type)
        if key in seen:
            return
        seen.add(key)
        models.append({"source": source, "model": model, "type": model_type})

    def _load_model_hierarchy(self) -> List[Dict[str, str]]:
        models = []
        seen: set[tuple[str, str, str]] = set()

        # Prefer current single FREE provider format:
        # LLM_API_FREE_SOURCE="nvidia" + LLM_API_FREE_MODEL="minimaxai/minimax-m2.7".
        source = self._clean_env_value(os.environ.get("LLM_API_FREE_SOURCE"))
        if source and source.lower() != "openrouter":
            self._append_model(models, seen, source, os.environ.get("LLM_API_FREE_MODEL"), "free")

        # Backward-compatible numbered FREE providers. OpenRouter remains skipped for
        # free-tier routes because those models have been unstable in this project.
        for i in range(1, 10):
            source_key = f"LLM_API_FREE_SOURCE_{i}"
            if source_key in os.environ:
                source = self._clean_env_value(os.environ[source_key])
                if not source or source.lower() == "openrouter":
                    continue # Bypassa o OpenRouter nas APIs FREE permanentemente
                model_key = f"LLM_API_FREE_{source.upper()}_MODEL"
                self._append_model(models, seen, source, os.environ.get(model_key), "free")
            else:
                break
                
        # Carrega os modelos PAID
        for i in range(1, 10):
            source_key = f"LLM_API_PAID_SOURCE_{i}"
            if source_key in os.environ:
                source = self._clean_env_value(os.environ[source_key])
                model_key = f"LLM_API_PAID_{source.upper()}_MODEL"
                self._append_model(models, seen, source, os.environ.get(model_key), "paid")
            else:
                break
                
        return models

    def predict_support(
        self, 
        claim: str, 
        contexts: List[str], 
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Avalia o claim chamando os modelos configurados na ordem de prioridade via HTTP direto.
        """
        if not self._models:
            raise ValueError("Nenhum modelo LLM configurado nas variáveis de ambiente (.env).")
            
        system_prompt = (
            "You are an expert, highly precise multilingual scientific evaluator of RAG factual correctness.\n"
            "Your task is to strictly determine if a claim is supported, unsupported, or contradicted by the provided contexts.\n"
            "Apply these definitions strictly across all supported languages (English, Portuguese, Spanish, French, German, Chinese, Japanese, and Arabic):\n"
            "- \"supported\": The claim's factual core is fully and directly verified by the contexts. Minor stylistic variation or paraphrasing is allowed.\n"
            "- \"contradicted\": The claim directly conflicts with, denies, or refutes a fact explicitly written in the contexts. Any direct numeric, date, or quantitative conflict with a pre-existing value in the context MUST be classified as contradicted.\n"
            "- \"unsupported\": The claim introduces external, unverified information, entities, dates, assumptions, or hallucinations that are not mentioned in the contexts. Crucially, if a claim invents an entirely new fact or entity (e.g., claiming someone invented an unrelated device not in the text, or placing an event in an unmentioned year), it MUST be classified as \"unsupported\" rather than \"contradicted\", as there is no pre-existing factual claim in the context to contradict.\n"
            "Return ONLY a valid JSON object with the following keys (do not output any other text):\n"
            '- "label": strictly one of ["supported", "unsupported", "contradicted"].\n'
            '- "confidence": a float between 0.0 and 1.0.\n'
            '- "evidence_doc_idx": the 0-based integer index of the context supporting/contradicting the claim, or null if unsupported.\n'
            '- "evidence_span": an array [start, end] of the exact character span in the context supporting/contradicting the claim, or null.'
        )
        
        contexts_str = "\n".join([f"Context [{i}]: {ctx}" for i, ctx in enumerate(contexts)])
        user_prompt = f"Contexts:\n{contexts_str}\n\nClaim:\n{claim}\n\nEvaluate the claim."
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]

        import hashlib
        from groundcite.backends.pricing import calculate_inference_cost

        last_error = None
        for model_info in self._models:
            raw_model = model_info["model"]
            source = model_info["source"]
            
            # Pula imediatamente se este modelo provou ser instável (Timeout/Error contínuo)
            if raw_model in _BLACKLISTED_MODELS:
                continue

            # --- 1. Verificação de Cache Local ---
            cache_key = None
            if self.cache_enabled and not self.refresh_cache:
                key_data = json.dumps({
                    "claim": claim,
                    "contexts": contexts,
                    "model": raw_model,
                    "temperature": self.temperature
                }, sort_keys=True)
                cache_key = hashlib.sha256(key_data.encode("utf-8")).hexdigest()
                
                if cache_key in self._cache:
                    logger.info(f"CACHE HIT: Retornando resposta de {raw_model} do cache local.")
                    cached_val = self._cache[cache_key]
                    
                    # Atualiza a ordem do LRU movendo o item acessado para o fim do dicionário
                    self._cache.pop(cache_key)
                    self._cache[cache_key] = cached_val
                    self._save_cache()
                    
                    span = cached_val.get("evidence_span")
                    if span and isinstance(span, list) and len(span) == 2:
                        span = tuple(span)
                    else:
                        span = None
                    return {
                        "label": cached_val["label"],
                        "confidence": cached_val["confidence"],
                        "evidence_doc_idx": cached_val["evidence_doc_idx"],
                        "evidence_span": span,
                        "cached": True
                    }

            # --- 2. Budget Guard de API ---
            if self.budget_usd is not None and self.accumulated_cost > self.budget_usd:
                raise RuntimeError(
                    f"Orçamento limite de USD {self.budget_usd:.4f} excedido. "
                    f"Custo total acumulado: USD {self.accumulated_cost:.5f}"
                )
            
            api_key_env_var = f"LLM_API_{source.upper()}_KEY"
            api_key = self._clean_env_value(os.environ.get(api_key_env_var))
            
            logger.info(f"DEBUG: Enviando payload REST direto para {raw_model} (Source: {source}). Timeout: 15s")
            
            if not api_key:
                logger.warning(f"Chave de API {api_key_env_var} ausente. Pulando modelo.")
                continue

            try:
                headers = {
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                }
                
                payload = {
                    "model": raw_model,
                    "messages": messages,
                    "temperature": self.temperature,
                    "response_format": {"type": "json_object"}
                }

                url = ""
                if source.lower() == "openrouter":
                    url = "https://openrouter.ai/api/v1/chat/completions"
                    headers["HTTP-Referer"] = "https://github.com/groundcite" 
                elif source.lower() == "openai":
                    url = "https://api.openai.com/v1/chat/completions"
                elif source.lower() == "nvidia":
                    url = "https://integrate.api.nvidia.com/v1/chat/completions"
                else:
                    logger.warning(f"Source {source} não suportada via REST no momento.")
                    continue
                
                # Timeout real garantido pelo Requests (15 segundos)
                res = requests.post(url, headers=headers, json=payload, timeout=15.0)
                
                if res.status_code != 200:
                    raise Exception(f"HTTP {res.status_code}: {res.text}")
                    
                data = res.json()
                content = data["choices"][0]["message"]["content"]
                result = json.loads(content)
                
                label = result.get("label", "unsupported")
                if label not in ["supported", "unsupported", "contradicted"]:
                    label = "unsupported"
                
                evidence_span = result.get("evidence_span")
                if evidence_span and isinstance(evidence_span, list) and len(evidence_span) == 2:
                    evidence_span = tuple(evidence_span)
                else:
                    evidence_span = None
                    
                evidence_doc_idx = result.get("evidence_doc_idx")
                if evidence_doc_idx is not None:
                    try:
                        evidence_doc_idx = int(evidence_doc_idx)
                    except ValueError:
                        evidence_doc_idx = None
                
                result_payload = {
                    "label": label,
                    "confidence": float(result.get("confidence", 0.0)),
                    "evidence_doc_idx": evidence_doc_idx,
                    "evidence_span": evidence_span
                }

                # --- 3. Atualização Financeira e Persistência de Cache ---
                call_cost = calculate_inference_cost(
                    text_input=system_prompt + "\n" + user_prompt,
                    text_output=content,
                    model_name=raw_model
                )
                self.accumulated_cost += call_cost
                
                if self.cache_enabled and cache_key:
                    self._cache[cache_key] = result_payload
                    self._save_cache()

                return result_payload
            except requests.exceptions.Timeout:
                err_msg = f"Timeout de 15 segundos excedido para {raw_model}. Adicionado à blacklist."
                logger.warning(err_msg)
                last_error = err_msg
                _BLACKLISTED_MODELS.add(raw_model)
                continue
            except Exception as e:
                err_msg = f"Falha ao avaliar com {raw_model} ({model_info['type']}): {str(e)}. Adicionado à blacklist."
                logger.warning(err_msg)
                last_error = e
                _BLACKLISTED_MODELS.add(raw_model)
                continue
                
        logger.error(f"Todos os modelos falharam, deram timeout ou estão na blacklist. Último erro: {str(last_error)}")
        return {
            "label": "unsupported",
            "confidence": 0.0,
            "evidence_doc_idx": None,
            "evidence_span": None,
            "error": str(last_error)
        }
