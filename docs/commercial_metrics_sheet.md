# Commercial Metrics Sheet

## Seed Evidence

| Metric | Current value | Scope |
| --- | ---: | --- |
| Synthetic seed samples | 12 | engineering/scientific seed |
| Correct decisions | 11 | deterministic seed baseline |
| False allow rate | 0.0833 | deterministic seed baseline |
| False block rate | 0.0 | deterministic seed baseline |
| Useful abstention rate | 0.8 | deterministic seed baseline |
| Harmful abstention rate | 0.0 | deterministic seed baseline |
| Full regression suite | 209 passing tests | local repository |

## Known Limitation

`policy-undecidable-001` is currently expected as `UNDECIDABLE` but observed as `TRUE`. This is a policy uncertainty hardening target before stronger policy-governance claims.

## Pilot Metrics To Collect

- Setup time in engineer-hours.
- Number of samples reviewed.
- False allow count and rate.
- False block count and rate.
- `UNDECIDABLE` count and usefulness rating.
- Proof lookup success rate.
- Time to reconstruct a decision.
- Number of policy/ontology changes required.

## Reporting Boundary

These metrics support discovery and pilot evaluation. Do not present seed metrics as production accuracy.
