"""Optional FastAPI runtime for Quimera Semantic Trust Guardrail.

This module is intentionally lazy: the rest of the product can be used
without FastAPI installed. The ``[fastapi]`` optional extra pulls in
``fastapi`` and ``uvicorn[standard]`` for the HTTP runtime.

Tenant authentication is currently a *placeholder*: callers pass an
``X-Tenant-ID`` header. A real deployment should swap
:func:`require_tenant` for a JWT or API-key check before exposing this
app publicly.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

try:
    from fastapi import (
        Depends,
        FastAPI,
        Header,
        HTTPException,
        Path,
        status,
    )
    from pydantic import BaseModel, Field
except ImportError as exc:  # pragma: no cover - requires optional extra
    raise ImportError(
        "FastAPI runtime requires the [fastapi] extra. "
        "Install with: pip install 'quimera-semantic-trust-guardrail[fastapi]'"
    ) from exc

from . import __version__
from .decision_model import SemanticTrustDecision
from .main import GuardrailsConfig, QuimeraGuardrails


def _default_ontology_for(guardrails: QuimeraGuardrails) -> str:
    """Return the active ontology_id, the first existing one, or a
    freshly created default ontology for the tenant."""
    if guardrails.ontology_id:
        return guardrails.ontology_id
    existing = guardrails.list_ontologies()
    if existing:
        return existing[0]["ontology_id"]
    return guardrails.create_ontology(
        name="Default",
        domain="default",
    )


# ---------------------------------------------------------------------------
# Request/response models
# ---------------------------------------------------------------------------


class ClaimCheckRequest(BaseModel):
    claim: str = Field(..., min_length=1, description="The claim to validate.")
    domain: Optional[str] = None
    context: Optional[Dict[str, Any]] = None
    evidence: Optional[List[Dict[str, Any]]] = None
    ontology_id: Optional[str] = None


class AnswerCheckRequest(BaseModel):
    answer: str = Field(..., min_length=1)
    question: Optional[str] = None
    context: Optional[Dict[str, Any]] = None
    ontology_id: Optional[str] = None


class ActionCheckRequest(BaseModel):
    action: str = Field(..., min_length=1)
    actor: Optional[str] = None
    resource: Optional[str] = None
    purpose: Optional[str] = None
    tenant: Optional[str] = None
    context: Optional[Dict[str, Any]] = None
    ontology_id: Optional[str] = None


class PolicyCheckRequest(BaseModel):
    text: str = Field(..., min_length=1)
    scope: str = "output"
    context: Optional[Dict[str, Any]] = None
    ontology_id: Optional[str] = None


class SnapshotRequest(BaseModel):
    ontology_id: Optional[str] = None
    name: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class RollbackRequest(BaseModel):
    ontology_id: Optional[str] = None
    snapshot_id: str = Field(..., min_length=1)


# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------


def _decision_to_dict(decision: SemanticTrustDecision) -> Dict[str, Any]:
    return {
        "decision": decision.decision.value,
        "recommended_action": decision.recommended_action.value,
        "confidence": decision.confidence,
        "status": decision.status.value,
        "subject": decision.subject,
        "evidence": [e.model_dump(mode="json") for e in decision.evidence],
        "contradictions": [c.model_dump(mode="json") for c in decision.contradictions],
        "missing_requirements": [
            m.model_dump(mode="json") for m in decision.missing_requirements
        ],
        "proof": decision.proof.model_dump(mode="json"),
        "source": decision.source,
        "metadata": decision.metadata,
    }


def create_app(
    proof_storage_path: str = ".quimera_http_proofs",
    ontology_storage_path: str = ".quimera_http_ontologies",
) -> FastAPI:
    """Create a FastAPI app exposing the runtime checks as HTTP endpoints.

    The app keeps a ``QuimeraGuardrails`` instance per tenant, lazily
    created on the first request that names that tenant. This is a
    *placeholder* suitable for local testing; production deployments
    should manage lifecycle explicitly and add real authentication.
    """

    app = FastAPI(
        title="Quimera Semantic Trust Guardrail",
        version=__version__,
        description=(
            "HTTP runtime exposing the Quimera semantic trust API. "
            "All tenant-scoped endpoints require an `X-Tenant-ID` header."
        ),
    )

    # Per-tenant guardrail instances are created lazily and cached on
    # the app state to share proof storage across requests.
    tenants: Dict[str, QuimeraGuardrails] = {}

    def get_guardrails(tenant_id: str) -> QuimeraGuardrails:
        existing = tenants.get(tenant_id)
        if existing is not None:
            return existing
        # Allow tests / examples to pre-seed a guardrails instance on the
        # app under `app.tenant_guardrails` so they can inject adapters.
        preset = getattr(app, "tenant_guardrails", None)
        if isinstance(preset, dict) and tenant_id in preset:
            seeded = preset[tenant_id]
            tenants[tenant_id] = seeded
            return seeded
        config = GuardrailsConfig(
            proof_storage_path=f"{proof_storage_path.rstrip('/')}/{tenant_id}",
            ontology_storage_path=f"{ontology_storage_path.rstrip('/')}/{tenant_id}",
        )
        guardrails = QuimeraGuardrails(
            tenant_id=tenant_id,
            config=config,
            compliance_standards=["LGPD"],
        )
        tenants[tenant_id] = guardrails
        return guardrails

    def require_tenant(
        x_tenant_id: Optional[str] = Header(
            default=None,
            alias="X-Tenant-ID",
            description="Tenant identifier. Required for all guarded endpoints.",
        )
    ) -> str:
        if not x_tenant_id or not x_tenant_id.strip():
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing or empty X-Tenant-ID header.",
            )
        return x_tenant_id.strip()

    @app.get("/health")
    async def health() -> Dict[str, Any]:
        return {"status": "ok", "version": __version__}

    @app.post("/claim-check")
    async def claim_check(
        payload: ClaimCheckRequest,
        tenant_id: str = Depends(require_tenant),
    ) -> Dict[str, Any]:
        guardrails = get_guardrails(tenant_id)
        result = await guardrails.claim_check(
            payload.claim,
            domain=payload.domain,
            context=payload.context,
            evidence=payload.evidence,
            ontology_id=payload.ontology_id,
        )
        return _decision_to_dict(result)

    @app.post("/answer-check")
    async def answer_check(
        payload: AnswerCheckRequest,
        tenant_id: str = Depends(require_tenant),
    ) -> Dict[str, Any]:
        guardrails = get_guardrails(tenant_id)
        result = await guardrails.answer_check(
            payload.answer,
            question=payload.question,
            context=payload.context,
            ontology_id=payload.ontology_id,
        )
        return _decision_to_dict(result)

    @app.post("/action-check")
    async def action_check(
        payload: ActionCheckRequest,
        tenant_id: str = Depends(require_tenant),
    ) -> Dict[str, Any]:
        guardrails = get_guardrails(tenant_id)
        result = await guardrails.action_check(
            action=payload.action,
            actor=payload.actor or "anonymous",
            resource=payload.resource or "unknown",
            purpose=payload.purpose,
            tenant_id=payload.tenant or tenant_id,
            context=payload.context,
            ontology_id=payload.ontology_id,
        )
        return _decision_to_dict(result)

    @app.post("/policy-check")
    async def policy_check(
        payload: PolicyCheckRequest,
        tenant_id: str = Depends(require_tenant),
    ) -> Dict[str, Any]:
        guardrails = get_guardrails(tenant_id)
        result = await guardrails.policy_check(
            payload.text,
            scope=payload.scope,
            context=payload.context,
            ontology_id=payload.ontology_id,
        )
        return _decision_to_dict(result)

    @app.get("/proofs/{proof_id}")
    async def get_proof(
        proof_id: str = Path(..., min_length=1),
        tenant_id: str = Depends(require_tenant),
    ) -> Dict[str, Any]:
        guardrails = get_guardrails(tenant_id)
        proof = guardrails.proof_lookup(proof_id)
        if proof is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Proof {proof_id!r} not found for tenant {tenant_id!r}.",
            )
        return proof

    @app.post("/ontologies/snapshots")
    async def snapshot_ontology(
        payload: SnapshotRequest,
        tenant_id: str = Depends(require_tenant),
    ) -> Dict[str, Any]:
        guardrails = get_guardrails(tenant_id)
        ontology_id = payload.ontology_id or _default_ontology_for(guardrails)
        return guardrails.snapshot_ontology(
            ontology_id=ontology_id,
            name=payload.name,
            metadata=payload.metadata,
        )

    @app.post("/ontologies/rollback")
    async def rollback_ontology(
        payload: RollbackRequest,
        tenant_id: str = Depends(require_tenant),
    ) -> Dict[str, Any]:
        guardrails = get_guardrails(tenant_id)
        ontology_id = payload.ontology_id or _default_ontology_for(guardrails)
        try:
            return guardrails.rollback_ontology(
                snapshot_id=payload.snapshot_id,
                ontology_id=ontology_id,
            )
        except FileNotFoundError as exc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=str(exc),
            ) from exc

    @app.get("/ontologies/snapshots")
    async def list_snapshots(
        ontology_id: Optional[str] = None,
        tenant_id: str = Depends(require_tenant),
    ) -> Dict[str, Any]:
        guardrails = get_guardrails(tenant_id)
        if ontology_id is None:
            ontology_id = _default_ontology_for(guardrails)
        return {
            "snapshots": guardrails.list_ontology_snapshots(ontology_id=ontology_id),
        }

    return app


__all__ = ["create_app"]
