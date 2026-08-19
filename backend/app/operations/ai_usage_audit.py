from __future__ import annotations

import math
import sqlite3

from collections import Counter
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


AI_USAGE_AUDIT_VERSION = "sportabase-ai-usage-audit-v1"

TRUE_PROVIDER_STATUSES = (
    "reserved",
    "success",
    "failed",
    "expired",
)

COMPLETED_PROVIDER_STATUSES = (
    "success",
    "failed",
)


def _nonnegative_int(value: Any) -> int:
    try:
        return max(0, int(value or 0))
    except Exception:
        return 0


def _percent(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return round((numerator / denominator) * 100.0, 2)


def _percentile(values: Sequence[int], percentile: float) -> int:
    normalized = sorted(_nonnegative_int(value) for value in values)
    if not normalized:
        return 0

    position = max(
        0,
        min(
            len(normalized) - 1,
            int(math.ceil(float(percentile) * len(normalized)) - 1),
        ),
    )
    return int(normalized[position])


def _provider_attempt(row: Mapping[str, Any]) -> bool:
    return bool(
        _nonnegative_int(row["cache_hit"]) == 0
        and _nonnegative_int(row["inflight_join"]) == 0
        and str(row["status"]) in TRUE_PROVIDER_STATUSES
    )


def _completed_provider_call(row: Mapping[str, Any]) -> bool:
    return bool(
        _provider_attempt(row)
        and str(row["status"]) in COMPLETED_PROVIDER_STATUSES
    )


def _sum_tokens(
    rows: Iterable[Mapping[str, Any]],
    field: str,
) -> int:
    return sum(_nonnegative_int(row[field]) for row in rows)


def _summarize_rows(rows: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    normalized = tuple(rows)
    provider_rows = tuple(row for row in normalized if _provider_attempt(row))
    completed_rows = tuple(
        row for row in provider_rows if _completed_provider_call(row)
    )
    successful_rows = tuple(
        row for row in provider_rows if str(row["status"]) == "success"
    )
    failed_rows = tuple(
        row for row in provider_rows if str(row["status"]) == "failed"
    )

    status_counts = Counter(str(row["status"]) for row in normalized)
    failure_type_counts = Counter(
        str(row["failure_type"] or "unknown")
        for row in failed_rows
    )

    latencies = [
        _nonnegative_int(row["latency_ms"])
        for row in completed_rows
    ]

    prompt_tokens = _sum_tokens(provider_rows, "prompt_tokens")
    output_tokens = _sum_tokens(provider_rows, "output_tokens")
    thought_tokens = _sum_tokens(provider_rows, "thought_tokens")
    total_tokens = _sum_tokens(provider_rows, "total_tokens")
    estimated_prompt_tokens = _sum_tokens(
        provider_rows,
        "estimated_prompt_tokens",
    )

    successful_prompt_tokens = _sum_tokens(
        successful_rows,
        "prompt_tokens",
    )
    successful_output_tokens = _sum_tokens(
        successful_rows,
        "output_tokens",
    )
    successful_thought_tokens = _sum_tokens(
        successful_rows,
        "thought_tokens",
    )
    successful_total_tokens = _sum_tokens(
        successful_rows,
        "total_tokens",
    )

    reported_token_calls = sum(
        1
        for row in completed_rows
        if _nonnegative_int(row["total_tokens"]) > 0
    )

    return {
        "records": len(normalized),
        "provider_attempts": len(provider_rows),
        "completed_provider_calls": len(completed_rows),
        "successful_calls": len(successful_rows),
        "failed_calls": len(failed_rows),
        "reserved_calls": sum(
            1 for row in provider_rows if str(row["status"]) == "reserved"
        ),
        "expired_reservations": sum(
            1 for row in provider_rows if str(row["status"]) == "expired"
        ),
        "cache_hits": sum(
            1 for row in normalized if _nonnegative_int(row["cache_hit"]) == 1
        ),
        "inflight_joins": sum(
            1
            for row in normalized
            if _nonnegative_int(row["inflight_join"]) == 1
        ),
        "status_counts": dict(sorted(status_counts.items())),
        "failure_type_counts": dict(sorted(failure_type_counts.items())),
        "success_rate_percent": _percent(
            len(successful_rows),
            len(completed_rows),
        ),
        "failure_rate_percent": _percent(
            len(failed_rows),
            len(completed_rows),
        ),
        "reported_token_calls": reported_token_calls,
        "token_accounting_coverage_percent": _percent(
            reported_token_calls,
            len(completed_rows),
        ),
        "estimated_prompt_tokens": estimated_prompt_tokens,
        "prompt_tokens": prompt_tokens,
        "output_tokens": output_tokens,
        "thought_tokens": thought_tokens,
        "billable_output_tokens": output_tokens + thought_tokens,
        "total_tokens": total_tokens,
        "successful_prompt_tokens": successful_prompt_tokens,
        "successful_output_tokens": successful_output_tokens,
        "successful_thought_tokens": successful_thought_tokens,
        "successful_total_tokens": successful_total_tokens,
        "average_total_tokens_per_provider_attempt": round(
            total_tokens / len(provider_rows),
            2,
        ) if provider_rows else 0.0,
        "average_total_tokens_per_success": round(
            successful_total_tokens / len(successful_rows),
            2,
        ) if successful_rows else 0.0,
        "latency": {
            "average_ms": round(
                sum(latencies) / len(latencies),
                2,
            ) if latencies else 0.0,
            "fastest_ms": min(latencies) if latencies else 0,
            "median_ms": _percentile(latencies, 0.50),
            "p95_ms": _percentile(latencies, 0.95),
            "slowest_ms": max(latencies) if latencies else 0,
        },
    }


def _group_rows(
    rows: Sequence[Mapping[str, Any]],
    key: str,
) -> list[dict[str, Any]]:
    grouped: dict[str, list[Mapping[str, Any]]] = {}

    for row in rows:
        value = str(row[key] or "unknown")
        grouped.setdefault(value, []).append(row)

    return [
        {
            key: value,
            **_summarize_rows(group_rows),
        }
        for value, group_rows in sorted(grouped.items())
    ]


def build_provider_day_ai_usage_audit(
    *,
    db_path: str | Path,
    provider_day: str,
) -> dict[str, Any]:
    normalized_day = str(provider_day or "").strip()
    if not normalized_day:
        raise ValueError("provider_day is required")

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row

    try:
        rows = conn.execute(
            """
            SELECT
              id,
              created_at,
              usage_day,
              provider_day,
              client_key,
              mode,
              model,
              status,
              estimated_prompt_tokens,
              prompt_tokens,
              output_tokens,
              thought_tokens,
              total_tokens,
              cache_hit,
              inflight_join,
              latency_ms,
              failure_status_code,
              failure_type,
              failure_detail
            FROM gemini_usage
            WHERE provider_day = ?
            ORDER BY id ASC
            """,
            (normalized_day,),
        ).fetchall()
    finally:
        conn.close()

    row_dicts = tuple(dict(row) for row in rows)
    provider_rows = tuple(
        row for row in row_dicts if _provider_attempt(row)
    )

    failures = [
        {
            "id": _nonnegative_int(row["id"]),
            "created_at": str(row["created_at"]),
            "client_key": str(row["client_key"]),
            "mode": str(row["mode"]),
            "model": str(row["model"]),
            "status_code": (
                None
                if row["failure_status_code"] is None
                else _nonnegative_int(row["failure_status_code"])
            ),
            "failure_type": str(row["failure_type"] or "unknown"),
            "failure_detail": str(row["failure_detail"] or ""),
            "latency_ms": _nonnegative_int(row["latency_ms"]),
        }
        for row in provider_rows
        if str(row["status"]) == "failed"
    ]

    provider_calls = [
        {
            "id": _nonnegative_int(row["id"]),
            "created_at": str(row["created_at"]),
            "client_key": str(row["client_key"]),
            "mode": str(row["mode"]),
            "model": str(row["model"]),
            "status": str(row["status"]),
            "estimated_prompt_tokens": _nonnegative_int(
                row["estimated_prompt_tokens"]
            ),
            "prompt_tokens": _nonnegative_int(row["prompt_tokens"]),
            "output_tokens": _nonnegative_int(row["output_tokens"]),
            "thought_tokens": _nonnegative_int(row["thought_tokens"]),
            "total_tokens": _nonnegative_int(row["total_tokens"]),
            "latency_ms": _nonnegative_int(row["latency_ms"]),
            "failure_status_code": (
                None
                if row["failure_status_code"] is None
                else _nonnegative_int(row["failure_status_code"])
            ),
            "failure_type": str(row["failure_type"] or ""),
        }
        for row in provider_rows
    ]

    return {
        "version": AI_USAGE_AUDIT_VERSION,
        "provider_day": normalized_day,
        "summary": _summarize_rows(row_dicts),
        "by_model": _group_rows(row_dicts, "model"),
        "by_mode": _group_rows(row_dicts, "mode"),
        "by_client": _group_rows(row_dicts, "client_key"),
        "failures": failures,
        "provider_calls": provider_calls,
    }


__all__ = [
    "AI_USAGE_AUDIT_VERSION",
    "TRUE_PROVIDER_STATUSES",
    "COMPLETED_PROVIDER_STATUSES",
    "build_provider_day_ai_usage_audit",
]
