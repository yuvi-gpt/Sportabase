from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any

from app.intelligence.claim_support_graph import build_claim_support_graph


CLAIM_STATE_VERSION = "claim-state-v2"
STORY_CLAIM_STATE_VERSION = "story-claim-state-v2"

_SUPPORT_RELATIONSHIPS = {
    "supports",
    "support",
    "confirms",
    "confirm",
    "corroborates",
    "corroborate",
    "verifies",
    "verify",
}
_CONFLICT_RELATIONSHIPS = {
    "contradicts",
    "contradict",
    "refutes",
    "refute",
    "disputes",
    "dispute",
    "denies",
    "deny",
    "counterevidence",
    "counter_evidence",
}


def _clean(value: Any, maximum: int = 512) -> str:
    return " ".join(str(value or "").split())[:maximum]


def _relationship_family(value: Any) -> str:
    relationship = _clean(value, 64).casefold()
    if relationship in _SUPPORT_RELATIONSHIPS:
        return "support"
    if relationship in _CONFLICT_RELATIONSHIPS:
        return "conflict"
    return "other"


def _claim_evidence_rows(*, claim_id: str, connection_factory) -> list[dict[str, Any]]:
    conn = connection_factory()
    try:
        rows = conn.execute(
            """
            SELECT
              cl.id AS claim_link_id,
              cl.relationship_type,
              cl.confidence AS link_confidence,
              cl.observed_at AS link_observed_at,
              e.id AS evidence_id,
              e.evidence_type,
              e.subject_key AS evidence_subject_key,
              e.verification_status,
              e.published_at,
              e.observed_at AS evidence_observed_at
            FROM claim_links AS cl
            JOIN evidence_records AS e
              ON e.id = cl.evidence_id
            WHERE cl.claim_id = ?
              AND cl.evidence_id IS NOT NULL
            ORDER BY e.observed_at, e.id, cl.id
            """,
            (claim_id,),
        ).fetchall()
    finally:
        conn.close()
    return [dict(row) for row in rows]


def _history_rows(
    *,
    table: str,
    identity_column: str,
    identity_ids: list[str],
    subject_key: str,
    connection_factory,
) -> list[dict[str, Any]]:
    if not identity_ids:
        return []

    results: list[dict[str, Any]] = []
    for start in range(0, len(identity_ids), 300):
        chunk = identity_ids[start : start + 300]
        placeholders = ",".join("?" for _ in chunk)
        conn = connection_factory()
        try:
            rows = conn.execute(
                f"""
                SELECT
                  {identity_column} AS identity_id,
                  observation_type,
                  status,
                  COUNT(*) AS observation_count,
                  MIN(observed_at) AS first_observed_at,
                  MAX(observed_at) AS last_observed_at
                FROM {table}
                WHERE {identity_column} IN ({placeholders})
                  AND subject_key = ?
                GROUP BY {identity_column}, observation_type, status
                ORDER BY {identity_column}, observation_type, status
                """,
                tuple(chunk) + (subject_key,),
            ).fetchall()
        finally:
            conn.close()
        results.extend(dict(row) for row in rows)
    return results


def _build_history(
    *,
    rows: list[dict[str, Any]],
    labels: dict[str, dict[str, str]],
) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}
    for row in rows:
        identity_id = _clean(row.get("identity_id"), 128)
        if not identity_id:
            continue
        record = grouped.setdefault(
            identity_id,
            {
                "identity_id": identity_id,
                **labels.get(identity_id, {}),
                "observation_count": 0,
                "first_observed_at": "",
                "last_observed_at": "",
                "by_observation_type": Counter(),
                "by_status": Counter(),
            },
        )
        try:
            count = max(0, int(row.get("observation_count") or 0))
        except (TypeError, ValueError):
            count = 0
        record["observation_count"] += count
        observation_type = _clean(row.get("observation_type"), 64) or "unknown"
        status = _clean(row.get("status"), 64) or "unknown"
        record["by_observation_type"][observation_type] += count
        record["by_status"][status] += count
        first_seen = _clean(row.get("first_observed_at"), 128)
        last_seen = _clean(row.get("last_observed_at"), 128)
        if first_seen and (
            not record["first_observed_at"] or first_seen < record["first_observed_at"]
        ):
            record["first_observed_at"] = first_seen
        if last_seen and last_seen > record["last_observed_at"]:
            record["last_observed_at"] = last_seen

    result = []
    for identity_id in sorted(grouped):
        item = grouped[identity_id]
        item["by_observation_type"] = dict(sorted(item["by_observation_type"].items()))
        item["by_status"] = dict(sorted(item["by_status"].items()))
        result.append(item)
    return result


def _source_labels(*, source_ids: list[str], connection_factory) -> dict[str, dict[str, str]]:
    if not source_ids:
        return {}
    labels: dict[str, dict[str, str]] = {}
    for start in range(0, len(source_ids), 300):
        chunk = source_ids[start : start + 300]
        placeholders = ",".join("?" for _ in chunk)
        conn = connection_factory()
        try:
            rows = conn.execute(
                "SELECT id, source_key, display_name, source_type, canonical_domain "
                f"FROM intelligence_sources WHERE id IN ({placeholders})",
                tuple(chunk),
            ).fetchall()
        finally:
            conn.close()
        for row in rows:
            item = dict(row)
            labels[_clean(item.get("id"), 128)] = {
                "source_key": _clean(item.get("source_key"), 256),
                "display_name": _clean(item.get("display_name"), 256),
                "source_type": _clean(item.get("source_type"), 64),
                "canonical_domain": _clean(item.get("canonical_domain"), 256),
            }
    return labels


def _reporter_labels(
    *, reporter_ids: list[str], connection_factory
) -> dict[str, dict[str, str]]:
    if not reporter_ids:
        return {}
    labels: dict[str, dict[str, str]] = {}
    for start in range(0, len(reporter_ids), 300):
        chunk = reporter_ids[start : start + 300]
        placeholders = ",".join("?" for _ in chunk)
        conn = connection_factory()
        try:
            rows = conn.execute(
                "SELECT id, identity_key, display_name "
                f"FROM intelligence_reporters WHERE id IN ({placeholders})",
                tuple(chunk),
            ).fetchall()
        finally:
            conn.close()
        for row in rows:
            item = dict(row)
            labels[_clean(item.get("id"), 128)] = {
                "identity_key": _clean(item.get("identity_key"), 256),
                "display_name": _clean(item.get("display_name"), 256),
            }
    return labels


def _evidence_posture(rows: list[dict[str, Any]]) -> dict[str, Any]:
    records: list[dict[str, Any]] = []
    counts = Counter()
    verified_types = Counter()

    for row in rows:
        family = _relationship_family(row.get("relationship_type"))
        verification_status = _clean(row.get("verification_status"), 64).casefold()
        verified = verification_status == "verified"
        evidence_type = _clean(row.get("evidence_type"), 64) or "unknown"
        counts[f"{family}_{'verified' if verified else 'unverified'}"] += 1
        counts["total"] += 1
        if verified:
            counts["verified_total"] += 1
            verified_types[evidence_type] += 1
        else:
            counts["unverified_total"] += 1

        records.append(
            {
                "evidence_id": _clean(row.get("evidence_id"), 128),
                "evidence_type": evidence_type,
                "subject_key": _clean(row.get("evidence_subject_key"), 256),
                "verification_status": verification_status or "unknown",
                "relationship_type": _clean(row.get("relationship_type"), 64),
                "relationship_family": family,
                "published_at": _clean(row.get("published_at"), 128),
                "observed_at": _clean(row.get("evidence_observed_at"), 128),
            }
        )

    return {
        "counts": {
            "total": counts["total"],
            "verified_total": counts["verified_total"],
            "unverified_total": counts["unverified_total"],
            "verified_supporting": counts["support_verified"],
            "unverified_supporting": counts["support_unverified"],
            "verified_conflicting": counts["conflict_verified"],
            "unverified_conflicting": counts["conflict_unverified"],
            "verified_other": counts["other_verified"],
            "unverified_other": counts["other_unverified"],
        },
        "verified_evidence_types": dict(sorted(verified_types.items())),
        "records": records,
    }


def _derive_claim_state(*, support_state: str, evidence: dict[str, Any]) -> str:
    counts = evidence["counts"]
    verified_supporting = counts["verified_supporting"]
    verified_conflicting = counts["verified_conflicting"]
    verified_total = counts["verified_total"]

    if support_state == "provenance_conflict":
        return "provenance_conflict"
    if verified_supporting and verified_conflicting:
        return "verified_evidence_conflict"
    if verified_conflicting:
        return "verified_counterevidence_present"
    if verified_supporting and support_state == "verified_independence_present":
        return "verified_supporting_evidence_and_independence"
    if verified_supporting:
        return "verified_supporting_evidence_present"
    if support_state == "verified_independence_present":
        return "verified_independence_present"
    if verified_total:
        return "verified_context_evidence_present"
    if counts["total"]:
        return "evidence_present_unverified"

    mapping = {
        "no_observation_support": "no_recorded_support",
        "single_observation": "single_recorded_observation",
        "dependency_present": "dependent_reporting_present",
        "independence_verification_incomplete": "independence_verification_incomplete",
        "multiple_observations_independence_unverified": "multiple_reports_independence_unverified",
        "multiple_observations_dependency_unknown": "multiple_reports_dependency_unknown",
    }
    return mapping.get(support_state, "recorded_support_state_unknown")


def build_claim_state(*, claim_id: str, connection_factory) -> dict[str, Any]:
    normalized_claim_id = _clean(claim_id, 128)
    if not normalized_claim_id:
        raise ValueError("Claim state requires claim_id.")
    if connection_factory is None:
        raise ValueError("Claim state requires database access.")

    support_graph = build_claim_support_graph(
        claim_id=normalized_claim_id,
        connection_factory=connection_factory,
        strict_graph_integrity=False,
    )
    if support_graph.get("status") == "not_found":
        return {
            "version": CLAIM_STATE_VERSION,
            "status": "not_found",
            "claim_id": normalized_claim_id,
        }

    integrity_blocked = bool(support_graph.get("integrity_blocked"))
    evidence_rows = [] if integrity_blocked else _claim_evidence_rows(
        claim_id=normalized_claim_id,
        connection_factory=connection_factory,
    )
    evidence = _evidence_posture(evidence_rows)
    observations = list(support_graph.get("observations") or [])

    source_ids = sorted(
        {
            _clean(item.get("source_id"), 128)
            for item in observations
            if _clean(item.get("source_id"), 128)
        }
    )
    reporter_ids = sorted(
        {
            _clean(item.get("reporter_id"), 128)
            for item in observations
            if _clean(item.get("reporter_id"), 128)
        }
    )
    subject_key = _clean((support_graph.get("claim") or {}).get("subject_key"), 256)

    source_history_rows = _history_rows(
        table="source_observations",
        identity_column="source_id",
        identity_ids=source_ids,
        subject_key=subject_key,
        connection_factory=connection_factory,
    )
    reporter_history_rows = _history_rows(
        table="reporter_observations",
        identity_column="reporter_id",
        identity_ids=reporter_ids,
        subject_key=subject_key,
        connection_factory=connection_factory,
    )

    source_history = _build_history(
        rows=source_history_rows,
        labels=_source_labels(
            source_ids=source_ids,
            connection_factory=connection_factory,
        ),
    )
    reporter_history = _build_history(
        rows=reporter_history_rows,
        labels=_reporter_labels(
            reporter_ids=reporter_ids,
            connection_factory=connection_factory,
        ),
    )

    support_state = _clean(support_graph.get("support_state"), 128)
    claim_state = _derive_claim_state(
        support_state=support_state,
        evidence=evidence,
    )

    conflict_signals: list[dict[str, Any]] = []
    if integrity_blocked:
        conflict_signals.append({
            "type": "evidence_graph_integrity_blocked",
            "detail": "Claim evidence posture is incomplete because graph integrity validation was blocked.",
        })
    if evidence["counts"]["verified_supporting"] and evidence["counts"][
        "verified_conflicting"
    ]:
        conflict_signals.append(
            {
                "type": "verified_evidence_conflict",
                "detail": "Verified evidence is linked on both supporting and conflicting relationships.",
            }
        )
    for conflict in support_graph.get("provenance_conflicts") or support_graph.get(
        "conflicts"
    ) or []:
        conflict_signals.append(
            {
                "type": "dependency_independence_conflict",
                "detail": _clean(conflict.get("reason"), 256),
                "observation_pair": list(conflict.get("observation_pair") or []),
            }
        )

    return {
        "version": CLAIM_STATE_VERSION,
        "status": "ok",
        "claim": support_graph.get("claim"),
        "claim_state": claim_state,
        "support_state": support_state,
        "evidence": evidence,
        "support": {
            "observation_count": len(observations),
            "distinct_sources": len(source_ids),
            "distinct_reporters": len(reporter_ids),
            "verified_independent_pairs": len(
                support_graph.get("verified_independent_pairs") or []
            ),
            "dependency_pairs": len(support_graph.get("dependency_pairs") or []),
            "independence_assertions": len(
                support_graph.get("independence_assertions") or []
            ),
        },
        "conflict_signals": conflict_signals,
        "reporting_history": {
            "subject_key": subject_key,
            "sources": source_history,
            "reporters": reporter_history,
        },
        "support_graph": support_graph,
        "policy": {
            "claim_state_is_evidence_posture_not_truth": True,
            "verified_evidence_status_is_not_claim_truth": True,
            "source_count_is_not_independence": True,
            "independence_requires_verified_provenance": True,
            "history_is_descriptive_not_reputation_scoring": True,
            "no_arbitrary_source_authority_weights": True,
            "affects_live_merit": False,
        },
    }


def _story_record(*, story_id: str, connection_factory) -> dict[str, Any] | None:
    conn = connection_factory()
    try:
        row = conn.execute(
            "SELECT * FROM intelligence_stories WHERE id = ?",
            (story_id,),
        ).fetchone()
    finally:
        conn.close()
    return dict(row) if row is not None else None


def _story_claim_ids(*, story_id: str, connection_factory) -> list[str]:
    conn = connection_factory()
    try:
        rows = conn.execute(
            "SELECT claim_id FROM story_claim_links WHERE story_id = ? ORDER BY claim_id",
            (story_id,),
        ).fetchall()
    finally:
        conn.close()
    return [_clean(row["claim_id"], 128) for row in rows if _clean(row["claim_id"], 128)]


def build_story_claim_state_overview(
    *, story_id: str, connection_factory
) -> dict[str, Any]:
    normalized_story_id = _clean(story_id, 128)
    if not normalized_story_id:
        raise ValueError("Story claim state requires story_id.")
    if connection_factory is None:
        raise ValueError("Story claim state requires database access.")

    story = _story_record(
        story_id=normalized_story_id,
        connection_factory=connection_factory,
    )
    if story is None:
        return {
            "version": STORY_CLAIM_STATE_VERSION,
            "status": "not_found",
            "story_id": normalized_story_id,
        }

    claim_states = [
        build_claim_state(claim_id=claim_id, connection_factory=connection_factory)
        for claim_id in _story_claim_ids(
            story_id=normalized_story_id,
            connection_factory=connection_factory,
        )
    ]
    state_counts = Counter(
        _clean(item.get("claim_state"), 128) or "unknown"
        for item in claim_states
        if item.get("status") == "ok"
    )

    claims_with_verified_support = sum(
        1
        for item in claim_states
        if (item.get("evidence") or {}).get("counts", {}).get("verified_supporting", 0)
        > 0
    )
    claims_with_verified_conflict = sum(
        1
        for item in claim_states
        if (item.get("evidence") or {}).get("counts", {}).get("verified_conflicting", 0)
        > 0
    )
    claims_with_verified_independence = sum(
        1
        for item in claim_states
        if (item.get("support") or {}).get("verified_independent_pairs", 0) > 0
    )
    claims_with_conflict_signals = sum(
        1 for item in claim_states if item.get("conflict_signals")
    )

    if claims_with_conflict_signals:
        story_state = "claim_level_conflicts_present"
    elif claims_with_verified_support and claims_with_verified_conflict:
        story_state = "mixed_verified_evidence_across_claims"
    elif claims_with_verified_conflict:
        story_state = "verified_counterevidence_present"
    elif claims_with_verified_support:
        story_state = "verified_supporting_evidence_present"
    elif claims_with_verified_independence:
        story_state = "verified_independence_present"
    elif claim_states:
        story_state = "reporting_context_only"
    else:
        story_state = "no_claims_linked"

    return {
        "version": STORY_CLAIM_STATE_VERSION,
        "status": "ok",
        "story": {
            "id": _clean(story.get("id"), 128),
            "canonical_key": _clean(story.get("canonical_key"), 512),
            "canonical_title": _clean(story.get("canonical_title"), 1000),
            "status": _clean(story.get("status"), 64),
        },
        "story_state": story_state,
        "counts": {
            "claims": len(claim_states),
            "claims_with_verified_supporting_evidence": claims_with_verified_support,
            "claims_with_verified_counterevidence": claims_with_verified_conflict,
            "claims_with_verified_independence": claims_with_verified_independence,
            "claims_with_conflict_signals": claims_with_conflict_signals,
        },
        "claim_states_by_state": dict(sorted(state_counts.items())),
        "claims": claim_states,
        "policy": {
            "story_state_is_rollup_not_truth": True,
            "different_claims_do_not_corroborate_each_other": True,
            "claim_level_conflicts_are_preserved": True,
            "no_cross_claim_independence_inference": True,
            "affects_live_merit": False,
        },
    }


__all__ = [
    "CLAIM_STATE_VERSION",
    "STORY_CLAIM_STATE_VERSION",
    "build_claim_state",
    "build_story_claim_state_overview",
]
