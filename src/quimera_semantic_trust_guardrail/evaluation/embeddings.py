"""Embedding backends for reproducible evaluation runs.

The base SDK does not import Sentence Transformers at module import time. This
keeps the runtime lightweight while allowing evaluation commands to use a real
local embedding model when the optional dependency is installed.
"""

from __future__ import annotations

import hashlib
from math import sqrt
from typing import List, Optional, Protocol, Sequence


DEFAULT_EMBEDDING_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"


class EmbeddingDependencyError(RuntimeError):
    """Raised when the optional Sentence Transformers dependency is unavailable."""


class EmbeddingBackend(Protocol):
    """Minimal contract required by the RAG evaluation pipeline."""

    model_name: str

    def encode(self, texts: Sequence[str]) -> List[List[float]]:
        """Return one vector for each input text."""


def cosine_similarity(left: Sequence[float], right: Sequence[float]) -> float:
    """Compute cosine similarity without requiring NumPy."""

    if len(left) != len(right):
        raise ValueError("embedding vectors must have the same dimension")
    left_norm = sqrt(sum(value * value for value in left))
    right_norm = sqrt(sum(value * value for value in right))
    if not left_norm or not right_norm:
        return 0.0
    return sum(a * b for a, b in zip(left, right)) / (left_norm * right_norm)


class SentenceTransformerEmbedding:
    """Lazy local embedding backend backed by ``sentence-transformers``."""

    model_name: str

    def __init__(
        self,
        model_name: str = DEFAULT_EMBEDDING_MODEL,
        *,
        device: Optional[str] = None,
        batch_size: int = 32,
        normalize_embeddings: bool = True,
    ) -> None:
        if batch_size < 1:
            raise ValueError("batch_size must be positive")
        self.model_name = model_name
        self.device = device
        self.batch_size = batch_size
        self.normalize_embeddings = normalize_embeddings
        self._model = None

    def _load_model(self):
        if self._model is not None:
            return self._model
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:  # pragma: no cover - depends on environment
            raise EmbeddingDependencyError(
                "Embedding evaluation requires sentence-transformers. "
                "Install with: pip install -e '.[evaluation]'"
            ) from exc
        kwargs = {}
        if self.device:
            kwargs["device"] = self.device
        self._model = SentenceTransformer(self.model_name, **kwargs)
        return self._model

    def encode(self, texts: Sequence[str]) -> List[List[float]]:
        """Encode text locally and return JSON-serializable vectors."""

        values = list(texts)
        if not values:
            return []
        model = self._load_model()
        encoded = model.encode(
            values,
            batch_size=self.batch_size,
            normalize_embeddings=self.normalize_embeddings,
            convert_to_numpy=True,
            show_progress_bar=False,
        )
        return [[float(value) for value in vector] for vector in encoded]


class DeterministicHashEmbedding:
    """Small offline baseline for showcases and unit tests.

    It is intentionally not presented as a semantic model. Its purpose is to
    keep the showcase runnable without a model download while the benchmark
    uses the real Sentence Transformers backend.
    """

    def __init__(self, dimensions: int = 128) -> None:
        if dimensions < 8:
            raise ValueError("dimensions must be at least 8")
        self.dimensions = dimensions
        self.model_name = f"deterministic-hash-{dimensions}d"

    def encode(self, texts: Sequence[str]) -> List[List[float]]:
        vectors: List[List[float]] = []
        for text in texts:
            vector = [0.0] * self.dimensions
            for token in text.lower().split():
                digest = hashlib.sha256(token.encode("utf-8")).digest()
                index = int.from_bytes(digest[:4], "big") % self.dimensions
                vector[index] += 1.0
            norm = sqrt(sum(value * value for value in vector))
            vectors.append([value / norm for value in vector] if norm else vector)
        return vectors
