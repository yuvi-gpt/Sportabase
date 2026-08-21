from __future__ import annotations

from contextvars import ContextVar, Token
from typing import Any, Callable


_CURRENT_OPERATIONAL_EVENT_RECORDER: ContextVar[Callable[..., Any] | None] = (
    ContextVar(
        "sportabase_current_operational_event_recorder",
        default=None,
    )
)


def current_operational_event_recorder() -> Callable[..., Any] | None:
    value = _CURRENT_OPERATIONAL_EVENT_RECORDER.get()
    return value if callable(value) else None


def set_operational_event_recorder(
    recorder: Callable[..., Any] | None,
) -> Token:
    return _CURRENT_OPERATIONAL_EVENT_RECORDER.set(
        recorder if callable(recorder) else None
    )


def reset_operational_event_recorder(token: Token) -> None:
    _CURRENT_OPERATIONAL_EVENT_RECORDER.reset(token)


def invoke_with_operational_event_recorder(
    *,
    handler: Callable[..., Any],
    recorder: Callable[..., Any] | None,
    args: tuple[Any, ...] = (),
    kwargs: dict[str, Any] | None = None,
) -> Any:
    if not callable(handler):
        raise TypeError("Telemetry context handler must be callable.")

    token = set_operational_event_recorder(recorder)
    try:
        return handler(*(args or ()), **(kwargs or {}))
    finally:
        reset_operational_event_recorder(token)


__all__ = [
    "current_operational_event_recorder",
    "set_operational_event_recorder",
    "reset_operational_event_recorder",
    "invoke_with_operational_event_recorder",
]
