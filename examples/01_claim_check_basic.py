"""Runnable example: end-to-end claim check with the SDK.

Run with:
    .venv\\Scripts\\python.exe examples\\01_claim_check_basic.py
"""

from __future__ import annotations

import asyncio
import json

from quimera_semantic_trust_guardrail import (
    QuimeraGuardrails,
    SimpleKnowledgeAdapter,
)


async def main() -> None:
    adapter = SimpleKnowledgeAdapter()
    adapter.add_fact(
        "Refunds are available within 30 days.",
        source="policy",
        keywords=["refunds"],
    )
    guardrails = QuimeraGuardrails(
        tenant_id="example_tenant",
        knowledge_adapter=adapter,
    )

    supported = await guardrails.claim_check(
        "Refunds are available within 30 days.",
    )
    print("Supported claim:")
    print(json.dumps(supported.model_dump(mode="json"), indent=2, ensure_ascii=False))

    unsupported = await guardrails.claim_check(
        "An obscure claim with no support anywhere.",
    )
    print("\nUnsupported claim:")
    print(
        json.dumps(
            unsupported.model_dump(mode="json"), indent=2, ensure_ascii=False
        )
    )

    proof = guardrails.proof_lookup(supported.proof.proof_id)
    print("\nProof lookup:")
    print(json.dumps(proof, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    asyncio.run(main())
