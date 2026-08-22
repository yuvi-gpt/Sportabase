from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Mapping, Sequence

from app.ai.tasks import (
    AGENTIC_PROVENANCE_INSPECTION,
    CLAIM_DEEP_SHADOW_REVIEW,
    CLAIM_SHADOW_REVIEW,
    LOCAL_RETRIEVAL_EMBEDDING,
    PROVENANCE_RESEARCH,
    PROVENANCE_RESEARCH_MAX,
    RETRIEVAL_EMBEDDING,
)


MULTIMODEL_ORCHESTRATION_VERSION = "google-multimodel-orchestration-v1"

_CONFLICT_STATES = {
    "adjudication_history_conflict",
    "claim_conflict_present",
}

_MAX_CLAIMS = 50
_MAX_PLAN_ITEMS = 100


@dataclass(frozen=True)
class SpecializedPlanItem:
    task_id: str
    subject_id: str
    reason: str
    priority: int
    background_only: bool
    provider_optional: bool

    def as_dict(self) -> dict[str, object]:
        return {
            "task_id": self.task_id,
            "subject_id": self.subject_id,
            "reason": self.reason,
            "priority": int(self.priority),
            "background_only": bool(self.background_only),
            "provider_optional": bool(self.provider_optional),
        }


def _clean(value: Any, maximum: int = 256) -> str:
    return " ".join(str(value or "").split())[:maximum]


def _bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().casefold() in {
        "1",
        "true",
        "yes",
        "on",
    }


def _safe_int(value: Any) -> int:
    if isinstance(value, bool):
        return 0
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError, OverflowError):
        return 0


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


def _append_unique(
    items: list[SpecializedPlanItem],
    *,
    task_id: str,
    subject_id: str,
    reason: str,
    priority: int,
    background_only: bool,
    provider_optional: bool,
) -> None:
    key = (task_id, subject_id)
    if any((item.task_id, item.subject_id) == key for item in items):
        return
    if len(items) >= _MAX_PLAN_ITEMS:
        return
    items.append(
        SpecializedPlanItem(
            task_id=task_id,
            subject_id=subject_id,
            reason=_clean(reason, 256),
            priority=max(1, min(100, int(priority))),
            background_only=background_only,
            provider_optional=provider_optional,
        )
    )


def build_specialized_ai_plan(
    *,
    claim_states: Any,
    hosted_embeddings_enabled: bool = False,
    local_embeddings_enabled: bool = False,
    gemma_shadow_enabled: bool = False,
    provenance_agents_enabled: bool = False,
    high_impact_claim_ids: Sequence[str] = (),
    direct_web_inspection_claim_ids: Sequence[str] = (),
    independent_source_counts: Mapping[str, Any] | None = None,
    max_research_independent_sources: int = 1,
) -> dict[str, Any]:
    """Build a bounded, deterministic plan for specialized Google AI work.

    This function does not execute providers and does not mutate intelligence
    state. It decides which already-implemented specialized runtime should be
    considered after the normal deterministic intelligence refresh.
    """
    rows = _claim_rows(claim_states)
    high_impact = {
        _clean(value, 128)
        for value in high_impact_claim_ids
        if _clean(value, 128)
    }
    direct_web = {
        _clean(value, 128)
        for value in direct_web_inspection_claim_ids
        if _clean(value, 128)
    }
    source_counts = dict(independent_source_counts or {})
    research_threshold = max(0, min(10, _safe_int(max_research_independent_sources)))

    items: list[SpecializedPlanItem] = []

    for row in rows:
        claim_id = row["id"]
        structured = _bool(row.get("structured_identity"))
        state = _clean(row.get("projection_state"), 128).casefold()
        freshness = _clean(row.get("freshness_state"), 64).casefold()
        conflict = state in _CONFLICT_STATES
        is_high_impact = claim_id in high_impact
        needs_direct_web = claim_id in direct_web
        independent_sources = _safe_int(source_counts.get(claim_id))

        if structured and hosted_embeddings_enabled:
            _append_unique(
                items,
                task_id=RETRIEVAL_EMBEDDING,
                subject_id=claim_id,
                reason="structured canonical claim semantic retrieval index",
                priority=25,
                background_only=True,
                provider_optional=True,
            )
        elif structured and local_embeddings_enabled:
            _append_unique(
                items,
                task_id=LOCAL_RETRIEVAL_EMBEDDING,
                subject_id=claim_id,
                reason="structured canonical claim local semantic retrieval index",
                priority=25,
                background_only=True,
                provider_optional=True,
            )

        if structured and gemma_shadow_enabled and conflict:
            shadow_task = (
                CLAIM_DEEP_SHADOW_REVIEW
                if is_high_impact
                else CLAIM_SHADOW_REVIEW
            )
            _append_unique(
                items,
                task_id=shadow_task,
                subject_id=claim_id,
                reason=(
                    "high-impact conflicting structured claim second-model review"
                    if is_high_impact
                    else "conflicting structured claim second-model review"
                ),
                priority=80 if is_high_impact else 60,
                background_only=True,
                provider_optional=True,
            )

        should_research = (
            structured
            and provenance_agents_enabled
            and (
                conflict
                or freshness == "stale"
                or is_high_impact
            )
            and independent_sources <= research_threshold
        )
        if should_research:
            research_task = (
                PROVENANCE_RESEARCH_MAX
                if conflict and is_high_impact
                else PROVENANCE_RESEARCH
            )
            _append_unique(
                items,
                task_id=research_task,
                subject_id=claim_id,
                reason=(
                    "high-impact conflict with insufficient independent provenance"
                    if research_task == PROVENANCE_RESEARCH_MAX
                    else "claim needs additional independent provenance"
                ),
                priority=95 if research_task == PROVENANCE_RESEARCH_MAX else 70,
                background_only=True,
                provider_optional=False,
            )

        if structured and provenance_agents_enabled and needs_direct_web:
            _append_unique(
                items,
                task_id=AGENTIC_PROVENANCE_INSPECTION,
                subject_id=claim_id,
                reason="explicit direct public-web provenance inspection required",
                priority=90,
                background_only=True,
                provider_optional=False,
            )

    items.sort(
        key=lambda item: (
            -item.priority,
            item.task_id,
            item.subject_id,
        )
    )

    return {
        "version": MULTIMODEL_ORCHESTRATION_VERSION,
        "status": "planned",
        "counts": {
            "claims_considered": len(rows),
            "items": len(items),
            "embedding_items": sum(
                item.task_id in {
                    RETRIEVAL_EMBEDDING,
                    LOCAL_RETRIEVAL_EMBEDDING,
                }
                for item in items
            ),
            "shadow_items": sum(
                item.task_id in {
                    CLAIM_SHADOW_REVIEW,
                    CLAIM_DEEP_SHADOW_REVIEW,
                }
                for item in items
            ),
            "provenance_items": sum(
                item.task_id in {
                    PROVENANCE_RESEARCH,
                    PROVENANCE_RESEARCH_MAX,
                    AGENTIC_PROVENANCE_INSPECTION,
                }
                for item in items
            ),
        },
        "items": [item.as_dict() for item in items],
        "policy": {
            "provider_call_performed": False,
            "deterministic_planning_only": True,
            "background_only": True,
            "structured_identity_required": True,
            "embedding_is_not_truth": True,
            "shadow_review_is_not_independent_evidence": True,
            "agent_research_is_not_truth_authority": True,
            "affects_live_merit": False,
            "automatic_escalation_requires_explicit_feature_enablement": True,
        },
    }


def execute_specialized_ai_plan(
    plan: Mapping[str, Any],
    *,
    executors: Mapping[str, Callable[[Mapping[str, Any]], Any]],
    allow_provider_execution: bool = False,
) -> dict[str, Any]:
    """Execute an explicit plan through injected task executors.

    There is intentionally no default provider executor. Callers must opt in
    and supply an executor for every selected task, which keeps expensive model
    use auditable and prevents the planner from silently creating provider
    traffic.
    """
    if not allow_provider_execution:
        raise RuntimeError(
            "Specialized AI plan execution is disabled by default."
        )

    raw_items = plan.get("items") if isinstance(plan, Mapping) else None
    if not isinstance(raw_items, list):
        raise ValueError("Specialized AI plan items are required.")

    observations: list[dict[str, Any]] = []
    for raw in raw_items[:_MAX_PLAN_ITEMS]:
        if not isinstance(raw, Mapping):
            continue
        item = dict(raw)
        task_id = _clean(item.get("task_id"), 128)
        subject_id = _clean(item.get("subject_id"), 128)
        executor = executors.get(task_id)
        if not callable(executor):
            observations.append(
                {
                    "task_id": task_id,
                    "subject_id": subject_id,
                    "status": "blocked",
                    "failure_type": "executor_unavailable",
                }
            )
            continue

        try:
            output = executor(item)
            observations.append(
                {
                    "task_id": task_id,
                    "subject_id": subject_id,
                    "status": "completed",
                    "output": output,
                }
            )
        except Exception as error:
            observations.append(
                {
                    "task_id": task_id,
                    "subject_id": subject_id,
                    "status": "failed",
                    "failure_type": type(error).__name__,
                    "failure_detail": _clean(error, 500),
                }
            )

    completed = sum(item.get("status") == "completed" for item in observations)
    failed = sum(item.get("status") == "failed" for item in observations)
    blocked = sum(item.get("status") == "blocked" for item in observations)

    return {
        "version": MULTIMODEL_ORCHESTRATION_VERSION,
        "status": "completed" if not failed and not blocked else "partial",
        "counts": {
            "completed": completed,
            "failed": failed,
            "blocked": blocked,
        },
        "observations": observations,
        "policy": {
            "explicit_execution_opt_in": True,
            "injected_executors_only": True,
            "planner_does_not_establish_truth": True,
            "affects_live_merit": False,
        },
    }


__all__ = [
    "MULTIMODEL_ORCHESTRATION_VERSION",
    "SpecializedPlanItem",
    "build_specialized_ai_plan",
    "execute_specialized_ai_plan",
]
