from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

from app.intelligence.claim_state import build_claim_state


CLAIM_PROJECTION_VERSION = "claim-intelligence-projection-v1"
STORY_PROJECTION_VERSION = "story-intelligence-projection-v1"
SUBJECT_TIMELINE_VERSION = "subject-intelligence-timeline-v1"


def _clean(value: Any, maximum: int = 512) -> str:
    return " ".join(str(value or "").split())[:maximum]


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_timestamp(value: Any) -> datetime | None:
    text = _clean(value, 128)
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed.astimezone(timezone.utc)


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat()


def _json_object(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    text = str(value or "").strip()
    if not text:
        return {}
    try:
        parsed = json.loads(text)
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}
    return dict(parsed) if isinstance(parsed, dict) else {}


def _claim_record(*, claim_id: str, connection_factory) -> dict[str, Any] | None:
    conn = connection_factory()
    try:
        row = conn.execute(
            "SELECT * FROM intelligence_claims WHERE id = ?",
            (claim_id,),
        ).fetchone()
    finally:
        conn.close()
    return dict(row) if row is not None else None


def _latest_adjudication(*, claim_id: str, connection_factory) -> dict[str, Any]:
    conn = connection_factory()
    try:
        rows = conn.execute(
            """
            SELECT revision.*
            FROM adjudication_state_revisions AS revision
            WHERE revision.claim_id = ?
              AND NOT EXISTS (
                SELECT 1
                FROM adjudication_state_revisions AS child
                WHERE child.previous_revision_id = revision.id
              )
            ORDER BY revision.recorded_at DESC, revision.id DESC
            LIMIT 2
            """,
            (claim_id,),
        ).fetchall()
    finally:
        conn.close()

    if not rows:
        return {
            "status": "none",
            "active_leaf_count": 0,
            "revision": None,
        }

    if len(rows) > 1:
        return {
            "status": "multiple_active_leaves",
            "active_leaf_count": len(rows),
            "revision": None,
        }

    row = dict(rows[0])
    revision_json = _json_object(row.get("revision_json"))
    trigger_ids = []
    try:
        parsed_ids = json.loads(str(row.get("trigger_evidence_ids_json") or "[]"))
        if isinstance(parsed_ids, list):
            trigger_ids = sorted({_clean(item, 128) for item in parsed_ids if _clean(item, 128)})
    except (TypeError, ValueError, json.JSONDecodeError):
        trigger_ids = []

    return {
        "status": "ready",
        "active_leaf_count": 1,
        "revision": {
            "id": _clean(row.get("id"), 128),
            "state_version": _clean(row.get("state_version"), 128),
            "adjudication_version": _clean(row.get("adjudication_version"), 128),
            "adjudication_sha256": _clean(row.get("adjudication_sha256"), 128),
            "as_of": _clean(row.get("as_of"), 128),
            "previous_revision_id": _clean(row.get("previous_revision_id"), 128),
            "trigger_type": _clean(row.get("trigger_type"), 64),
            "trigger_evidence_ids": trigger_ids,
            "recorded_at": _clean(row.get("recorded_at"), 128),
            "revision_id": _clean(revision_json.get("revision_id"), 128),
        },
    }


def _claim_relations(*, claim_id: str, connection_factory) -> dict[str, Any]:
    conn = connection_factory()
    try:
        story_rows = conn.execute(
            """
            SELECT
              s.id AS story_id,
              s.canonical_key,
              s.canonical_title,
              s.status,
              l.linked_at
            FROM story_claim_links AS l
            JOIN intelligence_stories AS s ON s.id = l.story_id
            WHERE l.claim_id = ?
            ORDER BY s.last_seen_at DESC, s.id
            """,
            (claim_id,),
        ).fetchall()
        participant_rows = conn.execute(
            """
            SELECT
              p.participant_role,
              p.verification_status,
              p.confidence,
              p.observed_at,
              p.evidence_id,
              e.id AS entity_id,
              e.entity_key,
              e.entity_type,
              e.canonical_name
            FROM verified_claim_entity_participants AS p
            JOIN canonical_entities AS e ON e.id = p.entity_id
            WHERE p.claim_id = ?
            ORDER BY p.participant_role, e.entity_type, e.canonical_name, e.id
            """,
            (claim_id,),
        ).fetchall()
    finally:
        conn.close()

    return {
        "stories": [dict(row) for row in story_rows],
        "verified_participants": [dict(row) for row in participant_rows],
    }


def _latest_claim_activity(claim: dict[str, Any], state: dict[str, Any], adjudication: dict[str, Any]) -> datetime | None:
    candidates: list[datetime] = []

    for value in (
        claim.get("last_seen_at"),
        claim.get("first_seen_at"),
    ):
        parsed = _parse_timestamp(value)
        if parsed is not None:
            candidates.append(parsed)

    evidence = state.get("evidence") or {}
    for record in evidence.get("records") or []:
        parsed = _parse_timestamp(record.get("observed_at"))
        if parsed is not None:
            candidates.append(parsed)

    support_graph = state.get("support_graph") or {}
    for record in support_graph.get("observations") or []:
        parsed = _parse_timestamp(record.get("observed_at"))
        if parsed is not None:
            candidates.append(parsed)

    revision = adjudication.get("revision") or {}
    for value in (revision.get("as_of"), revision.get("recorded_at")):
        parsed = _parse_timestamp(value)
        if parsed is not None:
            candidates.append(parsed)

    return max(candidates) if candidates else None


def _freshness(*, activity_at: datetime | None, now_value: datetime, stale_after_days: int) -> dict[str, Any]:
    if activity_at is None:
        return {
            "state": "unknown",
            "last_activity_at": "",
            "age_days": None,
            "stale_after_days": stale_after_days,
        }

    age = max(timedelta(0), now_value - activity_at)
    age_days = age.total_seconds() / 86400.0
    return {
        "state": "current" if age_days <= stale_after_days else "stale",
        "last_activity_at": _iso(activity_at),
        "age_days": round(age_days, 3),
        "stale_after_days": stale_after_days,
    }


def build_claim_projection(
    *,
    claim_id: str,
    connection_factory,
    stale_after_days: int = 30,
    now_provider: Callable[[], datetime] = _utc_now,
) -> dict[str, Any]:
    normalized_claim_id = _clean(claim_id, 128)
    if not normalized_claim_id:
        raise ValueError("Claim projection requires claim_id.")
    if connection_factory is None:
        raise ValueError("Claim projection requires database access.")

    try:
        stale_days = int(stale_after_days)
    except (TypeError, ValueError) as exc:
        raise ValueError("Claim projection stale_after_days must be an integer.") from exc
    if stale_days < 1 or stale_days > 3650:
        raise ValueError("Claim projection stale_after_days must be between 1 and 3650.")

    now_value = now_provider()
    if not isinstance(now_value, datetime):
        raise ValueError("Claim projection clock must return a datetime.")
    if now_value.tzinfo is None or now_value.utcoffset() is None:
        now_value = now_value.replace(tzinfo=timezone.utc)
    now_value = now_value.astimezone(timezone.utc)

    claim = _claim_record(
        claim_id=normalized_claim_id,
        connection_factory=connection_factory,
    )
    if claim is None:
        return {
            "version": CLAIM_PROJECTION_VERSION,
            "status": "not_found",
            "claim_id": normalized_claim_id,
        }

    state = build_claim_state(
        claim_id=normalized_claim_id,
        connection_factory=connection_factory,
    )
    adjudication = _latest_adjudication(
        claim_id=normalized_claim_id,
        connection_factory=connection_factory,
    )
    relations = _claim_relations(
        claim_id=normalized_claim_id,
        connection_factory=connection_factory,
    )

    activity_at = _latest_claim_activity(claim, state, adjudication)
    freshness = _freshness(
        activity_at=activity_at,
        now_value=now_value,
        stale_after_days=stale_days,
    )

    if adjudication["status"] == "multiple_active_leaves":
        projection_state = "adjudication_history_conflict"
    elif state.get("conflict_signals"):
        projection_state = "claim_conflict_present"
    elif freshness["state"] == "stale":
        projection_state = "stale_claim_context"
    else:
        projection_state = _clean(state.get("claim_state"), 128) or "claim_state_unknown"

    participant_roles = Counter(
        _clean(item.get("participant_role"), 64) or "unknown"
        for item in relations["verified_participants"]
    )

    return {
        "version": CLAIM_PROJECTION_VERSION,
        "status": "ok",
        "projection_state": projection_state,
        "claim": {
            "id": normalized_claim_id,
            "canonical_key": _clean(claim.get("canonical_key"), 512),
            "subject_key": _clean(claim.get("subject_key"), 256),
            "canonical_text": _clean(claim.get("canonical_text"), 1000),
            "claim_type": _clean(claim.get("claim_type"), 64),
            "first_seen_at": _clean(claim.get("first_seen_at"), 128),
            "last_seen_at": _clean(claim.get("last_seen_at"), 128),
        },
        "freshness": freshness,
        "claim_state": state,
        "adjudication": adjudication,
        "verified_participants": relations["verified_participants"],
        "stories": relations["stories"],
        "counts": {
            "verified_participants": len(relations["verified_participants"]),
            "stories": len(relations["stories"]),
            "conflict_signals": len(state.get("conflict_signals") or []),
        },
        "verified_participants_by_role": dict(sorted(participant_roles.items())),
        "generated_at_utc": _iso(now_value),
        "policy": {
            "projection_is_operational_context_not_truth": True,
            "adjudication_is_exposed_as_recorded_state_not_ground_truth": True,
            "multiple_adjudication_leaves_fail_closed": True,
            "staleness_is_temporal_context_not_falsehood": True,
            "verified_participants_are_identity_provenance_only": True,
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


def _story_runtime_context(*, story_id: str, connection_factory) -> dict[str, Any]:
    conn = connection_factory()
    try:
        media_count = int(
            conn.execute(
                "SELECT COUNT(*) FROM story_media_links WHERE story_id = ?",
                (story_id,),
            ).fetchone()[0]
        )
        direct_evidence = int(
            conn.execute(
                "SELECT COUNT(*) FROM evidence_links WHERE story_id = ?",
                (story_id,),
            ).fetchone()[0]
        )
        latest_snapshot = conn.execute(
            """
            SELECT
              id, analyzed_at, mode, analysis_version, scoring_version,
              merit_score, evidence_score, logic_score, badge, verdict, article_type
            FROM analysis_snapshots
            WHERE story_id = ?
            ORDER BY analyzed_at DESC, id DESC
            LIMIT 1
            """,
            (story_id,),
        ).fetchone()
    finally:
        conn.close()

    return {
        "media_items": max(0, media_count),
        "direct_story_evidence": max(0, direct_evidence),
        "latest_analysis_snapshot": dict(latest_snapshot) if latest_snapshot is not None else None,
    }


def build_story_projection(
    *,
    story_id: str,
    connection_factory,
    stale_after_days: int = 30,
    now_provider: Callable[[], datetime] = _utc_now,
) -> dict[str, Any]:
    normalized_story_id = _clean(story_id, 128)
    if not normalized_story_id:
        raise ValueError("Story projection requires story_id.")
    if connection_factory is None:
        raise ValueError("Story projection requires database access.")

    story = _story_record(
        story_id=normalized_story_id,
        connection_factory=connection_factory,
    )
    if story is None:
        return {
            "version": STORY_PROJECTION_VERSION,
            "status": "not_found",
            "story_id": normalized_story_id,
        }

    claim_ids = _story_claim_ids(
        story_id=normalized_story_id,
        connection_factory=connection_factory,
    )
    claims = [
        build_claim_projection(
            claim_id=claim_id,
            connection_factory=connection_factory,
            stale_after_days=stale_after_days,
            now_provider=now_provider,
        )
        for claim_id in claim_ids
    ]
    runtime = _story_runtime_context(
        story_id=normalized_story_id,
        connection_factory=connection_factory,
    )

    projection_states = Counter(
        _clean(item.get("projection_state"), 128) or "unknown"
        for item in claims
        if item.get("status") == "ok"
    )
    conflict_claims = sum(
        1
        for item in claims
        if item.get("projection_state") in {
            "adjudication_history_conflict",
            "claim_conflict_present",
        }
    )
    stale_claims = sum(
        1
        for item in claims
        if (item.get("freshness") or {}).get("state") == "stale"
    )

    if conflict_claims:
        projection_state = "claim_conflicts_present"
    elif stale_claims and stale_claims == len(claims) and claims:
        projection_state = "all_claim_context_stale"
    elif stale_claims:
        projection_state = "mixed_claim_freshness"
    elif claims:
        projection_state = "claim_context_ready"
    else:
        projection_state = "no_claims_linked"

    return {
        "version": STORY_PROJECTION_VERSION,
        "status": "ok",
        "projection_state": projection_state,
        "story": {
            "id": normalized_story_id,
            "canonical_key": _clean(story.get("canonical_key"), 512),
            "canonical_title": _clean(story.get("canonical_title"), 1000),
            "status": _clean(story.get("status"), 64),
            "first_seen_at": _clean(story.get("first_seen_at"), 128),
            "last_seen_at": _clean(story.get("last_seen_at"), 128),
        },
        "claims": claims,
        "runtime_context": runtime,
        "claim_projection_states": dict(sorted(projection_states.items())),
        "counts": {
            "claims": len(claims),
            "conflict_claims": conflict_claims,
            "stale_claims": stale_claims,
            "media_items": runtime["media_items"],
            "direct_story_evidence": runtime["direct_story_evidence"],
        },
        "policy": {
            "story_projection_preserves_claim_boundaries": True,
            "latest_analysis_snapshot_is_historical_product_output_not_truth": True,
            "cross_claim_support_is_not_inferred": True,
            "conflicts_fail_closed": True,
            "affects_live_merit": False,
        },
    }


def build_subject_timeline(
    *,
    subject_key: str,
    connection_factory,
    limit: int = 100,
) -> dict[str, Any]:
    normalized_subject_key = _clean(subject_key, 256)
    if not normalized_subject_key:
        raise ValueError("Subject timeline requires subject_key.")
    if connection_factory is None:
        raise ValueError("Subject timeline requires database access.")
    try:
        bounded_limit = int(limit)
    except (TypeError, ValueError) as exc:
        raise ValueError("Subject timeline limit must be an integer.") from exc
    if bounded_limit < 1 or bounded_limit > 500:
        raise ValueError("Subject timeline limit must be between 1 and 500.")

    conn = connection_factory()
    try:
        claim_rows = [
            dict(row)
            for row in conn.execute(
                """
                SELECT id, canonical_key, canonical_text, claim_type, first_seen_at, last_seen_at
                FROM intelligence_claims
                WHERE subject_key = ?
                ORDER BY last_seen_at DESC, id
                """,
                (normalized_subject_key,),
            ).fetchall()
        ]
        source_rows = [
            dict(row)
            for row in conn.execute(
                """
                SELECT
                  o.id, o.observation_type, o.status, o.claim_summary,
                  o.observed_at, s.id AS source_id, s.source_key,
                  s.display_name, s.canonical_domain
                FROM source_observations AS o
                JOIN intelligence_sources AS s ON s.id = o.source_id
                WHERE o.subject_key = ?
                ORDER BY o.observed_at DESC, o.id
                LIMIT ?
                """,
                (normalized_subject_key, bounded_limit),
            ).fetchall()
        ]
        reporter_rows = [
            dict(row)
            for row in conn.execute(
                """
                SELECT
                  o.id, o.observation_type, o.status, o.claim_summary,
                  o.observed_at, r.id AS reporter_id, r.identity_key,
                  r.display_name, o.source_id
                FROM reporter_observations AS o
                JOIN intelligence_reporters AS r ON r.id = o.reporter_id
                WHERE o.subject_key = ?
                ORDER BY o.observed_at DESC, o.id
                LIMIT ?
                """,
                (normalized_subject_key, bounded_limit),
            ).fetchall()
        ]
        evidence_rows = [
            dict(row)
            for row in conn.execute(
                """
                SELECT
                  id, evidence_type, verification_status, claim_summary,
                  published_at, observed_at
                FROM evidence_records
                WHERE subject_key = ?
                ORDER BY observed_at DESC, id
                LIMIT ?
                """,
                (normalized_subject_key, bounded_limit),
            ).fetchall()
        ]
    finally:
        conn.close()

    events: list[dict[str, Any]] = []
    for row in claim_rows:
        events.append({
            "event_type": "claim_seen",
            "occurred_at": _clean(row.get("last_seen_at"), 128),
            "claim_id": _clean(row.get("id"), 128),
            "claim_type": _clean(row.get("claim_type"), 64),
            "canonical_text": _clean(row.get("canonical_text"), 1000),
        })
    for row in source_rows:
        events.append({
            "event_type": "source_observation",
            "occurred_at": _clean(row.get("observed_at"), 128),
            "observation_id": _clean(row.get("id"), 128),
            "observation_type": _clean(row.get("observation_type"), 64),
            "status": _clean(row.get("status"), 64),
            "source_id": _clean(row.get("source_id"), 128),
            "source_key": _clean(row.get("source_key"), 256),
            "display_name": _clean(row.get("display_name"), 256),
            "canonical_domain": _clean(row.get("canonical_domain"), 256),
        })
    for row in reporter_rows:
        events.append({
            "event_type": "reporter_observation",
            "occurred_at": _clean(row.get("observed_at"), 128),
            "observation_id": _clean(row.get("id"), 128),
            "observation_type": _clean(row.get("observation_type"), 64),
            "status": _clean(row.get("status"), 64),
            "reporter_id": _clean(row.get("reporter_id"), 128),
            "identity_key": _clean(row.get("identity_key"), 256),
            "display_name": _clean(row.get("display_name"), 256),
            "source_id": _clean(row.get("source_id"), 128),
        })
    for row in evidence_rows:
        events.append({
            "event_type": "evidence_observed",
            "occurred_at": _clean(row.get("observed_at"), 128),
            "evidence_id": _clean(row.get("id"), 128),
            "evidence_type": _clean(row.get("evidence_type"), 64),
            "verification_status": _clean(row.get("verification_status"), 64),
            "published_at": _clean(row.get("published_at"), 128),
        })

    events.sort(
        key=lambda item: (
            _clean(item.get("occurred_at"), 128),
            _clean(item.get("event_type"), 64),
            _clean(item.get("claim_id") or item.get("observation_id") or item.get("evidence_id"), 128),
        ),
        reverse=True,
    )
    events = events[:bounded_limit]

    return {
        "version": SUBJECT_TIMELINE_VERSION,
        "status": "ok",
        "subject_key": normalized_subject_key,
        "counts": {
            "claims": len(claim_rows),
            "source_observations": len(source_rows),
            "reporter_observations": len(reporter_rows),
            "evidence_records": len(evidence_rows),
            "returned_events": len(events),
        },
        "events": events,
        "policy": {
            "timeline_is_chronology_not_truth": True,
            "observation_frequency_is_not_source_reliability": True,
            "verified_evidence_status_is_not_claim_truth": True,
            "timeline_does_not_establish_independence": True,
            "affects_live_merit": False,
        },
    }


__all__ = [
    "CLAIM_PROJECTION_VERSION",
    "STORY_PROJECTION_VERSION",
    "SUBJECT_TIMELINE_VERSION",
    "build_claim_projection",
    "build_story_projection",
    "build_subject_timeline",
]
