from groundcite.schema import (
    Context,
    EvidenceSpan,
    GoldClaim,
    GoldSchema,
    Sample,
    EvalResult,
)
from groundcite.evaluator import Evaluator
from groundcite.backends.base import BaseBackend
from groundcite.backends.lexical import LexicalBackend
from groundcite.backends.local_nli import LocalNLIBackend
from groundcite.backends.hybrid import HybridBackend

__version__ = "0.9.1.dev0"
__all__ = [
    "Context",
    "EvidenceSpan",
    "GoldClaim",
    "GoldSchema",
    "Sample",
    "EvalResult",
    "Evaluator",
    "BaseBackend",
    "LexicalBackend",
    "LocalNLIBackend",
    "HybridBackend",
]
