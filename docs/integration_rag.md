# RAG Integration Guide

Ontology RAG Guardrail can be attached after retrieval and generation to decide whether an answer is supported enough to show, retry, abstain, or escalate.

## Minimal Pattern

```python
from quimera_semantic_trust_guardrail import SemanticTrustRuntime

runtime = SemanticTrustRuntime(tenant_id="tenant_a")

decision = runtime.answer_check(
    answer="The policy allows refunds within 30 days.",
    context={
        "domain": "support",
        "retrieved_documents": ["policy-v4"],
    },
    evidence=[
        {
            "id": "policy-v4#chunk-12",
            "text": "Customers may request refunds within 30 days.",
            "source": "refund_policy",
        }
    ],
)

if decision.decision.value == "TRUE":
    action = "show"
elif decision.decision.value == "UNDECIDABLE":
    action = "retrieve_more_or_abstain"
else:
    action = "block_or_regenerate"
```

## Recommended RAG Control Loop

1. Retrieve documents and keep source ids, chunk ids, spans, and document versions.
2. Generate an answer.
3. Run `answer_check` with the answer, retrieval context, and explicit evidence records.
4. If the result is `TRUE`, return the answer with citations.
5. If the result is `UNDECIDABLE`, retry retrieval with a narrower query or abstain.
6. If the result is `FALSE`, block or regenerate with contradiction details.
7. Persist the returned proof id with the application request log.

## GroundCite Mapping

GroundCite labels are mapped conservatively:

- `supported` -> `TRUE`
- `contradicted` -> `FALSE`
- `unsupported` and `partially_unsupported` -> `UNDECIDABLE`

This avoids treating absent support as a contradiction.

## Production Notes

Use stable evidence ids. Avoid sending sensitive data to external judges unless the deployment policy explicitly allows it. Treat Ontology RAG Guardrail output as an evidence-grounded runtime decision, not a factual proof about the world.
