from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException, Path, Response
from pydantic import BaseModel, Field

from app.notifications.runtime import (
    NotificationLimitError,
    NotificationNotFoundError,
    list_devices,
    register_device,
    unregister_device,
)
from app.watchlists.runtime import client_key


class NotificationDeviceCreate(BaseModel):
    push_token: str = Field(min_length=20, max_length=512)
    platform: str = Field(min_length=2, max_length=16)


def build_router(*, connection_factory) -> APIRouter:
    router = APIRouter(prefix="/notifications", tags=["product-notifications"])

    def owner(value: str | None) -> str:
        try:
            return client_key(value or "")
        except ValueError as exc:
            raise HTTPException(status_code=401, detail=str(exc)) from exc

    @router.post("/devices")
    def create_device(
        body: NotificationDeviceCreate,
        x_sportabase_client_id: str | None = Header(None),
    ):
        try:
            return register_device(
                owner_key=owner(x_sportabase_client_id),
                push_token=body.push_token,
                platform=body.platform,
                connection_factory=connection_factory,
            )
        except NotificationLimitError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @router.get("/devices")
    def devices(x_sportabase_client_id: str | None = Header(None)):
        return list_devices(
            owner_key=owner(x_sportabase_client_id),
            connection_factory=connection_factory,
        )

    @router.delete("/devices/{device_id}", status_code=204)
    def remove_device(
        device_id: str = Path(..., min_length=1, max_length=128),
        x_sportabase_client_id: str | None = Header(None),
    ):
        try:
            unregister_device(
                owner_key=owner(x_sportabase_client_id),
                device_id=device_id,
                connection_factory=connection_factory,
            )
        except NotificationNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return Response(status_code=204)

    return router
