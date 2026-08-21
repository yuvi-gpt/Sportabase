from __future__ import annotations

from typing import Any, Callable

from fastapi import APIRouter, HTTPException, Query, Request

from app.application.config import (
    CONTROL_ROOM_UPSTREAM_ADMIN_API_KEY,
    CONTROL_ROOM_UPSTREAM_API_ORIGIN,
    CONTROL_ROOM_UPSTREAM_REQUEST_TIMEOUT_SECONDS,
)
from app.operations.control_room_usage_bridge import (
    ControlRoomUsageBridgeMisconfigured,
    ControlRoomUsageBridgeUnavailable,
    fetch_control_room_upstream_usage,
)
from app.security.control_room import (
    ControlRoomAccessDenied,
    ControlRoomPrincipal,
    ControlRoomSecurityMisconfigured,
)


CONTROL_ROOM_ROUTE_VERSION = "sportabase-control-room-route-v1"


def _unconfigured_control_room_guard(
    request: Request,
) -> ControlRoomPrincipal:
    del request
    raise HTTPException(
        status_code=503,
        detail="Control Room identity verification is not configured.",
    )


def _default_ai_usage_handler(days: int) -> dict[str, Any]:
    return fetch_control_room_upstream_usage(
        api_origin=CONTROL_ROOM_UPSTREAM_API_ORIGIN,
        admin_api_key=CONTROL_ROOM_UPSTREAM_ADMIN_API_KEY,
        days=days,
        timeout_seconds=CONTROL_ROOM_UPSTREAM_REQUEST_TIMEOUT_SECONDS,
    )


def _authorized_principal(
    *,
    guard: Callable[[Request], ControlRoomPrincipal],
    request: Request,
) -> ControlRoomPrincipal:
    try:
        principal = guard(request)
    except ControlRoomAccessDenied as error:
        raise HTTPException(
            status_code=403,
            detail="Control Room access denied.",
        ) from error
    except ControlRoomSecurityMisconfigured as error:
        raise HTTPException(
            status_code=503,
            detail="Control Room security is not configured.",
        ) from error

    if not isinstance(principal, ControlRoomPrincipal):
        raise HTTPException(
            status_code=503,
            detail="Control Room authorization did not produce a principal.",
        )

    return principal


def _normalized_days(raw_value: str) -> int:
    normalized = str(raw_value or "").strip()
    if not normalized:
        return 7

    try:
        days = int(normalized)
    except (TypeError, ValueError) as error:
        raise HTTPException(
            status_code=400,
            detail="days must be an integer between 1 and 30.",
        ) from error

    if days < 1 or days > 30 or str(days) != normalized:
        raise HTTPException(
            status_code=400,
            detail="days must be an integer between 1 and 30.",
        )

    return days


def build_router(
    *,
    require_control_room: Callable[[Request], ControlRoomPrincipal] | None = None,
    ai_usage_handler: Callable[[int], dict[str, Any]] | None = None,
) -> APIRouter:
    router = APIRouter()
    guard = (
        require_control_room
        if callable(require_control_room)
        else _unconfigured_control_room_guard
    )
    usage_handler = (
        ai_usage_handler
        if callable(ai_usage_handler)
        else _default_ai_usage_handler
    )

    @router.get("/admin/control-room/session")
    def control_room_session(
        request: Request,
    ):
        principal = _authorized_principal(
            guard=guard,
            request=request,
        )

        return {
            "version": CONTROL_ROOM_ROUTE_VERSION,
            "authenticated": True,
            "principal": principal.as_dict(),
        }

    @router.get("/admin/control-room/ai-usage")
    def control_room_ai_usage(
        request: Request,
        days: str = Query(default="7"),
    ):
        _authorized_principal(
            guard=guard,
            request=request,
        )

        effective_days = _normalized_days(days)

        try:
            return usage_handler(effective_days)
        except ControlRoomUsageBridgeMisconfigured as error:
            raise HTTPException(
                status_code=503,
                detail="Control Room upstream usage bridge is not configured.",
            ) from error
        except ControlRoomUsageBridgeUnavailable as error:
            raise HTTPException(
                status_code=502,
                detail="Control Room upstream usage service is unavailable.",
            ) from error

    return router


__all__ = [
    "CONTROL_ROOM_ROUTE_VERSION",
    "build_router",
]
