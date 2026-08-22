from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from app.intelligence.claim_evolution import (
    load_claim_evolution,
    reconcile_claim_evolution_safely,
)
from app.intelligence.readiness import (
    build_backend_intelligence_readiness,
)


def build_router(
    *,
    require_admin,
    connection_factory,
) -> APIRouter:
    router = APIRouter()

    @router.get("/admin/intelligence/readiness")
    def intelligence_readiness(request: Request):
        require_admin(request)
        return build_backend_intelligence_readiness(
            connection_factory=connection_factory,
        )

    @router.get("/admin/intelligence/claims/{claim_id}/evolution")
    def intelligence_claim_evolution(
        claim_id: str,
        request: Request,
    ):
        require_admin(request)
        result = load_claim_evolution(
            claim_id=claim_id,
            connection_factory=connection_factory,
        )
        return result

    @router.post("/admin/intelligence/claims/{claim_id}/evolution/reconcile")
    def intelligence_reconcile_claim_evolution(
        claim_id: str,
        request: Request,
    ):
        require_admin(request)
        result = reconcile_claim_evolution_safely(
            claim_id=claim_id,
            connection_factory=connection_factory,
        )
        if result.get("status") == "not_found":
            raise HTTPException(status_code=404, detail="Claim not found.")
        return result

    return router


__all__ = ["build_router"]
