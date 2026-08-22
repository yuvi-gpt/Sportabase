from __future__ import annotations

from typing import Any

from app.intelligence.claim_evolution import reconcile_claim_evolution_safely


CLAIM_EVOLUTION_BACKFILL_VERSION = "claim-evolution-backfill-v1"
_DEFAULT_LIMIT = 5000
_MAX_LIMIT = 50000


def _normalize_limit(value: Any) -> int:
    try:
        limit = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("Claim evolution backfill limit must be an integer.") from exc
    if limit < 1 or limit > _MAX_LIMIT:
        raise ValueError(
            f"Claim evolution backfill limit must be between 1 and {_MAX_LIMIT}."
        )
    return limit


def run_claim_evolution_backfill(
    *,
    connection_factory,
    limit: int = _DEFAULT_LIMIT,
    apply: bool = False,
) -> dict[str, Any]:
    """Plan or execute an idempotent reconciliation pass for stored claims.

    Dry-run is the default. The report intentionally exposes counts rather than
    claim IDs or stored text so it is safe to use in staging diagnostics.
    """

    if connection_factory is None:
        raise ValueError("Claim evolution backfill requires database access.")
    bounded_limit = _normalize_limit(limit)

    conn = connection_factory()
    try:
        rows = conn.execute(
            """
            SELECT id
            FROM intelligence_claims
            WHERE claim_type LIKE 'structured_%'
            ORDER BY first_seen_at, id
            LIMIT ?
            """,
            (bounded_limit + 1,),
        ).fetchall()
    finally:
        conn.close()

    truncated = len(rows) > bounded_limit
    rows = rows[:bounded_limit]
    claim_ids = [
        str(row["id"] if hasattr(row, "keys") else row[0])
        for row in rows
    ]

    base = {
        "version": CLAIM_EVOLUTION_BACKFILL_VERSION,
        "status": "planned" if not apply else "completed",
        "apply": bool(apply),
        "counts": {
            "claims_selected": len(claim_ids),
            "reconciled": 0,
            "no_prior_claims": 0,
            "not_reconciled": 0,
            "not_found": 0,
            "unavailable": 0,
            "other": 0,
        },
        "selection": {
            "limit": bounded_limit,
            "truncated": truncated,
        },
        "policy": {
            "dry_run_default": True,
            "bounded_scan": True,
            "idempotent_reconciliation": True,
            "claim_ids_returned": False,
            "raw_content_returned": False,
            "no_provider_call_performed": True,
            "no_model_call_performed": True,
            "affects_live_merit": False,
        },
    }

    if not apply:
        return base

    counts = dict(base["counts"])
    for claim_id in claim_ids:
        result = reconcile_claim_evolution_safely(
            claim_id=claim_id,
            connection_factory=connection_factory,
        )
        status = str(result.get("status") or "").strip().casefold()
        if status in counts:
            counts[status] += 1
        else:
            counts["other"] += 1

    return {
        **base,
        "counts": counts,
    }


__all__ = [
    "CLAIM_EVOLUTION_BACKFILL_VERSION",
    "run_claim_evolution_backfill",
]
