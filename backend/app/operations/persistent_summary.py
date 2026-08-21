from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Callable

from app.operations.persistent_store import (
    PersistentOperationsStoreMisconfigured,
    PersistentOperationsStoreUnavailable,
    _close_quietly,
    _default_connect,
    _normalized_database_url,
    _open_connection,
    _validated_timeout,
)


PERSISTENT_OPERATIONS_SUMMARY_VERSION = (
    "sportabase-persistent-operations-summary-v1"
)
MAX_SOURCE_HEALTH_ROWS = 50


def _validated_days(value: Any) -> int:
    try:
        days = int(value)
    except Exception as error:
        raise PersistentOperationsStoreMisconfigured(
            "Persistent operations summary window is invalid."
        ) from error

    if days < 1 or days > 30:
        raise PersistentOperationsStoreMisconfigured(
            "Persistent operations summary window is invalid."
        )

    return days


def _row_values(row: Any) -> tuple[Any, ...]:
    if isinstance(row, tuple):
        return row
    try:
        return tuple(row)
    except Exception as error:
        raise PersistentOperationsStoreUnavailable(
            "Persistent operations summary returned an invalid row."
        ) from error


def summarize_persistent_operations(
    *,
    database_url: str,
    days: int = 7,
    timeout_seconds: int | float = 2.0,
    now: datetime | None = None,
    connect_factory: Callable[[str, float], Any] = _default_connect,
) -> dict[str, Any]:
    normalized_url = _normalized_database_url(database_url)
    window_days = _validated_days(days)
    timeout = _validated_timeout(timeout_seconds)

    if not normalized_url:
        return {
            "version": PERSISTENT_OPERATIONS_SUMMARY_VERSION,
            "state": "disabled",
            "window_days": window_days,
            "total_events": 0,
            "statuses": {},
            "components": {},
            "event_types": {},
            "modes": {},
            "pipeline": {},
            "jobs": {},
            "source_health": [],
        }

    observed_now = now or datetime.now(timezone.utc)
    if observed_now.tzinfo is None or observed_now.utcoffset() is None:
        raise PersistentOperationsStoreMisconfigured(
            "Persistent operations summary clock must be timezone-aware."
        )

    cutoff = observed_now.astimezone(timezone.utc) - timedelta(
        days=window_days
    )

    connection = _open_connection(
        database_url=normalized_url,
        timeout_seconds=timeout,
        connect_factory=connect_factory,
    )
    cursor = None

    try:
        cursor = connection.cursor()

        cursor.execute(
            """
            SELECT status, COUNT(*)
            FROM sportabase_operational_events
            WHERE occurred_at >= %s
            GROUP BY status
            ORDER BY status ASC
            """,
            (cutoff,),
        )
        status_rows = cursor.fetchall()

        cursor.execute(
            """
            SELECT component, event_type, status, COUNT(*)
            FROM sportabase_operational_events
            WHERE occurred_at >= %s
            GROUP BY component, event_type, status
            ORDER BY component ASC, event_type ASC, status ASC
            """,
            (cutoff,),
        )
        event_rows = cursor.fetchall()

        cursor.execute(
            """
            SELECT mode, COUNT(*)
            FROM sportabase_operational_events
            WHERE occurred_at >= %s
              AND mode <> ''
            GROUP BY mode
            ORDER BY mode ASC
            """,
            (cutoff,),
        )
        mode_rows = cursor.fetchall()

        cursor.execute(
            """
            SELECT
              source_key,
              COUNT(*) AS event_count,
              SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) AS successes,
              SUM(CASE WHEN status = 'error' THEN 1 ELSE 0 END) AS failures,
              MAX(occurred_at) AS last_seen_at
            FROM sportabase_operational_events
            WHERE occurred_at >= %s
              AND source_key <> ''
            GROUP BY source_key
            ORDER BY event_count DESC, source_key ASC
            LIMIT %s
            """,
            (cutoff, MAX_SOURCE_HEALTH_ROWS),
        )
        source_rows = cursor.fetchall()

    except PersistentOperationsStoreUnavailable:
        raise
    except Exception as error:
        raise PersistentOperationsStoreUnavailable(
            "Persistent operations summary query failed."
        ) from error
    finally:
        _close_quietly(cursor)
        _close_quietly(connection)

    statuses: dict[str, int] = {}
    for raw in status_rows:
        status, count = _row_values(raw)
        statuses[str(status or "")] = int(count or 0)

    components: dict[str, int] = {}
    event_types: dict[str, int] = {}
    event_statuses: dict[str, dict[str, int]] = {}

    for raw in event_rows:
        component, event_type, status, count = _row_values(raw)
        component_name = str(component or "")
        event_name = str(event_type or "")
        status_name = str(status or "")
        event_count = int(count or 0)

        components[component_name] = (
            components.get(component_name, 0) + event_count
        )
        event_types[event_name] = (
            event_types.get(event_name, 0) + event_count
        )
        status_bucket = event_statuses.setdefault(event_name, {})
        status_bucket[status_name] = (
            status_bucket.get(status_name, 0) + event_count
        )

    modes = {
        str(mode or ""): int(count or 0)
        for mode, count in map(_row_values, mode_rows)
        if str(mode or "")
    }

    def event_count(name: str) -> int:
        return int(event_types.get(name, 0))

    pipeline = {
        "capture_processed": event_count("capture.processed"),
        "capture_failed": event_count("capture.failed"),
        "analysis_completed": event_count("analysis.completed"),
        "analysis_failed": event_count("analysis.failed"),
    }

    jobs = {
        "enqueued": event_count("job.enqueued"),
        "retry_scheduled": event_count("job.retry_scheduled"),
        "completed": event_count("job.completed"),
        "failed": event_count("job.failed"),
        "reconciled": event_count("job.reconciled"),
    }

    source_health = []
    for raw in source_rows:
        source_key, count, successes, failures, last_seen_at = _row_values(raw)
        timestamp = last_seen_at
        if isinstance(timestamp, datetime):
            timestamp_text = timestamp.astimezone(timezone.utc).isoformat()
        else:
            timestamp_text = str(timestamp or "")

        source_health.append({
            "source_key": str(source_key or "")[:192],
            "events": int(count or 0),
            "successes": int(successes or 0),
            "failures": int(failures or 0),
            "last_seen_at": timestamp_text,
        })

    return {
        "version": PERSISTENT_OPERATIONS_SUMMARY_VERSION,
        "state": "ready",
        "window_days": window_days,
        "total_events": sum(statuses.values()),
        "statuses": statuses,
        "components": components,
        "event_types": event_types,
        "event_statuses": event_statuses,
        "modes": modes,
        "pipeline": pipeline,
        "jobs": jobs,
        "source_health": source_health,
    }


__all__ = [
    "PERSISTENT_OPERATIONS_SUMMARY_VERSION",
    "MAX_SOURCE_HEALTH_ROWS",
    "summarize_persistent_operations",
]
