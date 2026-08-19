from __future__ import annotations

from typing import Callable

from fastapi import APIRouter, HTTPException, Request

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


def build_router(
    *,
    require_control_room: Callable[[Request], ControlRoomPrincipal] | None = None,
) -> APIRouter:
    router = APIRouter()
    guard = (
        require_control_room
        if callable(require_control_room)
        else _unconfigured_control_room_guard
    )

    @router.get("/admin/control-room/session")
    def control_room_session(
        request: Request,
    ):
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

        return {
            "version": CONTROL_ROOM_ROUTE_VERSION,
            "authenticated": True,
            "principal": principal.as_dict(),
        }

    return router


__all__ = [
    "CONTROL_ROOM_ROUTE_VERSION",
    "build_router",
]
