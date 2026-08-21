from __future__ import annotations

from collections.abc import Mapping
from typing import Any


CONTROL_ROOM_PIPELINE_VERSION = (
    "sportabase-control-room-pipeline-v1"
)


def _mapping(value: Any) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    return {}


def _rows(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [
        dict(row)
        for row in value
        if isinstance(row, Mapping)
    ]


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


def _mode_family(mode: str) -> str:
    normalized = str(mode or "").strip().casefold()
    if normalized == "article" or normalized.startswith("article_"):
        return "article"
    if normalized == "video" or normalized.startswith("video_"):
        return "video"
    return "other"


def _curated_mode_rows(value: Any) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []

    for row in _rows(value):
        output.append(
            {
                "mode": str(row.get("mode") or "unknown"),
                "total_records": _nonnegative_int(
                    row.get("total_records")
                ),
                "provider_attempts": _nonnegative_int(
                    row.get("gemini_attempts")
                ),
                "successful_calls": _nonnegative_int(
                    row.get("successful_calls")
                ),
                "failed_calls": _nonnegative_int(
                    row.get("failed_calls")
                ),
                "cache_hits": _nonnegative_int(
                    row.get("cache_hits")
                ),
                "inflight_joins": _nonnegative_int(
                    row.get("inflight_joins")
                ),
                "success_rate_percent": _float_value(
                    row.get("success_rate_percent")
                ),
                "failure_rate_percent": _float_value(
                    row.get("failure_rate_percent")
                ),
                "cache_hit_rate_percent": _float_value(
                    row.get("cache_hit_rate_percent")
                ),
            }
        )

    return output


def _curated_recent_days(value: Any) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []

    for row in _rows(value)[:30]:
        output.append(
            {
                "usage_day": str(row.get("usage_day") or ""),
                "total_records": _nonnegative_int(
                    row.get("total_records")
                ),
                "provider_attempts": _nonnegative_int(
                    row.get("provider_attempts")
                ),
                "successful_calls": _nonnegative_int(
                    row.get("successful_calls")
                ),
                "failed_calls": _nonnegative_int(
                    row.get("failed_calls")
                ),
                "cache_hits": _nonnegative_int(
                    row.get("cache_hits")
                ),
                "inflight_joins": _nonnegative_int(
                    row.get("inflight_joins")
                ),
            }
        )

    return output


def build_control_room_pipeline_snapshot(
    upstream_usage: Mapping[str, Any],
) -> dict[str, Any]:
    if not isinstance(upstream_usage, Mapping):
        raise ValueError("upstream_usage must be an object")

    usage = dict(upstream_usage)
    summary = _mapping(usage.get("summary"))
    metrics = _mapping(usage.get("metrics"))
    window = _mapping(usage.get("window"))
    by_mode = _curated_mode_rows(
        usage.get("mode_metrics")
    )

    total_records = _nonnegative_int(
        summary.get("records")
    )
    failed_calls = _nonnegative_int(
        summary.get("failed_calls")
    )

    article_records = sum(
        row["total_records"]
        for row in by_mode
        if _mode_family(row["mode"]) == "article"
    )
    video_records = sum(
        row["total_records"]
        for row in by_mode
        if _mode_family(row["mode"]) == "video"
    )
    categorized = article_records + video_records
    other_records = max(
        0,
        total_records - categorized,
    )

    return {
        "version": CONTROL_ROOM_PIPELINE_VERSION,
        "source": str(usage.get("source") or "sportabase-api"),
        "upstream_generated_at": str(
            usage.get("upstream_generated_at") or ""
        ),
        "usage_day_utc": str(usage.get("usage_day_utc") or ""),
        "state": {
            "activity": (
                "active"
                if total_records > 0
                else "idle"
            ),
            "outcomes": (
                "failures_observed"
                if failed_calls > 0
                else "no_failures_observed"
            ),
            "coverage": "partial",
        },
        "today": {
            "total_records": total_records,
            "article_records": article_records,
            "video_records": video_records,
            "other_records": other_records,
            "provider_attempts": _nonnegative_int(
                summary.get("provider_attempts")
            ),
            "successful_calls": _nonnegative_int(
                summary.get("successful_calls")
            ),
            "failed_calls": failed_calls,
            "cache_hits": _nonnegative_int(
                summary.get("cache_hits")
            ),
            "inflight_joins": _nonnegative_int(
                summary.get("inflight_joins")
            ),
            "average_latency_ms": _nonnegative_int(
                summary.get("average_latency_ms")
            ),
            "success_rate_percent": _float_value(
                metrics.get("success_rate_percent")
            ),
            "failure_rate_percent": _float_value(
                metrics.get("failure_rate_percent")
            ),
            "cache_hit_rate_percent": _float_value(
                metrics.get("cache_hit_rate_percent")
            ),
        },
        "by_mode": by_mode,
        "recent_days": _curated_recent_days(
            usage.get("recent_days")
        ),
        "window": {
            "requested_days": _nonnegative_int(
                window.get("requested_days")
            ),
            "start_day_utc": str(
                window.get("start_day_utc") or ""
            ),
            "end_day_utc": str(
                window.get("end_day_utc") or ""
            ),
            "days_with_activity": _nonnegative_int(
                window.get("days_with_activity")
            ),
        },
        "instrumentation": {
            "analysis_activity": "live",
            "cache_activity": "live",
            "provider_outcomes": "live",
            "mode_breakdown": "live",
            "browser_capture_ingestion": (
                "not_available_from_upstream_contract"
            ),
            "extraction_stage": (
                "not_available_from_upstream_contract"
            ),
            "automation_jobs": (
                "not_available_from_upstream_contract"
            ),
        },
    }


__all__ = [
    "CONTROL_ROOM_PIPELINE_VERSION",
    "build_control_room_pipeline_snapshot",
]
