from __future__ import annotations

from datetime import date
from typing import Any, Callable

from fastapi import APIRouter, HTTPException, Query, Request

from app.ai.quota import provider_usage_day
from app.application.config import (
    DB_PATH,
    GLOBAL_DAILY_GEMINI_CALL_CAP,
)
from app.operations.control_room_ai_usage import (
    build_control_room_ai_usage_snapshot,
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


def _default_ai_usage_handler(provider_day: str) -> dict[str, Any]:
    return build_control_room_ai_usage_snapshot(
        db_path=DB_PATH,
        provider_day=provider_day,
        global_daily_call_cap=GLOBAL_DAILY_GEMINI_CALL_CAP,
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


def _normalized_provider_day(raw_value: str) -> str:
    normalized = str(raw_value or "").strip()
    if not normalized:
        return provider_usage_day()

    try:
        parsed = date.fromisoformat(normalized)
    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail="provider_day must use YYYY-MM-DD.",
        ) from error

    canonical = parsed.isoformat()
    if canonical != normalized:
        raise HTTPException(
            status_code=400,
            detail="provider_day must use YYYY-MM-DD.",
        )

    return canonical


def build_router(
    *,
    require_control_room: Callable[[Request], ControlRoomPrincipal] | None = None,
    ai_usage_handler: Callable[[str], dict[str, Any]] | None = None,
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
        provider_day: str = Query(default=""),
    ):
        _authorized_principal(
            guard=guard,
            request=request,
        )

        effective_day = _normalized_provider_day(provider_day)
        return usage_handler(effective_day)

    return router


__all__ = [
    "CONTROL_ROOM_ROUTE_VERSION",
    "build_router",
]
