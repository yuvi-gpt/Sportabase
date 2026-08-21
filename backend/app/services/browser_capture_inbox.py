"""Compatibility facade for browser-capture inbox operations."""

from __future__ import annotations

import importlib as _importlib
import os
from collections.abc import Mapping

from app.operations.job_runtime import (
    record_browser_capture_job_enqueued,
)
from app.operations.telemetry_context import (
    current_operational_event_recorder,
)


_implementation = _importlib.import_module(
    "app.content.capture_inbox"
)

# Keep these concrete attributes on the facade so legacy tests/callers that
# patch them still affect the HTTP path below.
inbox_enabled = _implementation.inbox_enabled
inbox_max_bytes = _implementation.inbox_max_bytes


def _capture_platform(req):
    capture = getattr(req, "capture", None)
    if not isinstance(capture, Mapping):
        return "", ""

    payload = capture.get("payload")
    if not isinstance(payload, Mapping):
        return "", ""

    return (
        str(payload.get("platform") or "").strip(),
        str(payload.get("surface") or "").strip(),
    )


def _compat_env_getter(key, default=None):
    if key == _implementation.BROWSER_CAPTURE_INBOX_FLAG:
        return "1" if bool(inbox_enabled()) else "0"

    if key == _implementation.BROWSER_CAPTURE_INBOX_MAX_BYTES:
        return str(inbox_max_bytes())

    return os.getenv(key, default)


def execute_browser_capture_http(
    *,
    req,
    connection_factory,
    response_model,
    automation_enqueue=None,
    analysis_version: str = "",
    scoring_version: str = "",
):
    wrapped_enqueue = None

    if callable(automation_enqueue):
        platform, platform_surface = _capture_platform(req)

        def wrapped_enqueue(**kwargs):
            result = automation_enqueue(**kwargs)
            record_browser_capture_job_enqueued(
                event_recorder=(
                    current_operational_event_recorder()
                ),
                result=result,
                platform=platform,
                platform_surface=platform_surface,
            )
            return result

    return _implementation.execute_browser_capture_http(
        req=req,
        connection_factory=connection_factory,
        response_model=response_model,
        automation_enqueue=wrapped_enqueue,
        analysis_version=analysis_version,
        scoring_version=scoring_version,
        env_getter=_compat_env_getter,
    )


def __getattr__(name):
    return getattr(_implementation, name)


def __dir__():
    return sorted(
        set(globals()) | set(dir(_implementation))
    )
