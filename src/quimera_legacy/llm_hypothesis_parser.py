"""Parser robusto para hipóteses estruturadas de LLMs.

Este módulo implementa um parser não-ganancioso que:
1. Usa contagem de chaves para extrair o primeiro JSON válido
2. Aceita apenas blocos marcados por sentinelas
3. Valida schema obrigatório (facts[], rules[], meta)
4. Rejeita textos com múltiplos JSONs ou lixo fora das sentinelas
"""

import json
import re
import logging
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class ParseResult(Enum):
    """Resultado do parsing de hipóteses."""
    SUCCESS = "success"
    NO_SENTINELS = "no_sentinels"
    INVALID_JSON = "invalid_json"
    INVALID_SCHEMA = "invalid_schema"
    MULTIPLE_BLOCKS = "multiple_blocks"
    EXTRACTION_ERROR = "extraction_error"


@dataclass
class HypothesisParseResult:
    """Resultado do parsing de hipóteses estruturadas."""
    success: bool
    data: Optional[Dict[str, Any]] = None
    error_type: Optional[ParseResult] = None
    error_message: Optional[str] = None
    raw_json: Optional[str] = None


class HypothesisParseError(Exception):
    """Exceção específica para erros de parsing de hipóteses."""
    def __init__(self, message: str, error_type: ParseResult):
        super().__init__(message)
        self.error_type = error_type


class LLMHypothesisParser:
    """Parser robusto para hipóteses estruturadas de LLMs.
    
    Implementa parsing não-ganancioso com:
    - Contagem de chaves para extrair primeiro JSON válido
    - Suporte a sentinelas BEGIN_HYPOTHESES_JSON/END_HYPOTHESES_JSON
    - Suporte a blocos fenced ```json
    - Validação rigorosa de schema
    """
    
    # Sentinelas suportadas
    SENTINEL_BEGIN = "BEGIN_HYPOTHESES_JSON"
    SENTINEL_END = "END_HYPOTHESES_JSON"
    
    # Schema obrigatório
    REQUIRED_FIELDS = {"facts", "rules", "meta"}
    
    def __init__(self, strict_sentinels: bool = True):
        """Inicializa o parser.
        
        Args:
            strict_sentinels: Se True, exige sentinelas. Se False, tenta extrair JSON sem sentinelas.
        """
        self.strict_sentinels = strict_sentinels
        
    def parse(self, text: str) -> HypothesisParseResult:
        """Faz o parsing de hipóteses estruturadas do texto.
        
        Args:
            text: Texto contendo hipóteses estruturadas
            
        Returns:
            HypothesisParseResult com resultado do parsing
        """
        try:
            # 1. Tentar extrair com sentinelas primeiro
            json_blocks = self._extract_with_sentinels(text)
            
            if not json_blocks:
                # 2. Tentar extrair com fenced code blocks
                json_blocks = self._extract_fenced_json(text)
                
            if not json_blocks:
                if self.strict_sentinels:
                    return HypothesisParseResult(
                        success=False,
                        error_type=ParseResult.NO_SENTINELS,
                        error_message="Nenhum bloco JSON com sentinelas encontrado"
                    )
                else:
                    # 3. Fallback: tentar extrair primeiro JSON válido
                    json_blocks = self._extract_first_valid_json(text)
                    
            if not json_blocks:
                return HypothesisParseResult(
                    success=False,
                    error_type=ParseResult.NO_SENTINELS,
                    error_message="Nenhum JSON válido encontrado"
                )
                
            # Verificar se há múltiplos blocos (rejeitamos isso)
            if len(json_blocks) > 1:
                logger.warning(f"Múltiplos blocos JSON encontrados ({len(json_blocks)}), rejeitando")
                return HypothesisParseResult(
                    success=False,
                    error_type=ParseResult.MULTIPLE_BLOCKS,
                    error_message=f"Múltiplos blocos JSON encontrados: {len(json_blocks)}"
                )
                
            # Processar o único bloco encontrado
            raw_json = json_blocks[0]
            
            # Parse do JSON
            try:
                data = json.loads(raw_json)
            except json.JSONDecodeError as e:
                return HypothesisParseResult(
                    success=False,
                    error_type=ParseResult.INVALID_JSON,
                    error_message=f"JSON inválido: {str(e)}",
                    raw_json=raw_json
                )
                
            # Validação do schema
            validation_result = self._validate_schema(data)
            if not validation_result[0]:
                return HypothesisParseResult(
                    success=False,
                    error_type=ParseResult.INVALID_SCHEMA,
                    error_message=validation_result[1],
                    raw_json=raw_json
                )
                
            logger.debug(f"Parsing bem-sucedido: {len(data.get('facts', []))} facts, {len(data.get('rules', []))} rules")
            
            return HypothesisParseResult(
                success=True,
                data=data,
                raw_json=raw_json
            )
            
        except Exception as e:
            logger.error(f"Erro inesperado no parsing: {e}")
            return HypothesisParseResult(
                success=False,
                error_type=ParseResult.EXTRACTION_ERROR,
                error_message=f"Erro inesperado: {str(e)}"
            )
    
    def _extract_with_sentinels(self, text: str) -> List[str]:
        """Extrai blocos JSON marcados com sentinelas BEGIN/END."""
        pattern = rf"{self.SENTINEL_BEGIN}\s*\n?(.+?)\n?\s*{self.SENTINEL_END}"
        matches = re.findall(pattern, text, re.DOTALL | re.IGNORECASE)
        
        json_blocks = []
        for match in matches:
            # Limpar whitespace e tentar extrair JSON
            cleaned = match.strip()
            if self._is_valid_json_structure(cleaned):
                json_blocks.append(cleaned)
                
        return json_blocks
    
    def _extract_fenced_json(self, text: str) -> List[str]:
        """Extrai blocos JSON de fenced code blocks (```json)."""
        pattern = r"```json\s*\n?(.+?)\n?\s*```"
        matches = re.findall(pattern, text, re.DOTALL | re.IGNORECASE)
        
        json_blocks = []
        for match in matches:
            cleaned = match.strip()
            if self._is_valid_json_structure(cleaned):
                json_blocks.append(cleaned)
                
        return json_blocks
    
    def _extract_first_valid_json(self, text: str) -> List[str]:
        """Extrai o primeiro JSON válido usando contagem de chaves (não-ganancioso)."""
        json_blocks = []
        
        # Encontrar todas as posições de '{'
        brace_positions = [i for i, char in enumerate(text) if char == '{']
        
        for start_pos in brace_positions:
            json_candidate = self._extract_balanced_json(text, start_pos)
            if json_candidate and self._is_valid_json_structure(json_candidate):
                json_blocks.append(json_candidate)
                break  # Apenas o primeiro JSON válido
                
        return json_blocks
    
    def _extract_balanced_json(self, text: str, start_pos: int) -> Optional[str]:
        """Extrai JSON balanceado a partir de uma posição usando stack de chaves."""
        if start_pos >= len(text) or text[start_pos] != '{':
            return None
            
        brace_count = 0
        in_string = False
        escape_next = False
        
        for i in range(start_pos, len(text)):
            char = text[i]
            
            if escape_next:
                escape_next = False
                continue
                
            if char == '\\' and in_string:
                escape_next = True
                continue
                
            if char == '"' and not escape_next:
                in_string = not in_string
                continue
                
            if not in_string:
                if char == '{':
                    brace_count += 1
                elif char == '}':
                    brace_count -= 1
                    
                    if brace_count == 0:
                        # JSON completo encontrado
                        return text[start_pos:i+1]
                        
        return None  # JSON não balanceado
    
    def _is_valid_json_structure(self, text: str) -> bool:
        """Verifica se o texto tem estrutura JSON válida."""
        try:
            json.loads(text)
            return True
        except json.JSONDecodeError:
            return False
    
    def _validate_schema(self, data: Any) -> Tuple[bool, str]:
        """Valida o schema das hipóteses.
        
        Args:
            data: Dados para validar
            
        Returns:
            Tuple (is_valid, error_message)
        """
        if not isinstance(data, dict):
            return False, "Dados devem ser um objeto JSON"
            
        # Verificar campos obrigatórios
        missing_fields = self.REQUIRED_FIELDS - set(data.keys())
        if missing_fields:
            return False, f"Campos obrigatórios ausentes: {missing_fields}"
            
        # Validar tipos dos campos
        facts = data.get("facts")
        if not isinstance(facts, list):
            return False, "Campo 'facts' deve ser uma lista"
            
        rules = data.get("rules")
        if not isinstance(rules, list):
            return False, "Campo 'rules' deve ser uma lista"
            
        meta = data.get("meta")
        if not isinstance(meta, dict):
            return False, "Campo 'meta' deve ser um objeto"
            
        # Validação adicional dos facts
        for i, fact in enumerate(facts):
            if not isinstance(fact, dict):
                return False, f"Fact {i} deve ser um objeto"
            if not all(key in fact for key in ["subject", "relation", "object"]):
                return False, f"Fact {i} deve ter campos 'subject', 'relation', 'object'"
                
        # Validação adicional das rules
        for i, rule in enumerate(rules):
            if not isinstance(rule, dict):
                return False, f"Rule {i} deve ser um objeto"
            if not all(key in rule for key in ["head", "body"]):
                return False, f"Rule {i} deve ter campos 'head', 'body'"
                
        return True, ""


# Função de conveniência para compatibilidade com código existente
def parse_hypotheses(text: str, strict_sentinels: bool = False) -> Dict[str, Any]:
    """Função de conveniência para parsing de hipóteses.
    
    Args:
        text: Texto contendo hipóteses
        strict_sentinels: Se True, exige sentinelas
        
    Returns:
        Dict com facts e rules
        
    Raises:
        HypothesisParseError: Se o parsing falhar
    """
    parser = LLMHypothesisParser(strict_sentinels=strict_sentinels)
    result = parser.parse(text)
    
    if not result.success:
        raise HypothesisParseError(result.error_message or "Parsing failed", result.error_type)
        
    # Retornar apenas facts e rules para compatibilidade
    return {
        "facts": result.data.get("facts", []),
        "rules": result.data.get("rules", [])
    }


if __name__ == "__main__":
    # Demonstração e testes básicos
    parser = LLMHypothesisParser(strict_sentinels=False)
    
    # Teste 1: JSON com sentinelas
    test1 = """
    Aqui está minha análise:
    
    BEGIN_HYPOTHESES_JSON
    {
        "facts": [
            {"subject": "João", "relation": "é", "object": "programador"}
        ],
        "rules": [
            {"head": "X é competente", "body": "X é programador"}
        ],
        "meta": {"confidence": 0.8}
    }
    END_HYPOTHESES_JSON
    
    Essa é minha conclusão.
    """
    
    result1 = parser.parse(test1)
    print(f"Teste 1 - Sentinelas: {result1.success}")
    if result1.success:
        print(f"  Facts: {len(result1.data['facts'])}")
        print(f"  Rules: {len(result1.data['rules'])}")
    else:
        print(f"  Erro: {result1.error_message}")
    
    # Teste 2: Múltiplos JSONs (deve falhar)
    test2 = """
    {"facts": [], "rules": [], "meta": {}}
    Algum texto no meio
    {"facts": ["outro"], "rules": [], "meta": {}}
    """
    
    result2 = parser.parse(test2)
    print(f"\nTeste 2 - Múltiplos JSONs: {result2.success}")
    if not result2.success:
        print(f"  Erro esperado: {result2.error_message}")
    
    # Teste 3: Fenced code block
    test3 = """
    Aqui está o resultado:
    
    ```json
    {
        "facts": [{"subject": "Maria", "relation": "trabalha_em", "object": "empresa"}],
        "rules": [],
        "meta": {"source": "analysis"}
    }
    ```
    
    Fim da análise.
    """
    
    result3 = parser.parse(test3)
    print(f"\nTeste 3 - Fenced JSON: {result3.success}")
    if result3.success:
        print(f"  Facts: {len(result3.data['facts'])}")
    else:
        print(f"  Erro: {result3.error_message}")