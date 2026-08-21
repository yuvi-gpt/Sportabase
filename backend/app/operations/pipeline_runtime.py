from __future__ import annotations

from collections.abc import Callable, Mapping
from time import perf_counter
from typing import Any
from urllib.parse import urlparse


PIPELINE_OPERATIONAL_TELEMETRY_VERSION = (
    "sportabase-pipeline-operational-telemetry-v1"
)


def _mapping(value: Any) -> Mapping[str, Any]:
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


def _capture_mapping(req: Any) -> Mapping[str, Any]:
    capture = getattr(req, "capture", None)
    return capture if isinstance(capture, Mapping) else {}


def _source_key(req: Any) -> str:
    capture = _capture_mapping(req)
    raw_url = str(capture.get("source_url") or "").strip()

    try:
        hostname = urlparse(raw_url).hostname or ""
    except Exception:
        hostname = ""

    normalized = hostname.strip().casefold().rstrip(".")
    if normalized.startswith("www."):
        normalized = normalized[4:]
    return normalized[:192]


def _capture_platform(req: Any) -> tuple[str, str]:
    capture = _capture_mapping(req)
    payload = capture.get("payload")
    if not isinstance(payload, Mapping):
        return "", ""

    platform = str(payload.get("platform") or "").strip().casefold()[:64]
    surface = str(payload.get("surface") or "").strip().casefold()[:64]
    return platform, surface


def _capture_mode(platform: str, surface: str) -> str:
    if platform == "web" and surface == "article":
        return "article"

    video_surfaces = {
        "video",
        "short_video",
        "reel",
        "short",
        "clip",
    }
    if surface in video_surfaces or platform in {"youtube", "tiktok"}:
        return "video"

    return "capture"


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
        return None


def _status_for_inbox(value: str) -> str:
    normalized = str(value or "").strip().casefold()
    if normalized in {"stored", "replayed"}:
        return "success"
    if normalized == "disabled":
        return "skipped"
    if normalized == "oversize":
        return "rejected"
    if normalized == "unavailable":
        return "degraded"
    return "unknown"


def execute_browser_capture_with_operational_telemetry(
    *,
    handler: Callable[[Any], Any],
    req: Any,
    event_recorder: Callable[..., Any] | None,
    clock: Callable[[], float] = perf_counter,
) -> Any:
    """Execute browser capture ingestion and emit privacy-minimized telemetry.

    Only source hostname, platform/surface classification, persistence outcome,
    duration, and exception class are emitted. Raw URLs, paths/query strings,
    capture payloads, article/video text, actor identifiers, and record IDs are
    excluded from persistent operational event details.
    """

    if not callable(handler):
        raise TypeError("Browser capture handler must be callable.")

    platform, surface = _capture_platform(req)
    mode = _capture_mode(platform, surface)
    source_key = _source_key(req)
    started = float(clock())

    try:
        response = handler(req)
    except Exception as error:
        _emit_quietly(
            event_recorder,
            component="content_pipeline",
            event_type="capture.failed",
            status="error",
            mode=mode,
            source_key=source_key,
            duration_ms=_elapsed_ms(started=started, clock=clock),
            details={
                "error_type": type(error).__name__,
                "platform": platform,
                "platform_surface": surface,
                "telemetry_version": PIPELINE_OPERATIONAL_TELEMETRY_VERSION,
            },
        )
        raise

    payload = _mapping(response)
    inbox_status = str(
        payload.get("capture_inbox_status") or ""
    ).strip().casefold()

    _emit_quietly(
        event_recorder,
        component="content_pipeline",
        event_type="capture.processed",
        status=_status_for_inbox(inbox_status),
        mode=mode,
        source_key=source_key,
        duration_ms=_elapsed_ms(started=started, clock=clock),
        details={
            "capture_inbox_status": inbox_status,
            "capture_persisted": bool(payload.get("capture_persisted", False)),
            "platform": platform,
            "platform_surface": surface,
            "telemetry_version": PIPELINE_OPERATIONAL_TELEMETRY_VERSION,
        },
    )

    return response


__all__ = [
    "PIPELINE_OPERATIONAL_TELEMETRY_VERSION",
    "execute_browser_capture_with_operational_telemetry",
]
