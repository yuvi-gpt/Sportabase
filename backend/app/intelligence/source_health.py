from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Callable


SOURCE_EVIDENCE_HEALTH_VERSION = (
    "source-evidence-health-v1"
)


def _clean(value: Any, maximum: int = 256) -> str:
    return " ".join(str(value or "").split())[:maximum]


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat()


def _count(row: dict[str, Any], key: str) -> int:
    try:
        return max(0, int(row.get(key) or 0))
    except (TypeError, ValueError):
        return 0


def build_source_evidence_health(
    *,
    connection_factory,
    days: int = 30,
    now_provider: Callable[[], datetime] = _utc_now,
) -> dict[str, Any]:
    if connection_factory is None:
        raise ValueError(
            "Source evidence health requires database access."
        )

    try:
        window_days = int(days)
    except (TypeError, ValueError) as exc:
        raise ValueError("Source evidence health days must be an integer.") from exc

    if window_days < 1 or window_days > 365:
        raise ValueError("Source evidence health days must be between 1 and 365.")

    now_value = now_provider()
    if not isinstance(now_value, datetime):
        raise ValueError("Source evidence health clock must return a datetime.")
    if now_value.tzinfo is None:
        now_value = now_value.replace(tzinfo=timezone.utc)

    cutoff = now_value.astimezone(timezone.utc) - timedelta(days=window_days)
    cutoff_iso = _iso(cutoff)

    conn = connection_factory()
    try:
        source_rows = [
            dict(row)
            for row in conn.execute(
                """
                WITH
                media_counts AS (
                  SELECT
                    source_id,
                    COUNT(*) AS media_items
                  FROM media_items
                  WHERE source_id IS NOT NULL
                  GROUP BY source_id
                ),
                observation_counts AS (
                  SELECT
                    source_id,
                    COUNT(*) AS observations,
                    MAX(observed_at) AS last_observation_at
                  FROM source_observations
                  WHERE observed_at >= ?
                  GROUP BY source_id
                ),
                source_evidence AS (
                  SELECT
                    source_id,
                    evidence_id
                  FROM evidence_links
                  WHERE source_id IS NOT NULL

                  UNION

                  SELECT
                    m.source_id AS source_id,
                    el.evidence_id AS evidence_id
                  FROM evidence_links AS el
                  JOIN media_items AS m
                    ON m.id = el.media_item_id
                  WHERE
                    el.media_item_id IS NOT NULL
                    AND m.source_id IS NOT NULL
                ),
                evidence_counts AS (
                  SELECT
                    se.source_id,
                    COUNT(DISTINCT se.evidence_id) AS evidence_records,
                    COUNT(DISTINCT CASE
                      WHEN e.verification_status = 'verified'
                      THEN se.evidence_id
                    END) AS verified_evidence_records,
                    MAX(e.observed_at) AS last_evidence_at
                  FROM source_evidence AS se
                  JOIN evidence_records AS e
                    ON e.id = se.evidence_id
                  WHERE e.observed_at >= ?
                  GROUP BY se.source_id
                ),
                binding_counts AS (
                  SELECT
                    source_id,
                    COUNT(*) AS verified_entity_bindings,
                    MAX(observed_at) AS last_verified_binding_at
                  FROM verified_source_entity_bindings
                  WHERE observed_at >= ?
                  GROUP BY source_id
                )
                SELECT
                  s.id,
                  s.source_key,
                  s.display_name,
                  s.source_type,
                  s.canonical_domain,
                  s.first_seen_at,
                  s.last_seen_at,
                  COALESCE(m.media_items, 0) AS media_items,
                  COALESCE(o.observations, 0) AS observations,
                  o.last_observation_at,
                  COALESCE(e.evidence_records, 0) AS evidence_records,
                  COALESCE(e.verified_evidence_records, 0)
                    AS verified_evidence_records,
                  e.last_evidence_at,
                  COALESCE(b.verified_entity_bindings, 0)
                    AS verified_entity_bindings,
                  b.last_verified_binding_at
                FROM intelligence_sources AS s
                LEFT JOIN media_counts AS m
                  ON m.source_id = s.id
                LEFT JOIN observation_counts AS o
                  ON o.source_id = s.id
                LEFT JOIN evidence_counts AS e
                  ON e.source_id = s.id
                LEFT JOIN binding_counts AS b
                  ON b.source_id = s.id
                ORDER BY
                  s.last_seen_at DESC,
                  s.canonical_domain,
                  s.id
                """,
                (
                    cutoff_iso,
                    cutoff_iso,
                    cutoff_iso,
                ),
            ).fetchall()
        ]

        evidence_status_rows = [
            dict(row)
            for row in conn.execute(
                """
                SELECT
                  verification_status,
                  COUNT(*) AS count
                FROM evidence_records
                WHERE observed_at >= ?
                GROUP BY verification_status
                ORDER BY verification_status
                """,
                (cutoff_iso,),
            ).fetchall()
        ]

        entity_counts = dict(
            conn.execute(
                """
                SELECT
                  COUNT(*) AS canonical_entities,
                  (
                    SELECT COUNT(*)
                    FROM entity_aliases
                  ) AS entity_aliases,
                  (
                    SELECT COUNT(*)
                    FROM verified_claim_entity_participants
                  ) AS verified_claim_entity_participants
                FROM canonical_entities
                """
            ).fetchone()
        )
    finally:
        conn.close()

    sources: list[dict[str, Any]] = []
    aggregate = {
        "sources": 0,
        "sources_with_media": 0,
        "sources_with_observations": 0,
        "sources_with_evidence": 0,
        "sources_with_verified_evidence": 0,
        "sources_with_verified_entity_bindings": 0,
        "media_items": 0,
        "observations": 0,
        "evidence_records": 0,
        "verified_evidence_records": 0,
        "verified_entity_bindings": 0,
    }

    for row in source_rows:
        media_items = _count(row, "media_items")
        observations = _count(row, "observations")
        evidence_records = _count(row, "evidence_records")
        verified_evidence = _count(row, "verified_evidence_records")
        verified_bindings = _count(row, "verified_entity_bindings")

        if verified_bindings > 0:
            coverage_state = "verified_identity_binding_observed"
        elif evidence_records > 0:
            coverage_state = "evidence_observed"
        elif observations > 0 or media_items > 0:
            coverage_state = "observation_only"
        else:
            coverage_state = "unobserved"

        latest_signal = max(
            (
                _clean(row.get("last_seen_at"), 128),
                _clean(row.get("last_observation_at"), 128),
                _clean(row.get("last_evidence_at"), 128),
                _clean(row.get("last_verified_binding_at"), 128),
            ),
            default="",
        )

        freshness_state = (
            "within_window"
            if latest_signal and latest_signal >= cutoff_iso
            else "outside_window"
        )

        sources.append({
            "source_id": _clean(row.get("id"), 128),
            "source_key": _clean(row.get("source_key"), 256),
            "display_name": _clean(row.get("display_name"), 256),
            "source_type": _clean(row.get("source_type"), 64),
            "canonical_domain": _clean(row.get("canonical_domain"), 256),
            "first_seen_at": _clean(row.get("first_seen_at"), 128),
            "last_seen_at": _clean(row.get("last_seen_at"), 128),
            "last_observation_at": _clean(row.get("last_observation_at"), 128),
            "last_evidence_at": _clean(row.get("last_evidence_at"), 128),
            "last_verified_binding_at": _clean(
                row.get("last_verified_binding_at"),
                128,
            ),
            "counts": {
                "media_items": media_items,
                "observations": observations,
                "evidence_records": evidence_records,
                "verified_evidence_records": verified_evidence,
                "verified_entity_bindings": verified_bindings,
            },
            "coverage_state": coverage_state,
            "freshness_state": freshness_state,
        })

        aggregate["sources"] += 1
        aggregate["media_items"] += media_items
        aggregate["observations"] += observations
        aggregate["evidence_records"] += evidence_records
        aggregate["verified_evidence_records"] += verified_evidence
        aggregate["verified_entity_bindings"] += verified_bindings
        aggregate["sources_with_media"] += int(media_items > 0)
        aggregate["sources_with_observations"] += int(observations > 0)
        aggregate["sources_with_evidence"] += int(evidence_records > 0)
        aggregate["sources_with_verified_evidence"] += int(verified_evidence > 0)
        aggregate["sources_with_verified_entity_bindings"] += int(
            verified_bindings > 0
        )

    evidence_by_status = {
        _clean(row.get("verification_status"), 64) or "unknown": _count(
            row,
            "count",
        )
        for row in evidence_status_rows
    }

    return {
        "version": SOURCE_EVIDENCE_HEALTH_VERSION,
        "status": "ok",
        "window": {
            "days": window_days,
            "cutoff_utc": cutoff_iso,
            "generated_at_utc": _iso(now_value),
        },
        "aggregate": aggregate,
        "evidence_by_verification_status": evidence_by_status,
        "entities": {
            "canonical_entities": _count(entity_counts, "canonical_entities"),
            "entity_aliases": _count(entity_counts, "entity_aliases"),
            "verified_claim_entity_participants": _count(
                entity_counts,
                "verified_claim_entity_participants",
            ),
        },
        "sources": sources,
        "policy": {
            "coverage_is_observability_not_truth": True,
            "verified_evidence_status_is_not_claim_truth": True,
            "verified_entity_binding_is_identity_provenance_only": True,
            "missing_evidence_is_reported_not_inferred": True,
            "affects_live_merit": False,
        },
    }


__all__ = [
    "SOURCE_EVIDENCE_HEALTH_VERSION",
    "build_source_evidence_health",
]
