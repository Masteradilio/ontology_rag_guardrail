# Enterprise RAG Benchmark V1

This package expands the four-case regression seed into 96 balanced cases
covering 24 enterprise policy families:

- customer support and refunds;
- records retention;
- identity and access;
- privacy and data export;
- incident response;
- third-party risk;
- finance and expenses;
- travel;
- people operations;
- service management;
- cybersecurity;
- information governance;
- data governance;
- procurement;
- business continuity;
- legal operations;
- IT service management;
- software engineering;
- restricted records access;
- AI governance;
- data residency;
- customer identity;
- knowledge management;
- workplace operations.

Each family contains one supported case, one contradicted case, one
insufficient-evidence case, and one partial-coverage case. Candidate context
lists intentionally include noise and one duplicated retrieval in contradicted
cases so the benchmark can distinguish retrieval ranking from context assembly.

The package is balanced by case type: 24 supported, 24 contradicted, 24
insufficient-evidence, and 24 partial-coverage cases.

## Provenance

The corpus is **template-generated and semisynthetic**. It contains no
production records, names, account identifiers, or personal data. The scenario
language is modeled on common enterprise policy workflows, but it must not be
described as a real customer dataset or as evidence of production quality.

The generator is committed at
`data/evaluation/rag_enterprise_v1/generate_cases.py`. Recreate the JSONL and
manifest with:

```powershell
python data/evaluation/rag_enterprise_v1/generate_cases.py
```

The manifest records the provenance and privacy status. A future real-data
version should replace the generated records only after legal/privacy review,
identifier removal, label adjudication, and a train/evaluation split.

## Intended Use

Use this package for threshold calibration and portfolio benchmarking. The
main artifact reports precision, recall, F1, useful abstention, harmful
abstention, context size, and the selected threshold. It is still an
engineering benchmark, not a production RAG accuracy claim.
