from __future__ import annotations

from typing import Any

from app.intelligence.product_history import (
    PRODUCT_INTELLIGENCE_VERSION,
    _clean,
    _identity,
    _page_events,
)


_PROFILE_POLICY = {
    "chronology_is_not_truth": True,
    "reporting_volume_is_not_reliability": True,
    "source_count_is_not_independence": True,
    "dependency_is_not_falsehood": True,
    "absence_of_verified_independence_is_not_dependence": True,
    "evidence_quantity_is_not_probability": True,
}


def _marks(values: list[str]) -> str:
    return ",".join("?" for _ in values)


def _observation_dependencies(
    conn,
    *,
    observation_ids: list[str],
    upstream_source_id: str = "",
    upstream_reporter_id: str = "",
) -> list[dict[str, Any]]:
    clauses: list[str] = []
    params: list[Any] = []

    if observation_ids:
        marks = _marks(observation_ids)
        for column in (
            "downstream_source_observation_id",
            "downstream_reporter_observation_id",
            "upstream_source_observation_id",
            "upstream_reporter_observation_id",
        ):
            clauses.append(f"{column} IN ({marks})")
            params.extend(observation_ids)

    if upstream_source_id:
        clauses.append("upstream_source_id = ?")
        params.append(upstream_source_id)

    if upstream_reporter_id:
        clauses.append("upstream_reporter_id = ?")
        params.append(upstream_reporter_id)

    if not clauses:
        return []

    rows = conn.execute(
        """
        SELECT
          id,
          downstream_source_observation_id,
          downstream_reporter_observation_id,
          upstream_source_observation_id,
          upstream_reporter_observation_id,
          upstream_source_id,
          upstream_reporter_id,
          relationship_type,
          confidence,
          observed_at,
          recorded_at
        FROM observation_dependencies
        WHERE """
        + " OR ".join(f"({clause})" for clause in clauses)
        + " ORDER BY observed_at, id",
        params,
    ).fetchall()
    return [dict(row) for row in rows]


def _independence_assertions(
    conn,
    *,
    observation_ids: list[str],
) -> list[dict[str, Any]]:
    if not observation_ids:
        return []

    marks = _marks(observation_ids)
    params = observation_ids * 4
    rows = conn.execute(
        f"""
        SELECT
          a.id,
          a.observation_a_source_observation_id,
          a.observation_a_reporter_observation_id,
          a.observation_b_source_observation_id,
          a.observation_b_reporter_observation_id,
          a.provenance_evidence_id,
          a.verification_status,
          a.confidence,
          a.observed_at,
          a.recorded_at,
          e.evidence_type AS provenance_evidence_type,
          e.canonical_url AS provenance_evidence_url,
          e.reference_key AS provenance_reference_key
        FROM observation_independence_assertions a
        JOIN evidence_records e
          ON e.id = a.provenance_evidence_id
        WHERE
          a.observation_a_source_observation_id IN ({marks})
          OR a.observation_a_reporter_observation_id IN ({marks})
          OR a.observation_b_source_observation_id IN ({marks})
          OR a.observation_b_reporter_observation_id IN ({marks})
        ORDER BY a.observed_at, a.id
        """,
        params,
    ).fetchall()
    return [dict(row) for row in rows]


def _verified_independence_count(
    assertions: list[dict[str, Any]],
) -> int:
    return sum(
        1
        for item in assertions
        if _clean(item.get("verification_status"), 32) == "verified"
    )


def _profile_events(
    *,
    observations: list[dict[str, Any]],
    media: list[dict[str, Any]],
    claim_links: list[dict[str, Any]],
    evidence_links: list[dict[str, Any]],
    dependencies: list[dict[str, Any]],
    independence_assertions: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []

    for row in observations:
        event = dict(row)
        event["type"] = event.pop("event_type")
        event["occurred_at"] = event.pop("observed_at")
        events.append(event)

    for row in media:
        events.append(
            {
                "type": "media_attribution",
                "id": row["id"],
                "occurred_at": row["first_seen_at"],
                "media_item_id": row["id"],
                "title": row["title"],
                "mode": row["mode"],
                "canonical_url": row["canonical_url"],
                "source_id": row.get("source_id"),
                "reporter_id": row.get("reporter_id"),
                "published_at": row.get("published_at"),
            }
        )

    for row in claim_links:
        event = dict(row)
        event["type"] = "claim_link"
        event["occurred_at"] = event.pop("observed_at")
        events.append(event)

    for row in evidence_links:
        event = dict(row)
        event["type"] = "evidence_link"
        event["occurred_at"] = event.pop("observed_at")
        events.append(event)

    for row in dependencies:
        event = dict(row)
        event["type"] = "observation_dependency"
        event["occurred_at"] = event.pop("observed_at")
        events.append(event)

    for row in independence_assertions:
        event = dict(row)
        event["type"] = "independence_assertion"
        event["occurred_at"] = event.pop("observed_at")
        events.append(event)

    return events


def source_history(
    *,
    source_id: str,
    connection_factory,
    after: str = "",
    before: str = "",
    limit: int = 100,
    cursor: str = "",
) -> dict[str, Any] | None:
    conn = connection_factory()
    try:
        source = _identity(conn, "intelligence_sources", source_id)
        if source is None:
            return None

        source_observations = [
            dict(row)
            for row in conn.execute(
                """
                SELECT
                  id, source_id, media_item_id, story_id, subject_key,
                  observation_type, status, claim_summary, provenance_url,
                  confidence, observed_at, recorded_at
                FROM source_observations
                WHERE source_id = ?
                ORDER BY observed_at, id
                """,
                (source_id,),
            ).fetchall()
        ]
        reporter_observations = [
            dict(row)
            for row in conn.execute(
                """
                SELECT
                  id, reporter_id, source_id, media_item_id, story_id,
                  subject_key, observation_type, status, claim_summary,
                  provenance_url, confidence, observed_at, recorded_at
                FROM reporter_observations
                WHERE source_id = ?
                ORDER BY observed_at, id
                """,
                (source_id,),
            ).fetchall()
        ]
        media = [
            dict(row)
            for row in conn.execute(
                """
                SELECT
                  id, canonical_url, mode, source_id, reporter_id, title,
                  published_at, first_seen_at, last_seen_at
                FROM media_items
                WHERE source_id = ?
                ORDER BY first_seen_at, id
                """,
                (source_id,),
            ).fetchall()
        ]

        observation_ids = [row["id"] for row in source_observations]
        observation_ids += [row["id"] for row in reporter_observations]

        claim_links: list[dict[str, Any]] = []
        if observation_ids:
            marks = _marks(observation_ids)
            claim_links = [
                dict(row)
                for row in conn.execute(
                    f"""
                    SELECT DISTINCT
                      cl.id, cl.claim_id, cl.source_observation_id,
                      cl.reporter_observation_id, cl.relationship_type,
                      cl.confidence, cl.observed_at,
                      c.canonical_text, c.subject_key, c.claim_type
                    FROM claim_links cl
                    JOIN intelligence_claims c ON c.id = cl.claim_id
                    WHERE cl.source_observation_id IN ({marks})
                       OR cl.reporter_observation_id IN ({marks})
                    ORDER BY cl.observed_at, cl.id
                    """,
                    observation_ids + observation_ids,
                ).fetchall()
            ]

        story_ids = {
            _clean(row.get("story_id"), 128)
            for row in source_observations + reporter_observations
            if _clean(row.get("story_id"), 128)
        }
        media_ids = [row["id"] for row in media]
        if media_ids:
            marks = _marks(media_ids)
            story_ids.update(
                _clean(row["story_id"], 128)
                for row in conn.execute(
                    f"""
                    SELECT DISTINCT story_id
                    FROM story_media_links
                    WHERE media_item_id IN ({marks})
                    ORDER BY story_id
                    """,
                    media_ids,
                ).fetchall()
            )

        claim_ids = sorted({row["claim_id"] for row in claim_links})
        if claim_ids:
            marks = _marks(claim_ids)
            story_ids.update(
                _clean(row["story_id"], 128)
                for row in conn.execute(
                    f"""
                    SELECT DISTINCT story_id
                    FROM story_claim_links
                    WHERE claim_id IN ({marks})
                    ORDER BY story_id
                    """,
                    claim_ids,
                ).fetchall()
            )

        ordered_story_ids = sorted(value for value in story_ids if value)
        stories: list[dict[str, Any]] = []
        if ordered_story_ids:
            marks = _marks(ordered_story_ids)
            stories = [
                dict(row)
                for row in conn.execute(
                    f"""
                    SELECT id, canonical_title, status, first_seen_at, last_seen_at
                    FROM intelligence_stories
                    WHERE id IN ({marks})
                    ORDER BY first_seen_at, id
                    """,
                    ordered_story_ids,
                ).fetchall()
            ]

        reporters = [
            dict(row)
            for row in conn.execute(
                """
                SELECT DISTINCT
                  r.id, r.identity_key, r.display_name,
                  r.first_seen_at, r.last_seen_at
                FROM intelligence_reporters r
                WHERE r.id IN (
                  SELECT reporter_id FROM reporter_observations
                  WHERE source_id = ? AND reporter_id IS NOT NULL
                  UNION
                  SELECT reporter_id FROM media_items
                  WHERE source_id = ? AND reporter_id IS NOT NULL
                )
                ORDER BY r.display_name, r.id
                """,
                (source_id, source_id),
            ).fetchall()
        ]

        evidence_links = [
            dict(row)
            for row in conn.execute(
                """
                SELECT
                  l.id, l.evidence_id, l.relationship_type, l.confidence,
                  l.linked_at, e.evidence_type, e.subject_key,
                  e.claim_summary, e.canonical_url, e.reference_key,
                  e.verification_status, e.published_at, e.observed_at
                FROM evidence_links l
                JOIN evidence_records e ON e.id = l.evidence_id
                WHERE l.source_id = ?
                ORDER BY e.observed_at, l.id
                """,
                (source_id,),
            ).fetchall()
        ]

        dependencies = _observation_dependencies(
            conn,
            observation_ids=observation_ids,
            upstream_source_id=source_id,
        )
        independence_assertions = _independence_assertions(
            conn,
            observation_ids=observation_ids,
        )
    finally:
        conn.close()

    observations = [
        {"event_type": "source_observation", **row}
        for row in source_observations
    ] + [
        {"event_type": "reporter_observation", **row}
        for row in reporter_observations
    ]
    events = _profile_events(
        observations=observations,
        media=media,
        claim_links=claim_links,
        evidence_links=evidence_links,
        dependencies=dependencies,
        independence_assertions=independence_assertions,
    )
    page = _page_events(
        events,
        scope="source:" + source_id,
        after=after,
        before=before,
        limit=limit,
        cursor=cursor,
    )

    public_source = {
        key: source[key]
        for key in (
            "id",
            "source_key",
            "display_name",
            "source_type",
            "canonical_domain",
            "publication_founded_at",
            "domain_registered_at",
            "first_seen_at",
            "last_seen_at",
        )
    }
    return {
        "version": PRODUCT_INTELLIGENCE_VERSION,
        "source": public_source,
        "counts": {
            "observations": len(source_observations) + len(reporter_observations),
            "direct_source_observations": len(source_observations),
            "reporter_observations": len(reporter_observations),
            "media_items": len(media),
            "claims": len(claim_ids),
            "stories": len(stories),
            "reporters": len(reporters),
            "dependency_links": len(dependencies),
            "independence_assertions": len(independence_assertions),
            "verified_independence_assertions": _verified_independence_count(independence_assertions),
            "evidence_links": len(evidence_links),
        },
        "media": media,
        "claims": claim_links,
        "stories": stories,
        "reporters": reporters,
        "dependencies": dependencies,
        "independence_assertions": independence_assertions,
        "evidence_links": evidence_links,
        **page,
        "policy": dict(_PROFILE_POLICY),
    }


def reporter_history(
    *,
    reporter_id: str,
    connection_factory,
    after: str = "",
    before: str = "",
    limit: int = 100,
    cursor: str = "",
) -> dict[str, Any] | None:
    conn = connection_factory()
    try:
        reporter = _identity(conn, "intelligence_reporters", reporter_id)
        if reporter is None:
            return None

        observations = [
            dict(row)
            for row in conn.execute(
                """
                SELECT
                  id, reporter_id, source_id, media_item_id, story_id,
                  subject_key, observation_type, status, claim_summary,
                  provenance_url, confidence, observed_at, recorded_at
                FROM reporter_observations
                WHERE reporter_id = ?
                ORDER BY observed_at, id
                """,
                (reporter_id,),
            ).fetchall()
        ]
        media = [
            dict(row)
            for row in conn.execute(
                """
                SELECT
                  id, canonical_url, mode, source_id, reporter_id, title,
                  published_at, first_seen_at, last_seen_at
                FROM media_items
                WHERE reporter_id = ?
                ORDER BY first_seen_at, id
                """,
                (reporter_id,),
            ).fetchall()
        ]
        observation_ids = [row["id"] for row in observations]

        claim_links: list[dict[str, Any]] = []
        if observation_ids:
            marks = _marks(observation_ids)
            claim_links = [
                dict(row)
                for row in conn.execute(
                    f"""
                    SELECT DISTINCT
                      cl.id, cl.claim_id, cl.reporter_observation_id,
                      cl.relationship_type, cl.confidence, cl.observed_at,
                      c.canonical_text, c.subject_key, c.claim_type
                    FROM claim_links cl
                    JOIN intelligence_claims c ON c.id = cl.claim_id
                    WHERE cl.reporter_observation_id IN ({marks})
                    ORDER BY cl.observed_at, cl.id
                    """,
                    observation_ids,
                ).fetchall()
            ]

        story_ids = {
            _clean(row.get("story_id"), 128)
            for row in observations
            if _clean(row.get("story_id"), 128)
        }
        media_ids = [row["id"] for row in media]
        if media_ids:
            marks = _marks(media_ids)
            story_ids.update(
                _clean(row["story_id"], 128)
                for row in conn.execute(
                    f"""
                    SELECT DISTINCT story_id
                    FROM story_media_links
                    WHERE media_item_id IN ({marks})
                    ORDER BY story_id
                    """,
                    media_ids,
                ).fetchall()
            )

        claim_ids = sorted({row["claim_id"] for row in claim_links})
        if claim_ids:
            marks = _marks(claim_ids)
            story_ids.update(
                _clean(row["story_id"], 128)
                for row in conn.execute(
                    f"""
                    SELECT DISTINCT story_id
                    FROM story_claim_links
                    WHERE claim_id IN ({marks})
                    ORDER BY story_id
                    """,
                    claim_ids,
                ).fetchall()
            )

        ordered_story_ids = sorted(value for value in story_ids if value)
        stories: list[dict[str, Any]] = []
        if ordered_story_ids:
            marks = _marks(ordered_story_ids)
            stories = [
                dict(row)
                for row in conn.execute(
                    f"""
                    SELECT id, canonical_title, status, first_seen_at, last_seen_at
                    FROM intelligence_stories
                    WHERE id IN ({marks})
                    ORDER BY first_seen_at, id
                    """,
                    ordered_story_ids,
                ).fetchall()
            ]

        sources = [
            dict(row)
            for row in conn.execute(
                """
                SELECT DISTINCT
                  s.id, s.source_key, s.display_name, s.source_type,
                  s.canonical_domain, s.first_seen_at, s.last_seen_at
                FROM intelligence_sources s
                WHERE s.id IN (
                  SELECT source_id FROM reporter_observations
                  WHERE reporter_id = ? AND source_id IS NOT NULL
                  UNION
                  SELECT source_id FROM media_items
                  WHERE reporter_id = ? AND source_id IS NOT NULL
                )
                ORDER BY s.display_name, s.id
                """,
                (reporter_id, reporter_id),
            ).fetchall()
        ]

        evidence_links = [
            dict(row)
            for row in conn.execute(
                """
                SELECT
                  l.id, l.evidence_id, l.relationship_type, l.confidence,
                  l.linked_at, e.evidence_type, e.subject_key,
                  e.claim_summary, e.canonical_url, e.reference_key,
                  e.verification_status, e.published_at, e.observed_at
                FROM evidence_links l
                JOIN evidence_records e ON e.id = l.evidence_id
                WHERE l.reporter_id = ?
                ORDER BY e.observed_at, l.id
                """,
                (reporter_id,),
            ).fetchall()
        ]
        dependencies = _observation_dependencies(
            conn,
            observation_ids=observation_ids,
            upstream_reporter_id=reporter_id,
        )
        independence_assertions = _independence_assertions(
            conn,
            observation_ids=observation_ids,
        )
    finally:
        conn.close()

    profile_observations = [
        {"event_type": "reporter_observation", **row}
        for row in observations
    ]
    events = _profile_events(
        observations=profile_observations,
        media=media,
        claim_links=claim_links,
        evidence_links=evidence_links,
        dependencies=dependencies,
        independence_assertions=independence_assertions,
    )
    page = _page_events(
        events,
        scope="reporter:" + reporter_id,
        after=after,
        before=before,
        limit=limit,
        cursor=cursor,
    )

    public_reporter = {
        key: reporter[key]
        for key in (
            "id",
            "identity_key",
            "display_name",
            "first_seen_at",
            "last_seen_at",
        )
    }
    return {
        "version": PRODUCT_INTELLIGENCE_VERSION,
        "reporter": public_reporter,
        "counts": {
            "observations": len(observations),
            "media_items": len(media),
            "claims": len(claim_ids),
            "stories": len(stories),
            "sources": len(sources),
            "dependency_links": len(dependencies),
            "independence_assertions": len(independence_assertions),
            "verified_independence_assertions": _verified_independence_count(independence_assertions),
            "evidence_links": len(evidence_links),
        },
        "media": media,
        "claims": claim_links,
        "stories": stories,
        "sources": sources,
        "dependencies": dependencies,
        "independence_assertions": independence_assertions,
        "evidence_links": evidence_links,
        **page,
        "policy": dict(_PROFILE_POLICY),
    }


__all__ = ["source_history", "reporter_history"]
