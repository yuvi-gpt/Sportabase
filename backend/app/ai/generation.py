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

from app.services.gemini_capacity import (
    GeminiCapacityPacingRequired,
    capacity_policy_for_model,
    estimate_prompt_tokens,
    normalized_model_name,
    provider_usage_day,
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

    cutoff = (
        current_time
        - timedelta(
            seconds=(
                reservation_timeout_seconds
            )
        )
    ).isoformat()

    query = """
        UPDATE gemini_usage
        SET
          status = 'expired',
          failure_type = 'reservation_timeout',
          failure_detail = (
            'Gemini reservation expired before completion.'
          )
        WHERE status = 'reserved'
          AND created_at < ?
          AND cache_hit = 0
          AND inflight_join = 0
    """
    params = [cutoff]

    if usage_day:
        query += " AND usage_day = ?"
        params.append(str(usage_day))

    cursor = conn.execute(
        query,
        tuple(params),
    )

    return max(
        0,
        int(cursor.rowcount or 0),
    )


def _capacity_timestamp(
    value: Any,
) -> datetime:
    try:
        parsed = datetime.fromisoformat(
            str(value or "")
        )
    except (TypeError, ValueError) as error:
        raise RuntimeError(
            "Invalid Gemini capacity timestamp."
        ) from error

    if parsed.tzinfo is None:
        parsed = parsed.replace(
            tzinfo=timezone.utc,
        )

    return parsed.astimezone(
        timezone.utc
    )


def _capacity_pacing_wait(
    *,
    rows,
    current_time: datetime,
    estimated_prompt_tokens: int,
    dispatch_rpm: int,
    usable_tpm: int,
    minimum_interval_seconds: float,
) -> tuple[float, str]:
    if not rows:
        return (0.0, "")

    parsed = [
        (
            _capacity_timestamp(
                row[0]
            ),
            max(
                0,
                int(row[1] or 0),
            ),
        )
        for row in rows
    ]

    wait_seconds = 0.0
    reason = ""

    latest_time = parsed[-1][0]
    since_latest = max(
        0.0,
        (
            current_time
            - latest_time
        ).total_seconds(),
    )
    spacing_wait = (
        float(minimum_interval_seconds)
        - since_latest
    )

    if spacing_wait > wait_seconds:
        wait_seconds = spacing_wait
        reason = "rpm"

    if len(parsed) >= int(dispatch_rpm):
        oldest_in_limit = parsed[
            -int(dispatch_rpm)
        ][0]
        age = max(
            0.0,
            (
                current_time
                - oldest_in_limit
            ).total_seconds(),
        )
        rolling_wait = 60.0 - age

        if rolling_wait > wait_seconds:
            wait_seconds = rolling_wait
            reason = "rpm"

    current_tokens = sum(
        tokens
        for _, tokens in parsed
    )

    if (
        current_tokens
        + int(estimated_prompt_tokens)
        > int(usable_tpm)
    ):
        remaining = current_tokens

        for timestamp, tokens in parsed:
            remaining -= tokens

            if (
                remaining
                + int(estimated_prompt_tokens)
                <= int(usable_tpm)
            ):
                age = max(
                    0.0,
                    (
                        current_time
                        - timestamp
                    ).total_seconds(),
                )
                token_wait = 60.0 - age

                if token_wait > wait_seconds:
                    wait_seconds = token_wait
                    reason = "tpm"
                break

    if wait_seconds <= 0.0:
        return (0.0, "")

    return (
        max(
            0.05,
            wait_seconds + 0.01,
        ),
        reason or "capacity",
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
    estimated_prompt_tokens: int = 0,
    now: Optional[datetime] = None,
) -> int:
    current_time = (
        now
        if now is not None
        else datetime.now(timezone.utc)
    )

    if current_time.tzinfo is None:
        current_time = current_time.replace(
            tzinfo=timezone.utc,
        )

    current_time = current_time.astimezone(
        timezone.utc
    )

    usage_day = usage_day_resolver()
    provider_day = provider_usage_day(
        current_time
    )
    normalized_model = normalized_model_name(
        model
    )
    policy = capacity_policy_for_model(
        normalized_model
    )

    estimate = max(
        0,
        int(
            estimated_prompt_tokens
            or 0
        ),
    )

    if (
        estimate
        > policy.max_estimated_input_tokens
    ):
        raise HTTPException(
            status_code=429,
            detail=(
                "This AI request is too large "
                "for the current Sportabase "
                "Gemini capacity budget."
            ),
        )

    created_at = current_time.isoformat()
    minute_cutoff = (
        current_time
        - timedelta(seconds=60)
    ).isoformat()

    conn = connection_factory()

    try:
        conn.execute("BEGIN IMMEDIATE")

        expire_reservations(
            conn,
            now=current_time,
        )

        true_provider_statuses = (
            "reserved",
            "success",
            "failed",
            "expired",
        )

        placeholders = ",".join(
            "?"
            for _ in true_provider_statuses
        )

        global_count = int(
            conn.execute(
                f"""
                SELECT COUNT(*)
                FROM gemini_usage
                WHERE provider_day = ?
                  AND cache_hit = 0
                  AND inflight_join = 0
                  AND status IN ({placeholders})
                """,
                (
                    provider_day,
                    *true_provider_statuses,
                ),
            ).fetchone()[0]
        )

        client_count = int(
            conn.execute(
                f"""
                SELECT COUNT(*)
                FROM gemini_usage
                WHERE provider_day = ?
                  AND client_key = ?
                  AND cache_hit = 0
                  AND inflight_join = 0
                  AND status IN ({placeholders})
                """,
                (
                    provider_day,
                    client_key,
                    *true_provider_statuses,
                ),
            ).fetchone()[0]
        )

        model_daily_count = int(
            conn.execute(
                f"""
                SELECT COUNT(*)
                FROM gemini_usage
                WHERE provider_day = ?
                  AND model = ?
                  AND cache_hit = 0
                  AND inflight_join = 0
                  AND status IN ({placeholders})
                """,
                (
                    provider_day,
                    normalized_model,
                    *true_provider_statuses,
                ),
            ).fetchone()[0]
        )

        if (
            model_daily_count
            >= policy.usable_rpd
        ):
            conn.rollback()

            raise HTTPException(
                status_code=429,
                detail=(
                    "Sportabase is preserving "
                    "the Gemini daily provider "
                    "reserve for this model. "
                    "Please try again after the "
                    "provider's Pacific-day reset."
                ),
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
                    "Sportabase beta AI capacity "
                    "has been reached for the "
                    "current provider day."
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
                    "its fair-share AI capacity "
                    "for the current provider day."
                ),
            )

        recent_rows = conn.execute(
            f"""
            SELECT
              created_at,
              CASE
                WHEN prompt_tokens > 0
                  THEN prompt_tokens
                ELSE estimated_prompt_tokens
              END AS input_tokens
            FROM gemini_usage
            WHERE model = ?
              AND created_at >= ?
              AND cache_hit = 0
              AND inflight_join = 0
              AND status IN ({placeholders})
            ORDER BY created_at ASC, id ASC
            """,
            (
                normalized_model,
                minute_cutoff,
                *true_provider_statuses,
            ),
        ).fetchall()

        wait_seconds, wait_reason = (
            _capacity_pacing_wait(
                rows=recent_rows,
                current_time=current_time,
                estimated_prompt_tokens=estimate,
                dispatch_rpm=(
                    policy.dispatch_rpm
                ),
                usable_tpm=(
                    policy.usable_tpm
                ),
                minimum_interval_seconds=(
                    policy
                    .minimum_dispatch_interval_seconds
                ),
            )
        )

        if wait_seconds > 0.0:
            conn.rollback()

            raise GeminiCapacityPacingRequired(
                wait_seconds=wait_seconds,
                reason=wait_reason,
            )

        cursor = conn.execute(
            """
            INSERT INTO gemini_usage (
              created_at,
              usage_day,
              provider_day,
              client_key,
              mode,
              model,
              status,
              estimated_prompt_tokens,
              cache_hit
            )
            VALUES (
              ?, ?, ?, ?, ?, ?, ?, ?, 0
            )
            """,
            (
                created_at,
                usage_day,
                provider_day,
                client_key,
                str(mode),
                normalized_model,
                "reserved",
                estimate,
            ),
        )

        usage_id = int(
            cursor.lastrowid
        )

        conn.commit()

        return usage_id

    except (
        HTTPException,
        GeminiCapacityPacingRequired,
    ):
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
    sleep_func=time.sleep,
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
        estimated_prompt_tokens = (
            estimate_prompt_tokens(
                contents
            )
        )
        policy = capacity_policy_for_model(
            model
        )
        total_wait = 0.0

        while True:
            try:
                usage_id = reserve_call(
                    client_key=client_key,
                    mode=mode,
                    model=model,
                    estimated_prompt_tokens=(
                        estimated_prompt_tokens
                    ),
                )
                break

            except GeminiCapacityPacingRequired as pacing:
                wait_seconds = max(
                    0.0,
                    float(
                        pacing.wait_seconds
                    ),
                )

                if (
                    total_wait
                    + wait_seconds
                    > policy.max_pacing_wait_seconds
                ):
                    raise HTTPException(
                        status_code=429,
                        detail=(
                            "Sportabase is pacing "
                            "Gemini traffic to stay "
                            "inside provider RPM/TPM "
                            "capacity. Please retry "
                            "shortly."
                        ),
                    )

                sleep_func(
                    wait_seconds
                )
                total_wait += wait_seconds

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
