from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any


JOB_OPERATIONAL_TELEMETRY_VERSION = (
    "sportabase-job-operational-telemetry-v1"
)


def _clean(value: Any, maximum: int = 128) -> str:
    return " ".join(str(value or "").split())[:maximum]


def _emit_quietly(
    event_recorder: Callable[..., Any] | None,
    **event: Any,
) -> Any:
    if not callable(event_recorder):
        return None

    try:
        return event_recorder(**event)
    except Exception:
        # Background telemetry is advisory and must never alter queue behavior.
        return None


def _mode_for_capture(platform: Any, surface: Any) -> str:
    normalized_platform = _clean(platform, 64).casefold()
    normalized_surface = _clean(surface, 64).casefold()

    if normalized_platform == "web" and normalized_surface == "article":
        return "article"
    if normalized_platform or normalized_surface:
        return "non_article"
    return "unknown"


def record_browser_capture_job_enqueued(
    *,
    event_recorder: Callable[..., Any] | None,
    result: Mapping[str, Any] | None,
    platform: Any = "",
    platform_surface: Any = "",
) -> Any:
    if not isinstance(result, Mapping):
        return None

    if _clean(result.get("status")).casefold() != "enqueued":
        return None

    details = {
        "telemetry_version": JOB_OPERATIONAL_TELEMETRY_VERSION,
        "platform": _clean(platform, 64).casefold(),
        "platform_surface": _clean(platform_surface, 64).casefold(),
        "job_status": _clean(result.get("job_status"), 64).casefold(),
        "attempts": max(0, int(result.get("attempts") or 0)),
        "max_attempts": max(0, int(result.get("max_attempts") or 0)),
    }

    return _emit_quietly(
        event_recorder,
        component="automation_jobs",
        event_type="job.enqueued",
        status="queued",
        mode=_mode_for_capture(platform, platform_surface),
        details=details,
    )


def record_browser_capture_job_result(
    *,
    event_recorder: Callable[..., Any] | None,
    result: Mapping[str, Any] | None,
) -> Any:
    if not isinstance(result, Mapping):
        return None

    result_status = _clean(result.get("status"), 64).casefold()
    event_map = {
        "retry_scheduled": ("job.retry_scheduled", "retrying"),
        "completed": ("job.completed", "success"),
        "failed": ("job.failed", "error"),
    }

    selected = event_map.get(result_status)
    if selected is None:
        return None

    raw_job = result.get("job")
    job = raw_job if isinstance(raw_job, Mapping) else {}

    execution_mode = _clean(result.get("execution_mode"), 96).casefold()
    mode = "unknown"
    if execution_mode == "article_history_merit":
        mode = "article"
    elif execution_mode == "non_article_no_merit":
        mode = "non_article"

    details: dict[str, Any] = {
        "telemetry_version": JOB_OPERATIONAL_TELEMETRY_VERSION,
        "job_status": _clean(job.get("status"), 64).casefold(),
        "attempts": max(0, int(job.get("attempts") or 0)),
        "max_attempts": max(0, int(job.get("max_attempts") or 0)),
        "last_outcome": _clean(job.get("last_outcome"), 160),
    }

    if execution_mode:
        details["execution_mode"] = execution_mode

    retry_delay = result.get("retry_delay_seconds")
    if isinstance(retry_delay, (int, float)) and not isinstance(
        retry_delay,
        bool,
    ):
        details["retry_delay_seconds"] = max(0, int(retry_delay))

    error_type = _clean(job.get("error_type"), 128)
    if error_type:
        details["error_type"] = error_type

    event_type, status = selected
    return _emit_quietly(
        event_recorder,
        component="automation_jobs",
        event_type=event_type,
        status=status,
        mode=mode,
        details=details,
    )


__all__ = [
    "JOB_OPERATIONAL_TELEMETRY_VERSION",
    "record_browser_capture_job_enqueued",
    "record_browser_capture_job_result",
]
