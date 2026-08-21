from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Any, Callable
from urllib.parse import urlparse
from uuid import uuid4


PERSISTENT_OPERATIONS_STORE_VERSION = (
    "sportabase-persistent-operations-store-v1"
)
DEFAULT_OPERATIONS_CONNECT_TIMEOUT_SECONDS = 10.0
DEFAULT_OPERATIONS_EVENT_MAX_DETAILS_BYTES = 16384

_OPERATIONS_SCHEMA_STATEMENTS = (
    """
    CREATE TABLE IF NOT EXISTS sportabase_operational_events (
      id TEXT PRIMARY KEY,
      occurred_at TIMESTAMPTZ NOT NULL,
      service_name TEXT NOT NULL,
      component TEXT NOT NULL,
      event_type TEXT NOT NULL,
      status TEXT NOT NULL,
      mode TEXT NOT NULL DEFAULT '',
      source_key TEXT NOT NULL DEFAULT '',
      correlation_id TEXT NOT NULL DEFAULT '',
      duration_ms BIGINT NOT NULL DEFAULT 0 CHECK (duration_ms >= 0),
      details_json TEXT NOT NULL DEFAULT '{}'
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_operational_events_time
    ON sportabase_operational_events(occurred_at DESC)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_operational_events_component_time
    ON sportabase_operational_events(component, occurred_at DESC)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_operational_events_type_time
    ON sportabase_operational_events(event_type, occurred_at DESC)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_operational_events_status_time
    ON sportabase_operational_events(status, occurred_at DESC)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_operational_events_source_time
    ON sportabase_operational_events(source_key, occurred_at DESC)
    """,
)

_SENSITIVE_DETAIL_KEY_TOKENS = (
    "authorization",
    "cookie",
    "secret",
    "token",
    "password",
    "api_key",
    "apikey",
    "jwt",
    "client_key",
    "email",
    "subject",
)


class PersistentOperationsStoreMisconfigured(RuntimeError):
    pass


class PersistentOperationsStoreUnavailable(RuntimeError):
    pass


def _normalized_database_url(value: str) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""

    parsed = urlparse(raw)
    if (
        parsed.scheme.casefold() not in {"postgres", "postgresql"}
        or not parsed.hostname
        or not parsed.path
        or parsed.path == "/"
        or parsed.fragment
    ):
        raise PersistentOperationsStoreMisconfigured(
            "Persistent operations database URL is invalid."
        )

    return raw


def _validated_timeout(value: int | float) -> float:
    try:
        timeout = float(value)
    except Exception as error:
        raise PersistentOperationsStoreMisconfigured(
            "Persistent operations database timeout is invalid."
        ) from error

    if timeout <= 0.0 or timeout > 60.0:
        raise PersistentOperationsStoreMisconfigured(
            "Persistent operations database timeout is invalid."
        )

    return timeout


def _validated_max_details_bytes(value: int) -> int:
    try:
        maximum = int(value)
    except Exception as error:
        raise PersistentOperationsStoreMisconfigured(
            "Persistent operations details limit is invalid."
        ) from error

    if maximum < 256 or maximum > 65536:
        raise PersistentOperationsStoreMisconfigured(
            "Persistent operations details limit is invalid."
        )

    return maximum


def _safe_text(value: Any, *, maximum: int) -> str:
    text = str(value or "").strip()
    if len(text) > maximum:
        return text[:maximum]
    return text


def _sensitive_detail_key(value: Any) -> bool:
    normalized = str(value or "").strip().casefold()
    return any(
        token in normalized
        for token in _SENSITIVE_DETAIL_KEY_TOKENS
    )


def _sanitize_detail_value(value: Any, *, depth: int = 0) -> Any:
    if depth >= 6:
        return "[depth-limited]"

    if isinstance(value, Mapping):
        output: dict[str, Any] = {}
        for raw_key, raw_value in value.items():
            key = _safe_text(raw_key, maximum=128)
            if not key:
                continue
            if _sensitive_detail_key(key):
                output[key] = "[redacted]"
            else:
                output[key] = _sanitize_detail_value(
                    raw_value,
                    depth=depth + 1,
                )
        return output

    if isinstance(value, (list, tuple)):
        return [
            _sanitize_detail_value(item, depth=depth + 1)
            for item in list(value)[:50]
        ]

    if value is None or isinstance(value, (bool, int, float)):
        return value

    return _safe_text(value, maximum=1024)


def _serialized_details(
    details: Mapping[str, Any] | None,
    *,
    maximum_bytes: int,
) -> str:
    maximum = _validated_max_details_bytes(maximum_bytes)
    safe_details = _sanitize_detail_value(details or {})
    encoded = json.dumps(
        safe_details,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )

    encoded_bytes = encoded.encode("utf-8")
    if len(encoded_bytes) <= maximum:
        return encoded

    return json.dumps(
        {
            "details_truncated": True,
            "encoded_bytes": len(encoded_bytes),
        },
        separators=(",", ":"),
        sort_keys=True,
    )


def _default_connect(
    database_url: str,
    timeout_seconds: float,
):
    try:
        import psycopg
    except ImportError as error:
        raise PersistentOperationsStoreMisconfigured(
            "Persistent operations PostgreSQL driver is unavailable."
        ) from error

    return psycopg.connect(
        database_url,
        connect_timeout=timeout_seconds,
    )


def _open_connection(
    *,
    database_url: str,
    timeout_seconds: float,
    connect_factory: Callable[[str, float], Any],
):
    try:
        return connect_factory(
            database_url,
            timeout_seconds,
        )
    except PersistentOperationsStoreMisconfigured:
        raise
    except Exception as error:
        raise PersistentOperationsStoreUnavailable(
            "Persistent operations database is unavailable."
        ) from error


def _close_quietly(value: Any) -> None:
    close = getattr(value, "close", None)
    if callable(close):
        try:
            close()
        except Exception:
            pass


def initialize_persistent_operations_store(
    *,
    database_url: str,
    timeout_seconds: int | float = DEFAULT_OPERATIONS_CONNECT_TIMEOUT_SECONDS,
    connect_factory: Callable[[str, float], Any] = _default_connect,
) -> bool:
    normalized_url = _normalized_database_url(database_url)
    if not normalized_url:
        return False

    timeout = _validated_timeout(timeout_seconds)
    connection = _open_connection(
        database_url=normalized_url,
        timeout_seconds=timeout,
        connect_factory=connect_factory,
    )
    cursor = None

    try:
        cursor = connection.cursor()
        for statement in _OPERATIONS_SCHEMA_STATEMENTS:
            cursor.execute(statement)
        connection.commit()
    except Exception as error:
        rollback = getattr(connection, "rollback", None)
        if callable(rollback):
            try:
                rollback()
            except Exception:
                pass
        raise PersistentOperationsStoreUnavailable(
            "Persistent operations database schema initialization failed."
        ) from error
    finally:
        _close_quietly(cursor)
        _close_quietly(connection)

    return True


def record_operational_event(
    *,
    database_url: str,
    service_name: str,
    component: str,
    event_type: str,
    status: str,
    mode: str = "",
    source_key: str = "",
    correlation_id: str = "",
    duration_ms: int = 0,
    details: Mapping[str, Any] | None = None,
    occurred_at: datetime | None = None,
    event_id: str | None = None,
    timeout_seconds: int | float = DEFAULT_OPERATIONS_CONNECT_TIMEOUT_SECONDS,
    maximum_details_bytes: int = DEFAULT_OPERATIONS_EVENT_MAX_DETAILS_BYTES,
    connect_factory: Callable[[str, float], Any] = _default_connect,
) -> str | None:
    normalized_url = _normalized_database_url(database_url)
    if not normalized_url:
        return None

    timeout = _validated_timeout(timeout_seconds)
    identifier = _safe_text(event_id or uuid4().hex, maximum=128)
    service = _safe_text(service_name, maximum=96)
    component_name = _safe_text(component, maximum=96)
    event_name = _safe_text(event_type, maximum=128)
    event_status = _safe_text(status, maximum=48)

    if not identifier or not service or not component_name or not event_name or not event_status:
        raise PersistentOperationsStoreMisconfigured(
            "Persistent operations event identity fields are required."
        )

    try:
        safe_duration_ms = max(0, int(duration_ms or 0))
    except Exception as error:
        raise PersistentOperationsStoreMisconfigured(
            "Persistent operations event duration is invalid."
        ) from error

    timestamp = occurred_at or datetime.now(timezone.utc)
    if timestamp.tzinfo is None or timestamp.utcoffset() is None:
        raise PersistentOperationsStoreMisconfigured(
            "Persistent operations event timestamp must be timezone-aware."
        )

    details_json = _serialized_details(
        details,
        maximum_bytes=maximum_details_bytes,
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
            INSERT INTO sportabase_operational_events (
              id,
              occurred_at,
              service_name,
              component,
              event_type,
              status,
              mode,
              source_key,
              correlation_id,
              duration_ms,
              details_json
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (id) DO NOTHING
            """,
            (
                identifier,
                timestamp.astimezone(timezone.utc),
                service,
                component_name,
                event_name,
                event_status,
                _safe_text(mode, maximum=64),
                _safe_text(source_key, maximum=192),
                _safe_text(correlation_id, maximum=128),
                safe_duration_ms,
                details_json,
            ),
        )
        connection.commit()
    except Exception as error:
        rollback = getattr(connection, "rollback", None)
        if callable(rollback):
            try:
                rollback()
            except Exception:
                pass
        raise PersistentOperationsStoreUnavailable(
            "Persistent operations event write failed."
        ) from error
    finally:
        _close_quietly(cursor)
        _close_quietly(connection)

    return identifier


__all__ = [
    "PERSISTENT_OPERATIONS_STORE_VERSION",
    "DEFAULT_OPERATIONS_CONNECT_TIMEOUT_SECONDS",
    "DEFAULT_OPERATIONS_EVENT_MAX_DETAILS_BYTES",
    "PersistentOperationsStoreMisconfigured",
    "PersistentOperationsStoreUnavailable",
    "initialize_persistent_operations_store",
    "record_operational_event",
]
