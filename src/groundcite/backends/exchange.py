import json
import time
from pathlib import Path
from typing import Dict, Any

# Diretório e arquivo para o cache local de taxas de câmbio (armazenado na pasta do usuário)
CACHE_DIR = Path.home() / ".groundcite"
CACHE_FILE = CACHE_DIR / "exchange_cache.json"

# Lista de principais moedas do mundo suportadas pelo sistema de ROI
SUPPORTED_CURRENCIES: Dict[str, str] = {
    "USD": "Dólar Americano",
    "BRL": "Real Brasileiro",
    "EUR": "Euro",
    "GBP": "Libra Esterlina",
    "JPY": "Iene Japonês",
    "CAD": "Dólar Canadense",
    "AUD": "Dólar Australiano",
    "CHF": "Franco Suíço",
    "CNY": "Yuan Chinês",
}

# Taxas estáticas padrão de fallback (caso a rede esteja offline/indisponível)
# Mapeia o valor de 1 USD nas respectivas moedas
EXCHANGE_FALLBACK: Dict[str, float] = {
    "USD": 1.0,
    "BRL": 5.00,
    "EUR": 0.92,
    "GBP": 0.79,
    "JPY": 155.0,
    "CAD": 1.36,
    "AUD": 1.50,
    "CHF": 0.90,
    "CNY": 7.24,
}

# Tabela global de taxas de câmbio vigentes em relação ao USD
EXCHANGE_RATES: Dict[str, float] = EXCHANGE_FALLBACK.copy()

def update_exchange_cache(force: bool = False) -> Dict[str, float]:
    """
    Carrega as taxas de câmbio do cache local ou consulta a API pública para obter taxas atualizadas.
    Mantém cache local válido por 24 horas.
    
    Args:
        force: Se True, ignora o cache local de 24h e força atualização pela rede.
        
    Returns:
        Dicionário atualizado de taxas de câmbio em relação ao USD.
    """
    global EXCHANGE_RATES
    
    # 1. Tenta carregar do cache local se o cache for válido (< 24 horas)
    if not force and CACHE_FILE.exists():
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                cache_data = json.load(f)
                
            last_updated = cache_data.get("last_updated", 0.0)
            if time.time() - last_updated < 86400:
                cached_rates = cache_data.get("rates", {})
                if cached_rates:
                    EXCHANGE_RATES.update(cached_rates)
                    return EXCHANGE_RATES
        except Exception:
            pass
            
    # 2. Executa a atualização pela rede usando a API pública gratuita do ExchangeRate
    try:
        import urllib.request
        
        req = urllib.request.Request(
            "https://open.er-api.com/v6/latest/USD",
            headers={"User-Agent": "GroundCite-ExchangeUpdater/0.1.0"}
        )
        
        # Timeout curto de 4 segundos para evitar travamentos
        with urllib.request.urlopen(req, timeout=4) as response:
            data = json.loads(response.read().decode("utf-8"))
            
        rates_data = data.get("rates", {})
        network_rates: Dict[str, float] = {}
        
        # Filtra apenas as moedas suportadas pelo nosso sistema
        for currency_code in SUPPORTED_CURRENCIES:
            if currency_code in rates_data:
                network_rates[currency_code] = float(rates_data[currency_code])
                
        if network_rates:
            # Cria a pasta de cache local se necessário e salva o arquivo
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump({
                    "last_updated": time.time(),
                    "rates": network_rates
                }, f, indent=2)
                
            EXCHANGE_RATES.update(network_rates)
            
    except Exception:
        # Falha silenciosa para manter robustez e segurança
        pass
        
    return EXCHANGE_RATES

# Inicializa o cache de câmbio de forma automática na primeira importação do módulo
update_exchange_cache()

def convert_usd_to(usd_value: float, target_currency: str) -> float:
    """
    Converte um valor em USD para a moeda de destino selecionada.
    
    Args:
        usd_value: Valor em USD.
        target_currency: Código da moeda de destino (ex: 'BRL', 'EUR').
        
    Returns:
        Valor convertido.
    """
    currency_code = target_currency.upper()
    rate = EXCHANGE_RATES.get(currency_code)
    
    if rate is None:
        # Se a moeda não for diretamente suportada ou faltar, recorre a fallback local
        rate = EXCHANGE_FALLBACK.get(currency_code, 1.0)
        
    return usd_value * rate
