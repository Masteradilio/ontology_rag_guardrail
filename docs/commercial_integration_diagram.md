# Commercial Integration Diagram

```mermaid
flowchart LR
    A["Enterprise RAG or Agent"] --> B["Ontology RAG Guardrail Runtime"]
    B --> C["claim_check / answer_check"]
    B --> D["action_check"]
    B --> E["policy_check"]
    C --> F["TRUE / FALSE / UNDECIDABLE"]
    D --> F
    E --> F
    F --> G["allow / retry / abstain / block / escalate"]
    F --> H["Proof metadata"]
    H --> I["Audit review"]
```

## Integration Notes

- RAG teams usually start with `answer_check`.
- Agent teams usually start with `action_check`.
- Compliance teams usually start with `policy_check` and proof lookup.
- `UNDECIDABLE` should route to retrieval retry, human review, or escalation.
