from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Request

from app.application.readiness import build_backend_readiness
from app.intelligence.claim_evolution import (
    reconcile_claim_evolution_safely,
)
from app.intelligence.story_evolution import build_story_evolution
from app.story.story_claim_graph_materialization import (
    StoryClaimGraphMaterializationIntegrityError,
)
from app.intelligence.readiness import (
    build_backend_intelligence_readiness,
)


def build_router(
    *,
    app,
    require_admin,
    connection_factory,
    operations_database_url: str = "",
) -> APIRouter:
    router = APIRouter()

    @router.get("/admin/readiness")
    def backend_readiness(request: Request):
        require_admin(request)
        return build_backend_readiness(
            app=app,
            connection_factory=connection_factory,
            operations_database_url=operations_database_url,
        )

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
        limit: int = Query(100, ge=1, le=500),
    ):
        require_admin(request)
        try:
            result = build_story_evolution(
                canonical_claim_id=claim_id,
                connection_factory=connection_factory,
                limit=limit,
            )
        except StoryClaimGraphMaterializationIntegrityError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        if result.get("status") == "not_found":
            raise HTTPException(status_code=404, detail="Claim not found.")
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
