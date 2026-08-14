import hashlib
import json
import re
import sqlite3
import time

from concurrent.futures import Future

from datetime import (
    datetime,
    timedelta,
    timezone,
)

from typing import (
    Any,
    Dict,
    Optional,
)

import requests

from fastapi import (
    HTTPException,
    Request,
)


def request_client_key(
    request: Request,
) -> str:
    installation_id = str(
        request.headers.get(
            "x-sportabase-client-id",
            "",
        )
    ).strip()

    if installation_id:
        identity = (
            f"installation:{installation_id}"
        )
    else:
        forwarded_for = str(
            request.headers.get(
                "x-forwarded-for",
                "",
            )
        ).split(",", 1)[0].strip()

        client_host = (
            request.client.host
            if request.client
            else ""
        )

        identity = (
            f"ip:{forwarded_for or client_host or 'unknown'}"
        )

    return hashlib.sha256(
        identity.encode("utf-8")
    ).hexdigest()[:32]


def expire_stale_gemini_reservations(
    conn: sqlite3.Connection,
    *,
    usage_day: Optional[str] = None,
    now: Optional[datetime] = None,
    reservation_timeout_seconds: int,
) -> int:
    current_time = (
        now
        if now is not None
        else datetime.now(timezone.utc)
    )

    current_usage_day = (
        str(usage_day)
        if usage_day
        else current_time.date().isoformat()
    )

    cutoff = (
        current_time
        - timedelta(
            seconds=(
                reservation_timeout_seconds
            )
        )
    ).isoformat()

    cursor = conn.execute(
        """
        UPDATE gemini_usage
        SET
          status = 'expired',
          failure_type = 'reservation_timeout',
          failure_detail = (
            'Gemini reservation expired before completion.'
          )
        WHERE usage_day = ?
          AND status = 'reserved'
          AND created_at < ?
          AND cache_hit = 0
          AND inflight_join = 0
        """,
        (
            current_usage_day,
            cutoff,
        ),
    )

    return max(
        0,
        int(cursor.rowcount or 0),
    )


def reserve_gemini_call(
    client_key: str,
    mode: str,
    model: str,
    *,
    usage_day_resolver,
    connection_factory,
    expire_reservations,
    global_daily_call_cap: int,
    client_daily_call_cap: int,
) -> int:
    usage_day = usage_day_resolver()
    created_at = datetime.now(
        timezone.utc
    ).isoformat()

    conn = connection_factory()

    try:
        conn.execute("BEGIN IMMEDIATE")

        expire_reservations(
            conn,
            usage_day=usage_day,
        )

        global_count = int(
            conn.execute(
                """
                SELECT COUNT(*)
                FROM gemini_usage
                WHERE usage_day = ?
                  AND cache_hit = 0
                  AND inflight_join = 0
                  AND status IN (
                    'reserved',
                    'success',
                    'failed'
                  )
                """,
                (usage_day,),
            ).fetchone()[0]
        )

        client_count = int(
            conn.execute(
                """
                SELECT COUNT(*)
                FROM gemini_usage
                WHERE usage_day = ?
                  AND client_key = ?
                  AND cache_hit = 0
                  AND inflight_join = 0
                  AND status IN (
                    'reserved',
                    'success',
                    'failed'
                  )
                """,
                (
                    usage_day,
                    client_key,
                ),
            ).fetchone()[0]
        )

        if (
            global_daily_call_cap > 0
            and global_count
            >= global_daily_call_cap
        ):
            conn.rollback()

            raise HTTPException(
                status_code=429,
                detail=(
                    "Sportabase beta capacity "
                    "has been reached for today. "
                    "Please try again after the "
                    "daily UTC reset."
                ),
            )

        if (
            client_daily_call_cap > 0
            and client_count
            >= client_daily_call_cap
        ):
            conn.rollback()

            raise HTTPException(
                status_code=429,
                detail=(
                    "This Sportabase beta "
                    "installation has reached "
                    "its daily analysis limit. "
                    "Please try again after the "
                    "daily UTC reset."
                ),
            )

        cursor = conn.execute(
            """
            INSERT INTO gemini_usage (
              created_at,
              usage_day,
              client_key,
              mode,
              model,
              status,
              cache_hit
            )
            VALUES (?, ?, ?, ?, ?, ?, 0)
            """,
            (
                created_at,
                usage_day,
                client_key,
                str(mode),
                str(model),
                "reserved",
            ),
        )

        usage_id = int(
            cursor.lastrowid
        )

        conn.commit()

        return usage_id

    except HTTPException:
        raise

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()


def usage_metadata_counts(
    response: Any,
) -> Dict[str, int]:
    metadata = getattr(
        response,
        "usage_metadata",
        None,
    )

    def read_value(
        *names: str,
    ) -> int:
        if metadata is None:
            return 0

        for name in names:
            if isinstance(metadata, dict):
                value = metadata.get(name)
            else:
                value = getattr(
                    metadata,
                    name,
                    None,
                )

            try:
                if value is not None:
                    return max(
                        0,
                        int(value),
                    )
            except Exception:
                continue

        return 0

    prompt_tokens = read_value(
        "prompt_token_count",
        "input_token_count",
    )

    output_tokens = read_value(
        "candidates_token_count",
        "output_token_count",
    )

    thought_tokens = read_value(
        "thoughts_token_count",
        "thought_token_count",
    )

    total_tokens = read_value(
        "total_token_count",
    )

    if total_tokens <= 0:
        total_tokens = (
            prompt_tokens
            + output_tokens
            + thought_tokens
        )

    return {
        "prompt_tokens": prompt_tokens,
        "output_tokens": output_tokens,
        "thought_tokens": thought_tokens,
        "total_tokens": total_tokens,
    }


def classify_gemini_failure(
    error: Exception,
) -> Dict[str, Any]:
    error_name = type(error).__name__

    raw_detail = re.sub(
        r"\s+",
        " ",
        str(error or ""),
    ).strip()

    detail = (
        f"{error_name}: {raw_detail}"
        if raw_detail
        else error_name
    )

    detail = detail[:500]
    lowered = detail.lower()

    status_code: Optional[int] = None

    for attribute_name in (
        "status_code",
        "status",
        "code",
    ):
        value = getattr(
            error,
            attribute_name,
            None,
        )

        if callable(value):
            try:
                value = value()
            except Exception:
                value = None

        enum_value = getattr(
            value,
            "value",
            None,
        )

        if enum_value is not None:
            value = enum_value

        match = re.search(
            r"\b([1-5]\d{2})\b",
            str(value or ""),
        )

        if match:
            status_code = int(
                match.group(1)
            )
            break

    if status_code is None:
        match = re.search(
            r"\b([1-5]\d{2})\b",
            detail,
        )

        if match:
            status_code = int(
                match.group(1)
            )

    if (
        status_code in {401, 403}
        or "unauthenticated" in lowered
        or "permission denied" in lowered
        or "invalid api key" in lowered
        or "api key not valid" in lowered
    ):
        failure_type = "authentication"

    elif (
        status_code == 429
        or "resource_exhausted" in lowered
        or "resource exhausted" in lowered
        or "rate limit" in lowered
        or "quota exceeded" in lowered
        or "too many requests" in lowered
    ):
        failure_type = "rate_limit"

    elif (
        status_code == 503
        or "service unavailable" in lowered
        or "temporarily unavailable" in lowered
        or "temporarily busy" in lowered
        or "model capacity" in lowered
        or "overloaded" in lowered
    ):
        failure_type = "provider_capacity"

    elif (
        isinstance(
            error,
            (
                TimeoutError,
                requests.Timeout,
            ),
        )
        or "timed out" in lowered
        or "timeout" in lowered
        or "deadline exceeded" in lowered
    ):
        failure_type = "timeout"

    elif (
        isinstance(
            error,
            (
                ConnectionError,
                requests.ConnectionError,
            ),
        )
        or "connection error" in lowered
        or "connection reset" in lowered
        or "name resolution" in lowered
        or "network is unreachable" in lowered
    ):
        failure_type = "network"

    elif (
        status_code in {400, 404, 409, 422}
        or "invalid argument" in lowered
        or "bad request" in lowered
        or "malformed" in lowered
    ):
        failure_type = "invalid_request"

    elif (
        status_code is not None
        and status_code >= 500
    ):
        failure_type = "provider_error"

    else:
        failure_type = "unknown"

    return {
        "failure_status_code": status_code,
        "failure_type": failure_type,
        "failure_detail": detail,
    }


def finish_gemini_call(
    usage_id: int,
    status: str,
    response: Any = None,
    latency_ms: int = 0,
    failure_status_code: Optional[int] = None,
    failure_type: str = "",
    failure_detail: str = "",
    *,
    usage_counter,
    connection_factory,
) -> Dict[str, int]:
    counts = usage_counter(
        response
    )

    conn = connection_factory()

    try:
        conn.execute(
            """
            UPDATE gemini_usage
            SET
              status = ?,
              prompt_tokens = ?,
              output_tokens = ?,
              thought_tokens = ?,
              total_tokens = ?,
              latency_ms = ?,
              failure_status_code = ?,
              failure_type = ?,
              failure_detail = ?
            WHERE id = ?
            """,
            (
                str(status),
                counts["prompt_tokens"],
                counts["output_tokens"],
                counts["thought_tokens"],
                counts["total_tokens"],
                max(
                    0,
                    int(latency_ms or 0),
                ),
                failure_status_code,
                str(failure_type or ""),
                str(failure_detail or "")[:500],
                int(usage_id),
            ),
        )

        conn.commit()

    finally:
        conn.close()

    return counts


def record_inflight_gemini_join(
    *,
    client_key: str,
    mode: str,
    model: str,
    succeeded: bool,
    connection_factory,
    usage_day_resolver,
) -> None:
    conn = connection_factory()

    try:
        conn.execute(
            """
            INSERT INTO gemini_usage (
              created_at,
              usage_day,
              client_key,
              mode,
              model,
              status,
              cache_hit,
              inflight_join
            )
            VALUES (
              ?, ?, ?, ?, ?, ?, 0, 1
            )
            """,
            (
                datetime.now(
                    timezone.utc
                ).isoformat(),
                usage_day_resolver(),
                str(client_key),
                str(mode),
                str(model),
                (
                    "inflight_join_success"
                    if succeeded
                    else "inflight_join_failed"
                ),
            ),
        )

        conn.commit()

    except Exception:
        conn.rollback()

    finally:
        conn.close()


def gemini_request_fingerprint(
    *,
    mode: str,
    model: str,
    contents: Any,
) -> str:
    try:
        serialized_contents = json.dumps(
            contents,
            ensure_ascii=False,
            sort_keys=True,
            default=str,
        )
    except Exception:
        serialized_contents = repr(contents)

    raw_key = "|".join(
        [
            str(mode or "").strip().lower(),
            str(model or "").strip().lower(),
            serialized_contents,
        ]
    )

    return hashlib.sha256(
        raw_key.encode("utf-8")
    ).hexdigest()


def generate_gemini_content(
    *,
    client: Any,
    client_key: str,
    mode: str,
    model: str,
    contents: Any,
    inflight_lock,
    inflight_calls,
    fingerprint_resolver,
    reserve_call,
    finish_call,
    classify_failure,
    record_join,
) -> Any:
    request_key = fingerprint_resolver(
        mode=mode,
        model=model,
        contents=contents,
    )

    with inflight_lock:
        shared_future = (
            inflight_calls.get(
                request_key
            )
        )

        if shared_future is None:
            shared_future = Future()

            inflight_calls[
                request_key
            ] = shared_future

            is_request_leader = True
        else:
            is_request_leader = False

    if not is_request_leader:
        try:
            shared_result = (
                shared_future.result()
            )

        except Exception:
            record_join(
                client_key=client_key,
                mode=mode,
                model=model,
                succeeded=False,
            )
            raise

        record_join(
            client_key=client_key,
            mode=mode,
            model=model,
            succeeded=True,
        )

        return shared_result

    usage_id: Optional[int] = None
    provider_started_at: Optional[
        float
    ] = None

    try:
        usage_id = reserve_call(
            client_key=client_key,
            mode=mode,
            model=model,
        )

        provider_started_at = (
            time.perf_counter()
        )

        response = (
            client.models.generate_content(
                model=model,
                contents=contents,
            )
        )

        success_latency_ms = max(
            0,
            int(
                round(
                    (
                        time.perf_counter()
                        - provider_started_at
                    )
                    * 1000
                )
            ),
        )

        finish_call(
            usage_id,
            "success",
            response,
            latency_ms=success_latency_ms,
        )

        shared_future.set_result(
            response
        )

        return response

    except Exception as error:
        if (
            usage_id is not None
            and provider_started_at
            is not None
        ):
            failure = (
                classify_failure(
                    error
                )
            )

            failure_latency_ms = max(
                0,
                int(
                    round(
                        (
                            time.perf_counter()
                            - provider_started_at
                        )
                        * 1000
                    )
                ),
            )

            finish_call(
                usage_id,
                "failed",
                latency_ms=(
                    failure_latency_ms
                ),
                failure_status_code=(
                    failure[
                        "failure_status_code"
                    ]
                ),
                failure_type=(
                    failure["failure_type"]
                ),
                failure_detail=(
                    failure["failure_detail"]
                ),
            )

        shared_future.set_exception(
            error
        )

        raise

    finally:
        with inflight_lock:
            current_future = (
                inflight_calls.get(
                    request_key
                )
            )

            if (
                current_future
                is shared_future
            ):
                inflight_calls.pop(
                    request_key,
                    None,
                )


def record_analysis_cache_hit(
    client_key: str,
    mode: str,
    *,
    connection_factory,
    usage_day_resolver,
) -> None:
    conn = connection_factory()

    try:
        conn.execute(
            """
            INSERT INTO gemini_usage (
              created_at,
              usage_day,
              client_key,
              mode,
              model,
              status,
              cache_hit
            )
            VALUES (?, ?, ?, ?, ?, ?, 1)
            """,
            (
                datetime.now(
                    timezone.utc
                ).isoformat(),
                usage_day_resolver(),
                client_key,
                str(mode),
                "cache",
                "cache_hit",
            ),
        )

        conn.commit()

    finally:
        conn.close()
