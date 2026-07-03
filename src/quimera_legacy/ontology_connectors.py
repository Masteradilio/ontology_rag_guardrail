"""Connectores de ontologia para múltiplos domínios."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional


@dataclass
class ConnectorPayload:
    facts: List[Dict[str, str]]
    source: str


class OntologyConnector:
    domain: str = "general"
    name: str = "connector"

    def __init__(self, sources: Optional[Iterable[Path]] = None) -> None:
        self.sources = [Path(s) for s in sources] if sources else []

    def _default_facts(self) -> List[Dict[str, str]]:
        raise NotImplementedError

    def fetch_entries(self) -> List[Dict[str, List[Dict[str, str]]]]:
        payloads: List[Dict[str, List[Dict[str, str]]]] = []
        if self.sources:
            for source in self.sources:
                facts: List[Dict[str, str]] = []
                try:
                    data = json.loads(source.read_text(encoding="utf-8"))
                    facts = data.get("facts", [])
                except Exception:  # pragma: no cover
                    facts = []
                if not facts:
                    facts = self._default_facts()
                payloads.append({"facts": facts, "source": str(source)})
        else:
            payloads.append({"facts": self._default_facts(), "source": self.name})
        return payloads


class _FileBackedConnector(OntologyConnector):
    default_samples: List[Dict[str, str]] = []

    def _default_facts(self) -> List[Dict[str, str]]:
        return list(self.default_samples)


class MedicalConnector(_FileBackedConnector):
    domain = "medical"
    name = "medical_connector"
    default_samples = [
        {"subject": "febre", "relation": "indica", "object": "processo_inflamatorio", "state": "TRUE"},
        {"subject": "paciente", "relation": "apresenta", "object": "febre", "state": "TRUE"},
    ]


class FinancialConnector(_FileBackedConnector):
    domain = "financial"
    name = "financial_connector"
    default_samples = [
        {"subject": "acao", "relation": "pertence_setor", "object": "tecnologia", "state": "TRUE"},
        {"subject": "inflacao", "relation": "impacta", "object": "taxa_juros", "state": "TRUE"},
    ]


class ComputingConnector(_FileBackedConnector):
    domain = "computacao"
    name = "computing_connector"
    default_samples = [
        {"subject": "python", "relation": "e_linguagem", "object": "programacao", "state": "TRUE"},
        {"subject": "algoritmo", "relation": "resolve", "object": "problema", "state": "TRUE"},
    ]


class ScienceConnector(_FileBackedConnector):
    domain = "ciencias"
    name = "science_connector"
    default_samples = [
        {"subject": "gravidade", "relation": "e_forca", "object": "fundamental", "state": "TRUE"},
        {"subject": "evolucao", "relation": "explica", "object": "diversidade", "state": "TRUE"},
    ]


class ReligionConnector(_FileBackedConnector):
    domain = "religiao"
    name = "religion_connector"
    default_samples = [
        {"subject": "ritual", "relation": "associado_a", "object": "tradicao", "state": "TRUE"},
        {"subject": "etica", "relation": "influencia", "object": "comportamento", "state": "TRUE"},
    ]


__all__ = [
    "OntologyConnector",
    "ConnectorPayload",
    "MedicalConnector",
    "FinancialConnector",
    "ComputingConnector",
    "ScienceConnector",
    "ReligionConnector",
]
