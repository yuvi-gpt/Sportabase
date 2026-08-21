from __future__ import annotations

from collections.abc import Callable, Mapping
from time import perf_counter
from typing import Any
from urllib.parse import urlparse


ANALYSIS_OPERATIONAL_TELEMETRY_VERSION = (
    "sportabase-analysis-operational-telemetry-v1"
)


def _normalized_mode(value: Any) -> str:
    mode = str(value or "").strip().casefold()
    return mode if mode in {"article", "video"} else "unknown"


def _source_key_for_url(value: Any) -> str:
    try:
        hostname = urlparse(str(value or "").strip()).hostname or ""
    except Exception:
        return ""

    normalized = hostname.strip().casefold().rstrip(".")
    if normalized.startswith("www."):
        normalized = normalized[4:]
    return normalized[:192]


def _response_mapping(value: Any) -> Mapping[str, Any]:
    if isinstance(value, Mapping):
        return value

    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        try:
            dumped = model_dump()
        except Exception:
            dumped = None
        if isinstance(dumped, Mapping):
            return dumped

    raw = getattr(value, "__dict__", None)
    if isinstance(raw, Mapping):
        return raw

    return {}


def _cache_hit_from_response(response: Any) -> bool:
    payload = _response_mapping(response)
    debug = payload.get("debug")
    if not isinstance(debug, Mapping):
        return False

    cache = debug.get("cache")
    if not isinstance(cache, Mapping):
        return False

    return bool(cache.get("hit", False))


def _success_details(*, mode: str, response: Any) -> dict[str, Any]:
    payload = _response_mapping(response)
    details: dict[str, Any] = {
        "cache_hit": _cache_hit_from_response(response),
        "telemetry_version": ANALYSIS_OPERATIONAL_TELEMETRY_VERSION,
    }

    if mode == "article":
        article_type = str(payload.get("article_type") or "").strip()
        if article_type:
            details["article_type"] = article_type[:128]

        merit_score = payload.get("merit_score")
        if isinstance(merit_score, (int, float)) and not isinstance(
            merit_score,
            bool,
        ):
            details["merit_score"] = int(merit_score)

    elif mode == "video":
        content_type = str(payload.get("content_type") or "").strip()
        if content_type:
            details["content_type"] = content_type[:128]

        verdict = str(payload.get("verdict") or "").strip()
        if verdict:
            details["verdict"] = verdict[:128]

    return details


def _elapsed_ms(
    *,
    started: float,
    clock: Callable[[], float],
) -> int:
    try:
        elapsed = (float(clock()) - float(started)) * 1000.0
    except Exception:
        return 0
    return max(0, int(round(elapsed)))


def _emit_quietly(
    event_recorder: Callable[..., Any] | None,
    **event: Any,
) -> Any:
    if not callable(event_recorder):
        return None

    try:
        return event_recorder(**event)
    except Exception:
        # Operational telemetry must never turn a valid analysis response into
        # a product outage. Store health is tracked independently by runtime.
        return None


def execute_analysis_with_operational_telemetry(
    *,
    handler: Callable[[Any, Any], Any],
    req: Any,
    request: Any,
    mode: str,
    event_recorder: Callable[..., Any] | None,
    clock: Callable[[], float] = perf_counter,
) -> Any:
    """Run one article/video analysis and emit a privacy-minimized event.

    The wrapper records only operational metadata: mode, source hostname,
    duration, cache-hit state, bounded response classification fields, and the
    exception class on failure. Raw URLs, article text, transcripts, titles,
    client identifiers, credentials, and exception messages are never sent to
    the persistent operations store.
    """

    if not callable(handler):
        raise TypeError("Analysis handler must be callable.")

    normalized_mode = _normalized_mode(mode)
    source_key = _source_key_for_url(getattr(req, "url", ""))
    started = float(clock())

    try:
        response = handler(req, request)
    except Exception as error:
        _emit_quietly(
            event_recorder,
            component="content_pipeline",
            event_type="analysis.failed",
            status="error",
            mode=normalized_mode,
            source_key=source_key,
            duration_ms=_elapsed_ms(started=started, clock=clock),
            details={
                "error_type": type(error).__name__,
                "telemetry_version": ANALYSIS_OPERATIONAL_TELEMETRY_VERSION,
            },
        )
        raise

    _emit_quietly(
        event_recorder,
        component="content_pipeline",
        event_type="analysis.completed",
        status="success",
        mode=normalized_mode,
        source_key=source_key,
        duration_ms=_elapsed_ms(started=started, clock=clock),
        details=_success_details(
            mode=normalized_mode,
            response=response,
        ),
    )

    return response


__all__ = [
    "ANALYSIS_OPERATIONAL_TELEMETRY_VERSION",
    "execute_analysis_with_operational_telemetry",
]
