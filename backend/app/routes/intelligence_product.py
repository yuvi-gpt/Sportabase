from __future__ import annotations

from fastapi import APIRouter, HTTPException, Path, Query

from app.intelligence.product_history import (
    ProductIntelligenceIntegrityError, SEARCH_KINDS, claim_history, entity_history,
    media_history, search_intelligence, story_history,
)


def build_router(*, connection_factory) -> APIRouter:
    router = APIRouter(prefix="/intelligence", tags=["product-intelligence"])

    @router.get("/search")
    def search(q: str = Query(..., min_length=1, max_length=200), kind: list[str] | None = Query(None), sport_key: str = Query("", max_length=64), limit: int = Query(20, ge=1, le=100), cursor: str = Query("", max_length=4096)):
        if kind and any(value not in SEARCH_KINDS for value in kind):
            raise HTTPException(status_code=422, detail="Search kind is invalid.")
        try:
            return search_intelligence(q=q, kinds=kind, sport_key=sport_key, limit=limit, cursor=cursor, connection_factory=connection_factory)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    def history_params(after: str, before: str, limit: int, cursor: str) -> dict:
        return {"after": after, "before": before, "limit": limit, "cursor": cursor, "connection_factory": connection_factory}

    def result_or_error(builder, resource_id: str, label: str, after: str, before: str, limit: int, cursor: str):
        try:
            result = builder(**{label + "_id": resource_id}, **history_params(after, before, limit, cursor))
        except ProductIntelligenceIntegrityError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        if result is None:
            raise HTTPException(status_code=404, detail=label.title() + " not found.")
        return result

    def common_history(builder, resource_id, label, after, before, limit, cursor):
        return result_or_error(builder, resource_id, label, after, before, limit, cursor)

    @router.get("/entities/{entity_id}/history")
    def entity(entity_id: str = Path(..., min_length=1, max_length=128), after: str = Query("", max_length=128), before: str = Query("", max_length=128), limit: int = Query(100, ge=1, le=200), cursor: str = Query("", max_length=4096)):
        return common_history(entity_history, entity_id, "entity", after, before, limit, cursor)

    @router.get("/stories/{story_id}/history")
    def story(story_id: str = Path(..., min_length=1, max_length=128), after: str = Query("", max_length=128), before: str = Query("", max_length=128), limit: int = Query(100, ge=1, le=200), cursor: str = Query("", max_length=4096)):
        return common_history(story_history, story_id, "story", after, before, limit, cursor)

    @router.get("/claims/{claim_id}/history")
    def claim(claim_id: str = Path(..., min_length=1, max_length=128), after: str = Query("", max_length=128), before: str = Query("", max_length=128), limit: int = Query(100, ge=1, le=200), cursor: str = Query("", max_length=4096)):
        return common_history(claim_history, claim_id, "claim", after, before, limit, cursor)

    @router.get("/media/{media_item_id}/history")
    def media(media_item_id: str = Path(..., min_length=1, max_length=128), after: str = Query("", max_length=128), before: str = Query("", max_length=128), limit: int = Query(100, ge=1, le=200), cursor: str = Query("", max_length=4096)):
        return common_history(media_history, media_item_id, "media_item", after, before, limit, cursor)

    return router
