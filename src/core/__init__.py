"""Compatibility namespace for Quimera original reference tests.

The product package keeps the copied Quimera modules under ``quimera_legacy``.
These shims preserve the historical ``core.*`` import paths used by the
reference test suite without making them part of the new public SDK surface.
"""

__all__ = [
    "knowledge_ontology",
    "llm_hypothesis_parser",
    "proof_ledger",
    "qgsl_core",
    "symbolic_inference",
    "truth_mapping",
    "validation_cascade",
]
