# Agent Integration Guide

Ontology RAG Guardrail can be placed in front of agent tool calls so actions require semantic and policy authorization before execution.

## Minimal Pattern

```python
from quimera_semantic_trust_guardrail import SemanticTrustRuntime

runtime = SemanticTrustRuntime(tenant_id="tenant_a")

decision = runtime.action_check(
    actor="support_agent",
    action="refund",
    resource="order_123",
    purpose="customer_support",
    context={"channel": "chat"},
)

if decision.recommended_action.value == "allow":
    execute_tool()
elif decision.decision.value == "UNDECIDABLE":
    request_human_approval()
else:
    block_tool_call()
```

## Authorization Model

Agent permissions should be modeled as tenant-scoped semantic facts or policy facts. The runtime defaults to `UNDECIDABLE` when an action has no explicit authorization. This is deliberate: missing authorization is not automatically the same as a policy denial, but it is not enough to execute the action.

## Suggested Agent Gate

1. Planner proposes a tool call.
2. Application converts the tool call into actor/action/resource/purpose/context.
3. `action_check` evaluates policy and ontology facts.
4. The application only executes the tool for `TRUE` plus `allow`.
5. `UNDECIDABLE` routes to retry with more context or human approval.
6. `FALSE` routes to block and incident/audit handling as appropriate.

## Audit Requirements

Store the proof id alongside the agent trace. For high-risk actions, include the ontology version, policy version, actor identity, resource id, and approval outcome in the application audit trail.
