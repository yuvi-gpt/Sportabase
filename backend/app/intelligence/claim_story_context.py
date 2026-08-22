from __future__ import annotations

import json
from collections import Counter
from typing import Any


CLAIM_INTELLIGENCE_CONTEXT_VERSION = "claim-intelligence-context-v1"
STORY_INTELLIGENCE_CONTEXT_VERSION = "story-intelligence-context-v1"


def _clean(value: Any, maximum: int = 512) -> str:
    return " ".join(str(value or "").split())[:maximum]


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


def _row(value: Any) -> dict[str, Any] | None:
    return dict(value) if value is not None else None


def _claim_context_from_connection(
    conn,
    claim_id: str,
) -> dict[str, Any] | None:
    claim = _row(
        conn.execute(
            """
            SELECT *
            FROM intelligence_claims
            WHERE id = ?
            """,
            (claim_id,),
        ).fetchone()
    )
    if claim is None:
        return None

    participants = [
        dict(row)
        for row in conn.execute(
            """
            SELECT
              p.id AS participant_id,
              p.participant_role,
              p.verification_status,
              p.confidence,
              p.observed_at,
              p.recorded_at,
              p.evidence_id,
              e.id AS entity_id,
              e.entity_key,
              e.entity_type,
              e.sport_key,
              e.canonical_name,
              er.evidence_type,
              er.verification_status AS evidence_verification_status
            FROM verified_claim_entity_participants AS p
            JOIN canonical_entities AS e
              ON e.id = p.entity_id
            JOIN evidence_records AS er
              ON er.id = p.evidence_id
            WHERE p.claim_id = ?
            ORDER BY
              p.participant_role,
              e.entity_type,
              e.canonical_name,
              e.id,
              p.id
            """,
            (claim_id,),
        ).fetchall()
    ]

    evidence_links = [
        dict(row)
        for row in conn.execute(
            """
            SELECT
              cl.id AS claim_link_id,
              cl.relationship_type,
              cl.confidence,
              cl.observed_at AS linked_observed_at,
              er.id AS evidence_id,
              er.evidence_type,
              er.subject_key,
              er.claim_summary,
              er.verification_status,
              er.published_at,
              er.observed_at
            FROM claim_links AS cl
            JOIN evidence_records AS er
              ON er.id = cl.evidence_id
            WHERE
              cl.claim_id = ?
              AND cl.evidence_id IS NOT NULL
            ORDER BY er.observed_at DESC, er.id
            """,
            (claim_id,),
        ).fetchall()
    ]

    source_observations = [
        dict(row)
        for row in conn.execute(
            """
            SELECT
              cl.id AS claim_link_id,
              cl.relationship_type,
              cl.confidence AS link_confidence,
              o.id AS observation_id,
              o.observation_type,
              o.status,
              o.claim_summary,
              o.confidence,
              o.observed_at,
              o.media_item_id,
              o.story_id,
              o.metadata_json,
              s.id AS source_id,
              s.source_key,
              s.display_name,
              s.source_type,
              s.canonical_domain
            FROM claim_links AS cl
            JOIN source_observations AS o
              ON o.id = cl.source_observation_id
            JOIN intelligence_sources AS s
              ON s.id = o.source_id
            WHERE
              cl.claim_id = ?
              AND cl.source_observation_id IS NOT NULL
            ORDER BY o.observed_at DESC, o.id
            """,
            (claim_id,),
        ).fetchall()
    ]

    reporter_observations = [
        dict(row)
        for row in conn.execute(
            """
            SELECT
              cl.id AS claim_link_id,
              cl.relationship_type,
              cl.confidence AS link_confidence,
              o.id AS observation_id,
              o.observation_type,
              o.status,
              o.claim_summary,
              o.confidence,
              o.observed_at,
              o.media_item_id,
              o.story_id,
              r.id AS reporter_id,
              r.identity_key,
              r.display_name AS reporter_name,
              s.id AS source_id,
              s.source_key,
              s.display_name AS source_name,
              s.canonical_domain
            FROM claim_links AS cl
            JOIN reporter_observations AS o
              ON o.id = cl.reporter_observation_id
            JOIN intelligence_reporters AS r
              ON r.id = o.reporter_id
            LEFT JOIN intelligence_sources AS s
              ON s.id = o.source_id
            WHERE
              cl.claim_id = ?
              AND cl.reporter_observation_id IS NOT NULL
            ORDER BY o.observed_at DESC, o.id
            """,
            (claim_id,),
        ).fetchall()
    ]

    stories = [
        dict(row)
        for row in conn.execute(
            """
            SELECT
              s.id AS story_id,
              s.canonical_key,
              s.canonical_title,
              s.status,
              l.relationship_type,
              l.link_basis,
              l.linked_at
            FROM story_claim_links AS l
            JOIN intelligence_stories AS s
              ON s.id = l.story_id
            WHERE l.claim_id = ?
            ORDER BY s.last_seen_at DESC, s.id
            """,
            (claim_id,),
        ).fetchall()
    ]

    source_ids = {
        _clean(item.get("source_id"), 128)
        for item in source_observations + reporter_observations
        if _clean(item.get("source_id"), 128)
    }
    evidence_statuses = Counter(
        _clean(item.get("verification_status"), 64) or "unknown"
        for item in evidence_links
    )

    for item in source_observations:
        metadata = _json_object(item.pop("metadata_json", ""))
        entity_resolution = metadata.get("entity_resolution")
        claim_entity_context = metadata.get("claim_entity_context")
        item["candidate_context"] = {
            "entity_resolution": (
                entity_resolution
                if isinstance(entity_resolution, dict)
                else None
            ),
            "claim_entity_context": (
                claim_entity_context
                if isinstance(claim_entity_context, dict)
                else None
            ),
        }

    return {
        "version": CLAIM_INTELLIGENCE_CONTEXT_VERSION,
        "status": "ok",
        "claim": {
            "id": _clean(claim.get("id"), 128),
            "canonical_key": _clean(claim.get("canonical_key"), 512),
            "subject_key": _clean(claim.get("subject_key"), 256),
            "canonical_text": _clean(claim.get("canonical_text"), 1000),
            "claim_type": _clean(claim.get("claim_type"), 64),
            "first_seen_at": _clean(claim.get("first_seen_at"), 128),
            "last_seen_at": _clean(claim.get("last_seen_at"), 128),
        },
        "verified_participants": participants,
        "evidence": evidence_links,
        "source_observations": source_observations,
        "reporter_observations": reporter_observations,
        "stories": stories,
        "counts": {
            "verified_participants": len(participants),
            "evidence_records": len(evidence_links),
            "source_observations": len(source_observations),
            "reporter_observations": len(reporter_observations),
            "distinct_observed_sources": len(source_ids),
            "stories": len(stories),
        },
        "evidence_by_verification_status": dict(sorted(evidence_statuses.items())),
        "policy": {
            "verified_participants_are_identity_provenance_only": True,
            "verified_evidence_status_is_not_claim_truth": True,
            "source_count_is_not_independence": True,
            "observation_count_is_not_corroboration": True,
            "candidate_entity_context_is_not_verified_participation": True,
            "establishes_truth": False,
            "establishes_authority": False,
            "establishes_independence": False,
            "affects_live_merit": False,
        },
    }


def build_claim_intelligence_context(
    *,
    claim_id: str,
    connection_factory,
) -> dict[str, Any]:
    if connection_factory is None:
        raise ValueError("Claim intelligence context requires database access.")

    normalized_claim_id = _clean(claim_id, 128)
    if not normalized_claim_id:
        raise ValueError("Claim intelligence context claim_id is required.")

    conn = connection_factory()
    try:
        result = _claim_context_from_connection(conn, normalized_claim_id)
    finally:
        conn.close()

    if result is None:
        return {
            "version": CLAIM_INTELLIGENCE_CONTEXT_VERSION,
            "status": "not_found",
            "claim_id": normalized_claim_id,
        }
    return result


def build_story_intelligence_context(
    *,
    story_id: str,
    connection_factory,
) -> dict[str, Any]:
    if connection_factory is None:
        raise ValueError("Story intelligence context requires database access.")

    normalized_story_id = _clean(story_id, 128)
    if not normalized_story_id:
        raise ValueError("Story intelligence context story_id is required.")

    conn = connection_factory()
    try:
        story = _row(
            conn.execute(
                """
                SELECT *
                FROM intelligence_stories
                WHERE id = ?
                """,
                (normalized_story_id,),
            ).fetchone()
        )
        if story is None:
            return {
                "version": STORY_INTELLIGENCE_CONTEXT_VERSION,
                "status": "not_found",
                "story_id": normalized_story_id,
            }

        claim_ids = [
            _clean(row["claim_id"], 128)
            for row in conn.execute(
                """
                SELECT claim_id
                FROM story_claim_links
                WHERE story_id = ?
                ORDER BY claim_id
                """,
                (normalized_story_id,),
            ).fetchall()
        ]
        claim_contexts = [
            context
            for claim_id in claim_ids
            for context in [_claim_context_from_connection(conn, claim_id)]
            if context is not None
        ]

        media = [
            dict(row)
            for row in conn.execute(
                """
                SELECT
                  m.id AS media_item_id,
                  m.mode,
                  m.title,
                  m.published_at,
                  l.relationship_type,
                  l.confidence,
                  l.linked_at,
                  s.id AS source_id,
                  s.source_key,
                  s.display_name AS source_name,
                  s.source_type,
                  s.canonical_domain
                FROM story_media_links AS l
                JOIN media_items AS m
                  ON m.id = l.media_item_id
                LEFT JOIN intelligence_sources AS s
                  ON s.id = m.source_id
                WHERE l.story_id = ?
                ORDER BY m.published_at DESC, m.id
                """,
                (normalized_story_id,),
            ).fetchall()
        ]

        direct_evidence = [
            dict(row)
            for row in conn.execute(
                """
                SELECT
                  er.id AS evidence_id,
                  er.evidence_type,
                  er.subject_key,
                  er.claim_summary,
                  er.verification_status,
                  er.published_at,
                  er.observed_at,
                  el.relationship_type,
                  el.confidence,
                  el.linked_at
                FROM evidence_links AS el
                JOIN evidence_records AS er
                  ON er.id = el.evidence_id
                WHERE el.story_id = ?
                ORDER BY er.observed_at DESC, er.id
                """,
                (normalized_story_id,),
            ).fetchall()
        ]
    finally:
        conn.close()

    distinct_sources = {
        _clean(item.get("source_id"), 128)
        for item in media
        if _clean(item.get("source_id"), 128)
    }
    verified_participant_ids = {
        _clean(participant.get("participant_id"), 128)
        for context in claim_contexts
        for participant in context.get("verified_participants", [])
        if _clean(participant.get("participant_id"), 128)
    }
    claim_evidence_ids = {
        _clean(evidence.get("evidence_id"), 128)
        for context in claim_contexts
        for evidence in context.get("evidence", [])
        if _clean(evidence.get("evidence_id"), 128)
    }

    return {
        "version": STORY_INTELLIGENCE_CONTEXT_VERSION,
        "status": "ok",
        "story": {
            "id": _clean(story.get("id"), 128),
            "canonical_key": _clean(story.get("canonical_key"), 512),
            "canonical_title": _clean(story.get("canonical_title"), 1000),
            "status": _clean(story.get("status"), 64),
            "first_seen_at": _clean(story.get("first_seen_at"), 128),
            "last_seen_at": _clean(story.get("last_seen_at"), 128),
        },
        "claims": claim_contexts,
        "media": media,
        "direct_story_evidence": direct_evidence,
        "counts": {
            "claims": len(claim_contexts),
            "media_items": len(media),
            "distinct_media_sources": len(distinct_sources),
            "direct_story_evidence": len(direct_evidence),
            "claim_evidence_records": len(claim_evidence_ids),
            "verified_claim_participants": len(verified_participant_ids),
        },
        "policy": {
            "story_membership_is_structural_not_truth": True,
            "distinct_source_count_is_not_independence": True,
            "evidence_count_is_not_corroboration": True,
            "verified_participants_are_identity_provenance_only": True,
            "verified_evidence_status_is_not_claim_truth": True,
            "establishes_truth": False,
            "establishes_authority": False,
            "establishes_independence": False,
            "affects_live_merit": False,
        },
    }


__all__ = [
    "CLAIM_INTELLIGENCE_CONTEXT_VERSION",
    "STORY_INTELLIGENCE_CONTEXT_VERSION",
    "build_claim_intelligence_context",
    "build_story_intelligence_context",
]
