from __future__ import annotations

from fastapi import APIRouter, Query, Request

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

    return router
