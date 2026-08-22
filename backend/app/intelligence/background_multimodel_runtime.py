from __future__ import annotations

import json
import os
from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from typing import Any

from app.ai.orchestration import (
    MULTIMODEL_ORCHESTRATION_VERSION,
    build_specialized_ai_plan,
)
from app.intelligence.claim_support_graph import (
    build_claim_support_graph,
)


BACKGROUND_MULTIMODEL_PLAN_VERSION = "background-multimodel-plan-v1"

_MAX_CLAIMS = 50
_MAX_TASK_COUNT_KEYS = 32

_HOSTED_EMBEDDING_FLAG = "SPORTABASE_EMBEDDING_RUNTIME_ENABLED"
_LOCAL_EMBEDDING_FLAG = "SPORTABASE_LOCAL_EMBEDDING_RUNTIME_ENABLED"
_GEMMA_SHADOW_FLAG = "SPORTABASE_GEMMA_SHADOW_ENABLED"
_PROVENANCE_AGENT_FLAG = "SPORTABASE_PROVENANCE_AGENTS_ENABLED"


class BackgroundMultimodelInputError(ValueError):
    pass


def _clean(value: Any, maximum: int = 256) -> str:
    return " ".join(str(value or "").split())[:maximum]


def _enabled(
    name: str,
    *,
    env_getter: Callable[[str, str], Any],
) -> bool:
    return str(
        env_getter(name, "") or ""
    ).strip().casefold() in {
        "1",
        "true",
        "yes",
        "on",
    }


def _json_object(value: Any) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)

    text = str(value or "").strip()
    if not text:
        return {}

    try:
        parsed = json.loads(text)
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}

    return dict(parsed) if isinstance(parsed, dict) else {}


def _canonical_json(value: Mapping[str, Any]) -> str:
    return json.dumps(
        dict(value),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def _unique_ids(values: Any, *, maximum: int = _MAX_CLAIMS) -> list[str]:
    if not isinstance(values, Sequence) or isinstance(values, (str, bytes)):
        return []

    output: list[str] = []
    seen: set[str] = set()
    for raw in values:
        value = _clean(raw, 128)
        if not value or value in seen:
            continue
        seen.add(value)
        output.append(value)
        if len(output) >= maximum:
            break
    return output


def _claim_rows(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        return []

    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw in value:
        if not isinstance(raw, Mapping):
            continue
        row = dict(raw)
        claim_id = _clean(row.get("id"), 128)
        if not claim_id or claim_id in seen:
            continue
        seen.add(claim_id)
        row["id"] = claim_id
        rows.append(row)
        if len(rows) >= _MAX_CLAIMS:
            break
    return rows


def _verified_independence_floor_counts(
    *,
    claim_states: Sequence[Mapping[str, Any]],
    connection_factory,
) -> dict[str, int]:
    """Return only a conservative lower bound supported by verified provenance.

    A qualified pair proves at least two observations have recorded, verified
    independence provenance. Distinct publishers or reporters are deliberately
    not treated as independent support.
    """
    counts: dict[str, int] = {}

    for raw in claim_states[:_MAX_CLAIMS]:
        row = dict(raw)
        claim_id = _clean(row.get("id"), 128)
        if not claim_id or row.get("structured_identity") is not True:
            continue

        try:
            graph = build_claim_support_graph(
                claim_id=claim_id,
                connection_factory=connection_factory,
            )
        except Exception:
            counts[claim_id] = 0
            continue

        raw_counts = graph.get("counts")
        graph_counts = raw_counts if isinstance(raw_counts, Mapping) else {}
        try:
            qualified_pairs = max(
                0,
                int(graph_counts.get("qualified_verified_independent_pairs") or 0),
            )
        except (TypeError, ValueError, OverflowError):
            qualified_pairs = 0

        counts[claim_id] = 2 if qualified_pairs > 0 else 0

    return counts


def _task_counts(items: Any) -> dict[str, int]:
    if not isinstance(items, list):
        return {}

    counts: Counter[str] = Counter()
    for raw in items:
        if not isinstance(raw, Mapping):
            continue
        task_id = _clean(raw.get("task_id"), 128)
        if task_id:
            counts[task_id] += 1

    return dict(
        sorted(counts.items())[:_MAX_TASK_COUNT_KEYS]
    )


def build_background_multimodel_plan(
    *,
    result: Mapping[str, Any],
    connection_factory,
    env_getter: Callable[[str, str], Any] = os.getenv,
) -> dict[str, Any]:
    if not isinstance(result, Mapping):
        raise BackgroundMultimodelInputError(
            "Background multimodel planning requires a job result."
        )
    if connection_factory is None:
        raise BackgroundMultimodelInputError(
            "Background multimodel planning requires database access."
        )

    if _clean(result.get("status"), 64).casefold() != "completed":
        return {
            "version": BACKGROUND_MULTIMODEL_PLAN_VERSION,
            "orchestration_version": MULTIMODEL_ORCHESTRATION_VERSION,
            "status": "not_applicable",
            "counts": {
                "claims_considered": 0,
                "items": 0,
                "embedding_items": 0,
                "shadow_items": 0,
                "provenance_items": 0,
            },
            "task_counts": {},
            "items": [],
            "policy": {
                "completed_jobs_only": True,
                "provider_call_performed": False,
                "affects_live_merit": False,
            },
        }

    refresh = result.get("intelligence_refresh")
    if not isinstance(refresh, Mapping):
        return {
            "version": BACKGROUND_MULTIMODEL_PLAN_VERSION,
            "orchestration_version": MULTIMODEL_ORCHESTRATION_VERSION,
            "status": "refresh_unavailable",
            "counts": {
                "claims_considered": 0,
                "items": 0,
                "embedding_items": 0,
                "shadow_items": 0,
                "provenance_items": 0,
            },
            "task_counts": {},
            "items": [],
            "policy": {
                "completed_jobs_only": True,
                "provider_call_performed": False,
                "affects_live_merit": False,
            },
        }

    claim_states = _claim_rows(refresh.get("claim_states"))
    payload = result.get("result")
    payload = dict(payload) if isinstance(payload, Mapping) else {}

    hosted_embeddings_enabled = _enabled(
        _HOSTED_EMBEDDING_FLAG,
        env_getter=env_getter,
    )
    local_embeddings_enabled = _enabled(
        _LOCAL_EMBEDDING_FLAG,
        env_getter=env_getter,
    )
    gemma_shadow_enabled = _enabled(
        _GEMMA_SHADOW_FLAG,
        env_getter=env_getter,
    )
    provenance_agents_enabled = _enabled(
        _PROVENANCE_AGENT_FLAG,
        env_getter=env_getter,
    )

    support_counts = (
        _verified_independence_floor_counts(
            claim_states=claim_states,
            connection_factory=connection_factory,
        )
        if provenance_agents_enabled
        else {}
    )

    high_impact_claim_ids = _unique_ids(
        payload.get("high_impact_claim_ids")
    )
    direct_web_inspection_claim_ids = _unique_ids(
        payload.get("direct_web_inspection_claim_ids")
    )

    plan = build_specialized_ai_plan(
        claim_states=claim_states,
        hosted_embeddings_enabled=hosted_embeddings_enabled,
        local_embeddings_enabled=local_embeddings_enabled,
        gemma_shadow_enabled=gemma_shadow_enabled,
        provenance_agents_enabled=provenance_agents_enabled,
        high_impact_claim_ids=high_impact_claim_ids,
        direct_web_inspection_claim_ids=direct_web_inspection_claim_ids,
        independent_source_counts=support_counts,
    )

    items = list(plan.get("items") or [])
    return {
        "version": BACKGROUND_MULTIMODEL_PLAN_VERSION,
        "orchestration_version": _clean(plan.get("version"), 128),
        "status": _clean(plan.get("status"), 64) or "planned",
        "counts": dict(plan.get("counts") or {}),
        "task_counts": _task_counts(items),
        "items": items,
        "feature_gates": {
            "hosted_embeddings": hosted_embeddings_enabled,
            "local_embeddings": local_embeddings_enabled,
            "gemma_shadow": gemma_shadow_enabled,
            "provenance_agents": provenance_agents_enabled,
        },
        "policy": {
            "provider_call_performed": False,
            "deterministic_planning_only": True,
            "background_only": True,
            "structured_identity_required": True,
            "distinct_sources_do_not_imply_independence": True,
            "verified_independence_floor_only": True,
            "high_impact_escalation_requires_explicit_claim_ids": True,
            "direct_web_inspection_requires_explicit_claim_ids": True,
            "shadow_review_is_not_independent_evidence": True,
            "agent_research_is_not_truth_authority": True,
            "affects_live_merit": False,
        },
    }


def persisted_background_multimodel_plan(
    plan: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "version": _clean(plan.get("version"), 128),
        "orchestration_version": _clean(
            plan.get("orchestration_version"),
            128,
        ),
        "status": _clean(plan.get("status"), 64),
        "counts": dict(plan.get("counts") or {}),
        "task_counts": dict(plan.get("task_counts") or {}),
        "feature_gates": dict(plan.get("feature_gates") or {}),
        "policy": dict(plan.get("policy") or {}),
    }


def persist_background_multimodel_plan(
    *,
    result: Mapping[str, Any],
    plan: Mapping[str, Any],
    connection_factory,
) -> dict[str, Any] | None:
    raw_job = result.get("job")
    if not isinstance(raw_job, Mapping):
        return None

    job_id = _clean(raw_job.get("id"), 128)
    if not job_id:
        return None

    conn = connection_factory()
    try:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute(
            "SELECT status, result_json FROM browser_capture_automation_jobs "
            "WHERE id = ?",
            (job_id,),
        ).fetchone()
        if row is None:
            conn.rollback()
            return None

        current = dict(row)
        if _clean(current.get("status"), 64).casefold() != "completed":
            conn.rollback()
            return None

        payload = _json_object(current.get("result_json"))
        payload["specialized_ai_plan"] = persisted_background_multimodel_plan(
            plan
        )

        conn.execute(
            "UPDATE browser_capture_automation_jobs "
            "SET result_json = ? WHERE id = ? AND status = 'completed'",
            (_canonical_json(payload), job_id),
        )
        updated = conn.execute(
            "SELECT * FROM browser_capture_automation_jobs WHERE id = ?",
            (job_id,),
        ).fetchone()
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    return dict(updated) if updated is not None else None


def plan_completed_job_specialized_ai(
    *,
    result: Mapping[str, Any] | None,
    connection_factory,
    env_getter: Callable[[str, str], Any] = os.getenv,
) -> dict[str, Any] | None:
    if not isinstance(result, Mapping):
        return None if result is None else dict(result)

    output = dict(result)
    if _clean(output.get("status"), 64).casefold() != "completed":
        return output

    try:
        plan = build_background_multimodel_plan(
            result=output,
            connection_factory=connection_factory,
            env_getter=env_getter,
        )
    except Exception as error:
        plan = {
            "version": BACKGROUND_MULTIMODEL_PLAN_VERSION,
            "orchestration_version": MULTIMODEL_ORCHESTRATION_VERSION,
            "status": "unavailable",
            "counts": {
                "claims_considered": 0,
                "items": 0,
                "embedding_items": 0,
                "shadow_items": 0,
                "provenance_items": 0,
            },
            "task_counts": {},
            "items": [],
            "feature_gates": {},
            "error_type": type(error).__name__,
            "policy": {
                "provider_call_performed": False,
                "planning_failure_is_advisory": True,
                "job_outcome_not_reclassified": True,
                "affects_live_merit": False,
            },
        }

    output["specialized_ai_plan"] = plan

    try:
        updated_job = persist_background_multimodel_plan(
            result=output,
            plan=plan,
            connection_factory=connection_factory,
        )
    except Exception:
        updated_job = None

    if updated_job is not None:
        output["job"] = updated_job

    raw_result = output.get("result")
    if isinstance(raw_result, Mapping):
        public_result = dict(raw_result)
        public_result["specialized_ai_plan"] = persisted_background_multimodel_plan(
            plan
        )
        output["result"] = public_result

    return output


__all__ = [
    "BACKGROUND_MULTIMODEL_PLAN_VERSION",
    "BackgroundMultimodelInputError",
    "build_background_multimodel_plan",
    "persisted_background_multimodel_plan",
    "persist_background_multimodel_plan",
    "plan_completed_job_specialized_ai",
]
