from __future__ import annotations

from pathlib import Path
from typing import Any

from app.operations.ai_usage_audit import (
    build_provider_day_ai_usage_audit,
)


CONTROL_ROOM_AI_USAGE_VERSION = (
    "sportabase-control-room-ai-usage-v1"
)


def _nonnegative_int(value: Any) -> int:
    try:
        return max(0, int(value or 0))
    except Exception:
        return 0


def _curated_failure(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": _nonnegative_int(row.get("id")),
        "created_at": str(row.get("created_at") or ""),
        "mode": str(row.get("mode") or ""),
        "model": str(row.get("model") or ""),
        "status_code": row.get("status_code"),
        "failure_type": str(row.get("failure_type") or "unknown"),
        "latency_ms": _nonnegative_int(row.get("latency_ms")),
    }


def _curated_provider_call(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": _nonnegative_int(row.get("id")),
        "created_at": str(row.get("created_at") or ""),
        "mode": str(row.get("mode") or ""),
        "model": str(row.get("model") or ""),
        "status": str(row.get("status") or ""),
        "prompt_tokens": _nonnegative_int(row.get("prompt_tokens")),
        "output_tokens": _nonnegative_int(row.get("output_tokens")),
        "thought_tokens": _nonnegative_int(row.get("thought_tokens")),
        "total_tokens": _nonnegative_int(row.get("total_tokens")),
        "latency_ms": _nonnegative_int(row.get("latency_ms")),
        "failure_status_code": row.get("failure_status_code"),
        "failure_type": str(row.get("failure_type") or ""),
    }


def build_control_room_ai_usage_snapshot(
    *,
    db_path: str | Path,
    provider_day: str,
    global_daily_call_cap: int,
) -> dict[str, Any]:
    normalized_day = str(provider_day or "").strip()
    if not normalized_day:
        raise ValueError("provider_day is required")

    audit = build_provider_day_ai_usage_audit(
        db_path=db_path,
        provider_day=normalized_day,
    )

    summary = dict(audit.get("summary") or {})
    provider_attempts = _nonnegative_int(
        summary.get("provider_attempts")
    )
    global_cap = max(1, _nonnegative_int(global_daily_call_cap))
    remaining_calls = max(0, global_cap - provider_attempts)

    capacity_used_percent = round(
        (provider_attempts / global_cap) * 100.0,
        2,
    )

    failures = [
        _curated_failure(dict(row))
        for row in list(audit.get("failures") or [])[-10:]
    ]
    provider_calls = [
        _curated_provider_call(dict(row))
        for row in list(audit.get("provider_calls") or [])[-20:]
    ]

    return {
        "version": CONTROL_ROOM_AI_USAGE_VERSION,
        "provider_day": normalized_day,
        "capacity": {
            "global_daily_call_cap": global_cap,
            "provider_attempts": provider_attempts,
            "remaining_calls": remaining_calls,
            "capacity_used_percent": capacity_used_percent,
            "exhausted": provider_attempts >= global_cap,
        },
        "summary": summary,
        "by_model": list(audit.get("by_model") or []),
        "by_mode": list(audit.get("by_mode") or []),
        "recent_failures": failures,
        "recent_provider_calls": provider_calls,
    }


__all__ = [
    "CONTROL_ROOM_AI_USAGE_VERSION",
    "build_control_room_ai_usage_snapshot",
]
