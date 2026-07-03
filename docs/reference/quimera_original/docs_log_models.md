# Modelos de Logs/Ledger

O ledger registra eventos em JSONL no diretório `.quimera/ledger`.

## Campos comuns

- `query_id`: string curta (hash)
- `query`: amostra da consulta (até 200 chars)
- `prove`: objeto com `proved`, `rejected`, `undecidable`, `trace`
- `security`: status do middleware de segurança
- `budget` e `consumption`: métricas de uso/estimativa
- `energy`: `watts`, `source`, `sample_ms` (quando disponível)
- `governor`: estratégia do `EntropicGovernor`
- `energy_governance`: snapshot de metas/observado/ações quando habilitado
- `qutrit_used`, `qutrit_thresholds`
- `processing_time_ms`, `cache_hit`
- `version`, `checksum`, `ts`

## Exemplos

```
{
  "query_id": "abc123def456",
  "query": "Como calcular retorno percentual?",
  "prove": {"proved": [], "rejected": [], "undecidable": [], "trace": []},
  "energy": {"watts": 7.5, "source": "rapl", "sample_ms": 500},
  "energy_governance": {"enabled": true, "targets": {"watts": 12.0}},
  "qutrit_thresholds": {"true": 0.65, "false": 0.65, "margin": 0.02},
  "processing_time_ms": 530,
  "version": "quimera-v1.0",
  "checksum": "abcd0123ef45...",
  "ts": "2024-01-01T12:00:00"
}
```

## Conformidade/Auditoria

- Checagem de integridade via `checksum` (SHA‑256 parcial) por linha.
- Histórico de snapshots/rollback em `.quimera/knowledge/history.jsonl`.
- CLI para inspeção:
  - `quimera ledger` (contagem)
  - `quimera ledger --last` (última entrada)

