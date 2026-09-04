from __future__ import annotations

import hashlib
import math
import os
import threading
import time
from datetime import datetime, timezone
from typing import Any, Callable

import requests

from app.watchlists.runtime import reconcile as reconcile_watchlists


VERSION = "notifications-v1"
PROVIDER = "expo"
EXPO_PUSH_URL = "https://exp.host/--/api/v2/push/send"
NOTIFICATIONS_ENABLED_ENV = "SPORTABASE_NOTIFICATIONS_ENABLED"
NOTIFICATIONS_POLL_SECONDS_ENV = "SPORTABASE_NOTIFICATIONS_POLL_SECONDS"
NOTIFICATIONS_LEASE_SECONDS_ENV = "SPORTABASE_NOTIFICATIONS_LEASE_SECONDS"
NOTIFICATIONS_REQUEST_TIMEOUT_SECONDS_ENV = "SPORTABASE_NOTIFICATIONS_REQUEST_TIMEOUT_SECONDS"

DEFAULT_POLL_SECONDS = 15.0
DEFAULT_LEASE_SECONDS = 120
DEFAULT_REQUEST_TIMEOUT_SECONDS = 10.0
MAX_DEVICES_PER_CLIENT = 10
MAX_NOTIFICATION_CLIENTS_PER_CYCLE = 200
MAX_LEDGER_SCAN_PER_DEVICE = 200
MAX_DELIVERIES_PER_REQUEST = 50
MAX_DELIVERY_ATTEMPTS = 5
RETRY_BASE_SECONDS = 15
RETRY_CAP_SECONDS = 900


class NotificationNotFoundError(RuntimeError):
    pass


class NotificationLimitError(RuntimeError):
    pass


_WORKER_LOCK = threading.Lock()
_WORKER_STOP = threading.Event()
_WORKER_WAKE = threading.Event()
_WORKER_THREAD: threading.Thread | None = None
_WORKER_ID = ""


def _clean(value: Any, maximum: int = 2048) -> str:
    return " ".join(str(value or "").split())[:maximum]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _iso_from_epoch(value: int | float) -> str:
    return datetime.fromtimestamp(float(value), tz=timezone.utc).isoformat()


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
    return max(minimum, min(maximum, value))


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
    return max(minimum, min(maximum, value))


def notifications_enabled(*, env_getter=os.getenv) -> bool:
    return _clean(env_getter(NOTIFICATIONS_ENABLED_ENV, "0"), 16).lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def notification_poll_seconds(*, env_getter=os.getenv) -> float:
    return _bounded_float(
        env_getter(NOTIFICATIONS_POLL_SECONDS_ENV, str(DEFAULT_POLL_SECONDS)),
        default=DEFAULT_POLL_SECONDS,
        minimum=1.0,
        maximum=300.0,
    )


def notification_lease_seconds(*, env_getter=os.getenv) -> int:
    return _bounded_int(
        env_getter(NOTIFICATIONS_LEASE_SECONDS_ENV, str(DEFAULT_LEASE_SECONDS)),
        default=DEFAULT_LEASE_SECONDS,
        minimum=30,
        maximum=1800,
    )


def notification_request_timeout_seconds(*, env_getter=os.getenv) -> float:
    return _bounded_float(
        env_getter(
            NOTIFICATIONS_REQUEST_TIMEOUT_SECONDS_ENV,
            str(DEFAULT_REQUEST_TIMEOUT_SECONDS),
        ),
        default=DEFAULT_REQUEST_TIMEOUT_SECONDS,
        minimum=1.0,
        maximum=60.0,
    )


def _validate_push_token(value: str) -> str:
    token = str(value or "").strip()
    if len(token) < 20 or len(token) > 512:
        raise ValueError("Expo push token is invalid.")
    if not (
        (token.startswith("ExpoPushToken[") or token.startswith("ExponentPushToken["))
        and token.endswith("]")
    ):
        raise ValueError("Expo push token is invalid.")
    if any(ord(char) < 33 or ord(char) == 127 for char in token):
        raise ValueError("Expo push token is invalid.")
    return token


def _validate_platform(value: str) -> str:
    platform = str(value or "").strip().lower()
    if platform not in {"ios", "android"}:
        raise ValueError("Notification platform must be ios or android.")
    return platform


def _token_hash(token: str) -> str:
    return hashlib.sha256(
        ("sportabase:expo-push-token:v1:" + token).encode("utf-8")
    ).hexdigest()


def _device_id(token_hash: str) -> str:
    return "device_" + token_hash[:32]


def _delivery_id(device_id: str, alert_id: str) -> str:
    digest = hashlib.sha256(
        ("sportabase:notification-delivery:v1:" + device_id + ":" + alert_id).encode(
            "utf-8"
        )
    ).hexdigest()
    return "delivery_" + digest[:32]


def _public_device(row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "provider": row["provider"],
        "platform": row["platform"],
        "enabled": bool(row["enabled"]),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def register_device(
    *,
    owner_key: str,
    push_token: str,
    platform: str,
    connection_factory,
) -> dict[str, Any]:
    token = _validate_push_token(push_token)
    normalized_platform = _validate_platform(platform)
    digest = _token_hash(token)
    device_id = _device_id(digest)
    now = _now()

    conn = connection_factory()
    try:
        conn.execute("BEGIN IMMEDIATE")
        watermark = int(
            conn.execute(
                "SELECT COALESCE(MAX(sequence),0) FROM product_notification_alert_ledger"
            ).fetchone()[0]
        )
        existing = conn.execute(
            "SELECT * FROM product_notification_devices WHERE token_hash=?",
            (digest,),
        ).fetchone()

        needs_slot = existing is None or (
            existing["client_key"] != owner_key or not bool(existing["enabled"])
        )
        if needs_slot:
            active_count = int(
                conn.execute(
                    "SELECT COUNT(*) FROM product_notification_devices "
                    "WHERE client_key=? AND enabled=1 AND id<>?",
                    (owner_key, device_id),
                ).fetchone()[0]
            )
            if active_count >= MAX_DEVICES_PER_CLIENT:
                raise NotificationLimitError(
                    f"Notification device limit of {MAX_DEVICES_PER_CLIENT} reached."
                )

        if existing is None:
            conn.execute(
                """
                INSERT INTO product_notification_devices(
                  id,client_key,provider,token_hash,push_token,platform,enabled,
                  alert_watermark,created_at,updated_at,disabled_at
                ) VALUES(?,?,?,?,?,?,?,?,?,?,NULL)
                """,
                (
                    device_id,
                    owner_key,
                    PROVIDER,
                    digest,
                    token,
                    normalized_platform,
                    1,
                    watermark,
                    now,
                    now,
                ),
            )
            registered = True
        else:
            registered = not (
                existing["client_key"] == owner_key and bool(existing["enabled"])
            )
            if registered:
                conn.execute(
                    """
                    UPDATE product_notification_deliveries
                    SET status='cancelled', updated_at=?, lease_owner='',
                        lease_expires_at_epoch=0
                    WHERE device_id=? AND status IN ('pending','sending')
                    """,
                    (now, existing["id"]),
                )
                conn.execute(
                    """
                    UPDATE product_notification_devices
                    SET client_key=?,provider=?,push_token=?,platform=?,enabled=1,
                        alert_watermark=?,updated_at=?,disabled_at=NULL
                    WHERE id=?
                    """,
                    (
                        owner_key,
                        PROVIDER,
                        token,
                        normalized_platform,
                        watermark,
                        now,
                        existing["id"],
                    ),
                )
            else:
                conn.execute(
                    """
                    UPDATE product_notification_devices
                    SET push_token=?,platform=?,updated_at=?
                    WHERE id=? AND client_key=?
                    """,
                    (token, normalized_platform, now, existing["id"], owner_key),
                )

        row = conn.execute(
            "SELECT * FROM product_notification_devices WHERE id=? AND client_key=?",
            (device_id, owner_key),
        ).fetchone()
        conn.commit()
        return {
            "version": VERSION,
            "device": _public_device(row),
            "registered": registered,
        }
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def list_devices(*, owner_key: str, connection_factory) -> dict[str, Any]:
    conn = connection_factory()
    try:
        rows = conn.execute(
            """
            SELECT * FROM product_notification_devices
            WHERE client_key=? AND enabled=1
            ORDER BY created_at,id
            """,
            (owner_key,),
        ).fetchall()
        return {
            "version": VERSION,
            "items": [_public_device(row) for row in rows],
            "count": len(rows),
            "limit": MAX_DEVICES_PER_CLIENT,
        }
    finally:
        conn.close()


def unregister_device(
    *,
    owner_key: str,
    device_id: str,
    connection_factory,
) -> None:
    resource_id = _clean(device_id, 128)
    conn = connection_factory()
    try:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute(
            "SELECT id FROM product_notification_devices WHERE id=? AND client_key=?",
            (resource_id, owner_key),
        ).fetchone()
        if row is None:
            raise NotificationNotFoundError("Notification device not found.")
        conn.execute(
            "DELETE FROM product_notification_devices WHERE id=? AND client_key=?",
            (resource_id, owner_key),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _active_client_keys(*, connection_factory) -> list[str]:
    conn = connection_factory()
    try:
        return [
            str(row["client_key"])
            for row in conn.execute(
                """
                SELECT DISTINCT client_key
                FROM product_notification_devices
                WHERE enabled=1 AND push_token<>''
                ORDER BY client_key
                LIMIT ?
                """,
                (MAX_NOTIFICATION_CLIENTS_PER_CYCLE,),
            ).fetchall()
        ]
    finally:
        conn.close()


def reconcile_notification_clients(*, connection_factory) -> dict[str, int]:
    clients = _active_client_keys(connection_factory=connection_factory)
    watches_checked = 0
    new_alerts = 0
    failures = 0
    for owner_key in clients:
        try:
            result = reconcile_watchlists(
                owner_key=owner_key,
                connection_factory=connection_factory,
            )
            watches_checked += int(result.get("watches_checked", 0))
            new_alerts += int(result.get("new_alerts", 0))
        except Exception:
            failures += 1
    return {
        "clients_checked": len(clients),
        "watches_checked": watches_checked,
        "new_alerts": new_alerts,
        "reconcile_failures": failures,
    }


def materialize_pending_deliveries(
    *,
    connection_factory,
    clock: Callable[[], float] = time.time,
) -> dict[str, int]:
    now_epoch = max(0, int(clock()))
    now = _iso_from_epoch(now_epoch)
    conn = connection_factory()
    try:
        conn.execute("BEGIN IMMEDIATE")
        devices = conn.execute(
            """
            SELECT * FROM product_notification_devices
            WHERE enabled=1 AND push_token<>''
            ORDER BY client_key,created_at,id
            """
        ).fetchall()
        created = 0
        scanned = 0
        for device in devices:
            rows = conn.execute(
                """
                SELECT sequence,alert_id
                FROM product_notification_alert_ledger
                WHERE client_key=? AND sequence>?
                ORDER BY sequence
                LIMIT ?
                """,
                (
                    device["client_key"],
                    int(device["alert_watermark"]),
                    MAX_LEDGER_SCAN_PER_DEVICE,
                ),
            ).fetchall()
            if not rows:
                continue
            scanned += len(rows)
            for row in rows:
                cursor = conn.execute(
                    """
                    INSERT OR IGNORE INTO product_notification_deliveries(
                      id,client_key,device_id,alert_id,provider,status,attempts,
                      available_at_epoch,lease_owner,lease_expires_at_epoch,
                      provider_message_id,error_type,error_detail,created_at,
                      updated_at,accepted_at
                    ) VALUES(?,?,?,?,?,'pending',0,?,'',0,'','','',?,?,NULL)
                    """,
                    (
                        _delivery_id(device["id"], row["alert_id"]),
                        device["client_key"],
                        device["id"],
                        row["alert_id"],
                        PROVIDER,
                        now_epoch,
                        now,
                        now,
                    ),
                )
                created += int(cursor.rowcount or 0)
            conn.execute(
                """
                UPDATE product_notification_devices
                SET alert_watermark=?,updated_at=?
                WHERE id=?
                """,
                (int(rows[-1]["sequence"]), now, device["id"]),
            )
        conn.commit()
        return {
            "devices_checked": len(devices),
            "ledger_rows_scanned": scanned,
            "deliveries_created": created,
        }
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _retry_delay(attempts: int) -> int:
    exponent = max(0, int(attempts) - 1)
    return min(RETRY_CAP_SECONDS, RETRY_BASE_SECONDS * (2**exponent))


def _claim_deliveries(
    *,
    connection_factory,
    worker_id: str,
    now_epoch: int,
    lease_seconds: int,
) -> list[dict[str, Any]]:
    conn = connection_factory()
    try:
        conn.execute("BEGIN IMMEDIATE")
        now = _iso_from_epoch(now_epoch)
        conn.execute(
            """
            UPDATE product_notification_deliveries
            SET status='cancelled',updated_at=?,lease_owner='',lease_expires_at_epoch=0
            WHERE status IN ('pending','sending')
              AND device_id IN (
                SELECT id FROM product_notification_devices
                WHERE enabled=0 OR push_token=''
              )
            """,
            (now,),
        )
        conn.execute(
            """
            UPDATE product_notification_deliveries
            SET status='failed',updated_at=?,error_type='attempts_exhausted',
                error_detail='Notification delivery attempts exhausted.',
                lease_owner='',lease_expires_at_epoch=0
            WHERE status IN ('pending','sending') AND attempts>=?
            """,
            (now, MAX_DELIVERY_ATTEMPTS),
        )
        ids = [
            str(row["id"])
            for row in conn.execute(
                """
                SELECT d.id
                FROM product_notification_deliveries d
                JOIN product_notification_devices dev ON dev.id=d.device_id
                WHERE dev.enabled=1 AND dev.push_token<>''
                  AND d.attempts<?
                  AND (
                    (d.status='pending' AND d.available_at_epoch<=?)
                    OR
                    (d.status='sending' AND d.lease_expires_at_epoch<=?)
                  )
                ORDER BY d.available_at_epoch,d.created_at,d.id
                LIMIT ?
                """,
                (
                    MAX_DELIVERY_ATTEMPTS,
                    now_epoch,
                    now_epoch,
                    MAX_DELIVERIES_PER_REQUEST,
                ),
            ).fetchall()
        ]
        if not ids:
            conn.commit()
            return []
        marks = ",".join("?" for _ in ids)
        lease_expires = now_epoch + lease_seconds
        conn.execute(
            f"""
            UPDATE product_notification_deliveries
            SET status='sending',attempts=attempts+1,lease_owner=?,
                lease_expires_at_epoch=?,updated_at=?
            WHERE id IN ({marks})
            """,
            (worker_id, lease_expires, now, *ids),
        )
        rows = [
            dict(row)
            for row in conn.execute(
                f"""
                SELECT
                  d.id,d.device_id,d.alert_id,d.attempts,
                  dev.push_token,dev.platform,
                  a.target_kind,a.target_id,a.event_type,a.summary
                FROM product_notification_deliveries d
                JOIN product_notification_devices dev ON dev.id=d.device_id
                JOIN product_alert_events a ON a.id=d.alert_id
                WHERE d.id IN ({marks})
                ORDER BY d.created_at,d.id
                """,
                ids,
            ).fetchall()
        ]
        conn.commit()
        return rows
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _message_for_delivery(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "to": row["push_token"],
        "sound": "default",
        "title": "Sportabase",
        "body": _clean(row["summary"], 240),
        "data": {
            "sportabase_notification_version": VERSION,
            "alert_id": row["alert_id"],
            "target_kind": row["target_kind"],
            "target_id": row["target_id"],
            "event_type": row["event_type"],
        },
        "channelId": "sportabase-intelligence",
    }


def _provider_error_detail(ticket: dict[str, Any]) -> tuple[str, str]:
    details = ticket.get("details")
    provider_code = ""
    if isinstance(details, dict):
        provider_code = _clean(details.get("error"), 128)
    message = _clean(ticket.get("message"), 1000)
    return provider_code, message


def _finish_batch(
    *,
    connection_factory,
    rows: list[dict[str, Any]],
    tickets: list[dict[str, Any]] | None,
    now_epoch: int,
    transport_error_type: str = "",
    transport_error_detail: str = "",
) -> dict[str, int]:
    accepted = retried = failed = invalid_devices = 0
    now = _iso_from_epoch(now_epoch)
    conn = connection_factory()
    try:
        conn.execute("BEGIN IMMEDIATE")
        for index, row in enumerate(rows):
            ticket = tickets[index] if tickets is not None and index < len(tickets) else None
            attempts = int(row["attempts"])
            if transport_error_type:
                if attempts >= MAX_DELIVERY_ATTEMPTS:
                    conn.execute(
                        """
                        UPDATE product_notification_deliveries
                        SET status='failed',updated_at=?,error_type=?,error_detail=?,
                            lease_owner='',lease_expires_at_epoch=0
                        WHERE id=?
                        """,
                        (now, transport_error_type, transport_error_detail, row["id"]),
                    )
                    failed += 1
                else:
                    conn.execute(
                        """
                        UPDATE product_notification_deliveries
                        SET status='pending',available_at_epoch=?,updated_at=?,
                            error_type=?,error_detail=?,lease_owner='',
                            lease_expires_at_epoch=0
                        WHERE id=?
                        """,
                        (
                            now_epoch + _retry_delay(attempts),
                            now,
                            transport_error_type,
                            transport_error_detail,
                            row["id"],
                        ),
                    )
                    retried += 1
                continue

            if not isinstance(ticket, dict):
                provider_code = "provider_protocol"
                message = "Expo push response did not contain a matching ticket."
                retryable = True
            else:
                status = _clean(ticket.get("status"), 32).lower()
                if status == "ok":
                    provider_id = _clean(ticket.get("id"), 256)
                    conn.execute(
                        """
                        UPDATE product_notification_deliveries
                        SET status='accepted',provider_message_id=?,accepted_at=?,
                            updated_at=?,error_type='',error_detail='',lease_owner='',
                            lease_expires_at_epoch=0
                        WHERE id=?
                        """,
                        (provider_id, now, now, row["id"]),
                    )
                    accepted += 1
                    continue
                provider_code, message = _provider_error_detail(ticket)
                retryable = provider_code in {
                    "MessageRateExceeded",
                    "TooManyRequests",
                }

            if provider_code == "DeviceNotRegistered":
                conn.execute(
                    """
                    UPDATE product_notification_devices
                    SET enabled=0,push_token='',updated_at=?,disabled_at=?
                    WHERE id=?
                    """,
                    (now, now, row["device_id"]),
                )
                conn.execute(
                    """
                    UPDATE product_notification_deliveries
                    SET status='failed',updated_at=?,error_type='device_not_registered',
                        error_detail=?,lease_owner='',lease_expires_at_epoch=0
                    WHERE id=?
                    """,
                    (now, message or "Expo reports that this device is not registered.", row["id"]),
                )
                failed += 1
                invalid_devices += 1
                continue

            error_type = _clean(provider_code or "provider_rejected", 128)
            error_detail = message or "Expo rejected the notification delivery."
            if retryable and attempts < MAX_DELIVERY_ATTEMPTS:
                conn.execute(
                    """
                    UPDATE product_notification_deliveries
                    SET status='pending',available_at_epoch=?,updated_at=?,error_type=?,
                        error_detail=?,lease_owner='',lease_expires_at_epoch=0
                    WHERE id=?
                    """,
                    (
                        now_epoch + _retry_delay(attempts),
                        now,
                        error_type,
                        error_detail,
                        row["id"],
                    ),
                )
                retried += 1
            else:
                conn.execute(
                    """
                    UPDATE product_notification_deliveries
                    SET status='failed',updated_at=?,error_type=?,error_detail=?,
                        lease_owner='',lease_expires_at_epoch=0
                    WHERE id=?
                    """,
                    (now, error_type, error_detail, row["id"]),
                )
                failed += 1
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    return {
        "accepted": accepted,
        "retried": retried,
        "failed": failed,
        "invalid_devices": invalid_devices,
    }


def dispatch_pending_deliveries(
    *,
    connection_factory,
    http_post: Callable[..., Any] = requests.post,
    clock: Callable[[], float] = time.time,
    worker_id: str = "notification-worker",
    lease_seconds: int = DEFAULT_LEASE_SECONDS,
    request_timeout_seconds: float = DEFAULT_REQUEST_TIMEOUT_SECONDS,
) -> dict[str, int]:
    now_epoch = max(0, int(clock()))
    rows = _claim_deliveries(
        connection_factory=connection_factory,
        worker_id=worker_id,
        now_epoch=now_epoch,
        lease_seconds=lease_seconds,
    )
    if not rows:
        return {
            "claimed": 0,
            "accepted": 0,
            "retried": 0,
            "failed": 0,
            "invalid_devices": 0,
        }

    messages = [_message_for_delivery(row) for row in rows]

    # Only provider transport belongs in this exception boundary. Persistence
    # and ticket-processing failures must propagate instead of being silently
    # reclassified as transient network failures.
    try:
        response = http_post(
            EXPO_PUSH_URL,
            json=messages,
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
            },
            timeout=request_timeout_seconds,
        )
    except Exception as exc:
        result = _finish_batch(
            connection_factory=connection_factory,
            rows=rows,
            tickets=None,
            now_epoch=now_epoch,
            transport_error_type="provider_transport",
            transport_error_detail=_clean(exc, 1000)
            or "Expo push transport failed.",
        )
        return {"claimed": len(rows), **result}

    status_code = int(getattr(response, "status_code", 0) or 0)
    if status_code == 429 or status_code >= 500 or status_code <= 0:
        result = _finish_batch(
            connection_factory=connection_factory,
            rows=rows,
            tickets=None,
            now_epoch=now_epoch,
            transport_error_type=f"provider_http_{status_code or 'unknown'}",
            transport_error_detail=_clean(getattr(response, "text", ""), 1000)
            or "Expo push transport is temporarily unavailable.",
        )
    elif status_code >= 400:
        result = _finish_batch(
            connection_factory=connection_factory,
            rows=rows,
            tickets=[
                {
                    "status": "error",
                    "message": _clean(getattr(response, "text", ""), 1000)
                    or f"Expo push returned HTTP {status_code}.",
                    "details": {"error": f"HTTP{status_code}"},
                }
                for _ in rows
            ],
            now_epoch=now_epoch,
        )
    else:
        try:
            payload = response.json()
        except Exception:
            payload = {}
        data = payload.get("data") if isinstance(payload, dict) else None
        if isinstance(data, dict):
            tickets = [data]
        elif isinstance(data, list):
            tickets = [item for item in data if isinstance(item, dict)]
        else:
            tickets = []
        result = _finish_batch(
            connection_factory=connection_factory,
            rows=rows,
            tickets=tickets,
            now_epoch=now_epoch,
        )

    return {"claimed": len(rows), **result}

def run_notification_cycle(
    *,
    connection_factory,
    http_post: Callable[..., Any] = requests.post,
    clock: Callable[[], float] = time.time,
    worker_id: str = "notification-worker",
    lease_seconds: int = DEFAULT_LEASE_SECONDS,
    request_timeout_seconds: float = DEFAULT_REQUEST_TIMEOUT_SECONDS,
) -> dict[str, int]:
    reconciliation = reconcile_notification_clients(
        connection_factory=connection_factory,
    )
    materialized = materialize_pending_deliveries(
        connection_factory=connection_factory,
        clock=clock,
    )
    dispatched = dispatch_pending_deliveries(
        connection_factory=connection_factory,
        http_post=http_post,
        clock=clock,
        worker_id=worker_id,
        lease_seconds=lease_seconds,
        request_timeout_seconds=request_timeout_seconds,
    )
    return {**reconciliation, **materialized, **dispatched}


def _worker_loop(
    *,
    connection_factory,
    http_post: Callable[..., Any],
    poll_seconds: float,
    lease_seconds: int,
    request_timeout_seconds: float,
    worker_id: str,
) -> None:
    while not _WORKER_STOP.is_set():
        try:
            run_notification_cycle(
                connection_factory=connection_factory,
                http_post=http_post,
                worker_id=worker_id,
                lease_seconds=lease_seconds,
                request_timeout_seconds=request_timeout_seconds,
            )
        except Exception as exc:
            print("[sportabase] notification worker cycle failed:", exc)
        _WORKER_WAKE.wait(poll_seconds)
        _WORKER_WAKE.clear()


def start_notification_worker(
    *,
    connection_factory,
    http_post: Callable[..., Any] = requests.post,
    env_getter=os.getenv,
) -> bool:
    global _WORKER_THREAD, _WORKER_ID
    if not notifications_enabled(env_getter=env_getter):
        return False
    with _WORKER_LOCK:
        if _WORKER_THREAD is not None and _WORKER_THREAD.is_alive():
            return True
        _WORKER_STOP.clear()
        _WORKER_WAKE.clear()
        _WORKER_ID = "notification-worker-" + hashlib.sha256(
            f"{os.getpid()}:{time.time_ns()}".encode("utf-8")
        ).hexdigest()[:12]
        thread = threading.Thread(
            target=_worker_loop,
            kwargs={
                "connection_factory": connection_factory,
                "http_post": http_post,
                "poll_seconds": notification_poll_seconds(env_getter=env_getter),
                "lease_seconds": notification_lease_seconds(env_getter=env_getter),
                "request_timeout_seconds": notification_request_timeout_seconds(
                    env_getter=env_getter
                ),
                "worker_id": _WORKER_ID,
            },
            daemon=True,
            name="sportabase-notifications",
        )
        _WORKER_THREAD = thread
        thread.start()
        return True


def stop_notification_worker(*, join_timeout_seconds: float = 5.0) -> None:
    global _WORKER_THREAD, _WORKER_ID
    with _WORKER_LOCK:
        thread = _WORKER_THREAD
        if thread is None:
            return
        _WORKER_STOP.set()
        _WORKER_WAKE.set()
    thread.join(max(0.0, float(join_timeout_seconds)))
    with _WORKER_LOCK:
        if _WORKER_THREAD is thread and not thread.is_alive():
            _WORKER_THREAD = None
            _WORKER_ID = ""


def register_notification_lifecycle(
    *,
    app,
    connection_factory,
    http_post: Callable[..., Any] = requests.post,
) -> None:
    app.add_event_handler(
        "startup",
        lambda: start_notification_worker(
            connection_factory=connection_factory,
            http_post=http_post,
        ),
    )
    app.add_event_handler("shutdown", stop_notification_worker)


__all__ = [
    "VERSION",
    "NotificationLimitError",
    "NotificationNotFoundError",
    "dispatch_pending_deliveries",
    "list_devices",
    "materialize_pending_deliveries",
    "notifications_enabled",
    "reconcile_notification_clients",
    "register_device",
    "register_notification_lifecycle",
    "run_notification_cycle",
    "start_notification_worker",
    "stop_notification_worker",
    "unregister_device",
]
