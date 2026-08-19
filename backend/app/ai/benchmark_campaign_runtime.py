from __future__ import annotations

import sqlite3

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Mapping

from app.ai.evaluation import EvaluationPlan
from app.ai.quota import capacity_policy_for_model


GENERATION_CAMPAIGN_EXECUTION_VERSION = (
    "sportabase-google-generation-campaign-execution-v1"
)

GENERATION_CAMPAIGN_CLIENT_KEY = "sportabase-generation-campaign"

TRUE_PROVIDER_STATUSES = (
    "reserved",
    "success",
    "failed",
    "expired",
)


@dataclass(frozen=True)
class CampaignDailyUsageSnapshot:
    provider_day: str
    global_count: int
    client_count: int
    model_counts: Mapping[str, int]
    global_daily_call_cap: int
    client_daily_call_cap: int

    def as_dict(self) -> dict[str, object]:
        return {
            "provider_day": self.provider_day,
            "global_count": int(self.global_count),
            "client_count": int(self.client_count),
            "model_counts": dict(self.model_counts),
            "global_daily_call_cap": int(self.global_daily_call_cap),
            "client_daily_call_cap": int(self.client_daily_call_cap),
        }


@dataclass(frozen=True)
class CampaignExecutionPreflight:
    version: str
    provider_day: str
    planned_provider_calls: int
    required_calls_by_model: Mapping[str, int]
    global_remaining_before_campaign: int
    client_remaining_before_campaign: int
    model_remaining_before_campaign: Mapping[str, int]
    capacity_blocked_resource_ids: tuple[str, ...]
    allowed: bool
    reasons: tuple[str, ...]

    def as_dict(self) -> dict[str, object]:
        return {
            "version": self.version,
            "provider_day": self.provider_day,
            "planned_provider_calls": int(self.planned_provider_calls),
            "required_calls_by_model": dict(self.required_calls_by_model),
            "global_remaining_before_campaign": int(
                self.global_remaining_before_campaign
            ),
            "client_remaining_before_campaign": int(
                self.client_remaining_before_campaign
            ),
            "model_remaining_before_campaign": dict(
                self.model_remaining_before_campaign
            ),
            "capacity_blocked_resource_ids": list(
                self.capacity_blocked_resource_ids
            ),
            "allowed": bool(self.allowed),
            "reasons": list(self.reasons),
        }


def campaign_required_calls_by_model(
    plan: EvaluationPlan,
) -> dict[str, int]:
    counts: dict[str, int] = {}

    for item in plan.items:
        counts[item.resource_id] = counts.get(item.resource_id, 0) + 1

    return dict(counts)


def load_campaign_daily_usage_snapshot(
    *,
    db_path: str | Path,
    provider_day: str,
    client_key: str,
    resource_ids: tuple[str, ...],
    global_daily_call_cap: int,
    client_daily_call_cap: int,
) -> CampaignDailyUsageSnapshot:
    statuses = TRUE_PROVIDER_STATUSES
    placeholders = ",".join("?" for _ in statuses)

    conn = sqlite3.connect(str(db_path))

    try:
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
                    *statuses,
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
                    *statuses,
                ),
            ).fetchone()[0]
        )

        model_counts: dict[str, int] = {}

        for resource_id in resource_ids:
            model_counts[resource_id] = int(
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
                        resource_id,
                        *statuses,
                    ),
                ).fetchone()[0]
            )

    finally:
        conn.close()

    return CampaignDailyUsageSnapshot(
        provider_day=str(provider_day),
        global_count=max(0, global_count),
        client_count=max(0, client_count),
        model_counts=model_counts,
        global_daily_call_cap=max(0, int(global_daily_call_cap)),
        client_daily_call_cap=max(0, int(client_daily_call_cap)),
    )


def evaluate_campaign_execution_preflight(
    plan: EvaluationPlan,
    *,
    snapshot: CampaignDailyUsageSnapshot,
    policy_resolver: Callable[[object], object] = capacity_policy_for_model,
) -> CampaignExecutionPreflight:
    required_calls = campaign_required_calls_by_model(plan)
    planned_calls = int(plan.planned_provider_calls)

    reasons: list[str] = []

    blocked_resources = tuple(
        sorted(
            {
                item.resource_id
                for item in plan.items
                if item.capacity_blocked
            }
        )
    )

    if blocked_resources:
        reasons.append(
            "Project capacity is not configured for: "
            + ", ".join(blocked_resources)
            + "."
        )

    if any(item.automatic_fallback_enabled for item in plan.items):
        reasons.append(
            "Automatic fallback must remain disabled for campaign evaluation."
        )

    global_remaining = max(
        0,
        int(snapshot.global_daily_call_cap) - int(snapshot.global_count),
    )
    client_remaining = max(
        0,
        int(snapshot.client_daily_call_cap) - int(snapshot.client_count),
    )

    if planned_calls > global_remaining:
        reasons.append(
            "Campaign does not fit the remaining Sportabase global daily "
            f"call cap: requires {planned_calls}, remaining {global_remaining}."
        )

    if planned_calls > client_remaining:
        reasons.append(
            "Campaign does not fit the remaining campaign-client daily "
            f"call cap: requires {planned_calls}, remaining {client_remaining}."
        )

    model_remaining: dict[str, int] = {}

    for resource_id, required in required_calls.items():
        policy = policy_resolver(resource_id)
        usable_rpd = max(0, int(getattr(policy, "usable_rpd")))
        used = max(0, int(snapshot.model_counts.get(resource_id, 0)))
        remaining = max(0, usable_rpd - used)
        model_remaining[resource_id] = remaining

        if int(required) > remaining:
            reasons.append(
                "Campaign does not fit the remaining model daily envelope for "
                f"{resource_id}: requires {required}, remaining {remaining}."
            )

    return CampaignExecutionPreflight(
        version=GENERATION_CAMPAIGN_EXECUTION_VERSION,
        provider_day=snapshot.provider_day,
        planned_provider_calls=planned_calls,
        required_calls_by_model=required_calls,
        global_remaining_before_campaign=global_remaining,
        client_remaining_before_campaign=client_remaining,
        model_remaining_before_campaign=model_remaining,
        capacity_blocked_resource_ids=blocked_resources,
        allowed=not reasons,
        reasons=tuple(reasons),
    )


__all__ = [
    "GENERATION_CAMPAIGN_EXECUTION_VERSION",
    "GENERATION_CAMPAIGN_CLIENT_KEY",
    "TRUE_PROVIDER_STATUSES",
    "CampaignDailyUsageSnapshot",
    "CampaignExecutionPreflight",
    "campaign_required_calls_by_model",
    "load_campaign_daily_usage_snapshot",
    "evaluate_campaign_execution_preflight",
]
