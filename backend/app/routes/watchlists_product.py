from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException, Path, Query, Response
from pydantic import BaseModel, Field

from app.watchlists.runtime import (
    NotFoundError, WatchlistLimitError, client_key, create_watch, delete_watch,
    list_alerts, list_watches, mark_read, reconcile,
)


class WatchCreate(BaseModel):
    target_kind: str = Field(min_length=1, max_length=16)
    target_id: str = Field(min_length=1, max_length=128)


def build_router(*, connection_factory) -> APIRouter:
    router = APIRouter(prefix="/watchlists", tags=["product-watchlists"])

    def owner(value: str | None) -> str:
        try:
            return client_key(value or "")
        except ValueError as exc:
            raise HTTPException(status_code=401, detail=str(exc)) from exc

    @router.post("", status_code=200)
    def create(body: WatchCreate, x_sportabase_client_id: str | None = Header(None)):
        try:
            return create_watch(owner_key=owner(x_sportabase_client_id), target_kind=body.target_kind, target_id=body.target_id, connection_factory=connection_factory)
        except NotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except WatchlistLimitError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @router.get("")
    def listing(x_sportabase_client_id: str | None = Header(None)):
        return list_watches(owner_key=owner(x_sportabase_client_id), connection_factory=connection_factory)

    @router.delete("/{watch_id}", status_code=204)
    def remove(watch_id: str = Path(..., min_length=1, max_length=128), x_sportabase_client_id: str | None = Header(None)):
        try:
            delete_watch(owner_key=owner(x_sportabase_client_id), watch_id=watch_id, connection_factory=connection_factory)
        except NotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return Response(status_code=204)

    @router.post("/alerts/reconcile")
    def reconcile_alerts(x_sportabase_client_id: str | None = Header(None)):
        return reconcile(owner_key=owner(x_sportabase_client_id), connection_factory=connection_factory)

    @router.get("/alerts")
    def alerts(unread_only: bool = Query(False), target_kind: str = Query("", max_length=16), limit: int = Query(50, ge=1, le=100), cursor: str = Query("", max_length=4096), x_sportabase_client_id: str | None = Header(None)):
        try:
            return list_alerts(owner_key=owner(x_sportabase_client_id), unread_only=unread_only, target_kind=target_kind, limit=limit, cursor=cursor, connection_factory=connection_factory)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @router.post("/alerts/{alert_id}/read")
    def read(alert_id: str = Path(..., min_length=1, max_length=128), x_sportabase_client_id: str | None = Header(None)):
        try:
            return mark_read(owner_key=owner(x_sportabase_client_id), alert_id=alert_id, connection_factory=connection_factory)
        except NotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    return router
