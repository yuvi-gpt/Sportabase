from __future__ import annotations

from hmac import compare_digest
from typing import Callable

from fastapi import Request

from app.security.control_room import (
    ControlRoomAccessDenied,
    ControlRoomPrincipal,
    ControlRoomSecurityMisconfigured,
)


CONTROL_ROOM_ORIGIN_PROVENANCE_VERSION = (
    "sportabase-control-room-origin-provenance-v1"
)
CONTROL_ROOM_ORIGIN_PROVENANCE_HEADER = (
    "X-Sportabase-Origin-Provenance"
)
MIN_ORIGIN_PROVENANCE_SECRET_LENGTH = 32


def _normalized_secret(value: object) -> str:
    return str(value or "").strip()


def validate_origin_provenance_secret(secret: object) -> str:
    normalized = _normalized_secret(secret)
    if len(normalized) < MIN_ORIGIN_PROVENANCE_SECRET_LENGTH:
        raise ControlRoomSecurityMisconfigured(
            "Control Room origin provenance secret is not configured securely."
        )
    return normalized


def _origin_header_values(request: Request) -> tuple[str, ...]:
    if not isinstance(request, Request):
        raise ControlRoomAccessDenied(
            "Control Room origin provenance verification failed."
        )

    target = CONTROL_ROOM_ORIGIN_PROVENANCE_HEADER.casefold()
    values: list[str] = []

    for raw_name, raw_value in request.scope.get("headers", ()):
        try:
            name = raw_name.decode("latin-1").casefold()
            value = raw_value.decode("latin-1")
        except (AttributeError, UnicodeDecodeError):
            raise ControlRoomAccessDenied(
                "Control Room origin provenance verification failed."
            )

        if name == target:
            values.append(value.strip())

    return tuple(values)


def verify_control_room_origin_provenance(
    request: Request,
    *,
    expected_secret: object,
) -> None:
    expected = validate_origin_provenance_secret(expected_secret)
    provided = _origin_header_values(request)

    if len(provided) != 1 or not provided[0]:
        raise ControlRoomAccessDenied(
            "Control Room origin provenance verification failed."
        )

    if not compare_digest(
        provided[0].encode("utf-8"),
        expected.encode("utf-8"),
    ):
        raise ControlRoomAccessDenied(
            "Control Room origin provenance verification failed."
        )


def protect_control_room_guard_with_origin_provenance(
    *,
    inner_guard: Callable[[Request], ControlRoomPrincipal],
    expected_secret: object,
) -> Callable[[Request], ControlRoomPrincipal]:
    if not callable(inner_guard):
        raise TypeError("Control Room inner guard must be callable.")

    def guard(request: Request) -> ControlRoomPrincipal:
        verify_control_room_origin_provenance(
            request,
            expected_secret=expected_secret,
        )
        return inner_guard(request)

    for attribute in (
        "clear_policy_cache",
        "runtime_version",
    ):
        if hasattr(inner_guard, attribute):
            setattr(
                guard,
                attribute,
                getattr(inner_guard, attribute),
            )

    setattr(
        guard,
        "origin_provenance_version",
        CONTROL_ROOM_ORIGIN_PROVENANCE_VERSION,
    )
    return guard


__all__ = [
    "CONTROL_ROOM_ORIGIN_PROVENANCE_VERSION",
    "CONTROL_ROOM_ORIGIN_PROVENANCE_HEADER",
    "MIN_ORIGIN_PROVENANCE_SECRET_LENGTH",
    "validate_origin_provenance_secret",
    "verify_control_room_origin_provenance",
    "protect_control_room_guard_with_origin_provenance",
]
