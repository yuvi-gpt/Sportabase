from __future__ import annotations

from typing import Any, Mapping

from app.intelligence.claim_state import build_claim_state
from app.intelligence.product_history import story_history
from app.services.content_resolution import normalized_analysis_url


ANALYSIS_RESULT_CONTEXT_VERSION = "analysis-result-context-v1"
_MAX_RELATED_REPORTS = 50
_MAX_EVOLUTION_EVENTS = 100


def _clean(value: Any, maximum: int = 2048) -> str:
    return " ".join(str(value or "").split())[:maximum]


def _humanize(value: Any) -> str:
    return _clean(value, 128).replace("_", " ").strip().capitalize()


def _empty(*, canonical_url: str, status: str) -> dict[str, Any]:
    return {
        "version": ANALYSIS_RESULT_CONTEXT_VERSION,
        "status": status,
        "canonical_url": canonical_url,
        "media": None,
        "primary_claim": None,
        "story": None,
        "evidence": None,
        "related_reports": [],
        "stakeholders": [],
        "evolution": [],
        "policy": {
            "read_only": True,
            "provider_call_performed": False,
            "context_is_not_truth": True,
            "source_count_is_not_independence": True,
            "verified_relationships_only": True,
            "affects_live_merit": False,
        },
    }


def _media_and_source(*, canonical_url: str, connection_factory) -> dict[str, Any] | None:
    conn = connection_factory()
    try:
        row = conn.execute(
            """
            SELECT m.*, s.display_name AS source_name, s.source_type,
                   s.canonical_domain
            FROM media_items AS m
            LEFT JOIN intelligence_sources AS s ON s.id = m.source_id
            WHERE m.canonical_url = ?
            LIMIT 1
            """,
            (canonical_url,),
        ).fetchone()
    finally:
        conn.close()
    return dict(row) if row is not None else None


def _claim_candidates(*, media_item_id: str, connection_factory) -> list[dict[str, Any]]:
    conn = connection_factory()
    try:
        rows = conn.execute(
            """
            WITH candidates AS (
              SELECT cl.claim_id, 0 AS binding_priority, cl.observed_at AS bound_at
              FROM claim_links AS cl
              JOIN source_observations AS observation
                ON observation.id = cl.source_observation_id
              WHERE observation.media_item_id = ?
              UNION ALL
              SELECT cl.claim_id, 0, cl.observed_at
              FROM claim_links AS cl
              JOIN reporter_observations AS observation
                ON observation.id = cl.reporter_observation_id
              WHERE observation.media_item_id = ?
              UNION ALL
              SELECT cl.claim_id, 0, cl.observed_at
              FROM claim_links AS cl
              JOIN evidence_links AS link ON link.evidence_id = cl.evidence_id
              WHERE link.media_item_id = ?
              UNION ALL
              SELECT story_claim.claim_id, 1, story_claim.linked_at
              FROM story_media_links AS story_media
              JOIN story_claim_links AS story_claim
                ON story_claim.story_id = story_media.story_id
              WHERE story_media.media_item_id = ?
            )
            SELECT claim.id, claim.canonical_text, claim.claim_type,
                   claim.subject_key, MIN(candidates.binding_priority) AS binding_priority,
                   MIN(candidates.bound_at) AS bound_at
            FROM candidates
            JOIN intelligence_claims AS claim ON claim.id = candidates.claim_id
            GROUP BY claim.id
            ORDER BY binding_priority, bound_at, claim.id
            """,
            (media_item_id, media_item_id, media_item_id, media_item_id),
        ).fetchall()
    finally:
        conn.close()
    return [dict(row) for row in rows]


def _story_for_media_or_claim(
    *, media_item_id: str, claim_id: str, connection_factory
) -> dict[str, Any] | None:
    conn = connection_factory()
    try:
        row = conn.execute(
            """
            SELECT story.id, story.canonical_title, story.status,
                   media_link.linked_at, 0 AS binding_priority
            FROM story_media_links AS media_link
            JOIN intelligence_stories AS story ON story.id = media_link.story_id
            WHERE media_link.media_item_id = ?
            UNION ALL
            SELECT story.id, story.canonical_title, story.status,
                   claim_link.linked_at, 1 AS binding_priority
            FROM story_claim_links AS claim_link
            JOIN intelligence_stories AS story ON story.id = claim_link.story_id
            WHERE claim_link.claim_id = ?
            ORDER BY binding_priority, linked_at, id
            LIMIT 1
            """,
            (media_item_id, claim_id),
        ).fetchone()
    finally:
        conn.close()
    return dict(row) if row is not None else None


def _stakeholders(*, claim_id: str, connection_factory) -> list[dict[str, Any]]:
    conn = connection_factory()
    try:
        rows = conn.execute(
            """
            SELECT participant.entity_id, entity.canonical_name AS name,
                   entity.entity_type, participant.participant_role,
                   participant.verification_status, participant.evidence_id,
                   participant.observed_at
            FROM verified_claim_entity_participants AS participant
            JOIN canonical_entities AS entity ON entity.id = participant.entity_id
            WHERE participant.claim_id = ?
              AND participant.verification_status = 'verified'
            ORDER BY participant.observed_at, participant.id
            """,
            (claim_id,),
        ).fetchall()
    finally:
        conn.close()
    return [dict(row) for row in rows]


def _observation_keys_by_media(
    *, claim_id: str, media_item_ids: list[str], connection_factory
) -> dict[str, set[str]]:
    if not media_item_ids:
        return {}
    marks = ",".join("?" for _ in media_item_ids)
    conn = connection_factory()
    try:
        rows = conn.execute(
            f"""
            SELECT source.media_item_id, 'source_observation:' || source.id AS observation_key
            FROM claim_links AS link
            JOIN source_observations AS source ON source.id = link.source_observation_id
            WHERE link.claim_id = ? AND source.media_item_id IN ({marks})
            UNION ALL
            SELECT reporter.media_item_id, 'reporter_observation:' || reporter.id
            FROM claim_links AS link
            JOIN reporter_observations AS reporter ON reporter.id = link.reporter_observation_id
            WHERE link.claim_id = ? AND reporter.media_item_id IN ({marks})
            """,
            (claim_id, *media_item_ids, claim_id, *media_item_ids),
        ).fetchall()
    finally:
        conn.close()
    result: dict[str, set[str]] = {}
    for row in rows:
        media_id = _clean(row["media_item_id"], 128)
        key = _clean(row["observation_key"], 256)
        if media_id and key:
            result.setdefault(media_id, set()).add(key)
    return result


def _claim_relationships_by_media(
    *, claim_id: str, media_item_ids: list[str], connection_factory
) -> dict[str, set[str]]:
    if not media_item_ids:
        return {}
    marks = ",".join("?" for _ in media_item_ids)
    conn = connection_factory()
    try:
        rows = conn.execute(
            f"""
            SELECT source.media_item_id, link.relationship_type
            FROM claim_links AS link
            JOIN source_observations AS source ON source.id = link.source_observation_id
            WHERE link.claim_id = ? AND source.media_item_id IN ({marks})
            UNION ALL
            SELECT reporter.media_item_id, link.relationship_type
            FROM claim_links AS link
            JOIN reporter_observations AS reporter ON reporter.id = link.reporter_observation_id
            WHERE link.claim_id = ? AND reporter.media_item_id IN ({marks})
            """,
            (claim_id, *media_item_ids, claim_id, *media_item_ids),
        ).fetchall()
    finally:
        conn.close()
    result: dict[str, set[str]] = {}
    for row in rows:
        media_id = _clean(row["media_item_id"], 128)
        relationship = _clean(row["relationship_type"], 64).casefold()
        if media_id and relationship:
            result.setdefault(media_id, set()).add(relationship)
    return result


def _official_source_ids(
    *, stakeholder_entity_ids: list[str], connection_factory
) -> set[str]:
    if not stakeholder_entity_ids:
        return set()
    marks = ",".join("?" for _ in stakeholder_entity_ids)
    conn = connection_factory()
    try:
        rows = conn.execute(
            f"""
            SELECT DISTINCT source_id
            FROM verified_source_entity_bindings
            WHERE verification_status = 'verified'
              AND entity_id IN ({marks})
            """,
            tuple(stakeholder_entity_ids),
        ).fetchall()
    finally:
        conn.close()
    return {_clean(row["source_id"], 128) for row in rows if _clean(row["source_id"], 128)}


def _dependency_label(
    related_keys: set[str], primary_keys: set[str], dependencies: list[Mapping[str, Any]]
) -> str:
    for dependency in dependencies:
        downstream = _clean(dependency.get("downstream_observation_key"), 256)
        linked_pairs = dependency.get("linked_observation_pairs") or []
        if downstream not in related_keys | primary_keys:
            continue
        if not any(
            bool(set(item or []) & related_keys)
            and bool(set(item or []) & primary_keys)
            for item in linked_pairs
        ):
            continue
        relationship = _clean(dependency.get("relationship_type"), 64).casefold()
        if relationship == "attributed_to":
            return "Cites same source"
        if relationship == "derived_from":
            return "Repeats earlier report"
    return ""


def _stance_label(values: set[str]) -> str:
    if values & {"contradicts", "contradict", "refutes", "refute", "disputes", "dispute"}:
        return "Contradicts claim"
    if values & {"qualifies", "qualify", "qualified"}:
        return "Qualifies claim"
    if values & {"supports", "support", "confirms", "confirm", "corroborates", "corroborate"}:
        return "Supports claim"
    return ""


def _related_reports(
    *, media: Mapping[str, Any], story: Mapping[str, Any] | None,
    claim_id: str, claim_state: Mapping[str, Any], stakeholders: list[Mapping[str, Any]],
    connection_factory,
) -> list[dict[str, Any]]:
    if not story:
        return []
    conn = connection_factory()
    try:
        rows = conn.execute(
            """
            SELECT related.id AS media_item_id, related.source_id,
                   source.display_name AS source_name, source.source_type,
                   related.title AS headline, related.canonical_url,
                   COALESCE(related.published_at, related.first_seen_at) AS observed_at
            FROM story_media_links AS link
            JOIN media_items AS related ON related.id = link.media_item_id
            LEFT JOIN intelligence_sources AS source ON source.id = related.source_id
            WHERE link.story_id = ? AND related.id != ?
            ORDER BY observed_at, related.id
            LIMIT ?
            """,
            (_clean(story.get("id"), 128), _clean(media.get("id"), 128), _MAX_RELATED_REPORTS),
        ).fetchall()
    finally:
        conn.close()
    reports = [dict(row) for row in rows]
    ids = [_clean(row.get("media_item_id"), 128) for row in reports]
    keys_by_media = _observation_keys_by_media(
        claim_id=claim_id,
        media_item_ids=[_clean(media.get("id"), 128), *ids],
        connection_factory=connection_factory,
    )
    relationships = _claim_relationships_by_media(
        claim_id=claim_id, media_item_ids=ids, connection_factory=connection_factory
    )
    official_sources = _official_source_ids(
        stakeholder_entity_ids=[_clean(item.get("entity_id"), 128) for item in stakeholders],
        connection_factory=connection_factory,
    )
    support_graph = claim_state.get("support_graph") or {}
    verified_pairs = {
        frozenset(_clean(key, 256) for key in pair if _clean(key, 256))
        for pair in support_graph.get("verified_independent_pairs") or []
    }
    dependencies = list(support_graph.get("dependency_edges") or [])
    primary_keys = keys_by_media.get(_clean(media.get("id"), 128), set())

    output = []
    for report in reports:
        report_id = _clean(report.get("media_item_id"), 128)
        related_keys = keys_by_media.get(report_id, set())
        explicitly_independent = any(
            frozenset((left, right)) in verified_pairs
            for left in primary_keys for right in related_keys
        )
        dependency = _dependency_label(related_keys, primary_keys, dependencies)
        stance = _stance_label(relationships.get(report_id, set()))
        source_id = _clean(report.get("source_id"), 128)
        if source_id and source_id in official_sources:
            relationship = "Official stakeholder"
        elif explicitly_independent:
            relationship = "Independent reporting"
        elif dependency:
            relationship = dependency
        elif stance:
            relationship = stance
        else:
            relationship = "Related reporting"
        output.append({
            "media_item_id": report_id or None,
            "source_id": source_id or None,
            "source_name": _clean(report.get("source_name"), 256) or _clean(report.get("canonical_url"), 256),
            "source_type": _clean(report.get("source_type"), 64),
            "headline": _clean(report.get("headline"), 1000),
            "canonical_url": _clean(report.get("canonical_url"), 2048) or None,
            "observed_at": _clean(report.get("observed_at"), 128),
            "relationship": relationship,
            "independence_status": "verified" if explicitly_independent else None,
            "verification_status": None,
        })
    return output


def _evidence_context(claim_state: Mapping[str, Any]) -> dict[str, Any] | None:
    if claim_state.get("status") != "ok":
        return None
    support = claim_state.get("support") or {}
    evidence = claim_state.get("evidence") or {}
    counts = evidence.get("counts") or {}
    verified_supporting = int(counts.get("verified_supporting") or 0)
    verified_conflicting = int(counts.get("verified_conflicting") or 0)
    verified_total = int(counts.get("verified_total") or 0)
    unverified_total = int(counts.get("unverified_total") or 0)
    verified_pairs = int(support.get("verified_independent_pairs") or 0)
    assertions = int(support.get("independence_assertions") or 0)
    if verified_supporting and verified_conflicting:
        corroboration = "Verified evidence is contested"
    elif verified_conflicting:
        corroboration = "Verified contradiction recorded"
    elif verified_supporting:
        corroboration = "Verified support recorded"
    elif verified_total:
        corroboration = "Verified context recorded"
    else:
        corroboration = "No verified evidence"
    independence = (
        "Verified independent reporting" if verified_pairs
        else "Not verified" if assertions
        else "Not assessed"
    )
    claim_state_value = _clean(claim_state.get("claim_state"), 128) or "recorded_support_state_unknown"
    return {
        "status": claim_state_value,
        "label": _humanize(claim_state_value),
        "detail": "Persisted evidence and reporting relationships linked to the primary canonical claim.",
        "signal": _clean(claim_state.get("support_state"), 128),
        "corroboration_status": corroboration,
        "independence_status": independence,
        "distinct_source_count": int(support.get("distinct_sources") or 0),
        "candidate_count": None,
        "verification_pairs": verified_pairs,
        "contested": bool(verified_conflicting),
        "provisional": bool(unverified_total and not verified_total),
        "affects_merit_score": False,
    }


def _evolution(
    *, story: Mapping[str, Any] | None, stakeholders: list[Mapping[str, Any]],
    claim_state: Mapping[str, Any], connection_factory,
) -> list[dict[str, Any]]:
    if not story:
        return []
    history = story_history(
        story_id=_clean(story.get("id"), 128),
        connection_factory=connection_factory,
        limit=_MAX_EVOLUTION_EVENTS,
    )
    if history is None:
        return []
    media_titles = {
        _clean(item.get("id"), 128): _clean(item.get("title"), 1000)
        for item in history.get("media") or []
    }
    events: list[dict[str, Any]] = []
    for item in history.get("events") or []:
        event_type = _clean(item.get("type"), 64)
        occurred_at = _clean(item.get("occurred_at"), 128)
        if event_type == "media_link":
            media_id = _clean(item.get("media_item_id"), 128)
            events.append({"id": f"media:{media_id}", "type": "related_report_observed", "label": "Related report observed", "detail": media_titles.get(media_id, "A persisted report was linked to this story."), "occurred_at": occurred_at})
        elif event_type in {"source_observation", "reporter_observation"}:
            events.append({"id": f"{event_type}:{_clean(item.get('id'), 128)}", "type": "claim_observed", "label": "Claim observed", "detail": _clean(item.get("claim_summary"), 1000) or "A persisted reporting observation was recorded.", "occurred_at": occurred_at})
        elif event_type == "evidence" and _clean(item.get("verification_status"), 64).casefold() == "verified":
            relation = _clean(item.get("relationship_type"), 64).casefold()
            if relation in {"supports", "support", "confirms", "confirm"}:
                label, kind = "Verified support recorded", "verified_support_recorded"
            elif relation in {"contradicts", "contradict", "refutes", "refute"}:
                label, kind = "Contradiction recorded", "contradiction_recorded"
            else:
                continue
            events.append({"id": f"evidence:{_clean(item.get('id'), 128)}", "type": kind, "label": label, "detail": _clean(item.get("claim_summary"), 1000) or _humanize(item.get("evidence_type")), "occurred_at": occurred_at})

    for stakeholder in stakeholders:
        events.append({
            "id": f"stakeholder:{_clean(stakeholder.get('entity_id'), 128)}:{_clean(stakeholder.get('evidence_id'), 128)}",
            "type": "verified_participant_recorded",
            "label": "Verified participant recorded",
            "detail": f"{_clean(stakeholder.get('name'), 256)} is a verified {_humanize(stakeholder.get('participant_role')).lower()} in the canonical claim.",
            "occurred_at": _clean(stakeholder.get("observed_at"), 128),
        })
    graph = claim_state.get("support_graph") or {}
    for assertion in graph.get("independence_assertions") or []:
        if not assertion.get("qualified_verified_independence"):
            continue
        events.append({
            "id": f"independence:{_clean(assertion.get('assertion_id'), 128)}",
            "type": "independence_verified",
            "label": "Independence verified",
            "detail": "A persisted verified independence assertion links two reporting observations.",
            "occurred_at": _clean(assertion.get("observed_at"), 128),
        })
    events = [item for item in events if item["occurred_at"]]
    events.sort(key=lambda item: (item["occurred_at"], item["type"], item["id"]))
    return events[:_MAX_EVOLUTION_EVENTS]


def build_analysis_result_context(*, url: str, connection_factory) -> dict[str, Any]:
    canonical_url = _clean(normalized_analysis_url(url), 2048)
    if not canonical_url:
        raise ValueError("Result context requires a valid URL.")
    if connection_factory is None:
        return _empty(canonical_url=canonical_url, status="disabled")
    media = _media_and_source(canonical_url=canonical_url, connection_factory=connection_factory)
    if media is None:
        return _empty(canonical_url=canonical_url, status="no_media_record")
    claims = _claim_candidates(media_item_id=_clean(media.get("id"), 128), connection_factory=connection_factory)
    primary_claim = claims[0] if claims else None
    claim_id = _clean((primary_claim or {}).get("id"), 128)
    story = _story_for_media_or_claim(
        media_item_id=_clean(media.get("id"), 128),
        claim_id=claim_id,
        connection_factory=connection_factory,
    )
    claim_state = build_claim_state(claim_id=claim_id, connection_factory=connection_factory) if claim_id else {}
    stakeholders = _stakeholders(claim_id=claim_id, connection_factory=connection_factory) if claim_id else []
    related = _related_reports(
        media=media, story=story, claim_id=claim_id, claim_state=claim_state,
        stakeholders=stakeholders, connection_factory=connection_factory,
    ) if claim_id else []
    return {
        "version": ANALYSIS_RESULT_CONTEXT_VERSION,
        "status": "ready",
        "canonical_url": canonical_url,
        "media": {
            "id": _clean(media.get("id"), 128),
            "title": _clean(media.get("title"), 1000),
            "canonical_url": canonical_url,
            "mode": _clean(media.get("mode"), 64),
            "published_at": _clean(media.get("published_at"), 128) or None,
            "observed_at": _clean(media.get("first_seen_at"), 128) or None,
            "source_id": _clean(media.get("source_id"), 128) or None,
            "source_name": _clean(media.get("source_name"), 256) or None,
            "source_type": _clean(media.get("source_type"), 64) or None,
            "source_domain": _clean(media.get("canonical_domain"), 256) or None,
        },
        "primary_claim": ({
            "id": claim_id,
            "canonical_text": _clean(primary_claim.get("canonical_text"), 1000),
            "claim_type": _clean(primary_claim.get("claim_type"), 64),
        } if primary_claim else None),
        "story": ({
            "id": _clean(story.get("id"), 128),
            "title": _clean(story.get("canonical_title"), 1000),
            "status": _clean(story.get("status"), 64),
        } if story else None),
        "evidence": _evidence_context(claim_state),
        "related_reports": related,
        "stakeholders": [{key: value for key, value in item.items() if key != "observed_at"} for item in stakeholders],
        "evolution": _evolution(story=story, stakeholders=stakeholders, claim_state=claim_state, connection_factory=connection_factory),
        "policy": {
            "read_only": True,
            "provider_call_performed": False,
            "context_is_not_truth": True,
            "source_count_is_not_independence": True,
            "verified_relationships_only": True,
            "neutral_story_relation_may_be_related_reporting": True,
            "affects_live_merit": False,
        },
    }


__all__ = ["ANALYSIS_RESULT_CONTEXT_VERSION", "build_analysis_result_context"]
