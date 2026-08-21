from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Callable
from urllib.parse import urlparse

import requests


CONTROL_ROOM_UPSTREAM_USAGE_VERSION = (
    "sportabase-control-room-ai-usage-upstream-v1"
)


class ControlRoomUsageBridgeMisconfigured(RuntimeError):
    pass


class ControlRoomUsageBridgeUnavailable(RuntimeError):
    pass


def _nonnegative_int(value: Any) -> int:
    try:
        return max(0, int(value or 0))
    except Exception:
        return 0


def _float_value(value: Any) -> float:
    try:
        return float(value or 0.0)
    except Exception:
        return 0.0


def _normalized_origin(value: str) -> str:
    raw = str(value or "").strip()
    if not raw:
        raise ControlRoomUsageBridgeMisconfigured(
            "Control Room upstream API origin is not configured."
        )

    parsed = urlparse(raw)
    if (
        parsed.scheme.casefold() != "https"
        or not parsed.netloc
        or parsed.username is not None
        or parsed.password is not None
        or parsed.params
        or parsed.query
        or parsed.fragment
        or parsed.path not in {"", "/"}
    ):
        raise ControlRoomUsageBridgeMisconfigured(
            "Control Room upstream API origin is invalid."
        )

    return f"https://{parsed.netloc}"


def _validated_admin_key(value: str) -> str:
    key = str(value or "").strip()
    if len(key) < 32:
        raise ControlRoomUsageBridgeMisconfigured(
            "Control Room upstream admin credential is not configured securely."
        )
    return key


def _validated_days(value: int) -> int:
    try:
        days = int(value)
    except Exception as error:
        raise ValueError("days must be an integer") from error

    if days < 1 or days > 30:
        raise ValueError("days must be between 1 and 30")
    return days


def _validated_timeout(value: int | float) -> float:
    try:
        timeout = float(value)
    except Exception as error:
        raise ControlRoomUsageBridgeMisconfigured(
            "Control Room upstream request timeout is invalid."
        ) from error

    if timeout <= 0.0 or timeout > 60.0:
        raise ControlRoomUsageBridgeMisconfigured(
            "Control Room upstream request timeout is invalid."
        )
    return timeout


def _mapping(value: Any) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    return {}


def _curated_breakdown(rows: Any) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    if not isinstance(rows, list):
        return output

    for raw_row in rows:
        row = _mapping(raw_row)
        output.append(
            {
                "mode": str(row.get("mode") or "unknown"),
                "model": str(row.get("model") or "unknown"),
                "status": str(row.get("status") or "unknown"),
                "cache_hit": bool(row.get("cache_hit", False)),
                "inflight_join": bool(row.get("inflight_join", False)),
                "request_count": _nonnegative_int(row.get("request_count")),
                "prompt_tokens": _nonnegative_int(row.get("prompt_tokens")),
                "output_tokens": _nonnegative_int(row.get("output_tokens")),
                "thought_tokens": _nonnegative_int(row.get("thought_tokens")),
                "total_tokens": _nonnegative_int(row.get("total_tokens")),
            }
        )
    return output


def _curated_mode_metrics(rows: Any) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    if not isinstance(rows, list):
        return output

    allowed = (
        "total_records",
        "cache_hits",
        "inflight_joins",
        "gemini_attempts",
        "successful_calls",
        "failed_calls",
        "reserved_calls",
        "expired_reservations",
        "prompt_tokens",
        "output_tokens",
        "thought_tokens",
        "total_tokens",
        "success_rate_percent",
        "failure_rate_percent",
        "cache_hit_rate_percent",
        "provider_avoidance_rate_percent",
        "average_total_tokens_per_attempt",
        "average_total_tokens_per_success",
        "estimated_paid_cost_usd",
        "provider_calls_avoided",
    )

    for raw_row in rows:
        row = _mapping(raw_row)
        item: dict[str, Any] = {
            "mode": str(row.get("mode") or "unknown")
        }
        for key in allowed:
            value = row.get(key)
            if key.endswith("_percent") or key.startswith("average_") or key.endswith("_usd"):
                item[key] = _float_value(value)
            else:
                item[key] = _nonnegative_int(value)
        output.append(item)
    return output


def _curated_failures(rows: Any) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    if not isinstance(rows, list):
        return output

    for raw_row in rows:
        row = _mapping(raw_row)
        output.append(
            {
                "mode": str(row.get("mode") or "unknown"),
                "status_code": _nonnegative_int(
                    row.get("failure_status_code")
                ),
                "failure_type": str(
                    row.get("failure_type") or "unknown"
                ),
                "count": _nonnegative_int(row.get("failure_count")),
            }
        )
    return output


def _curated_recent_days(rows: Any) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    if not isinstance(rows, list):
        return output

    for raw_row in rows[:30]:
        row = _mapping(raw_row)
        output.append(
            {
                "usage_day": str(row.get("usage_day") or ""),
                "total_records": _nonnegative_int(row.get("total_records")),
                "unique_clients": _nonnegative_int(row.get("unique_clients")),
                "provider_attempts": _nonnegative_int(row.get("gemini_attempts")),
                "successful_calls": _nonnegative_int(row.get("successful_calls")),
                "failed_calls": _nonnegative_int(row.get("failed_calls")),
                "cache_hits": _nonnegative_int(row.get("cache_hits")),
                "inflight_joins": _nonnegative_int(row.get("inflight_joins")),
                "total_tokens": _nonnegative_int(row.get("total_tokens")),
            }
        )
    return output


def curate_upstream_usage_summary(payload: Mapping[str, Any]) -> dict[str, Any]:
    source = dict(payload)
    today = _mapping(source.get("today"))
    today_metrics = _mapping(source.get("today_metrics"))
    limits = _mapping(source.get("limits"))
    rolling = _mapping(source.get("rolling_window"))

    provider_attempts = _nonnegative_int(today.get("gemini_attempts"))
    global_cap = _nonnegative_int(limits.get("global_daily_call_cap"))

    raw_remaining = limits.get("global_calls_remaining")
    if raw_remaining is None:
        remaining = (
            max(0, global_cap - provider_attempts)
            if global_cap > 0
            else None
        )
    else:
        remaining = _nonnegative_int(raw_remaining)

    capacity_used_percent = (
        round(provider_attempts / global_cap * 100.0, 2)
        if global_cap > 0
        else None
    )

    summary = {
        "records": _nonnegative_int(today.get("total_records")),
        "unique_clients": _nonnegative_int(today.get("unique_clients")),
        "provider_attempts": provider_attempts,
        "successful_calls": _nonnegative_int(today.get("successful_calls")),
        "failed_calls": _nonnegative_int(today.get("failed_calls")),
        "reserved_calls": _nonnegative_int(today.get("reserved_calls")),
        "expired_reservations": _nonnegative_int(
            today.get("expired_reservations")
        ),
        "cache_hits": _nonnegative_int(today.get("cache_hits")),
        "inflight_joins": _nonnegative_int(today.get("inflight_joins")),
        "prompt_tokens": _nonnegative_int(today.get("prompt_tokens")),
        "output_tokens": _nonnegative_int(today.get("output_tokens")),
        "thought_tokens": _nonnegative_int(today.get("thought_tokens")),
        "total_tokens": _nonnegative_int(today.get("total_tokens")),
        "average_latency_ms": _nonnegative_int(
            today.get("average_latency_ms")
        ),
        "fastest_latency_ms": _nonnegative_int(
            today.get("fastest_latency_ms")
        ),
        "slowest_latency_ms": _nonnegative_int(
            today.get("slowest_latency_ms")
        ),
    }

    metrics = {
        "success_rate_percent": _float_value(
            today_metrics.get("success_rate_percent")
        ),
        "failure_rate_percent": _float_value(
            today_metrics.get("failure_rate_percent")
        ),
        "cache_hit_rate_percent": _float_value(
            today_metrics.get("cache_hit_rate_percent")
        ),
        "provider_avoidance_rate_percent": _float_value(
            today_metrics.get("provider_avoidance_rate_percent")
        ),
        "average_total_tokens_per_success": _float_value(
            today_metrics.get("average_total_tokens_per_success")
        ),
        "estimated_paid_cost_usd": _float_value(
            today_metrics.get("estimated_paid_cost_usd")
        ),
    }

    return {
        "version": CONTROL_ROOM_UPSTREAM_USAGE_VERSION,
        "source": "sportabase-api",
        "upstream_generated_at": str(source.get("generated_at") or ""),
        "usage_day_utc": str(source.get("usage_day_utc") or ""),
        "capacity": {
            "global_daily_call_cap": global_cap,
            "provider_attempts": provider_attempts,
            "remaining_calls": remaining,
            "capacity_used_percent": capacity_used_percent,
            "exhausted": bool(global_cap > 0 and remaining == 0),
        },
        "summary": summary,
        "metrics": metrics,
        "today_breakdown": _curated_breakdown(
            source.get("today_breakdown")
        ),
        "mode_metrics": _curated_mode_metrics(
            source.get("mode_metrics")
        ),
        "failure_breakdown": _curated_failures(
            source.get("failure_breakdown")
        ),
        "recent_days": _curated_recent_days(
            source.get("recent_days")
        ),
        "window": {
            "requested_days": _nonnegative_int(
                rolling.get("requested_days")
            ),
            "start_day_utc": str(rolling.get("start_day_utc") or ""),
            "end_day_utc": str(rolling.get("end_day_utc") or ""),
            "days_with_activity": _nonnegative_int(
                rolling.get("days_with_activity")
            ),
        },
    }


def fetch_control_room_upstream_usage(
    *,
    api_origin: str,
    admin_api_key: str,
    days: int = 7,
    timeout_seconds: int | float = 10,
    request_get: Callable[..., Any] = requests.get,
) -> dict[str, Any]:
    origin = _normalized_origin(api_origin)
    key = _validated_admin_key(admin_api_key)
    normalized_days = _validated_days(days)
    timeout = _validated_timeout(timeout_seconds)

    try:
        response = request_get(
            origin + "/admin/usage/summary",
            headers={
                "Accept": "application/json",
                "User-Agent": "Sportabase-Control-Room/1",
                "x-sportabase-admin-key": key,
            },
            params={"days": normalized_days},
            timeout=timeout,
            allow_redirects=False,
        )
    except requests.RequestException as error:
        raise ControlRoomUsageBridgeUnavailable(
            "Control Room upstream usage service is unavailable."
        ) from error
    except Exception as error:
        raise ControlRoomUsageBridgeUnavailable(
            "Control Room upstream usage service is unavailable."
        ) from error

    status_code = _nonnegative_int(getattr(response, "status_code", 0))
    if status_code != 200:
        raise ControlRoomUsageBridgeUnavailable(
            "Control Room upstream usage service rejected the request."
        )

    try:
        payload = response.json()
    except Exception as error:
        raise ControlRoomUsageBridgeUnavailable(
            "Control Room upstream usage response is invalid."
        ) from error

    if not isinstance(payload, Mapping):
        raise ControlRoomUsageBridgeUnavailable(
            "Control Room upstream usage response is invalid."
        )

    return curate_upstream_usage_summary(payload)


__all__ = [
    "CONTROL_ROOM_UPSTREAM_USAGE_VERSION",
    "ControlRoomUsageBridgeMisconfigured",
    "ControlRoomUsageBridgeUnavailable",
    "curate_upstream_usage_summary",
    "fetch_control_room_upstream_usage",
]
