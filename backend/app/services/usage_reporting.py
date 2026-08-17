from datetime import (
    datetime,
    timedelta,
    timezone,
)

from typing import (
    Any,
    Dict,
    List,
)

from app.services.gemini_capacity import (
    capacity_policy_for_model,
    provider_usage_day,
)


def usage_derived_metrics(
    summary: Dict[str, Any],
    *,
    input_cost_per_million_usd: float,
    output_cost_per_million_usd: float,
    global_daily_call_cap: int,
) -> Dict[str, Any]:
    total_records = max(
        0,
        int(summary.get("total_records", 0) or 0),
    )
    cache_hits = max(
        0,
        int(summary.get("cache_hits", 0) or 0),
    )
    inflight_joins = max(
        0,
        int(summary.get("inflight_joins", 0) or 0),
    )
    gemini_attempts = max(
        0,
        int(summary.get("gemini_attempts", 0) or 0),
    )
    successful_calls = max(
        0,
        int(summary.get("successful_calls", 0) or 0),
    )
    failed_calls = max(
        0,
        int(summary.get("failed_calls", 0) or 0),
    )
    expired_reservations = max(
        0,
        int(
            summary.get(
                "expired_reservations",
                0,
            )
            or 0
        ),
    )
    prompt_tokens = max(
        0,
        int(summary.get("prompt_tokens", 0) or 0),
    )
    output_tokens = max(
        0,
        int(summary.get("output_tokens", 0) or 0),
    )
    thought_tokens = max(
        0,
        int(summary.get("thought_tokens", 0) or 0),
    )
    total_tokens = max(
        0,
        int(summary.get("total_tokens", 0) or 0),
    )

    completed_calls = (
        successful_calls + failed_calls
    )

    cache_hit_rate = (
        cache_hits / total_records
        if total_records > 0
        else 0.0
    )

    deduplication_rate = (
        inflight_joins / total_records
        if total_records > 0
        else 0.0
    )

    provider_avoidance_rate = (
        (
            cache_hits
            + inflight_joins
        )
        / total_records
        if total_records > 0
        else 0.0
    )

    success_rate = (
        successful_calls / completed_calls
        if completed_calls > 0
        else 0.0
    )

    failure_rate = (
        failed_calls / completed_calls
        if completed_calls > 0
        else 0.0
    )

    billable_output_tokens = (
        output_tokens + thought_tokens
    )

    estimated_input_cost = (
        prompt_tokens
        / 1_000_000
        * input_cost_per_million_usd
    )

    estimated_output_cost = (
        billable_output_tokens
        / 1_000_000
        * output_cost_per_million_usd
    )

    estimated_total_cost = (
        estimated_input_cost
        + estimated_output_cost
    )

    average_tokens_per_success = (
        total_tokens / successful_calls
        if successful_calls > 0
        else 0.0
    )

    global_capacity_used = (
        gemini_attempts
        / global_daily_call_cap
        if global_daily_call_cap > 0
        else None
    )

    return {
        "completed_calls": completed_calls,
        "expired_reservations": (
            expired_reservations
        ),
        "cache_hit_rate_percent": round(
            cache_hit_rate * 100,
            2,
        ),
        "deduplication_rate_percent": round(
            deduplication_rate * 100,
            2,
        ),
        "provider_avoidance_rate_percent": round(
            provider_avoidance_rate * 100,
            2,
        ),
        "success_rate_percent": round(
            success_rate * 100,
            2,
        ),
        "failure_rate_percent": round(
            failure_rate * 100,
            2,
        ),
        "average_total_tokens_per_success": round(
            average_tokens_per_success,
            2,
        ),
        "billable_output_tokens": (
            billable_output_tokens
        ),
        "estimated_paid_cost_usd": round(
            estimated_total_cost,
            6,
        ),
        "estimated_input_cost_usd": round(
            estimated_input_cost,
            6,
        ),
        "estimated_output_cost_usd": round(
            estimated_output_cost,
            6,
        ),
        "global_capacity_used_percent": (
            None
            if global_capacity_used is None
            else round(
                global_capacity_used * 100,
                2,
            )
        ),
    }


def usage_savings_metrics(
    summary: Dict[str, Any],
    *,
    input_cost_per_million_usd: float,
    output_cost_per_million_usd: float,
) -> Dict[str, Any]:
    def read_int(
        name: str,
        fallback: int = 0,
    ) -> int:
        try:
            return max(
                0,
                int(
                    summary.get(
                        name,
                        fallback,
                    )
                    or 0
                ),
            )
        except Exception:
            return max(
                0,
                int(fallback or 0),
            )

    cache_hits = read_int(
        "cache_hits"
    )
    inflight_joins = read_int(
        "inflight_joins"
    )
    successful_calls = read_int(
        "successful_calls"
    )

    prompt_tokens = read_int(
        "prompt_tokens"
    )
    output_tokens = read_int(
        "output_tokens"
    )
    thought_tokens = read_int(
        "thought_tokens"
    )

    successful_prompt_tokens = read_int(
        "successful_prompt_tokens",
        (
            prompt_tokens
            if successful_calls > 0
            else 0
        ),
    )

    successful_output_tokens = read_int(
        "successful_output_tokens",
        (
            output_tokens
            if successful_calls > 0
            else 0
        ),
    )

    successful_thought_tokens = read_int(
        "successful_thought_tokens",
        (
            thought_tokens
            if successful_calls > 0
            else 0
        ),
    )

    successful_total_tokens = read_int(
        "successful_total_tokens",
        (
            successful_prompt_tokens
            + successful_output_tokens
            + successful_thought_tokens
        ),
    )

    provider_calls_avoided = (
        cache_hits + inflight_joins
    )

    successful_billable_output_tokens = (
        successful_output_tokens
        + successful_thought_tokens
    )

    successful_input_cost = (
        successful_prompt_tokens
        / 1_000_000
        * input_cost_per_million_usd
    )

    successful_output_cost = (
        successful_billable_output_tokens
        / 1_000_000
        * output_cost_per_million_usd
    )

    successful_cost = (
        successful_input_cost
        + successful_output_cost
    )

    savings_basis_available = (
        successful_calls > 0
        and successful_total_tokens > 0
    )

    average_success_cost = (
        successful_cost
        / successful_calls
        if savings_basis_available
        else 0.0
    )

    average_success_prompt_tokens = (
        successful_prompt_tokens
        / successful_calls
        if savings_basis_available
        else 0.0
    )

    average_success_output_tokens = (
        successful_output_tokens
        / successful_calls
        if savings_basis_available
        else 0.0
    )

    average_success_thought_tokens = (
        successful_thought_tokens
        / successful_calls
        if savings_basis_available
        else 0.0
    )

    average_success_total_tokens = (
        successful_total_tokens
        / successful_calls
        if savings_basis_available
        else 0.0
    )

    estimated_cache_cost_avoided = (
        average_success_cost
        * cache_hits
    )

    estimated_inflight_cost_avoided = (
        average_success_cost
        * inflight_joins
    )

    estimated_total_cost_avoided = (
        estimated_cache_cost_avoided
        + estimated_inflight_cost_avoided
    )

    actual_estimated_cost = (
        prompt_tokens
        / 1_000_000
        * input_cost_per_million_usd
        + (
            output_tokens
            + thought_tokens
        )
        / 1_000_000
        * output_cost_per_million_usd
    )

    estimated_cost_without_avoidance = (
        actual_estimated_cost
        + estimated_total_cost_avoided
    )

    estimated_cost_reduction = (
        estimated_total_cost_avoided
        / estimated_cost_without_avoidance
        if estimated_cost_without_avoidance > 0
        else 0.0
    )

    unpriced_avoided_calls = (
        0
        if savings_basis_available
        else provider_calls_avoided
    )

    return {
        "estimation_basis": (
            "average_successful_call_in_scope"
        ),
        "cost_savings_estimate_available": (
            savings_basis_available
        ),
        "provider_calls_avoided": (
            provider_calls_avoided
        ),
        "cache_calls_avoided": cache_hits,
        "inflight_calls_avoided": (
            inflight_joins
        ),
        "unpriced_avoided_calls": (
            unpriced_avoided_calls
        ),
        "average_success_cost_basis_usd": round(
            average_success_cost,
            6,
        ),
        "estimated_cache_cost_avoided_usd": round(
            estimated_cache_cost_avoided,
            6,
        ),
        "estimated_inflight_cost_avoided_usd": round(
            estimated_inflight_cost_avoided,
            6,
        ),
        "estimated_total_cost_avoided_usd": round(
            estimated_total_cost_avoided,
            6,
        ),
        "estimated_actual_cost_usd": round(
            actual_estimated_cost,
            6,
        ),
        "estimated_cost_without_avoidance_usd": round(
            estimated_cost_without_avoidance,
            6,
        ),
        "estimated_cost_reduction_percent": round(
            estimated_cost_reduction * 100,
            2,
        ),
        "estimated_prompt_tokens_avoided": round(
            average_success_prompt_tokens
            * provider_calls_avoided,
            2,
        ),
        "estimated_output_tokens_avoided": round(
            average_success_output_tokens
            * provider_calls_avoided,
            2,
        ),
        "estimated_thought_tokens_avoided": round(
            average_success_thought_tokens
            * provider_calls_avoided,
            2,
        ),
        "estimated_total_tokens_avoided": round(
            average_success_total_tokens
            * provider_calls_avoided,
            2,
        ),
    }


def usage_scope_savings_summary(
    mode_metrics: List[Dict[str, Any]],
    *,
    actual_estimated_cost: float,
    estimation_basis: str,
) -> Dict[str, Any]:
    provider_calls_avoided = sum(
        int(
            row.get(
                "provider_calls_avoided",
                0,
            )
            or 0
        )
        for row in mode_metrics
    )

    cache_calls_avoided = sum(
        int(
            row.get(
                "cache_calls_avoided",
                0,
            )
            or 0
        )
        for row in mode_metrics
    )

    inflight_calls_avoided = sum(
        int(
            row.get(
                "inflight_calls_avoided",
                0,
            )
            or 0
        )
        for row in mode_metrics
    )

    unpriced_avoided_calls = sum(
        int(
            row.get(
                "unpriced_avoided_calls",
                0,
            )
            or 0
        )
        for row in mode_metrics
    )

    estimated_cache_cost_avoided = sum(
        float(
            row.get(
                "estimated_cache_cost_avoided_usd",
                0.0,
            )
            or 0.0
        )
        for row in mode_metrics
    )

    estimated_inflight_cost_avoided = sum(
        float(
            row.get(
                "estimated_inflight_cost_avoided_usd",
                0.0,
            )
            or 0.0
        )
        for row in mode_metrics
    )

    estimated_total_cost_avoided = (
        estimated_cache_cost_avoided
        + estimated_inflight_cost_avoided
    )

    estimated_cost_without_avoidance = (
        float(actual_estimated_cost or 0.0)
        + estimated_total_cost_avoided
    )

    estimated_cost_reduction = (
        estimated_total_cost_avoided
        / estimated_cost_without_avoidance
        if estimated_cost_without_avoidance > 0
        else 0.0
    )

    estimated_prompt_tokens_avoided = sum(
        float(
            row.get(
                "estimated_prompt_tokens_avoided",
                0.0,
            )
            or 0.0
        )
        for row in mode_metrics
    )

    estimated_output_tokens_avoided = sum(
        float(
            row.get(
                "estimated_output_tokens_avoided",
                0.0,
            )
            or 0.0
        )
        for row in mode_metrics
    )

    estimated_thought_tokens_avoided = sum(
        float(
            row.get(
                "estimated_thought_tokens_avoided",
                0.0,
            )
            or 0.0
        )
        for row in mode_metrics
    )

    estimated_total_tokens_avoided = sum(
        float(
            row.get(
                "estimated_total_tokens_avoided",
                0.0,
            )
            or 0.0
        )
        for row in mode_metrics
    )

    return {
        "estimation_basis": estimation_basis,
        "estimate_complete": (
            unpriced_avoided_calls == 0
        ),
        "cost_savings_estimate_available": (
            provider_calls_avoided
            > unpriced_avoided_calls
        ),
        "provider_calls_avoided": (
            provider_calls_avoided
        ),
        "cache_calls_avoided": (
            cache_calls_avoided
        ),
        "inflight_calls_avoided": (
            inflight_calls_avoided
        ),
        "unpriced_avoided_calls": (
            unpriced_avoided_calls
        ),
        "estimated_cache_cost_avoided_usd": round(
            estimated_cache_cost_avoided,
            6,
        ),
        "estimated_inflight_cost_avoided_usd": round(
            estimated_inflight_cost_avoided,
            6,
        ),
        "estimated_total_cost_avoided_usd": round(
            estimated_total_cost_avoided,
            6,
        ),
        "estimated_actual_cost_usd": round(
            float(actual_estimated_cost or 0.0),
            6,
        ),
        "estimated_cost_without_avoidance_usd": round(
            estimated_cost_without_avoidance,
            6,
        ),
        "estimated_cost_reduction_percent": round(
            estimated_cost_reduction * 100,
            2,
        ),
        "estimated_prompt_tokens_avoided": round(
            estimated_prompt_tokens_avoided,
            2,
        ),
        "estimated_output_tokens_avoided": round(
            estimated_output_tokens_avoided,
            2,
        ),
        "estimated_thought_tokens_avoided": round(
            estimated_thought_tokens_avoided,
            2,
        ),
        "estimated_total_tokens_avoided": round(
            estimated_total_tokens_avoided,
            2,
        ),
        "by_mode": [
            {
                "mode": row.get(
                    "mode",
                    "unknown",
                ),
                "cost_savings_estimate_available": (
                    row.get(
                        "cost_savings_estimate_available",
                        False,
                    )
                ),
                "provider_calls_avoided": (
                    row.get(
                        "provider_calls_avoided",
                        0,
                    )
                ),
                "cache_calls_avoided": (
                    row.get(
                        "cache_calls_avoided",
                        0,
                    )
                ),
                "inflight_calls_avoided": (
                    row.get(
                        "inflight_calls_avoided",
                        0,
                    )
                ),
                "unpriced_avoided_calls": (
                    row.get(
                        "unpriced_avoided_calls",
                        0,
                    )
                ),
                "average_success_cost_basis_usd": (
                    row.get(
                        "average_success_cost_basis_usd",
                        0.0,
                    )
                ),
                "estimated_total_cost_avoided_usd": (
                    row.get(
                        "estimated_total_cost_avoided_usd",
                        0.0,
                    )
                ),
                "estimated_total_tokens_avoided": (
                    row.get(
                        "estimated_total_tokens_avoided",
                        0.0,
                    )
                ),
            }
            for row in mode_metrics
        ],
    }


def usage_mode_metrics(
    summary: Dict[str, Any],
    *,
    derived_metrics_resolver,
    savings_metrics_resolver,
) -> Dict[str, Any]:
    def read_int(
        name: str,
    ) -> int:
        try:
            return max(
                0,
                int(
                    summary.get(
                        name,
                        0,
                    )
                    or 0
                ),
            )
        except Exception:
            return 0

    normalized = {
        "total_records": read_int(
            "total_records"
        ),
        "cache_hits": read_int(
            "cache_hits"
        ),
        "inflight_joins": read_int(
            "inflight_joins"
        ),
        "gemini_attempts": read_int(
            "gemini_attempts"
        ),
        "successful_calls": read_int(
            "successful_calls"
        ),
        "failed_calls": read_int(
            "failed_calls"
        ),
        "reserved_calls": read_int(
            "reserved_calls"
        ),
        "expired_reservations": read_int(
            "expired_reservations"
        ),
        "prompt_tokens": read_int(
            "prompt_tokens"
        ),
        "output_tokens": read_int(
            "output_tokens"
        ),
        "thought_tokens": read_int(
            "thought_tokens"
        ),
        "total_tokens": read_int(
            "total_tokens"
        ),
        "successful_prompt_tokens": read_int(
            "successful_prompt_tokens"
        ),
        "successful_output_tokens": read_int(
            "successful_output_tokens"
        ),
        "successful_thought_tokens": read_int(
            "successful_thought_tokens"
        ),
        "successful_total_tokens": read_int(
            "successful_total_tokens"
        ),
    }

    derived = derived_metrics_resolver(
        normalized
    )

    savings = savings_metrics_resolver(
        normalized
    )

    attempts = normalized[
        "gemini_attempts"
    ]

    successful_calls = normalized[
        "successful_calls"
    ]

    estimated_cost = float(
        derived[
            "estimated_paid_cost_usd"
        ]
        or 0.0
    )

    average_tokens_per_attempt = (
        normalized["total_tokens"]
        / attempts
        if attempts > 0
        else 0.0
    )

    average_cost_per_attempt = (
        estimated_cost / attempts
        if attempts > 0
        else 0.0
    )

    average_cost_per_success = (
        estimated_cost
        / successful_calls
        if successful_calls > 0
        else 0.0
    )

    return {
        **normalized,
        "completed_calls": (
            derived["completed_calls"]
        ),
        "cache_hit_rate_percent": (
            derived[
                "cache_hit_rate_percent"
            ]
        ),
        "deduplication_rate_percent": (
            derived[
                "deduplication_rate_percent"
            ]
        ),
        "provider_avoidance_rate_percent": (
            derived[
                "provider_avoidance_rate_percent"
            ]
        ),
        "success_rate_percent": (
            derived[
                "success_rate_percent"
            ]
        ),
        "failure_rate_percent": (
            derived[
                "failure_rate_percent"
            ]
        ),
        "average_total_tokens_per_success": (
            derived[
                "average_total_tokens_per_success"
            ]
        ),
        "average_total_tokens_per_attempt": round(
            average_tokens_per_attempt,
            2,
        ),
        "billable_output_tokens": (
            derived[
                "billable_output_tokens"
            ]
        ),
        "estimated_paid_cost_usd": (
            derived[
                "estimated_paid_cost_usd"
            ]
        ),
        "estimated_input_cost_usd": (
            derived[
                "estimated_input_cost_usd"
            ]
        ),
        "estimated_output_cost_usd": (
            derived[
                "estimated_output_cost_usd"
            ]
        ),
        "average_estimated_cost_per_attempt_usd": round(
            average_cost_per_attempt,
            6,
        ),
        "average_estimated_cost_per_success_usd": round(
            average_cost_per_success,
            6,
        ),
        **savings,
    }


def admin_usage_summary(
    *,
    days: int,
    connection_factory,
    usage_day_resolver,
    expire_reservations,
    derived_metrics_resolver,
    mode_metrics_resolver,
    scope_savings_resolver,
    reservation_timeout_seconds: int,
    global_daily_call_cap: int,
    client_daily_call_cap: int,
    input_cost_per_million_usd: float,
    output_cost_per_million_usd: float,
    provider_day_resolver=None,
    capacity_policy_resolver=None,
) -> Dict[str, Any]:
    usage_day = usage_day_resolver()
    provider_day = (
        provider_day_resolver()
        if callable(provider_day_resolver)
        else provider_usage_day()
    )
    capacity_resolver = (
        capacity_policy_resolver
        if callable(capacity_policy_resolver)
        else capacity_policy_for_model
    )

    window_end_day = usage_day

    window_start_day = (
        datetime.now(timezone.utc).date()
        - timedelta(days=days - 1)
    ).isoformat()

    conn = connection_factory()

    try:
        expire_reservations(
            conn,
            usage_day=usage_day,
        )
        conn.commit()

        usage_columns = {
            str(row["name"])
            for row in conn.execute(
                "PRAGMA table_info(gemini_usage)"
            ).fetchall()
        }

        if "provider_day" in usage_columns:
            provider_today_row = conn.execute(
                """
                SELECT
                  COUNT(*) AS provider_attempts
                FROM gemini_usage
                WHERE provider_day = ?
                  AND cache_hit = 0
                  AND inflight_join = 0
                  AND status IN (
                    'reserved',
                    'success',
                    'failed',
                    'expired'
                  )
                """,
                (provider_day,),
            ).fetchone()

            provider_top_client_row = conn.execute(
                """
                SELECT COALESCE(
                  MAX(client_attempts),
                  0
                ) AS highest_client_attempts
                FROM (
                  SELECT COUNT(*) AS client_attempts
                  FROM gemini_usage
                  WHERE provider_day = ?
                    AND cache_hit = 0
                    AND inflight_join = 0
                    AND status IN (
                      'reserved',
                      'success',
                      'failed',
                      'expired'
                    )
                  GROUP BY client_key
                )
                """,
                (provider_day,),
            ).fetchone()

            provider_model_rows = conn.execute(
                """
                SELECT
                  model,
                  COUNT(*) AS provider_attempts
                FROM gemini_usage
                WHERE provider_day = ?
                  AND cache_hit = 0
                  AND inflight_join = 0
                  AND status IN (
                    'reserved',
                    'success',
                    'failed',
                    'expired'
                  )
                GROUP BY model
                ORDER BY model
                """,
                (provider_day,),
            ).fetchall()

        else:
            provider_today_row = conn.execute(
                """
                SELECT
                  COUNT(*) AS provider_attempts
                FROM gemini_usage
                WHERE usage_day = ?
                  AND cache_hit = 0
                  AND inflight_join = 0
                  AND status IN (
                    'reserved',
                    'success',
                    'failed',
                    'expired'
                  )
                """,
                (usage_day,),
            ).fetchone()

            provider_top_client_row = conn.execute(
                """
                SELECT COALESCE(
                  MAX(client_attempts),
                  0
                ) AS highest_client_attempts
                FROM (
                  SELECT COUNT(*) AS client_attempts
                  FROM gemini_usage
                  WHERE usage_day = ?
                    AND cache_hit = 0
                    AND inflight_join = 0
                    AND status IN (
                      'reserved',
                      'success',
                      'failed',
                      'expired'
                    )
                  GROUP BY client_key
                )
                """,
                (usage_day,),
            ).fetchone()

            provider_model_rows = conn.execute(
                """
                SELECT
                  model,
                  COUNT(*) AS provider_attempts
                FROM gemini_usage
                WHERE usage_day = ?
                  AND cache_hit = 0
                  AND inflight_join = 0
                  AND status IN (
                    'reserved',
                    'success',
                    'failed',
                    'expired'
                  )
                GROUP BY model
                ORDER BY model
                """,
                (usage_day,),
            ).fetchall()

        today_row = conn.execute(
            """
            SELECT
              COUNT(*) AS total_records,
              COUNT(DISTINCT client_key) AS unique_clients,
              COALESCE(
                SUM(
                  CASE
                    WHEN cache_hit = 1
                    THEN 1
                    ELSE 0
                  END
                ),
                0
              ) AS cache_hits,
              COALESCE(
                SUM(
                  CASE
                    WHEN inflight_join = 1
                    THEN 1
                    ELSE 0
                  END
                ),
                0
              ) AS inflight_joins,
              COALESCE(
                SUM(
                  CASE
                    WHEN cache_hit = 0
                    AND inflight_join = 0
                    AND status IN (
                      'reserved',
                      'success',
                      'failed'
                    )
                    THEN 1
                    ELSE 0
                  END
                ),
                0
              ) AS gemini_attempts,
              COALESCE(
                SUM(
                  CASE
                    WHEN status = 'success'
                    THEN 1
                    ELSE 0
                  END
                ),
                0
              ) AS successful_calls,
              COALESCE(
                SUM(
                  CASE
                    WHEN status = 'failed'
                    THEN 1
                    ELSE 0
                  END
                ),
                0
              ) AS failed_calls,
              COALESCE(
                SUM(
                  CASE
                    WHEN status = 'reserved'
                    THEN 1
                    ELSE 0
                  END
                ),
                0
              ) AS reserved_calls,
              COALESCE(
                SUM(
                  CASE
                    WHEN status = 'expired'
                    THEN 1
                    ELSE 0
                  END
                ),
                0
              ) AS expired_reservations,
              COALESCE(
                SUM(
                  CASE
                    WHEN mode = 'article'
                     AND cache_hit = 0
                     AND inflight_join = 0
                     AND status IN (
                       'reserved',
                       'success',
                       'failed'
                     )
                    THEN 1
                    ELSE 0
                  END
                ),
                0
              ) AS article_attempts,
              COALESCE(
                SUM(
                  CASE
                    WHEN mode = 'video'
                     AND cache_hit = 0
                     AND inflight_join = 0
                     AND status IN (
                       'reserved',
                       'success',
                       'failed'
                     )
                    THEN 1
                    ELSE 0
                  END
                ),
                0
              ) AS video_attempts,
              COALESCE(SUM(prompt_tokens), 0)
                AS prompt_tokens,
              COALESCE(SUM(output_tokens), 0)
                AS output_tokens,
              COALESCE(SUM(thought_tokens), 0)
                AS thought_tokens,
              COALESCE(
                SUM(
                  CASE
                    WHEN status = 'success'
                    THEN prompt_tokens
                    ELSE 0
                  END
                ),
                0
              ) AS successful_prompt_tokens,
              COALESCE(
                SUM(
                  CASE
                    WHEN status = 'success'
                    THEN output_tokens
                    ELSE 0
                  END
                ),
                0
              ) AS successful_output_tokens,
              COALESCE(
                SUM(
                  CASE
                    WHEN status = 'success'
                    THEN thought_tokens
                    ELSE 0
                  END
                ),
                0
              ) AS successful_thought_tokens,
              COALESCE(
                SUM(
                  CASE
                    WHEN status = 'success'
                    THEN total_tokens
                    ELSE 0
                  END
                ),
                0
              ) AS successful_total_tokens,
              COALESCE(SUM(total_tokens), 0)
                AS total_tokens,
              COALESCE(
                ROUND(
                  AVG(
                    CASE
                      WHEN cache_hit = 0
                       AND status IN (
                         'success',
                         'failed'
                       )
                      THEN latency_ms
                    END
                  )
                ),
                0
              ) AS average_latency_ms,
              COALESCE(
                MIN(
                  CASE
                    WHEN cache_hit = 0
                     AND status IN (
                       'success',
                       'failed'
                     )
                    THEN latency_ms
                  END
                ),
                0
              ) AS fastest_latency_ms,
              COALESCE(
                MAX(
                  CASE
                    WHEN cache_hit = 0
                     AND status IN (
                       'success',
                       'failed'
                     )
                    THEN latency_ms
                  END
                ),
                0
              ) AS slowest_latency_ms
            FROM gemini_usage
            WHERE usage_day = ?
            """,
            (usage_day,),
        ).fetchone()

        top_client_row = conn.execute(
            """
            SELECT COALESCE(
              MAX(client_attempts),
              0
            ) AS highest_client_attempts
            FROM (
              SELECT COUNT(*) AS client_attempts
              FROM gemini_usage
              WHERE usage_day = ?
                AND cache_hit = 0
                AND inflight_join = 0
                AND status IN (
                  'reserved',
                  'success',
                  'failed'
                )
              GROUP BY client_key
            )
            """,
            (usage_day,),
        ).fetchone()

        breakdown_rows = conn.execute(
            """
            SELECT
              mode,
              model,
              status,
              cache_hit,
              inflight_join,
              COUNT(*) AS request_count,
              COALESCE(SUM(prompt_tokens), 0)
                AS prompt_tokens,
              COALESCE(SUM(output_tokens), 0)
                AS output_tokens,
              COALESCE(SUM(thought_tokens), 0)
                AS thought_tokens,
              COALESCE(SUM(total_tokens), 0)
                AS total_tokens
            FROM gemini_usage
            WHERE usage_day = ?
            GROUP BY
              mode,
              model,
              status,
              cache_hit
            ORDER BY
              mode,
              status,
              model
            """,
            (usage_day,),
        ).fetchall()

        mode_rows = conn.execute(
            """
            SELECT
              mode,
              COUNT(*) AS total_records,
              COALESCE(
                SUM(
                  CASE
                    WHEN cache_hit = 1
                    THEN 1
                    ELSE 0
                  END
                ),
                0
              ) AS cache_hits,
              COALESCE(
                SUM(
                  CASE
                    WHEN inflight_join = 1
                    THEN 1
                    ELSE 0
                  END
                ),
                0
              ) AS inflight_joins,
              COALESCE(
                SUM(
                  CASE
                    WHEN cache_hit = 0
                    AND inflight_join = 0
                    AND status IN (
                      'reserved',
                      'success',
                      'failed'
                    )
                    THEN 1
                    ELSE 0
                  END
                ),
                0
              ) AS gemini_attempts,
              COALESCE(
                SUM(
                  CASE
                    WHEN status = 'success'
                    THEN 1
                    ELSE 0
                  END
                ),
                0
              ) AS successful_calls,
              COALESCE(
                SUM(
                  CASE
                    WHEN status = 'failed'
                    THEN 1
                    ELSE 0
                  END
                ),
                0
              ) AS failed_calls,
              COALESCE(
                SUM(
                  CASE
                    WHEN status = 'reserved'
                    THEN 1
                    ELSE 0
                  END
                ),
                0
              ) AS reserved_calls,
              COALESCE(
                SUM(
                  CASE
                    WHEN status = 'expired'
                    THEN 1
                    ELSE 0
                  END
                ),
                0
              ) AS expired_reservations,
              COALESCE(
                SUM(prompt_tokens),
                0
              ) AS prompt_tokens,
              COALESCE(
                SUM(output_tokens),
                0
              ) AS output_tokens,
              COALESCE(
                SUM(thought_tokens),
                0
              ) AS thought_tokens,
              COALESCE(
                SUM(
                  CASE
                    WHEN status = 'success'
                    THEN prompt_tokens
                    ELSE 0
                  END
                ),
                0
              ) AS successful_prompt_tokens,
              COALESCE(
                SUM(
                  CASE
                    WHEN status = 'success'
                    THEN output_tokens
                    ELSE 0
                  END
                ),
                0
              ) AS successful_output_tokens,
              COALESCE(
                SUM(
                  CASE
                    WHEN status = 'success'
                    THEN thought_tokens
                    ELSE 0
                  END
                ),
                0
              ) AS successful_thought_tokens,
              COALESCE(
                SUM(
                  CASE
                    WHEN status = 'success'
                    THEN total_tokens
                    ELSE 0
                  END
                ),
                0
              ) AS successful_total_tokens,
              COALESCE(
                SUM(total_tokens),
                0
              ) AS total_tokens
            FROM gemini_usage
            WHERE usage_day = ?
            GROUP BY mode
            ORDER BY mode
            """,
            (usage_day,),
        ).fetchall()

        latency_rows = conn.execute(
            """
            SELECT
              mode,
              COUNT(*) AS completed_calls,
              COALESCE(
                SUM(
                  CASE
                    WHEN status = 'success'
                    THEN 1
                    ELSE 0
                  END
                ),
                0
              ) AS successful_calls,
              COALESCE(
                SUM(
                  CASE
                    WHEN status = 'failed'
                    THEN 1
                    ELSE 0
                  END
                ),
                0
              ) AS failed_calls,
              COALESCE(
                ROUND(AVG(latency_ms)),
                0
              ) AS average_latency_ms,
              COALESCE(
                MIN(latency_ms),
                0
              ) AS fastest_latency_ms,
              COALESCE(
                MAX(latency_ms),
                0
              ) AS slowest_latency_ms
            FROM gemini_usage
            WHERE usage_day = ?
              AND cache_hit = 0
              AND inflight_join = 0
              AND status IN (
                'success',
                'failed'
              )
            GROUP BY mode
            ORDER BY mode
            """,
            (usage_day,),
        ).fetchall()

        failure_rows = conn.execute(
            """
            SELECT
              mode,
              COALESCE(
                failure_status_code,
                0
              ) AS failure_status_code,
              COALESCE(
                NULLIF(failure_type, ''),
                'unknown'
              ) AS failure_type,
              COUNT(*) AS failure_count
            FROM gemini_usage
            WHERE usage_day = ?
              AND status = 'failed'
            GROUP BY
              mode,
              COALESCE(
                failure_status_code,
                0
              ),
              COALESCE(
                NULLIF(failure_type, ''),
                'unknown'
              )
            ORDER BY
              failure_count DESC,
              mode,
              failure_type
            """,
            (usage_day,),
        ).fetchall()

        rolling_row = conn.execute(
            """
            SELECT
              COUNT(*) AS total_records,
              COUNT(DISTINCT client_key)
                AS unique_clients,
              COALESCE(
                SUM(
                  CASE
                    WHEN cache_hit = 1
                    THEN 1
                    ELSE 0
                  END
                ),
                0
              ) AS cache_hits,
              COALESCE(
                SUM(
                  CASE
                    WHEN inflight_join = 1
                    THEN 1
                    ELSE 0
                  END
                ),
                0
              ) AS inflight_joins,
              COALESCE(
                SUM(
                  CASE
                    WHEN cache_hit = 0
                     AND inflight_join = 0
                     AND status IN (
                       'reserved',
                       'success',
                       'failed'
                     )
                    THEN 1
                    ELSE 0
                  END
                ),
                0
              ) AS gemini_attempts,
              COALESCE(
                SUM(
                  CASE
                    WHEN status = 'success'
                    THEN 1
                    ELSE 0
                  END
                ),
                0
              ) AS successful_calls,
              COALESCE(
                SUM(
                  CASE
                    WHEN status = 'failed'
                    THEN 1
                    ELSE 0
                  END
                ),
                0
              ) AS failed_calls,
              COALESCE(
                SUM(
                  CASE
                    WHEN status = 'reserved'
                    THEN 1
                    ELSE 0
                  END
                ),
                0
              ) AS reserved_calls,
              COALESCE(
                SUM(
                  CASE
                    WHEN status = 'expired'
                    THEN 1
                    ELSE 0
                  END
                ),
                0
              ) AS expired_reservations,
              COALESCE(
                SUM(
                  CASE
                    WHEN mode = 'article'
                     AND cache_hit = 0
                     AND inflight_join = 0
                     AND status IN (
                       'reserved',
                       'success',
                       'failed'
                     )
                    THEN 1
                    ELSE 0
                  END
                ),
                0
              ) AS article_attempts,
              COALESCE(
                SUM(
                  CASE
                    WHEN mode = 'video'
                     AND cache_hit = 0
                     AND inflight_join = 0
                     AND status IN (
                       'reserved',
                       'success',
                       'failed'
                     )
                    THEN 1
                    ELSE 0
                  END
                ),
                0
              ) AS video_attempts,
              COALESCE(
                SUM(prompt_tokens),
                0
              ) AS prompt_tokens,
              COALESCE(
                SUM(output_tokens),
                0
              ) AS output_tokens,
              COALESCE(
                SUM(thought_tokens),
                0
              ) AS thought_tokens,
              COALESCE(
                SUM(total_tokens),
                0
              ) AS total_tokens,
              COALESCE(
                SUM(
                  CASE
                    WHEN status = 'success'
                    THEN prompt_tokens
                    ELSE 0
                  END
                ),
                0
              ) AS successful_prompt_tokens,
              COALESCE(
                SUM(
                  CASE
                    WHEN status = 'success'
                    THEN output_tokens
                    ELSE 0
                  END
                ),
                0
              ) AS successful_output_tokens,
              COALESCE(
                SUM(
                  CASE
                    WHEN status = 'success'
                    THEN thought_tokens
                    ELSE 0
                  END
                ),
                0
              ) AS successful_thought_tokens,
              COALESCE(
                SUM(
                  CASE
                    WHEN status = 'success'
                    THEN total_tokens
                    ELSE 0
                  END
                ),
                0
              ) AS successful_total_tokens,
              COALESCE(
                ROUND(
                  AVG(
                    CASE
                      WHEN cache_hit = 0
                       AND inflight_join = 0
                       AND status IN (
                         'success',
                         'failed'
                       )
                      THEN latency_ms
                    END
                  )
                ),
                0
              ) AS average_latency_ms,
              COALESCE(
                MIN(
                  CASE
                    WHEN cache_hit = 0
                     AND inflight_join = 0
                     AND status IN (
                       'success',
                       'failed'
                     )
                    THEN latency_ms
                  END
                ),
                0
              ) AS fastest_latency_ms,
              COALESCE(
                MAX(
                  CASE
                    WHEN cache_hit = 0
                     AND inflight_join = 0
                     AND status IN (
                       'success',
                       'failed'
                     )
                    THEN latency_ms
                  END
                ),
                0
              ) AS slowest_latency_ms
            FROM gemini_usage
            WHERE usage_day BETWEEN ? AND ?
            """,
            (
                window_start_day,
                window_end_day,
            ),
        ).fetchone()

        rolling_mode_rows = conn.execute(
            """
            SELECT
              mode,
              COUNT(*) AS total_records,
              COALESCE(
                SUM(
                  CASE
                    WHEN cache_hit = 1
                    THEN 1
                    ELSE 0
                  END
                ),
                0
              ) AS cache_hits,
              COALESCE(
                SUM(
                  CASE
                    WHEN inflight_join = 1
                    THEN 1
                    ELSE 0
                  END
                ),
                0
              ) AS inflight_joins,
              COALESCE(
                SUM(
                  CASE
                    WHEN cache_hit = 0
                     AND inflight_join = 0
                     AND status IN (
                       'reserved',
                       'success',
                       'failed'
                     )
                    THEN 1
                    ELSE 0
                  END
                ),
                0
              ) AS gemini_attempts,
              COALESCE(
                SUM(
                  CASE
                    WHEN status = 'success'
                    THEN 1
                    ELSE 0
                  END
                ),
                0
              ) AS successful_calls,
              COALESCE(
                SUM(
                  CASE
                    WHEN status = 'failed'
                    THEN 1
                    ELSE 0
                  END
                ),
                0
              ) AS failed_calls,
              COALESCE(
                SUM(
                  CASE
                    WHEN status = 'reserved'
                    THEN 1
                    ELSE 0
                  END
                ),
                0
              ) AS reserved_calls,
              COALESCE(
                SUM(
                  CASE
                    WHEN status = 'expired'
                    THEN 1
                    ELSE 0
                  END
                ),
                0
              ) AS expired_reservations,
              COALESCE(
                SUM(prompt_tokens),
                0
              ) AS prompt_tokens,
              COALESCE(
                SUM(output_tokens),
                0
              ) AS output_tokens,
              COALESCE(
                SUM(thought_tokens),
                0
              ) AS thought_tokens,
              COALESCE(
                SUM(total_tokens),
                0
              ) AS total_tokens,
              COALESCE(
                SUM(
                  CASE
                    WHEN status = 'success'
                    THEN prompt_tokens
                    ELSE 0
                  END
                ),
                0
              ) AS successful_prompt_tokens,
              COALESCE(
                SUM(
                  CASE
                    WHEN status = 'success'
                    THEN output_tokens
                    ELSE 0
                  END
                ),
                0
              ) AS successful_output_tokens,
              COALESCE(
                SUM(
                  CASE
                    WHEN status = 'success'
                    THEN thought_tokens
                    ELSE 0
                  END
                ),
                0
              ) AS successful_thought_tokens,
              COALESCE(
                SUM(
                  CASE
                    WHEN status = 'success'
                    THEN total_tokens
                    ELSE 0
                  END
                ),
                0
              ) AS successful_total_tokens
            FROM gemini_usage
            WHERE usage_day BETWEEN ? AND ?
            GROUP BY mode
            ORDER BY mode
            """,
            (
                window_start_day,
                window_end_day,
            ),
        ).fetchall()

        rolling_day_rows = conn.execute(
            """
            SELECT
              usage_day,
              COUNT(*) AS total_records,
              COUNT(DISTINCT client_key)
                AS unique_clients,
              COALESCE(
                SUM(
                  CASE
                    WHEN cache_hit = 1
                    THEN 1
                    ELSE 0
                  END
                ),
                0
              ) AS cache_hits,
              COALESCE(
                SUM(
                  CASE
                    WHEN inflight_join = 1
                    THEN 1
                    ELSE 0
                  END
                ),
                0
              ) AS inflight_joins,
              COALESCE(
                SUM(
                  CASE
                    WHEN cache_hit = 0
                     AND inflight_join = 0
                     AND status IN (
                       'reserved',
                       'success',
                       'failed'
                     )
                    THEN 1
                    ELSE 0
                  END
                ),
                0
              ) AS gemini_attempts,
              COALESCE(
                SUM(
                  CASE
                    WHEN status = 'success'
                    THEN 1
                    ELSE 0
                  END
                ),
                0
              ) AS successful_calls,
              COALESCE(
                SUM(
                  CASE
                    WHEN status = 'failed'
                    THEN 1
                    ELSE 0
                  END
                ),
                0
              ) AS failed_calls,
              COALESCE(
                SUM(
                  CASE
                    WHEN status = 'expired'
                    THEN 1
                    ELSE 0
                  END
                ),
                0
              ) AS expired_reservations,
              COALESCE(
                SUM(prompt_tokens),
                0
              ) AS prompt_tokens,
              COALESCE(
                SUM(output_tokens),
                0
              ) AS output_tokens,
              COALESCE(
                SUM(thought_tokens),
                0
              ) AS thought_tokens,
              COALESCE(
                SUM(total_tokens),
                0
              ) AS total_tokens
            FROM gemini_usage
            WHERE usage_day BETWEEN ? AND ?
            GROUP BY usage_day
            ORDER BY usage_day ASC
            """,
            (
                window_start_day,
                window_end_day,
            ),
        ).fetchall()

        recent_rows = conn.execute(
            """
            SELECT
              usage_day,
              COUNT(*) AS total_records,
              COUNT(DISTINCT client_key)
                AS unique_clients,
              COALESCE(
                SUM(
                  CASE
                    WHEN cache_hit = 1
                    THEN 1
                    ELSE 0
                  END
                ),
                0
              ) AS cache_hits,
              COALESCE(
                SUM(
                  CASE
                    WHEN inflight_join = 1
                    THEN 1
                    ELSE 0
                  END
                ),
                0
              ) AS inflight_joins,
              COALESCE(
                SUM(
                  CASE
                    WHEN cache_hit = 0
                    AND inflight_join = 0
                    AND status IN (
                      'reserved',
                      'success',
                      'failed'
                    )
                    THEN 1
                    ELSE 0
                  END
                ),
                0
              ) AS gemini_attempts,
              COALESCE(
                SUM(
                  CASE
                    WHEN status = 'success'
                    THEN 1
                    ELSE 0
                  END
                ),
                0
              ) AS successful_calls,
              COALESCE(
                SUM(
                  CASE
                    WHEN status = 'failed'
                    THEN 1
                    ELSE 0
                  END
                ),
                0
              ) AS failed_calls,
              COALESCE(
                SUM(
                  CASE
                    WHEN status = 'expired'
                    THEN 1
                    ELSE 0
                  END
                ),
                0
              ) AS expired_reservations,
              COALESCE(SUM(total_tokens), 0)
                AS total_tokens
            FROM gemini_usage
            WHERE usage_day BETWEEN ? AND ?
            GROUP BY usage_day
            ORDER BY usage_day DESC
            """,
            (
                window_start_day,
                window_end_day,
            ),
        ).fetchall()

    finally:
        conn.close()

    today = {
        key: int(value or 0)
        for key, value
        in dict(today_row).items()
    }

    rolling = {
        key: int(value or 0)
        for key, value
        in dict(rolling_row).items()
    }

    provider_attempts = int(
        provider_today_row[
            "provider_attempts"
        ]
        or 0
    )

    highest_client_attempts = int(
        provider_top_client_row[
            "highest_client_attempts"
        ]
        or 0
    )

    global_remaining = (
        None
        if global_daily_call_cap <= 0
        else max(
            0,
            global_daily_call_cap
            - provider_attempts,
        )
    )

    highest_client_remaining = (
        None
        if client_daily_call_cap <= 0
        else max(
            0,
            client_daily_call_cap
            - highest_client_attempts,
        )
    )

    today_metrics = derived_metrics_resolver(
        today
    )

    today_estimated_cost = float(
        today_metrics[
            "estimated_paid_cost_usd"
        ]
        or 0.0
    )

    mode_metrics = []

    for row in mode_rows:
        payload = mode_metrics_resolver(
            dict(row)
        )

        mode_cost = float(
            payload[
                "estimated_paid_cost_usd"
            ]
            or 0.0
        )

        payload["mode"] = str(
            row["mode"] or "unknown"
        )

        payload[
            "share_of_today_estimated_cost_percent"
        ] = (
            round(
                mode_cost
                / today_estimated_cost
                * 100,
                2,
            )
            if today_estimated_cost > 0
            else 0.0
        )

        mode_metrics.append(payload)

    provider_calls_avoided = sum(
        int(
            row[
                "provider_calls_avoided"
            ]
            or 0
        )
        for row in mode_metrics
    )

    cache_calls_avoided = sum(
        int(
            row[
                "cache_calls_avoided"
            ]
            or 0
        )
        for row in mode_metrics
    )

    inflight_calls_avoided = sum(
        int(
            row[
                "inflight_calls_avoided"
            ]
            or 0
        )
        for row in mode_metrics
    )

    unpriced_avoided_calls = sum(
        int(
            row[
                "unpriced_avoided_calls"
            ]
            or 0
        )
        for row in mode_metrics
    )

    estimated_cache_cost_avoided = sum(
        float(
            row[
                "estimated_cache_cost_avoided_usd"
            ]
            or 0.0
        )
        for row in mode_metrics
    )

    estimated_inflight_cost_avoided = sum(
        float(
            row[
                "estimated_inflight_cost_avoided_usd"
            ]
            or 0.0
        )
        for row in mode_metrics
    )

    estimated_total_cost_avoided = (
        estimated_cache_cost_avoided
        + estimated_inflight_cost_avoided
    )

    estimated_cost_without_avoidance = (
        today_estimated_cost
        + estimated_total_cost_avoided
    )

    estimated_cost_reduction = (
        estimated_total_cost_avoided
        / estimated_cost_without_avoidance
        if estimated_cost_without_avoidance > 0
        else 0.0
    )

    estimated_prompt_tokens_avoided = sum(
        float(
            row[
                "estimated_prompt_tokens_avoided"
            ]
            or 0.0
        )
        for row in mode_metrics
    )

    estimated_output_tokens_avoided = sum(
        float(
            row[
                "estimated_output_tokens_avoided"
            ]
            or 0.0
        )
        for row in mode_metrics
    )

    estimated_thought_tokens_avoided = sum(
        float(
            row[
                "estimated_thought_tokens_avoided"
            ]
            or 0.0
        )
        for row in mode_metrics
    )

    estimated_total_tokens_avoided = sum(
        float(
            row[
                "estimated_total_tokens_avoided"
            ]
            or 0.0
        )
        for row in mode_metrics
    )

    savings_summary = {
        "estimation_basis": (
            "per_mode_average_successful_call"
        ),
        "estimate_complete": (
            unpriced_avoided_calls == 0
        ),
        "cost_savings_estimate_available": (
            provider_calls_avoided
            > unpriced_avoided_calls
        ),
        "provider_calls_avoided": (
            provider_calls_avoided
        ),
        "cache_calls_avoided": (
            cache_calls_avoided
        ),
        "inflight_calls_avoided": (
            inflight_calls_avoided
        ),
        "unpriced_avoided_calls": (
            unpriced_avoided_calls
        ),
        "estimated_cache_cost_avoided_usd": round(
            estimated_cache_cost_avoided,
            6,
        ),
        "estimated_inflight_cost_avoided_usd": round(
            estimated_inflight_cost_avoided,
            6,
        ),
        "estimated_total_cost_avoided_usd": round(
            estimated_total_cost_avoided,
            6,
        ),
        "estimated_actual_cost_usd": round(
            today_estimated_cost,
            6,
        ),
        "estimated_cost_without_avoidance_usd": round(
            estimated_cost_without_avoidance,
            6,
        ),
        "estimated_cost_reduction_percent": round(
            estimated_cost_reduction * 100,
            2,
        ),
        "estimated_prompt_tokens_avoided": round(
            estimated_prompt_tokens_avoided,
            2,
        ),
        "estimated_output_tokens_avoided": round(
            estimated_output_tokens_avoided,
            2,
        ),
        "estimated_thought_tokens_avoided": round(
            estimated_thought_tokens_avoided,
            2,
        ),
        "estimated_total_tokens_avoided": round(
            estimated_total_tokens_avoided,
            2,
        ),
        "by_mode": [
            {
                "mode": row["mode"],
                "cost_savings_estimate_available": (
                    row[
                        "cost_savings_estimate_available"
                    ]
                ),
                "provider_calls_avoided": (
                    row[
                        "provider_calls_avoided"
                    ]
                ),
                "cache_calls_avoided": (
                    row[
                        "cache_calls_avoided"
                    ]
                ),
                "inflight_calls_avoided": (
                    row[
                        "inflight_calls_avoided"
                    ]
                ),
                "unpriced_avoided_calls": (
                    row[
                        "unpriced_avoided_calls"
                    ]
                ),
                "average_success_cost_basis_usd": (
                    row[
                        "average_success_cost_basis_usd"
                    ]
                ),
                "estimated_total_cost_avoided_usd": (
                    row[
                        "estimated_total_cost_avoided_usd"
                    ]
                ),
                "estimated_total_tokens_avoided": (
                    row[
                        "estimated_total_tokens_avoided"
                    ]
                ),
            }
            for row in mode_metrics
        ],
    }

    rolling_metrics = derived_metrics_resolver(
        rolling
    )

    rolling_estimated_cost = float(
        rolling_metrics[
            "estimated_paid_cost_usd"
        ]
        or 0.0
    )

    rolling_mode_metrics = []

    for row in rolling_mode_rows:
        payload = mode_metrics_resolver(
            dict(row)
        )

        mode_cost = float(
            payload[
                "estimated_paid_cost_usd"
            ]
            or 0.0
        )

        payload["mode"] = str(
            row["mode"] or "unknown"
        )

        payload[
            "share_of_window_estimated_cost_percent"
        ] = (
            round(
                mode_cost
                / rolling_estimated_cost
                * 100,
                2,
            )
            if rolling_estimated_cost > 0
            else 0.0
        )

        rolling_mode_metrics.append(
            payload
        )

    rolling_savings_summary = (
        scope_savings_resolver(
            rolling_mode_metrics,
            actual_estimated_cost=(
                rolling_estimated_cost
            ),
            estimation_basis=(
                "rolling_per_mode_"
                "average_successful_call"
            ),
        )
    )

    rolling_daily = []

    for row in rolling_day_rows:
        daily_payload = {
            key: (
                value
                if key == "usage_day"
                else int(value or 0)
            )
            for key, value
            in dict(row).items()
        }

        daily_totals = {
            key: value
            for key, value
            in daily_payload.items()
            if key != "usage_day"
        }

        rolling_daily.append(
            {
                "usage_day": (
                    daily_payload[
                        "usage_day"
                    ]
                ),
                "totals": daily_totals,
                "metrics": (
                    derived_metrics_resolver(
                        daily_totals
                    )
                ),
            }
        )

    rolling_window = {
        "requested_days": int(days),
        "start_day_utc": (
            window_start_day
        ),
        "end_day_utc": (
            window_end_day
        ),
        "days_with_activity": len(
            rolling_daily
        ),
        "totals": rolling,
        "metrics": rolling_metrics,
        "savings_summary": (
            rolling_savings_summary
        ),
        "mode_metrics": (
            rolling_mode_metrics
        ),
        "daily": rolling_daily,
    }

    default_capacity_policy = (
        capacity_resolver("")
    )
    default_capacity = (
        default_capacity_policy.as_dict()
        if hasattr(
            default_capacity_policy,
            "as_dict",
        )
        else {}
    )

    provider_models = []

    for row in provider_model_rows:
        model_name = str(
            row["model"] or "unknown-model"
        )
        attempts = int(
            row["provider_attempts"]
            or 0
        )
        model_policy = capacity_resolver(
            model_name
        )
        descriptor = (
            model_policy.as_dict()
            if hasattr(
                model_policy,
                "as_dict",
            )
            else {}
        )
        usable_rpd = int(
            descriptor.get(
                "usable_rpd",
                0,
            )
            or 0
        )

        provider_models.append(
            {
                "model": model_name,
                "provider_attempts": attempts,
                "usable_rpd": usable_rpd,
                "rpd_remaining": (
                    None
                    if usable_rpd <= 0
                    else max(
                        0,
                        usable_rpd
                        - attempts,
                    )
                ),
                "policy": descriptor,
            }
        )

    return {
        "generated_at": datetime.now(
            timezone.utc
        ).isoformat(),
        "usage_day_utc": usage_day,
        "provider_capacity": {
            "provider_day": provider_day,
            "provider_timezone": (
                default_capacity.get(
                    "provider_timezone",
                    "America/Los_Angeles",
                )
            ),
            "provider_attempts": (
                provider_attempts
            ),
            "global_daily_call_cap": (
                global_daily_call_cap
            ),
            "global_calls_remaining": (
                global_remaining
            ),
            "client_daily_call_cap": (
                client_daily_call_cap
            ),
            "highest_client_attempts": (
                highest_client_attempts
            ),
            "highest_client_calls_remaining": (
                highest_client_remaining
            ),
            "default_policy": (
                default_capacity
            ),
            "by_model": provider_models,
        },
        "pricing": {
            "currency": "USD",
            "estimate_type": "paid_standard",
            "input_per_million_tokens": (
                input_cost_per_million_usd
            ),
            "output_per_million_tokens": (
                output_cost_per_million_usd
            ),
            "thinking_tokens_billed_as_output": True,
        },
        "today_metrics": today_metrics,
        "savings_summary": savings_summary,
        "rolling_window": rolling_window,
        "limits": {
            "reservation_timeout_seconds": (
                reservation_timeout_seconds
            ),
            "global_daily_call_cap": (
                global_daily_call_cap
            ),
            "client_daily_call_cap": (
                client_daily_call_cap
            ),
            "global_calls_remaining": (
                global_remaining
            ),
            "highest_client_attempts_today": (
                highest_client_attempts
            ),
            "highest_client_calls_remaining": (
                highest_client_remaining
            ),
        },
        "today": today,
        "today_breakdown": [
            {
                "mode": row["mode"],
                "model": row["model"],
                "status": row["status"],
                "cache_hit": bool(
                    row["cache_hit"]
                ),
                "inflight_join": bool(
                    row["inflight_join"]
                ),
                "request_count": int(
                    row["request_count"] or 0
                ),
                "prompt_tokens": int(
                    row["prompt_tokens"] or 0
                ),
                "output_tokens": int(
                    row["output_tokens"] or 0
                ),
                "thought_tokens": int(
                    row["thought_tokens"] or 0
                ),
                "total_tokens": int(
                    row["total_tokens"] or 0
                ),
            }
            for row in breakdown_rows
        ],
        "mode_metrics": mode_metrics,
        "latency_by_mode": [
            {
                "mode": row["mode"],
                "completed_calls": int(
                    row["completed_calls"] or 0
                ),
                "successful_calls": int(
                    row["successful_calls"] or 0
                ),
                "failed_calls": int(
                    row["failed_calls"] or 0
                ),
                "average_latency_ms": int(
                    row["average_latency_ms"] or 0
                ),
                "fastest_latency_ms": int(
                    row["fastest_latency_ms"] or 0
                ),
                "slowest_latency_ms": int(
                    row["slowest_latency_ms"] or 0
                ),
            }
            for row in latency_rows
        ],
        "failure_breakdown": [
            {
                "mode": row["mode"],
                "failure_status_code": (
                    int(
                        row[
                            "failure_status_code"
                        ]
                        or 0
                    )
                ),
                "failure_type": (
                    row["failure_type"]
                ),
                "failure_count": int(
                    row["failure_count"] or 0
                ),
            }
            for row in failure_rows
        ],
        "recent_days": [
            {
                key: (
                    value
                    if key == "usage_day"
                    else int(value or 0)
                )
                for key, value
                in dict(row).items()
            }
            for row in recent_rows
        ],
    }
