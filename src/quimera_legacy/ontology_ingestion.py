from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, List, Optional, Dict, Any

from .knowledge_ontology import KnowledgeOntology
from .qgsl_core import LogicalQubit
from . import proof_ledger
from .ontology_connectors import (
    OntologyConnector,
    MedicalConnector,
    FinancialConnector,
    ComputingConnector,
    ScienceConnector,
    ReligionConnector,
)

logger = logging.getLogger(__name__)


@dataclass
class IngestionArtifact:
    source: str
    imported_facts: int
    skipped_facts: int
    conflicts: int
    duration_seconds: float
    domain: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class OntologyIngestionService:
    """Executa ingestão básica de ontologias em lote."""

    def __init__(self, ontology: KnowledgeOntology, snapshot_dir: Optional[Path] = None) -> None:
        self.ontology = ontology
        self.snapshot_dir = snapshot_dir or Path("data/ingestion_snapshots")
        self.snapshot_dir.mkdir(parents=True, exist_ok=True)
        self._recent_artifacts: List[IngestionArtifact] = []

    async def ingest_files(self, files: Iterable[Path]) -> List[IngestionArtifact]:
        results: List[IngestionArtifact] = []
        for path in files:
            results.append(await self._ingest_single(path))
        return results

    async def ingest_from_connector(self, connector: OntologyConnector) -> List[IngestionArtifact]:
        artifacts: List[IngestionArtifact] = []
        for payload in connector.fetch_entries():
            artifact = await self._ingest_entries(
                entries=payload["facts"],
                domain=connector.domain,
                source=payload.get("source", connector.name),
            )
            arts_metadata = {"connector": connector.name}
            artifact.metadata.update(arts_metadata)
            artifacts.append(artifact)
        return artifacts

    async def _ingest_single(self, path: Path) -> IngestionArtifact:
        start = asyncio.get_event_loop().time()
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:  # pragma: no cover
            logger.error("Falha ao ler ontologia %s: %s", path, exc)
            return IngestionArtifact(str(path), 0, 0, 0, 0.0, metadata={"error": str(exc)})

        artifact = await self._ingest_entries(
            entries=data.get("facts", []),
            domain=data.get("domain"),
            source=str(path),
            start_time=start,
        )
        return artifact

    async def _ingest_entries(
        self,
        entries: Iterable[Dict[str, Any]],
        *,
        domain: Optional[str],
        source: str,
        start_time: Optional[float] = None,
    ) -> IngestionArtifact:
        imported = skipped = conflicts = 0
        start_clock = start_time or asyncio.get_event_loop().time()

        for fact in entries:
            subject = fact.get("subject")
            relation = fact.get("relation")
            obj = fact.get("object")
            state = fact.get("state", "TRUE")
            if not all([subject, relation, obj]):
                skipped += 1
                continue
            existing = self.ontology.query({"subject": subject, "relation": relation, "object": obj})
            if existing and any(str(item.state) != state for item in existing):
                conflicts += 1
                continue
            self.ontology.add_fact(subject, relation, obj, LogicalQubit(state))
            imported += 1

        duration = asyncio.get_event_loop().time() - start_clock
        artifact = IngestionArtifact(
            source=source,
            imported_facts=imported,
            skipped_facts=skipped,
            conflicts=conflicts,
            duration_seconds=duration,
            domain=domain,
        )
        self._remember_artifact(artifact)
        self._record_artifact(artifact)
        logger.info(
            "Ingestão concluída: %s | domínio=%s importados=%s conflitos=%s", source, domain, imported, conflicts
        )
        return artifact

    def _remember_artifact(self, artifact: IngestionArtifact) -> None:
        self._recent_artifacts.append(artifact)
        if len(self._recent_artifacts) > 20:
            self._recent_artifacts.pop(0)

    def _record_artifact(self, artifact: IngestionArtifact) -> None:
        try:  # pragma: no cover
            proof_ledger.record(
                {
                    "event": "ontology_ingestion",
                    "source": artifact.source,
                    "domain": artifact.domain,
                    "imported": artifact.imported_facts,
                    "skipped": artifact.skipped_facts,
                    "conflicts": artifact.conflicts,
                    "duration": artifact.duration_seconds,
                    "timestamp": time.time(),
                }
            )
        except Exception as exc:
            logger.debug("Falha ao registrar ingestão no ledger: %s", exc)

    def get_recent_artifacts(self) -> List[IngestionArtifact]:
        return list(self._recent_artifacts)


__all__ = [
    "OntologyIngestionService",
    "IngestionArtifact",
    "OntologyConnector",
    "MedicalConnector",
    "FinancialConnector",
    "ComputingConnector",
    "ScienceConnector",
    "ReligionConnector",
]
