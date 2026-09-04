from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.intelligence.claim_evolution import reconcile_claim_evolution_safely


INTELLIGENCE_RUNTIME_FINALIZATION_VERSION = (
    "intelligence-runtime-finalization-v1"
)


def _clean(value: Any, maximum: int = 256) -> str:
    return " ".join(str(value or "").split())[:maximum]


def finalize_structured_claim_materialization(
    *,
    materialization: Mapping[str, Any] | None,
    connection_factory,
) -> dict[str, Any]:
    """Reconcile claim evolution after successful canonical materialization.

    This stage is deliberately advisory. A failure to derive historical claim
    evolution must never roll back or invalidate an already successful claim
    materialization.
    """

    value = dict(materialization) if isinstance(materialization, Mapping) else {}
    status = _clean(value.get("status"), 64).casefold()
    claim_id = _clean(value.get("canonical_claim_id"), 128)

    base = {
        "version": INTELLIGENCE_RUNTIME_FINALIZATION_VERSION,
        "canonical_claim_id": claim_id,
        "policy": {
            "runs_only_after_canonical_materialization": True,
            "failure_is_advisory": True,
            "no_provider_call_performed": True,
            "no_model_call_performed": True,
            "story_membership_from_claim_links_only": True,
            "does_not_establish_truth": True,
            "does_not_establish_authority": True,
            "affects_live_merit": False,
        },
    }

    if status != "materialized" or not claim_id:
        return {
            **base,
            "status": "skipped",
            "reason": "canonical_materialization_unavailable",
            "evolution": None,
            "story": None,
        }

    evolution = reconcile_claim_evolution_safely(
        claim_id=claim_id,
        connection_factory=connection_factory,
    )
    evolution_status = _clean(evolution.get("status"), 64).casefold()

    try:
        from app.story.story_claim_graph_materialization import (
            materialize_canonical_claim_story,
        )

        story = materialize_canonical_claim_story(
            claim_id=claim_id,
            connection_factory=connection_factory,
        )
    except Exception as error:
        story = {
            "status": "unavailable",
            "reason": "canonical_claim_story_materialization_failed",
            "error_type": type(error).__name__,
        }

    return {
        **base,
        "status": (
            "completed"
            if evolution_status not in {"unavailable"}
            else "advisory_failure"
        ),
        "reason": (
            "claim_evolution_reconciled"
            if evolution_status not in {"unavailable"}
            else "claim_evolution_unavailable"
        ),
        "story": story,
        "evolution": evolution,
    }


__all__ = [
    "INTELLIGENCE_RUNTIME_FINALIZATION_VERSION",
    "finalize_structured_claim_materialization",
]
