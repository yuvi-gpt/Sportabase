from __future__ import annotations

from typing import Any, Callable

from app.operations.control_room_usage_bridge import (
    ControlRoomUsageBridgeMisconfigured,
    ControlRoomUsageBridgeUnavailable,
)


CONTROL_ROOM_UPSTREAM_TOTAL_WAIT_BUDGET_SECONDS = 90.0
CONTROL_ROOM_UPSTREAM_MAX_SINGLE_WAIT_SECONDS = 60.0


def _validated_primary_timeout(value: int | float) -> float:
    try:
        timeout = float(value)
    except Exception as error:
        raise ControlRoomUsageBridgeMisconfigured(
            "Control Room upstream request timeout is invalid."
        ) from error

    if timeout <= 0.0 or timeout > CONTROL_ROOM_UPSTREAM_MAX_SINGLE_WAIT_SECONDS:
        raise ControlRoomUsageBridgeMisconfigured(
            "Control Room upstream request timeout is invalid."
        )

    return timeout


def build_cold_start_timeout_plan(
    primary_timeout_seconds: int | float,
) -> tuple[float, ...]:
    primary = _validated_primary_timeout(
        primary_timeout_seconds
    )

    timeouts: list[float] = [primary]
    remaining = (
        CONTROL_ROOM_UPSTREAM_TOTAL_WAIT_BUDGET_SECONDS
        - primary
    )

    if remaining <= 0.0:
        return tuple(timeouts)

    long_retry = min(
        CONTROL_ROOM_UPSTREAM_MAX_SINGLE_WAIT_SECONDS,
        remaining,
    )
    if long_retry > 0.0:
        timeouts.append(long_retry)
        remaining -= long_retry

    final_retry = min(primary, remaining)
    if final_retry > 0.0:
        timeouts.append(final_retry)

    return tuple(timeouts)


def fetch_with_cold_start_resilience(
    *,
    usage_fetcher: Callable[[float], dict[str, Any]],
    primary_timeout_seconds: int | float,
) -> dict[str, Any]:
    if not callable(usage_fetcher):
        raise ControlRoomUsageBridgeMisconfigured(
            "Control Room upstream usage fetcher is not configured."
        )

    timeouts = build_cold_start_timeout_plan(
        primary_timeout_seconds
    )

    last_error: ControlRoomUsageBridgeUnavailable | None = None

    for timeout in timeouts:
        try:
            return usage_fetcher(timeout)
        except ControlRoomUsageBridgeUnavailable as error:
            last_error = error

    raise ControlRoomUsageBridgeUnavailable(
        "Control Room upstream usage service is unavailable."
    ) from last_error


__all__ = [
    "CONTROL_ROOM_UPSTREAM_MAX_SINGLE_WAIT_SECONDS",
    "CONTROL_ROOM_UPSTREAM_TOTAL_WAIT_BUDGET_SECONDS",
    "build_cold_start_timeout_plan",
    "fetch_with_cold_start_resilience",
]
