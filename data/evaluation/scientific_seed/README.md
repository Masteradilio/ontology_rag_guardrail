# Quimera Scientific Seed Dataset

This seed package is for engineering validation of Quimera Semantic Trust Guardrail. It is intentionally small and synthetic.

## Scope

The package covers:

- claim and answer validation labels: `supported`, `contradicted`, `unsupported`, and `partially_unsupported`;
- agent action authorization labels: `allow`, `deny`, and `missing_authorization`;
- policy/compliance labels: `policy_allow`, `policy_violation`, and `policy_undecidable`.

## Limitations

- The data does not support broad claims about real-world truth.
- The data does not prove legal compliance.
- The data is not a substitute for external benchmarks or customer pilot data.
- The dataset is intended to exercise runtime contracts, abstention behavior, proof capture, and failure analysis.
