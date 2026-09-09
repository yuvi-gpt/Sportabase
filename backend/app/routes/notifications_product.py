from __future__ import annotations

import logging

from fastapi import Request, APIRouter, Header, HTTPException, Path, Response
from pydantic import BaseModel, ConfigDict, Field

from app.notifications import web_push
from app.notifications.runtime import (
    NotificationLimitError,
    NotificationNotFoundError,
    list_devices,
    register_device,
    unregister_device,
)
from app.watchlists.runtime import client_key


LOGGER = logging.getLogger(__name__)


class NotificationDeviceCreate(BaseModel):
    push_token: str = Field(min_length=20, max_length=512)
    platform: str = Field(min_length=2, max_length=16)


class WebPushKeys(BaseModel):
    model_config = ConfigDict(extra="forbid")

    p256dh: str = Field(min_length=1, max_length=256)
    auth: str = Field(min_length=1, max_length=128)


class WebPushSubscriptionCreate(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    endpoint: str = Field(min_length=1, max_length=2048)
    expiration_time: int | None = Field(default=None, alias="expirationTime", ge=0)
    keys: WebPushKeys


def build_router(*, connection_factory) -> APIRouter:
    router = APIRouter(prefix="/notifications", tags=["product-notifications"])

    def owner(request: Request, value: str | None) -> str:
        try:
            from app.accounts.boundary import authenticated_owner
            return authenticated_owner(request, value, legacy_resolver=lambda v: client_key(v or ""))
        except ValueError as exc:
            raise HTTPException(status_code=401, detail=str(exc)) from exc

    @router.get("/web/config")
    def browser_config():
        return web_push.web_push_config()

    @router.post("/web/subscriptions")
    def create_web_subscription(
        request: Request,
        body: WebPushSubscriptionCreate,
        x_sportabase_client_id: str | None = Header(None),
    ):
        try:
            result = web_push.register_subscription(
                owner_key=owner(request, x_sportabase_client_id),
                endpoint=body.endpoint,
                p256dh=body.keys.p256dh,
                auth=body.keys.auth,
                expiration_time=body.expiration_time,
                connection_factory=connection_factory,
            )
            from app.accounts.notification_policy import bind_registration, record_registration_event
            try:
                bind_registration(connection_factory, request, "web", result["subscription"]["id"])
            except Exception as exc:
                try:
                    web_push.unregister_subscription(
                        owner_key=owner(request, x_sportabase_client_id),
                        subscription_id=result["subscription"]["id"],
                        connection_factory=connection_factory,
                    )
                except Exception:
                    LOGGER.exception("Web Push registration compensation failed")
                raise HTTPException(503, "Could not securely bind this notification registration. Retry enabling push.") from exc
            record_registration_event(connection_factory, request, "notification_enabled")
            return result
        except web_push.WebPushLimitError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @router.get("/web/subscriptions")
    def web_subscriptions(request: Request, x_sportabase_client_id: str | None = Header(None)):
        return web_push.list_subscriptions(
            owner_key=owner(request, x_sportabase_client_id),
            connection_factory=connection_factory,
        )

    @router.delete("/web/subscriptions/{subscription_id}", status_code=204)
    def remove_web_subscription(
        request: Request,
        subscription_id: str = Path(..., min_length=1, max_length=128),
        x_sportabase_client_id: str | None = Header(None),
    ):
        try:
            web_push.unregister_subscription(
                owner_key=owner(request, x_sportabase_client_id),
                subscription_id=subscription_id,
                connection_factory=connection_factory,
            )
            from app.accounts.notification_policy import cleanup_binding_after_unregistration, record_registration_event
            cleanup_binding_after_unregistration(connection_factory, request, "web", subscription_id)
            record_registration_event(connection_factory, request, "notification_disabled")
        except web_push.WebPushNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return Response(status_code=204)

    @router.post("/devices")
    def create_device(
        request: Request,
        body: NotificationDeviceCreate,
        x_sportabase_client_id: str | None = Header(None),
    ):
        try:
            result = register_device(
                owner_key=owner(request, x_sportabase_client_id),
                push_token=body.push_token,
                platform=body.platform,
                connection_factory=connection_factory,
            )
            from app.accounts.notification_policy import bind_registration, record_registration_event
            try:
                bind_registration(connection_factory, request, "expo", result["device"]["id"])
            except Exception as exc:
                try:
                    unregister_device(
                        owner_key=owner(request, x_sportabase_client_id),
                        device_id=result["device"]["id"],
                        connection_factory=connection_factory,
                    )
                except Exception:
                    LOGGER.exception("Expo registration compensation failed")
                raise HTTPException(503, "Could not securely bind this notification registration. Retry enabling push.") from exc
            record_registration_event(connection_factory, request, "notification_enabled")
            return result
        except NotificationLimitError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @router.get("/devices")
    def devices(request: Request, x_sportabase_client_id: str | None = Header(None)):
        return list_devices(
            owner_key=owner(request, x_sportabase_client_id),
            connection_factory=connection_factory,
        )

    @router.delete("/devices/{device_id}", status_code=204)
    def remove_device(
        request: Request,
        device_id: str = Path(..., min_length=1, max_length=128),
        x_sportabase_client_id: str | None = Header(None),
    ):
        try:
            unregister_device(
                owner_key=owner(request, x_sportabase_client_id),
                device_id=device_id,
                connection_factory=connection_factory,
            )
            from app.accounts.notification_policy import cleanup_binding_after_unregistration, record_registration_event
            cleanup_binding_after_unregistration(connection_factory, request, "expo", device_id)
            record_registration_event(connection_factory, request, "notification_disabled")
        except NotificationNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return Response(status_code=204)

    return router
