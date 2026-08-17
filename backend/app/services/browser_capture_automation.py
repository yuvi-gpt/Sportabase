from __future__ import annotations

import hashlib
import json
import math
import os
import sqlite3
import threading
import time
import uuid

from datetime import datetime, timezone
from typing import Any, Dict, Mapping

from app.services import inbox_history_auto_shadow_orchestration


BROWSER_CAPTURE_AUTOMATION_VERSION = (
    "browser-capture-automation-v1"
)

BROWSER_CAPTURE_AUTOMATION_FLAG = (
    "SPORTABASE_BROWSER_CAPTURE_AUTOMATION_ENABLED"
)

BROWSER_CAPTURE_AUTOMATION_POLL_SECONDS = (
    "SPORTABASE_BROWSER_CAPTURE_AUTOMATION_POLL_SECONDS"
)

BROWSER_CAPTURE_AUTOMATION_LEASE_SECONDS = (
    "SPORTABASE_BROWSER_CAPTURE_AUTOMATION_LEASE_SECONDS"
)

BROWSER_CAPTURE_AUTOMATION_MAX_ATTEMPTS = (
    "SPORTABASE_BROWSER_CAPTURE_AUTOMATION_MAX_ATTEMPTS"
)

BROWSER_CAPTURE_AUTOMATION_RETRY_BASE_SECONDS = (
    "SPORTABASE_BROWSER_CAPTURE_AUTOMATION_RETRY_BASE_SECONDS"
)

BROWSER_CAPTURE_AUTOMATION_RETRY_CAP_SECONDS = (
    "SPORTABASE_BROWSER_CAPTURE_AUTOMATION_RETRY_CAP_SECONDS"
)

DEFAULT_POLL_SECONDS = 3.0
DEFAULT_LEASE_SECONDS = 300
DEFAULT_MAX_ATTEMPTS = 24
DEFAULT_RETRY_BASE_SECONDS = 10
DEFAULT_RETRY_CAP_SECONDS = 900
DEFAULT_RECONCILE_LIMIT = 500


class BrowserCaptureAutomationError(RuntimeError):
    pass


class BrowserCaptureAutomationInputError(
    BrowserCaptureAutomationError
):
    pass


class BrowserCaptureAutomationPersistenceError(
    BrowserCaptureAutomationError
):
    pass


class BrowserCaptureAutomationIntegrityError(
    BrowserCaptureAutomationError
):
    pass


_WORKER_LOCK = threading.Lock()
_WORKER_STOP = threading.Event()
_WORKER_WAKE = threading.Event()
_WORKER_THREAD = None
_WORKER_ID = ""


def _clean(value: Any) -> str:
    return " ".join(
        str(value or "").split()
    )


def _json(value: Any) -> str:
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
    except (TypeError, ValueError) as error:
        raise BrowserCaptureAutomationIntegrityError(
            "Automation metadata is not JSON serializable."
        ) from error


def _epoch(value: Any) -> int:
    if isinstance(value, bool):
        raise BrowserCaptureAutomationIntegrityError(
            "Automation clock returned an invalid value."
        )

    try:
        number = float(value)
    except (TypeError, ValueError) as error:
        raise BrowserCaptureAutomationIntegrityError(
            "Automation clock returned an invalid value."
        ) from error

    if not math.isfinite(number) or number < 0:
        raise BrowserCaptureAutomationIntegrityError(
            "Automation clock returned an invalid value."
        )

    return int(number)


def _utc_from_epoch(value: int) -> str:
    return (
        datetime.fromtimestamp(
            int(value),
            tz=timezone.utc,
        )
        .isoformat()
        .replace("+00:00", "Z")
    )


def _bounded_int(
    raw: Any,
    *,
    default: int,
    minimum: int,
    maximum: int,
) -> int:
    try:
        value = int(str(raw).strip())
    except (TypeError, ValueError):
        return default

    return max(
        minimum,
        min(maximum, value),
    )


def _bounded_float(
    raw: Any,
    *,
    default: float,
    minimum: float,
    maximum: float,
) -> float:
    try:
        value = float(str(raw).strip())
    except (TypeError, ValueError):
        return default

    if not math.isfinite(value):
        return default

    return max(
        minimum,
        min(maximum, value),
    )


def automation_enabled(
    *,
    env_getter=os.getenv,
) -> bool:
    raw = _clean(
        env_getter(
            BROWSER_CAPTURE_AUTOMATION_FLAG,
            "0",
        )
    ).lower()

    return raw in {
        "1",
        "true",
        "yes",
        "on",
    }


def automation_poll_seconds(
    *,
    env_getter=os.getenv,
) -> float:
    return _bounded_float(
        env_getter(
            BROWSER_CAPTURE_AUTOMATION_POLL_SECONDS,
            str(DEFAULT_POLL_SECONDS),
        ),
        default=DEFAULT_POLL_SECONDS,
        minimum=0.25,
        maximum=60.0,
    )


def automation_lease_seconds(
    *,
    env_getter=os.getenv,
) -> int:
    return _bounded_int(
        env_getter(
            BROWSER_CAPTURE_AUTOMATION_LEASE_SECONDS,
            str(DEFAULT_LEASE_SECONDS),
        ),
        default=DEFAULT_LEASE_SECONDS,
        minimum=30,
        maximum=3600,
    )


def automation_max_attempts(
    *,
    env_getter=os.getenv,
) -> int:
    return _bounded_int(
        env_getter(
            BROWSER_CAPTURE_AUTOMATION_MAX_ATTEMPTS,
            str(DEFAULT_MAX_ATTEMPTS),
        ),
        default=DEFAULT_MAX_ATTEMPTS,
        minimum=1,
        maximum=100,
    )


def automation_retry_base_seconds(
    *,
    env_getter=os.getenv,
) -> int:
    return _bounded_int(
        env_getter(
            BROWSER_CAPTURE_AUTOMATION_RETRY_BASE_SECONDS,
            str(DEFAULT_RETRY_BASE_SECONDS),
        ),
        default=DEFAULT_RETRY_BASE_SECONDS,
        minimum=1,
        maximum=900,
    )


def automation_retry_cap_seconds(
    *,
    env_getter=os.getenv,
) -> int:
    return _bounded_int(
        env_getter(
            BROWSER_CAPTURE_AUTOMATION_RETRY_CAP_SECONDS,
            str(DEFAULT_RETRY_CAP_SECONDS),
        ),
        default=DEFAULT_RETRY_CAP_SECONDS,
        minimum=10,
        maximum=3600,
    )


def _versions(
    analysis_version: Any,
    scoring_version: Any,
) -> tuple[str, str]:
    analysis = _clean(analysis_version)
    scoring = _clean(scoring_version)

    if not analysis:
        raise BrowserCaptureAutomationInputError(
            "Current analysis version is required."
        )

    if not scoring:
        raise BrowserCaptureAutomationInputError(
            "Current scoring version is required."
        )

    return analysis, scoring


def automation_job_id(
    *,
    capture_record_id: str,
    analysis_version: str,
    scoring_version: str,
) -> str:
    capture_id = _clean(capture_record_id)
    analysis, scoring = _versions(
        analysis_version,
        scoring_version,
    )

    if not capture_id:
        raise BrowserCaptureAutomationInputError(
            "Capture record ID is required."
        )

    digest = hashlib.sha256(
        (
            BROWSER_CAPTURE_AUTOMATION_VERSION
            + "|"
            + capture_id
            + "|"
            + analysis
            + "|"
            + scoring
        ).encode("utf-8")
    ).hexdigest()

    return "bcaj_" + digest


def _connect(connection_factory):
    if connection_factory is None:
        raise BrowserCaptureAutomationPersistenceError(
            "Browser capture automation requires database access."
        )

    try:
        conn = connection_factory()
    except Exception as error:
        raise BrowserCaptureAutomationPersistenceError(
            "Browser capture automation database is unavailable."
        ) from error

    if conn is None:
        raise BrowserCaptureAutomationPersistenceError(
            "Browser capture automation database is unavailable."
        )

    return conn


def _one(conn, sql: str, parameters=()):
    row = conn.execute(
        sql,
        parameters,
    ).fetchone()

    return dict(row) if row is not None else None


def _job_row_policy(row: Mapping[str, Any]) -> Dict[str, Any]:
    return {
        "persistent_job": True,
        "lease_based_claim": True,
        "restart_recoverable": True,
        "article_anchor_only": True,
        "capture_remains_untrusted": True,
        "job_does_not_verify_subject": True,
        "job_does_not_establish_authority": True,
        "job_does_not_establish_independence": True,
        "live_merit_shadow_only": True,
        "affects_live_merit": False,
        "status": _clean(row.get("status")),
    }


def enqueue_browser_capture_job(
    *,
    capture_record_id: str,
    analysis_version: str,
    scoring_version: str,
    connection_factory,
    env_getter=os.getenv,
    now_provider=time.time,
) -> Dict[str, Any]:
    capture_id = _clean(capture_record_id)
    analysis, scoring = _versions(
        analysis_version,
        scoring_version,
    )

    if not capture_id:
        raise BrowserCaptureAutomationInputError(
            "Capture record ID is required."
        )

    if not automation_enabled(
        env_getter=env_getter
    ):
        return {
            "version": BROWSER_CAPTURE_AUTOMATION_VERSION,
            "status": "disabled",
            "job_id": "",
            "capture_record_id": capture_id,
            "policy": {
                "persistent_job": False,
                "capture_remains_untrusted": True,
                "affects_live_merit": False,
            },
        }

    now_epoch = _epoch(
        now_provider()
    )
    now_text = _utc_from_epoch(
        now_epoch
    )
    max_attempts = automation_max_attempts(
        env_getter=env_getter
    )
    job_id = automation_job_id(
        capture_record_id=capture_id,
        analysis_version=analysis,
        scoring_version=scoring,
    )

    conn = _connect(
        connection_factory
    )

    try:
        conn.execute(
            "BEGIN IMMEDIATE"
        )

        capture = _one(
            conn,
            """
            SELECT id, platform
            FROM browser_capture_inbox
            WHERE id = ?
            """,
            (capture_id,),
        )

        if capture is None:
            raise BrowserCaptureAutomationInputError(
                "Browser capture inbox record does not exist."
            )

        if _clean(
            capture.get("platform")
        ).lower() != "web":
            conn.rollback()
            return {
                "version": BROWSER_CAPTURE_AUTOMATION_VERSION,
                "status": "unsupported",
                "job_id": "",
                "capture_record_id": capture_id,
                "policy": {
                    "persistent_job": False,
                    "article_anchor_only": True,
                    "capture_remains_untrusted": True,
                    "affects_live_merit": False,
                },
            }

        existing = _one(
            conn,
            """
            SELECT *
            FROM browser_capture_automation_jobs
            WHERE id = ?
            """,
            (job_id,),
        )

        status = "enqueued"

        if existing is None:
            conn.execute(
                """
                INSERT INTO browser_capture_automation_jobs (
                  id,
                  capture_record_id,
                  analysis_version,
                  scoring_version,
                  status,
                  attempts,
                  max_attempts,
                  available_at_epoch,
                  lease_owner,
                  lease_expires_at_epoch,
                  created_at,
                  updated_at,
                  started_at,
                  finished_at,
                  last_outcome,
                  error_type,
                  error_detail,
                  result_json
                )
                VALUES (?, ?, ?, ?, 'pending', 0, ?, ?, '', 0, ?, ?, NULL, NULL, '', '', '', '{}')
                """,
                (
                    job_id,
                    capture_id,
                    analysis,
                    scoring,
                    max_attempts,
                    now_epoch,
                    now_text,
                    now_text,
                ),
            )
        else:
            for field, expected in (
                ("capture_record_id", capture_id),
                ("analysis_version", analysis),
                ("scoring_version", scoring),
            ):
                if _clean(existing.get(field)) != expected:
                    raise BrowserCaptureAutomationIntegrityError(
                        "Automation job identity changed: "
                        + field
                    )

            status = "existing"

        row = _one(
            conn,
            """
            SELECT *
            FROM browser_capture_automation_jobs
            WHERE id = ?
            """,
            (job_id,),
        )

        if row is None:
            raise BrowserCaptureAutomationPersistenceError(
                "Automation job persistence failed."
            )

        conn.commit()

    except BrowserCaptureAutomationError:
        conn.rollback()
        raise
    except sqlite3.Error as error:
        conn.rollback()
        raise BrowserCaptureAutomationPersistenceError(
            "Automation job persistence failed."
        ) from error
    finally:
        conn.close()

    _WORKER_WAKE.set()

    return {
        "version": BROWSER_CAPTURE_AUTOMATION_VERSION,
        "status": status,
        "job_id": row["id"],
        "capture_record_id": row["capture_record_id"],
        "job_status": row["status"],
        "attempts": int(row["attempts"]),
        "max_attempts": int(row["max_attempts"]),
        "policy": _job_row_policy(row),
    }


def reconcile_browser_capture_jobs(
    *,
    analysis_version: str,
    scoring_version: str,
    connection_factory,
    env_getter=os.getenv,
    limit: int = DEFAULT_RECONCILE_LIMIT,
    now_provider=time.time,
) -> Dict[str, Any]:
    analysis, scoring = _versions(
        analysis_version,
        scoring_version,
    )

    if not automation_enabled(
        env_getter=env_getter
    ):
        return {
            "status": "disabled",
            "created": 0,
        }

    limit = max(
        1,
        min(5000, int(limit)),
    )

    conn = _connect(
        connection_factory
    )

    try:
        rows = conn.execute(
            """
            SELECT b.id
            FROM browser_capture_inbox AS b
            LEFT JOIN browser_capture_automation_jobs AS j
              ON j.capture_record_id = b.id
             AND j.analysis_version = ?
             AND j.scoring_version = ?
            WHERE lower(b.platform) = 'web'
              AND j.id IS NULL
            ORDER BY b.first_received_at ASC, b.id ASC
            LIMIT ?
            """,
            (
                analysis,
                scoring,
                limit,
            ),
        ).fetchall()
    except sqlite3.Error as error:
        raise BrowserCaptureAutomationPersistenceError(
            "Automation reconciliation failed."
        ) from error
    finally:
        conn.close()

    created = 0

    for raw in rows:
        capture_id = _clean(raw[0])

        result = enqueue_browser_capture_job(
            capture_record_id=capture_id,
            analysis_version=analysis,
            scoring_version=scoring,
            connection_factory=connection_factory,
            env_getter=env_getter,
            now_provider=now_provider,
        )

        if result.get("status") == "enqueued":
            created += 1

    return {
        "status": "reconciled",
        "created": created,
        "examined": len(rows),
    }


def claim_next_browser_capture_job(
    *,
    worker_id: str,
    analysis_version: str,
    scoring_version: str,
    connection_factory,
    lease_seconds: int = DEFAULT_LEASE_SECONDS,
    now_provider=time.time,
) -> Dict[str, Any] | None:
    owner = _clean(worker_id)
    analysis, scoring = _versions(
        analysis_version,
        scoring_version,
    )

    if not owner:
        raise BrowserCaptureAutomationInputError(
            "Worker ID is required."
        )

    lease_seconds = max(
        30,
        min(3600, int(lease_seconds)),
    )

    now_epoch = _epoch(
        now_provider()
    )
    now_text = _utc_from_epoch(
        now_epoch
    )
    lease_expires = now_epoch + lease_seconds

    conn = _connect(
        connection_factory
    )

    try:
        conn.execute(
            "BEGIN IMMEDIATE"
        )

        conn.execute(
            """
            UPDATE browser_capture_automation_jobs
            SET
              status = 'failed',
              available_at_epoch = ?,
              lease_owner = '',
              lease_expires_at_epoch = 0,
              updated_at = ?,
              finished_at = ?,
              last_outcome = 'lease_expired_retry_exhausted',
              error_type = 'LeaseExpired',
              error_detail = 'Worker lease expired after the final allowed attempt.'
            WHERE status = 'running'
              AND lease_expires_at_epoch > 0
              AND lease_expires_at_epoch <= ?
              AND attempts >= max_attempts
            """,
            (
                now_epoch,
                now_text,
                now_text,
                now_epoch,
            ),
        )

        conn.execute(
            """
            UPDATE browser_capture_automation_jobs
            SET
              status = 'pending',
              available_at_epoch = ?,
              lease_owner = '',
              lease_expires_at_epoch = 0,
              updated_at = ?,
              last_outcome = 'lease_expired'
            WHERE status = 'running'
              AND lease_expires_at_epoch > 0
              AND lease_expires_at_epoch <= ?
              AND attempts < max_attempts
            """,
            (
                now_epoch,
                now_text,
                now_epoch,
            ),
        )

        selected = _one(
            conn,
            """
            SELECT *
            FROM browser_capture_automation_jobs
            WHERE status = 'pending'
              AND analysis_version = ?
              AND scoring_version = ?
              AND available_at_epoch <= ?
              AND attempts < max_attempts
            ORDER BY available_at_epoch ASC, created_at ASC, id ASC
            LIMIT 1
            """,
            (
                analysis,
                scoring,
                now_epoch,
            ),
        )

        if selected is None:
            conn.commit()
            return None

        cursor = conn.execute(
            """
            UPDATE browser_capture_automation_jobs
            SET
              status = 'running',
              attempts = attempts + 1,
              lease_owner = ?,
              lease_expires_at_epoch = ?,
              started_at = COALESCE(started_at, ?),
              updated_at = ?,
              last_outcome = 'running',
              error_type = '',
              error_detail = ''
            WHERE id = ?
              AND status = 'pending'
            """,
            (
                owner,
                lease_expires,
                now_text,
                now_text,
                selected["id"],
            ),
        )

        if cursor.rowcount != 1:
            raise BrowserCaptureAutomationIntegrityError(
                "Automation job claim lost its lease race."
            )

        row = _one(
            conn,
            """
            SELECT *
            FROM browser_capture_automation_jobs
            WHERE id = ?
            """,
            (selected["id"],),
        )

        conn.commit()

    except BrowserCaptureAutomationError:
        conn.rollback()
        raise
    except sqlite3.Error as error:
        conn.rollback()
        raise BrowserCaptureAutomationPersistenceError(
            "Automation job claim failed."
        ) from error
    finally:
        conn.close()

    if row is None:
        raise BrowserCaptureAutomationIntegrityError(
            "Claimed automation job disappeared."
        )

    return row


def _update_claimed_job(
    *,
    job_id: str,
    worker_id: str,
    status: str,
    available_at_epoch: int,
    last_outcome: str,
    error_type: str,
    error_detail: str,
    result: Mapping[str, Any] | None,
    finished: bool,
    connection_factory,
    now_provider=time.time,
) -> Dict[str, Any]:
    now_epoch = _epoch(
        now_provider()
    )
    now_text = _utc_from_epoch(
        now_epoch
    )
    result_json = _json(
        dict(result or {})
    )

    conn = _connect(
        connection_factory
    )

    try:
        conn.execute(
            "BEGIN IMMEDIATE"
        )

        cursor = conn.execute(
            """
            UPDATE browser_capture_automation_jobs
            SET
              status = ?,
              available_at_epoch = ?,
              lease_owner = '',
              lease_expires_at_epoch = 0,
              updated_at = ?,
              finished_at = CASE WHEN ? THEN ? ELSE NULL END,
              last_outcome = ?,
              error_type = ?,
              error_detail = ?,
              result_json = ?
            WHERE id = ?
              AND status = 'running'
              AND lease_owner = ?
            """,
            (
                status,
                int(available_at_epoch),
                now_text,
                1 if finished else 0,
                now_text,
                _clean(last_outcome),
                _clean(error_type),
                _clean(error_detail)[:1000],
                result_json,
                _clean(job_id),
                _clean(worker_id),
            ),
        )

        if cursor.rowcount != 1:
            raise BrowserCaptureAutomationIntegrityError(
                "Automation job lease ownership changed before completion."
            )

        row = _one(
            conn,
            """
            SELECT *
            FROM browser_capture_automation_jobs
            WHERE id = ?
            """,
            (_clean(job_id),),
        )

        conn.commit()

    except BrowserCaptureAutomationError:
        conn.rollback()
        raise
    except sqlite3.Error as error:
        conn.rollback()
        raise BrowserCaptureAutomationPersistenceError(
            "Automation job update failed."
        ) from error
    finally:
        conn.close()

    if row is None:
        raise BrowserCaptureAutomationIntegrityError(
            "Updated automation job disappeared."
        )

    return row


def _retry_delay(
    attempt: int,
    *,
    base_seconds: int,
    cap_seconds: int,
) -> int:
    safe_attempt = max(1, int(attempt))
    exponent = min(16, safe_attempt - 1)

    return min(
        max(1, int(cap_seconds)),
        max(1, int(base_seconds)) * (2 ** exponent),
    )


def _result_summary(value: Mapping[str, Any]) -> Dict[str, Any]:
    return {
        "version": _clean(value.get("version")),
        "status": _clean(value.get("status")),
        "claim_id": _clean(value.get("claim_id")),
        "anchor_capture_record_id": _clean(
            value.get("anchor_capture_record_id")
        ),
        "selected_candidate_capture_record_id": _clean(
            value.get("selected_candidate_capture_record_id")
        ),
        "selected_subject_entity_id": _clean(
            value.get("selected_subject_entity_id")
        ),
        "baseline_resolution": (
            dict(value.get("baseline_resolution"))
            if isinstance(
                value.get("baseline_resolution"),
                Mapping,
            )
            else {}
        ),
        "policy": {
            "live_merit_shadow_only": True,
            "score_effect_applied": False,
            "affects_live_merit": False,
        },
    }


def _validate_shadow_result(
    value: Any,
    *,
    capture_record_id: str,
) -> Dict[str, Any]:
    if not isinstance(value, Mapping):
        raise BrowserCaptureAutomationIntegrityError(
            "Background shadow runner returned an invalid result."
        )

    result = dict(value)

    if (
        _clean(result.get("version"))
        != inbox_history_auto_shadow_orchestration.MULTIMODAL_INBOX_HISTORY_AUTO_SHADOW_VERSION
    ):
        raise BrowserCaptureAutomationIntegrityError(
            "Background shadow runner version mismatch."
        )

    if _clean(result.get("status")).lower() != "completed_shadow":
        raise BrowserCaptureAutomationIntegrityError(
            "Background shadow runner did not complete."
        )

    if (
        _clean(result.get("anchor_capture_record_id"))
        != capture_record_id
    ):
        raise BrowserCaptureAutomationIntegrityError(
            "Background shadow runner changed anchor scope."
        )

    policy = result.get("policy")

    if not isinstance(policy, Mapping):
        raise BrowserCaptureAutomationIntegrityError(
            "Background shadow policy is missing."
        )

    if (
        policy.get("live_merit_shadow_only") is not True
        or policy.get("live_release_not_called") is not True
        or bool(policy.get("score_effect_applied"))
        or bool(policy.get("affects_live_merit"))
        or bool(policy.get("establishes_truth"))
        or bool(policy.get("establishes_authority"))
        or bool(policy.get("establishes_independence"))
    ):
        raise BrowserCaptureAutomationIntegrityError(
            "Background shadow runner crossed a safety boundary."
        )

    return result


def _retry_or_fail(
    *,
    job: Mapping[str, Any],
    worker_id: str,
    outcome: str,
    error: Exception,
    connection_factory,
    retry_base_seconds: int,
    retry_cap_seconds: int,
    now_provider=time.time,
) -> Dict[str, Any]:
    attempts = int(job.get("attempts") or 0)
    maximum = int(job.get("max_attempts") or 1)
    now_epoch = _epoch(
        now_provider()
    )

    if attempts >= maximum:
        row = _update_claimed_job(
            job_id=job["id"],
            worker_id=worker_id,
            status="failed",
            available_at_epoch=now_epoch,
            last_outcome=(
                "retry_exhausted:" + _clean(outcome)
            ),
            error_type=type(error).__name__,
            error_detail=str(error),
            result=None,
            finished=True,
            connection_factory=connection_factory,
            now_provider=lambda: now_epoch,
        )

        return {
            "status": "failed",
            "job": row,
        }

    delay = _retry_delay(
        attempts,
        base_seconds=retry_base_seconds,
        cap_seconds=retry_cap_seconds,
    )

    row = _update_claimed_job(
        job_id=job["id"],
        worker_id=worker_id,
        status="pending",
        available_at_epoch=now_epoch + delay,
        last_outcome=_clean(outcome),
        error_type=type(error).__name__,
        error_detail=str(error),
        result=None,
        finished=False,
        connection_factory=connection_factory,
        now_provider=lambda: now_epoch,
    )

    return {
        "status": "retry_scheduled",
        "retry_delay_seconds": delay,
        "job": row,
    }


def execute_claimed_browser_capture_job(
    *,
    job: Mapping[str, Any],
    worker_id: str,
    connection_factory,
    gemini_client_factory,
    gemini_generator,
    gemini_client_key: str = "automation:browser-capture",
    retry_base_seconds: int = DEFAULT_RETRY_BASE_SECONDS,
    retry_cap_seconds: int = DEFAULT_RETRY_CAP_SECONDS,
    now_provider=time.time,
    runner=(
        inbox_history_auto_shadow_orchestration
        .execute_multimodal_inbox_history_auto_shadow
    ),
) -> Dict[str, Any]:
    if not isinstance(job, Mapping):
        raise BrowserCaptureAutomationInputError(
            "Claimed job must be an object."
        )

    row = dict(job)
    job_id = _clean(row.get("id"))
    capture_id = _clean(
        row.get("capture_record_id")
    )

    if (
        not job_id
        or not capture_id
        or _clean(row.get("status")) != "running"
        or _clean(row.get("lease_owner")) != _clean(worker_id)
    ):
        raise BrowserCaptureAutomationInputError(
            "Claimed job is not owned by this worker."
        )

    try:
        if not callable(gemini_client_factory):
            raise inbox_history_auto_shadow_orchestration.MultimodalInboxHistoryAutoShadowProviderUnavailable(
                "Gemini multimodal client is not configured."
            )

        client = gemini_client_factory()

        if client is None or not callable(gemini_generator):
            raise inbox_history_auto_shadow_orchestration.MultimodalInboxHistoryAutoShadowProviderUnavailable(
                "Gemini multimodal analysis is not configured."
            )

        raw = runner(
            anchor_capture_record_id=capture_id,
            analysis_version=_clean(
                row.get("analysis_version")
            ),
            scoring_version=_clean(
                row.get("scoring_version")
            ),
            connection_factory=connection_factory,
            gemini_client=client,
            gemini_client_key=(
                _clean(gemini_client_key)
                or "automation:browser-capture"
            ),
            gemini_generator=gemini_generator,
        )

        result = _validate_shadow_result(
            raw,
            capture_record_id=capture_id,
        )

    except inbox_history_auto_shadow_orchestration.MultimodalInboxHistoryAutoShadowBaselineUnavailable as error:
        return _retry_or_fail(
            job=row,
            worker_id=worker_id,
            outcome="baseline_not_ready",
            error=error,
            connection_factory=connection_factory,
            retry_base_seconds=retry_base_seconds,
            retry_cap_seconds=retry_cap_seconds,
            now_provider=now_provider,
        )
    except inbox_history_auto_shadow_orchestration.MultimodalInboxHistoryAutoShadowLookupError as error:
        return _retry_or_fail(
            job=row,
            worker_id=worker_id,
            outcome="lookup_unavailable",
            error=error,
            connection_factory=connection_factory,
            retry_base_seconds=retry_base_seconds,
            retry_cap_seconds=retry_cap_seconds,
            now_provider=now_provider,
        )
    except inbox_history_auto_shadow_orchestration.MultimodalInboxHistoryAutoShadowProviderUnavailable as error:
        return _retry_or_fail(
            job=row,
            worker_id=worker_id,
            outcome="provider_unavailable",
            error=error,
            connection_factory=connection_factory,
            retry_base_seconds=retry_base_seconds,
            retry_cap_seconds=retry_cap_seconds,
            now_provider=now_provider,
        )
    except inbox_history_auto_shadow_orchestration.MultimodalInboxHistoryAutoShadowExecutionError as error:
        return _retry_or_fail(
            job=row,
            worker_id=worker_id,
            outcome="selection_or_shadow_not_ready",
            error=error,
            connection_factory=connection_factory,
            retry_base_seconds=retry_base_seconds,
            retry_cap_seconds=retry_cap_seconds,
            now_provider=now_provider,
        )
    except (
        inbox_history_auto_shadow_orchestration.MultimodalInboxHistoryAutoShadowInputError,
        inbox_history_auto_shadow_orchestration.MultimodalInboxHistoryAutoShadowIntegrityError,
        BrowserCaptureAutomationIntegrityError,
    ) as error:
        failed = _update_claimed_job(
            job_id=job_id,
            worker_id=worker_id,
            status="failed",
            available_at_epoch=_epoch(now_provider()),
            last_outcome="terminal_integrity_or_input_failure",
            error_type=type(error).__name__,
            error_detail=str(error),
            result=None,
            finished=True,
            connection_factory=connection_factory,
            now_provider=now_provider,
        )

        return {
            "status": "failed",
            "job": failed,
        }
    except Exception as error:
        return _retry_or_fail(
            job=row,
            worker_id=worker_id,
            outcome="unexpected_runtime_failure",
            error=error,
            connection_factory=connection_factory,
            retry_base_seconds=retry_base_seconds,
            retry_cap_seconds=retry_cap_seconds,
            now_provider=now_provider,
        )

    completed = _update_claimed_job(
        job_id=job_id,
        worker_id=worker_id,
        status="completed",
        available_at_epoch=_epoch(now_provider()),
        last_outcome="completed_shadow",
        error_type="",
        error_detail="",
        result=_result_summary(result),
        finished=True,
        connection_factory=connection_factory,
        now_provider=now_provider,
    )

    return {
        "status": "completed",
        "job": completed,
        "result": _result_summary(result),
    }


def run_browser_capture_automation_iteration(
    *,
    worker_id: str,
    analysis_version: str,
    scoring_version: str,
    connection_factory,
    gemini_client_factory,
    gemini_generator,
    env_getter=os.getenv,
    now_provider=time.time,
) -> Dict[str, Any]:
    if not automation_enabled(
        env_getter=env_getter
    ):
        return {
            "status": "disabled",
        }

    job = claim_next_browser_capture_job(
        worker_id=worker_id,
        analysis_version=analysis_version,
        scoring_version=scoring_version,
        connection_factory=connection_factory,
        lease_seconds=automation_lease_seconds(
            env_getter=env_getter
        ),
        now_provider=now_provider,
    )

    if job is None:
        return {
            "status": "idle",
        }

    return execute_claimed_browser_capture_job(
        job=job,
        worker_id=worker_id,
        connection_factory=connection_factory,
        gemini_client_factory=gemini_client_factory,
        gemini_generator=gemini_generator,
        retry_base_seconds=(
            automation_retry_base_seconds(
                env_getter=env_getter
            )
        ),
        retry_cap_seconds=(
            automation_retry_cap_seconds(
                env_getter=env_getter
            )
        ),
        now_provider=now_provider,
    )


def _worker_loop(config: Mapping[str, Any]) -> None:
    poll_seconds = float(
        config["poll_seconds"]
    )
    last_reconcile = 0.0

    while not _WORKER_STOP.is_set():
        now_value = time.time()

        if now_value - last_reconcile >= 60.0:
            try:
                reconcile_browser_capture_jobs(
                    analysis_version=config[
                        "analysis_version"
                    ],
                    scoring_version=config[
                        "scoring_version"
                    ],
                    connection_factory=config[
                        "connection_factory"
                    ],
                    env_getter=config[
                        "env_getter"
                    ],
                )
            except BrowserCaptureAutomationError:
                pass

            last_reconcile = now_value

        try:
            result = run_browser_capture_automation_iteration(
                worker_id=config["worker_id"],
                analysis_version=config[
                    "analysis_version"
                ],
                scoring_version=config[
                    "scoring_version"
                ],
                connection_factory=config[
                    "connection_factory"
                ],
                gemini_client_factory=config[
                    "gemini_client_factory"
                ],
                gemini_generator=config[
                    "gemini_generator"
                ],
                env_getter=config[
                    "env_getter"
                ],
            )
        except BrowserCaptureAutomationError:
            result = {
                "status": "worker_error",
            }

        if result.get("status") not in {
            "idle",
            "disabled",
            "worker_error",
        }:
            continue

        _WORKER_WAKE.wait(
            timeout=poll_seconds
        )
        _WORKER_WAKE.clear()


def start_browser_capture_automation_worker(
    *,
    connection_factory,
    analysis_version: str,
    scoring_version: str,
    gemini_client_factory,
    gemini_generator,
    env_getter=os.getenv,
) -> Dict[str, Any]:
    global _WORKER_THREAD
    global _WORKER_ID

    analysis, scoring = _versions(
        analysis_version,
        scoring_version,
    )

    if not automation_enabled(
        env_getter=env_getter
    ):
        return {
            "version": BROWSER_CAPTURE_AUTOMATION_VERSION,
            "status": "disabled",
        }

    if connection_factory is None:
        raise BrowserCaptureAutomationInputError(
            "Automation worker database access is required."
        )

    with _WORKER_LOCK:
        if (
            _WORKER_THREAD is not None
            and _WORKER_THREAD.is_alive()
        ):
            return {
                "version": BROWSER_CAPTURE_AUTOMATION_VERSION,
                "status": "already_running",
                "worker_id": _WORKER_ID,
            }

        _WORKER_STOP.clear()
        _WORKER_WAKE.clear()
        _WORKER_ID = (
            "bcaw_"
            + uuid.uuid4().hex
        )

        config = {
            "worker_id": _WORKER_ID,
            "analysis_version": analysis,
            "scoring_version": scoring,
            "connection_factory": connection_factory,
            "gemini_client_factory": gemini_client_factory,
            "gemini_generator": gemini_generator,
            "env_getter": env_getter,
            "poll_seconds": automation_poll_seconds(
                env_getter=env_getter
            ),
        }

        thread = threading.Thread(
            target=_worker_loop,
            args=(config,),
            name="sportabase-browser-capture-automation",
            daemon=True,
        )

        _WORKER_THREAD = thread
        thread.start()

    return {
        "version": BROWSER_CAPTURE_AUTOMATION_VERSION,
        "status": "started",
        "worker_id": _WORKER_ID,
        "policy": {
            "persistent_queue": True,
            "lease_based_claim": True,
            "restart_recoverable": True,
            "public_request_does_not_wait_for_gemini": True,
            "live_merit_shadow_only": True,
            "affects_live_merit": False,
        },
    }


def stop_browser_capture_automation_worker(
    *,
    join_timeout_seconds: float = 5.0,
) -> Dict[str, Any]:
    global _WORKER_THREAD
    global _WORKER_ID

    with _WORKER_LOCK:
        thread = _WORKER_THREAD

        if thread is None:
            return {
                "version": BROWSER_CAPTURE_AUTOMATION_VERSION,
                "status": "stopped",
            }

        _WORKER_STOP.set()
        _WORKER_WAKE.set()

    if thread.is_alive():
        thread.join(
            timeout=max(
                0.0,
                float(join_timeout_seconds),
            )
        )

    with _WORKER_LOCK:
        alive = thread.is_alive()

        if not alive:
            _WORKER_THREAD = None
            _WORKER_ID = ""

    return {
        "version": BROWSER_CAPTURE_AUTOMATION_VERSION,
        "status": (
            "stopping"
            if alive
            else "stopped"
        ),
    }


def register_browser_capture_automation_lifecycle(
    *,
    app,
    connection_factory,
    analysis_version: str,
    scoring_version: str,
    gemini_client_factory,
    gemini_generator,
    env_getter=os.getenv,
) -> Dict[str, Any]:
    if app is None or not hasattr(
        app,
        "add_event_handler",
    ):
        raise BrowserCaptureAutomationInputError(
            "FastAPI lifecycle registration requires an app."
        )

    def _startup():
        return start_browser_capture_automation_worker(
            connection_factory=connection_factory,
            analysis_version=analysis_version,
            scoring_version=scoring_version,
            gemini_client_factory=gemini_client_factory,
            gemini_generator=gemini_generator,
            env_getter=env_getter,
        )

    def _shutdown():
        return stop_browser_capture_automation_worker()

    app.add_event_handler(
        "startup",
        _startup,
    )
    app.add_event_handler(
        "shutdown",
        _shutdown,
    )

    return {
        "version": BROWSER_CAPTURE_AUTOMATION_VERSION,
        "status": "registered",
        "policy": {
            "database_initialization_remains_separate": True,
            "worker_starts_at_application_startup": True,
            "worker_stops_at_application_shutdown": True,
            "automation_flag_required": True,
            "live_merit_shadow_only": True,
            "affects_live_merit": False,
        },
    }
