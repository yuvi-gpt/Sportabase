from __future__ import annotations

import threading
import time
import uuid
from collections.abc import Mapping
from typing import Any

from app.intelligence.background_pipeline_runtime import (
    BACKGROUND_INTELLIGENCE_REFRESH_VERSION,
    refresh_completed_job_intelligence,
)
from app.operations.job_runtime import (
    record_browser_capture_job_result,
)
from app.workflows import browser_capture_automation


PERSISTENT_JOB_WORKER_RUNTIME_VERSION = (
    "sportabase-persistent-job-worker-runtime-v1"
)

_WORKER_LOCK = threading.Lock()
_WORKER_STOP = threading.Event()
_WORKER_WAKE = threading.Event()
_WORKER_THREAD = None
_WORKER_ID = ""


def _automation_wake_event():
    candidate = getattr(
        browser_capture_automation,
        "_WORKER_WAKE",
        None,
    )
    if (
        candidate is not None
        and callable(getattr(candidate, "wait", None))
        and callable(getattr(candidate, "set", None))
        and callable(getattr(candidate, "clear", None))
    ):
        return candidate
    return _WORKER_WAKE


def _emit_reconcile_event(
    event_recorder,
    result: Mapping[str, Any] | None,
) -> None:
    if not callable(event_recorder) or not isinstance(result, Mapping):
        return

    try:
        created = max(0, int(result.get("created") or 0))
        examined = max(0, int(result.get("examined") or 0))
    except (TypeError, ValueError):
        return

    if created <= 0:
        return

    try:
        event_recorder(
            component="automation_jobs",
            event_type="job.reconciled",
            status="queued",
            mode="unknown",
            details={
                "telemetry_version": PERSISTENT_JOB_WORKER_RUNTIME_VERSION,
                "created": created,
                "examined": examined,
            },
        )
    except Exception:
        pass


def _emit_intelligence_refresh_event(
    event_recorder,
    result: Mapping[str, Any] | None,
) -> None:
    if not callable(event_recorder) or not isinstance(result, Mapping):
        return

    raw_refresh = result.get("intelligence_refresh")
    if not isinstance(raw_refresh, Mapping):
        return

    refresh_status = str(raw_refresh.get("status") or "").strip().casefold()
    if refresh_status not in {"ready", "partial", "unavailable"}:
        return

    raw_counts = raw_refresh.get("counts")
    counts = raw_counts if isinstance(raw_counts, Mapping) else {}

    def safe_count(name: str) -> int:
        try:
            value = int(counts.get(name) or 0)
        except (TypeError, ValueError, OverflowError):
            return 0
        return max(0, value)

    execution_mode = str(
        result.get("execution_mode")
        or raw_refresh.get("execution_mode")
        or ""
    ).strip().casefold()
    mode = "unknown"
    if execution_mode == "article_history_merit":
        mode = "article"
    elif execution_mode == "non_article_no_merit":
        mode = "non_article"

    try:
        event_recorder(
            component="intelligence_pipeline",
            event_type=(
                "intelligence.background_refreshed"
                if refresh_status == "ready"
                else "intelligence.background_degraded"
            ),
            status=(
                "success"
                if refresh_status == "ready"
                else "degraded"
            ),
            mode=mode,
            details={
                "telemetry_version": BACKGROUND_INTELLIGENCE_REFRESH_VERSION,
                "refresh_status": refresh_status,
                "claims": safe_count("claims"),
                "stories": safe_count("stories"),
                "structured_claims": safe_count("structured_claims"),
                "stale_claims": safe_count("stale_claims"),
                "conflict_claims": safe_count("conflict_claims"),
                "projection_failures": safe_count("projection_failures"),
            },
        )
    except Exception:
        pass


def _worker_loop(config: Mapping[str, Any]) -> None:
    poll_seconds = float(config["poll_seconds"])
    last_reconcile = 0.0

    while not _WORKER_STOP.is_set():
        now_value = time.time()

        if now_value - last_reconcile >= 60.0:
            try:
                reconciled = (
                    browser_capture_automation
                    .reconcile_browser_capture_jobs(
                        analysis_version=config["analysis_version"],
                        scoring_version=config["scoring_version"],
                        connection_factory=config["connection_factory"],
                        env_getter=config["env_getter"],
                    )
                )
                _emit_reconcile_event(
                    config.get("operational_event_recorder"),
                    reconciled,
                )
            except browser_capture_automation.BrowserCaptureAutomationError:
                pass

            last_reconcile = now_value

        try:
            result = (
                browser_capture_automation
                .run_browser_capture_automation_iteration(
                    worker_id=config["worker_id"],
                    analysis_version=config["analysis_version"],
                    scoring_version=config["scoring_version"],
                    connection_factory=config["connection_factory"],
                    gemini_client_factory=config["gemini_client_factory"],
                    gemini_generator=config["gemini_generator"],
                    env_getter=config["env_getter"],
                )
            )
        except browser_capture_automation.BrowserCaptureAutomationError:
            result = {
                "status": "worker_error",
            }

        if result.get("status") == "completed":
            refreshed = refresh_completed_job_intelligence(
                result=result,
                connection_factory=config["connection_factory"],
            )
            if isinstance(refreshed, Mapping):
                result = dict(refreshed)

            _emit_intelligence_refresh_event(
                config.get("operational_event_recorder"),
                result,
            )

        record_browser_capture_job_result(
            event_recorder=config.get("operational_event_recorder"),
            result=result,
        )

        if result.get("status") not in {
            "idle",
            "disabled",
            "worker_error",
        }:
            continue

        wake_event = _automation_wake_event()
        wake_event.wait(timeout=poll_seconds)
        wake_event.clear()


def start_persistent_job_worker(
    *,
    connection_factory,
    analysis_version: str,
    scoring_version: str,
    gemini_client_factory,
    gemini_generator,
    operational_event_recorder=None,
    env_getter=None,
) -> dict[str, Any]:
    global _WORKER_THREAD
    global _WORKER_ID

    if env_getter is None:
        import os
        env_getter = os.getenv

    if not browser_capture_automation.automation_enabled(
        env_getter=env_getter
    ):
        return {
            "version": PERSISTENT_JOB_WORKER_RUNTIME_VERSION,
            "status": "disabled",
        }

    if connection_factory is None:
        raise browser_capture_automation.BrowserCaptureAutomationInputError(
            "Automation worker database access is required."
        )

    version_resolver = getattr(
        browser_capture_automation,
        "_versions",
        None,
    )
    if not callable(version_resolver):
        raise browser_capture_automation.BrowserCaptureAutomationInputError(
            "Automation version validator is unavailable."
        )

    analysis, scoring = version_resolver(
        analysis_version,
        scoring_version,
    )

    with _WORKER_LOCK:
        if (
            _WORKER_THREAD is not None
            and _WORKER_THREAD.is_alive()
        ):
            return {
                "version": PERSISTENT_JOB_WORKER_RUNTIME_VERSION,
                "status": "already_running",
                "worker_id": _WORKER_ID,
            }

        _WORKER_STOP.clear()
        _WORKER_WAKE.clear()
        _automation_wake_event().clear()
        _WORKER_ID = "bcaw_ops_" + uuid.uuid4().hex

        config = {
            "worker_id": _WORKER_ID,
            "analysis_version": analysis,
            "scoring_version": scoring,
            "connection_factory": connection_factory,
            "gemini_client_factory": gemini_client_factory,
            "gemini_generator": gemini_generator,
            "operational_event_recorder": operational_event_recorder,
            "env_getter": env_getter,
            "poll_seconds": (
                browser_capture_automation.automation_poll_seconds(
                    env_getter=env_getter
                )
            ),
        }

        thread = threading.Thread(
            target=_worker_loop,
            args=(config,),
            name="sportabase-persistent-job-worker",
            daemon=True,
        )
        _WORKER_THREAD = thread
        thread.start()

    return {
        "version": PERSISTENT_JOB_WORKER_RUNTIME_VERSION,
        "status": "started",
        "worker_id": _WORKER_ID,
        "policy": {
            "persistent_queue": True,
            "lease_based_claim": True,
            "restart_recoverable": True,
            "queue_wake_signal_reused": True,
            "operational_events_fail_open": True,
            "public_request_does_not_wait_for_gemini": True,
            "background_intelligence_refresh_enabled": True,
            "background_refresh_provider_free": True,
            "background_refresh_does_not_mutate_snapshots": True,
            "live_merit_shadow_only": True,
            "affects_live_merit": False,
        },
    }


def stop_persistent_job_worker(
    *,
    join_timeout_seconds: float = 5.0,
) -> dict[str, Any]:
    global _WORKER_THREAD
    global _WORKER_ID

    with _WORKER_LOCK:
        thread = _WORKER_THREAD
        if thread is None:
            return {
                "version": PERSISTENT_JOB_WORKER_RUNTIME_VERSION,
                "status": "stopped",
            }

        _WORKER_STOP.set()
        _WORKER_WAKE.set()
        _automation_wake_event().set()

    if thread.is_alive():
        thread.join(timeout=max(0.0, float(join_timeout_seconds)))

    with _WORKER_LOCK:
        alive = thread.is_alive()
        if not alive:
            _WORKER_THREAD = None
            _WORKER_ID = ""

    return {
        "version": PERSISTENT_JOB_WORKER_RUNTIME_VERSION,
        "status": "stopping" if alive else "stopped",
    }


def register_persistent_job_worker_lifecycle(
    *,
    app,
    connection_factory,
    analysis_version: str,
    scoring_version: str,
    gemini_client_factory,
    gemini_generator,
    operational_event_recorder=None,
    env_getter=None,
) -> dict[str, Any]:
    if app is None or not hasattr(app, "add_event_handler"):
        raise browser_capture_automation.BrowserCaptureAutomationInputError(
            "FastAPI lifecycle registration requires an app."
        )

    def _startup():
        return start_persistent_job_worker(
            connection_factory=connection_factory,
            analysis_version=analysis_version,
            scoring_version=scoring_version,
            gemini_client_factory=gemini_client_factory,
            gemini_generator=gemini_generator,
            operational_event_recorder=operational_event_recorder,
            env_getter=env_getter,
        )

    def _shutdown():
        return stop_persistent_job_worker()

    app.add_event_handler("startup", _startup)
    app.add_event_handler("shutdown", _shutdown)

    return {
        "version": PERSISTENT_JOB_WORKER_RUNTIME_VERSION,
        "status": "registered",
        "policy": {
            "automation_flag_required": True,
            "operational_events_fail_open": True,
            "background_intelligence_refresh_enabled": True,
            "background_refresh_provider_free": True,
            "live_merit_shadow_only": True,
            "affects_live_merit": False,
        },
    }


def register_browser_capture_automation_lifecycle(**kwargs):
    """Compatibility name for the instrumented browser-capture worker."""
    return register_persistent_job_worker_lifecycle(**kwargs)


__all__ = [
    "PERSISTENT_JOB_WORKER_RUNTIME_VERSION",
    "start_persistent_job_worker",
    "stop_persistent_job_worker",
    "register_persistent_job_worker_lifecycle",
    "register_browser_capture_automation_lifecycle",
]
