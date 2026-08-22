from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Request

from app.intelligence.claim_entity_context import (
    build_claim_entity_context,
)
from app.intelligence.claim_story_context import (
    build_claim_intelligence_context,
    build_story_intelligence_context,
)
from app.intelligence.claim_support_graph import (
    build_claim_support_graph,
    build_story_support_overview,
)
from app.intelligence.entity_resolution_runtime import (
    resolve_entity_mentions,
)
from app.intelligence.source_health import (
    build_source_evidence_health,
)


def build_router(
    *,
    require_admin,
    connection_factory,
) -> APIRouter:
    router = APIRouter()

    @router.get("/admin/intelligence/health")
    def intelligence_health(
        request: Request,
        days: int = Query(30, ge=1, le=365),
    ):
        require_admin(request)
        return build_source_evidence_health(
            connection_factory=connection_factory,
            days=days,
        )

    @router.get("/admin/intelligence/entities/resolve")
    def intelligence_entity_resolution(
        request: Request,
        text: str = Query(..., min_length=1, max_length=512),
        entity_type: str = Query("", max_length=64),
        sport_key: str = Query("", max_length=64),
        max_entities: int = Query(24, ge=1, le=100),
    ):
        require_admin(request)

        entity_types = (
            (entity_type,)
            if str(entity_type or "").strip()
            else None
        )

        return resolve_entity_mentions(
            text=text,
            connection_factory=connection_factory,
            entity_types=entity_types,
            sport_key=sport_key,
            max_entities=max_entities,
        )

    @router.get("/admin/intelligence/claim-entity-context")
    def intelligence_claim_entity_context(
        request: Request,
        text: str = Query(..., min_length=1, max_length=512),
        subject_key: str = Query(..., min_length=1, max_length=256),
        sport_key: str = Query("", max_length=64),
        max_entities: int = Query(24, ge=1, le=100),
    ):
        require_admin(request)
        return build_claim_entity_context(
            claim_text=text,
            subject_key=subject_key,
            connection_factory=connection_factory,
            sport_key=sport_key,
            max_entities=max_entities,
        )

    @router.get("/admin/intelligence/claims/{claim_id}/context")
    def intelligence_claim_context(
        claim_id: str,
        request: Request,
    ):
        require_admin(request)
        result = build_claim_intelligence_context(
            claim_id=claim_id,
            connection_factory=connection_factory,
        )
        if result.get("status") == "not_found":
            raise HTTPException(status_code=404, detail="Claim not found.")
        return result

    @router.get("/admin/intelligence/claims/{claim_id}/support-graph")
    def intelligence_claim_support_graph(
        claim_id: str,
        request: Request,
    ):
        require_admin(request)
        result = build_claim_support_graph(
            claim_id=claim_id,
            connection_factory=connection_factory,
        )
        if result.get("status") == "not_found":
            raise HTTPException(status_code=404, detail="Claim not found.")
        return result

    @router.get("/admin/intelligence/stories/{story_id}/context")
    def intelligence_story_context(
        story_id: str,
        request: Request,
    ):
        require_admin(request)
        result = build_story_intelligence_context(
            story_id=story_id,
            connection_factory=connection_factory,
        )
        if result.get("status") == "not_found":
            raise HTTPException(status_code=404, detail="Story not found.")
        return result

    @router.get("/admin/intelligence/stories/{story_id}/support-overview")
    def intelligence_story_support_overview(
        story_id: str,
        request: Request,
    ):
        require_admin(request)
        result = build_story_support_overview(
            story_id=story_id,
            connection_factory=connection_factory,
        )
        if result.get("status") == "not_found":
            raise HTTPException(status_code=404, detail="Story not found.")
        return result

    return router
