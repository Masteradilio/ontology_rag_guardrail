import json
import time
from pathlib import Path
from typing import Dict

# Diretório e arquivo para o cache local de preços de API (armazenado na pasta do usuário)
CACHE_DIR = Path.home() / ".groundcite"
CACHE_FILE = CACHE_DIR / "pricing_cache.json"

# Tabela estática padrão de fallbacks (caso a rede esteja offline/indisponível)
# Mapeia preços oficiais por 1.000.000 (1 Milhão) de tokens em USD.
PRICING_MODELS: Dict[str, Dict[str, float]] = {
    # OpenAI
    "gpt-4o": {"input": 5.0, "output": 15.0},
    "gpt-4-turbo": {"input": 10.0, "output": 30.0},
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
    # Anthropic
    "claude-3-5-sonnet": {"input": 3.0, "output": 15.0},
    # Google
    "gemini-1.5-pro": {"input": 1.25, "output": 5.0},
    "gemini-1.5-flash": {"input": 0.075, "output": 0.30},
    # DeepSeek
    "deepseek-chat": {"input": 0.14, "output": 0.28},
    "deepseek-coder": {"input": 0.14, "output": 0.28},
    # Meta Llama
    "llama-3-70b": {"input": 0.60, "output": 0.80},
    "llama-3-8b": {"input": 0.05, "output": 0.05},
    # Mistral
    "mistral-large": {"input": 2.0, "output": 6.0},
    # Grok (xAI)
    "grok-beta": {"input": 2.0, "output": 10.0},
    # Moonshot (Kimi)
    "kimi-chat": {"input": 1.6, "output": 1.6},
    # GLM (Zhipu)
    "glm-4": {"input": 1.5, "output": 1.5},
}

def update_prices_cache(force: bool = False) -> Dict[str, Dict[str, float]]:
    """
    Carrega os preços do cache local ou busca os dados mais recentes na API do OpenRouter
    contendo os modelos líderes de mercado. Mantém cache local válido por 24 horas.
    
    Args:
        force: Se True, ignora o cache local de 24h e força atualização pela rede.
        
    Returns:
        Dicionário atualizado de preços dos modelos de LLM.
    """
    global PRICING_MODELS
    
    # 1. Tenta carregar do cache local se o cache for válido (< 24 horas)
    if not force and CACHE_FILE.exists():
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                cache_data = json.load(f)
                
            last_updated = cache_data.get("last_updated", 0.0)
            # 86400 segundos = 24 horas
            if time.time() - last_updated < 86400:
                cached_pricing = cache_data.get("pricing", {})
                if cached_pricing:
                    PRICING_MODELS.update(cached_pricing)
                    return PRICING_MODELS
        except Exception:
            # Se o cache estiver corrompido, ignora e tenta obter da rede
            pass
            
    # 2. Executa a atualização pela rede usando a biblioteca padrão do Python
    try:
        import urllib.request
        
        req = urllib.request.Request(
            "https://openrouter.ai/api/v1/models",
            headers={"User-Agent": "GroundCite-AutoUpdater/0.1.0"}
        )
        
        # Timeout curto de 4 segundos para não atrasar as execuções locais do usuário
        with urllib.request.urlopen(req, timeout=4) as response:
            data = json.loads(response.read().decode("utf-8"))
            
        models_data = data.get("data", [])
        network_pricing: Dict[str, Dict[str, float]] = {}
        
        for m in models_data:
            model_id = m.get("id", "").lower()
            pricing_info = m.get("pricing", {})
            
            prompt_price_str = pricing_info.get("prompt", "0.0")
            completion_price_str = pricing_info.get("completion", "0.0")
            
            try:
                # OpenRouter retorna preço por token em USD.
                # Multiplicamos por 1.000.000 para converter para o nosso padrão (por milhão de tokens)
                prompt_price = float(prompt_price_str) * 1_000_000.0
                completion_price = float(completion_price_str) * 1_000_000.0
                
                # Registra sob o id do OpenRouter (ex: 'openai/gpt-4o')
                network_pricing[model_id] = {"input": prompt_price, "output": completion_price}
                
                # Registra também sob o nome curto para conveniência (ex: 'gpt-4o')
                if "/" in model_id:
                    simple_id = model_id.split("/")[-1]
                    network_pricing[simple_id] = {"input": prompt_price, "output": completion_price}
                    
            except (ValueError, TypeError):
                continue
                
        if network_pricing:
            # Cria a pasta de cache local se necessário e salva o arquivo
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump({
                    "last_updated": time.time(),
                    "pricing": network_pricing
                }, f, indent=2)
                
            PRICING_MODELS.update(network_pricing)
            
    except Exception:
        # Falha silenciosa para manter robustez e segurança
        pass
        
    return PRICING_MODELS

# Inicializa o cache de precificação de forma automática na primeira importação do módulo
update_prices_cache()

def estimate_tokens(text: str, lang: str = "pt-BR") -> int:
    """
    Estima a quantidade de tokens contida em um texto baseado em caracteres.
    """
    if not text:
        return 0
    char_per_token = 3.0 if lang.lower().startswith("pt") else 4.0
    return max(1, int(len(text) / char_per_token))

def estimate_image_tokens(width: int = 512, height: int = 512, detail: str = "low") -> int:
    """
    Estima a quantidade de tokens consumidos por uma imagem com base na resolução
    e detalhamento de acordo com a especificação técnica multimodal de mercado (ex: OpenAI GPT-4o).
    """
    if detail.lower() == "low":
        return 85
        
    w, h = width, height
    if w <= 0 or h <= 0:
        return 85
        
    # Scale to fit 2048x2048
    if w > 2048 or h > 2048:
        scale = 2048.0 / max(w, h)
        w = int(w * scale)
        h = int(h * scale)
        
    # Scale shortest side to 768
    if w < h:
        scale = 768.0 / w
        w = 768
        h = int(h * scale)
    else:
        scale = 768.0 / h
        h = 768
        w = int(w * scale)
        
    # Conta blocos de 512x512
    tiles_w = (w + 511) // 512
    tiles_h = (h + 511) // 512
    total_tiles = tiles_w * tiles_h
    
    return (total_tiles * 170) + 85

def calculate_inference_cost(text_input: str, text_output: str, model_name: str, lang: str = "pt-BR") -> float:
    """
    Calcula o custo de inferência com base no dicionário atualizado de precificação.
    """
    # Garante que os preços estejam sempre alinhados
    pricing = PRICING_MODELS.get(model_name.lower())
    if not pricing:
        # Mapeia provedores comuns caso o usuário passe com barra (ex: 'openai/gpt-4o-mini')
        clean_name = model_name.split("/")[-1].lower() if "/" in model_name else model_name.lower()
        pricing = PRICING_MODELS.get(clean_name)
        
    if not pricing:
        # Fallback de segurança para precificação de baixíssimo custo
        pricing = {"input": 0.15, "output": 0.60}
        
    input_tokens = estimate_tokens(text_input, lang)
    output_tokens = estimate_tokens(text_output, lang)
    
    cost_input = (input_tokens / 1_000_000.0) * pricing["input"]
    cost_output = (output_tokens / 1_000_000.0) * pricing["output"]
    
    return cost_input + cost_output
