from __future__ import annotations

import json
import math

from datetime import datetime
from typing import Any, Mapping

from app.intelligence.stories import story_id_for_canonical_key
from app.story import story_claim_graph_materialization as story_graph


REPORTING_COVERAGE_VERSION = "reporting-coverage-v1"


def _clean(value: Any, maximum: int = 2048) -> str:
    return " ".join(str(value or "").split())[:maximum]


def _row(value: Any) -> dict[str, Any] | None:
    return dict(value) if value is not None else None


def _json_object(value: Any, *, label: str) -> dict[str, Any]:
    try:
        parsed = json.loads(str(value or "{}"))
    except (TypeError, ValueError, json.JSONDecodeError) as error:
        raise story_graph.StoryClaimGraphMaterializationIntegrityError(
            label + " metadata is invalid."
        ) from error
    if not isinstance(parsed, dict):
        raise story_graph.StoryClaimGraphMaterializationIntegrityError(
            label + " metadata is invalid."
        )
    return dict(parsed)


def _aware_timestamp(value: Any, *, label: str) -> datetime:
    text = _clean(value, 128)
    try:
        parsed = datetime.fromisoformat(
            text[:-1] + "+00:00" if text.endswith("Z") else text
        )
        offset = parsed.utcoffset()
    except (TypeError, ValueError, OverflowError) as error:
        raise story_graph.StoryClaimGraphMaterializationIntegrityError(
            label + " timestamp is invalid."
        ) from error
    if offset is None:
        raise story_graph.StoryClaimGraphMaterializationIntegrityError(
            label + " timestamp must include a timezone."
        )
    return parsed


def _optional_aware_timestamp(value: Any, *, label: str) -> datetime | None:
    return _aware_timestamp(value, label=label) if _clean(value, 128) else None


def _validated_story(
    conn,
    *,
    claim: Mapping[str, Any],
) -> dict[str, Any]:
    claim_id = _clean(claim.get("id"), 128)
    subject_key = _clean(claim.get("subject_key"), 256)
    canonical_key = (
        story_graph.STORY_CANONICAL_KEY_PREFIX + "|claim:" + claim_id
    )
    expected_story_id = story_id_for_canonical_key(canonical_key)

    story = _row(
        conn.execute(
            "SELECT * FROM intelligence_stories WHERE canonical_key = ?",
            (canonical_key,),
        ).fetchone()
    )
    by_id = _row(
        conn.execute(
            "SELECT * FROM intelligence_stories WHERE id = ?",
            (expected_story_id,),
        ).fetchone()
    )
    if story is None or by_id is None:
        raise story_graph.StoryClaimGraphMaterializationIntegrityError(
            "Deterministic canonical claim story is not persisted."
        )
    if (
        _clean(story.get("id"), 128) != expected_story_id
        or _clean(by_id.get("canonical_key")) != canonical_key
    ):
        raise story_graph.StoryClaimGraphMaterializationIntegrityError(
            "Deterministic canonical story identity is inconsistent."
        )

    metadata = _json_object(
        story.get("metadata_json"),
        label="Canonical story",
    )
    if (
        _clean(metadata.get("claim_id"), 128) != claim_id
        or _clean(metadata.get("subject_key"), 256) != subject_key
        or _clean(metadata.get("materialization_basis"), 128)
        != story_graph.STORY_CLAIM_LINK_BASIS
        or _clean(
            metadata.get("canonical_claim_story_materialization_version"),
            128,
        )
        != story_graph.CANONICAL_CLAIM_STORY_MATERIALIZATION_VERSION
    ):
        raise story_graph.StoryClaimGraphMaterializationIntegrityError(
            "Canonical story provenance is inconsistent."
        )

    links = [
        dict(row)
        for row in conn.execute(
            """
            SELECT *
            FROM story_claim_links
            WHERE story_id = ?
            ORDER BY claim_id
            """,
            (expected_story_id,),
        ).fetchall()
    ]
    if len(links) != 1:
        raise story_graph.StoryClaimGraphMaterializationIntegrityError(
            "Canonical story claim scope is inconsistent."
        )
    link = links[0]
    if (
        _clean(link.get("claim_id"), 128) != claim_id
        or _clean(link.get("relationship_type"), 64)
        != story_graph.STORY_CLAIM_RELATIONSHIP_TYPE
        or _clean(link.get("link_basis"), 128)
        != story_graph.STORY_CLAIM_LINK_BASIS
    ):
        raise story_graph.StoryClaimGraphMaterializationIntegrityError(
            "Canonical story claim provenance is inconsistent."
        )
    link_metadata = _json_object(
        link.get("metadata_json"),
        label="Canonical story claim link",
    )
    if (
        _clean(link_metadata.get("materialization_version"), 128)
        != story_graph.STORY_CLAIM_GRAPH_MATERIALIZATION_VERSION
    ):
        raise story_graph.StoryClaimGraphMaterializationIntegrityError(
            "Canonical story claim path provenance is inconsistent."
        )
    return story


def _coverage_rows(
    conn,
    *,
    claim_ids: list[str],
) -> list[dict[str, Any]]:
    placeholders = ",".join("?" for _ in claim_ids)
    parameters = tuple(claim_ids) + tuple(claim_ids)
    return [
        dict(row)
        for row in conn.execute(
            f"""
            SELECT
              'source' AS observation_kind,
              cl.id AS claim_link_id,
              o.id AS observation_id,
              o.subject_key AS observation_subject_key,
              o.media_item_id AS observation_media_item_id,
              o.observed_at AS reporting_observed_at,
              NULL AS observation_reporter_id,
              NULL AS persisted_observation_reporter_id,
              m.id AS media_item_id,
              m.canonical_url,
              m.mode,
              m.title,
              m.published_at,
              m.first_seen_at,
              m.last_seen_at,
              m.source_id AS media_source_id,
              m.reporter_id AS media_reporter_id,
              s.id AS source_id,
              s.display_name AS source_name,
              s.source_type,
              s.canonical_domain,
              dr.id AS direct_reporter_id,
              dr.display_name AS direct_reporter_name,
              NULL AS observation_reporter_name
            FROM claim_links AS cl
            JOIN source_observations AS o
              ON o.id = cl.source_observation_id
            LEFT JOIN media_items AS m
              ON m.id = o.media_item_id
            LEFT JOIN intelligence_sources AS s
              ON s.id = m.source_id
            LEFT JOIN intelligence_reporters AS dr
              ON dr.id = m.reporter_id
            WHERE cl.claim_id IN ({placeholders})
              AND cl.relationship_type = 'reports'
              AND cl.source_observation_id IS NOT NULL

            UNION ALL

            SELECT
              'reporter' AS observation_kind,
              cl.id AS claim_link_id,
              o.id AS observation_id,
              o.subject_key AS observation_subject_key,
              o.media_item_id AS observation_media_item_id,
              o.observed_at AS reporting_observed_at,
              o.reporter_id AS observation_reporter_id,
              r.id AS persisted_observation_reporter_id,
              m.id AS media_item_id,
              m.canonical_url,
              m.mode,
              m.title,
              m.published_at,
              m.first_seen_at,
              m.last_seen_at,
              m.source_id AS media_source_id,
              m.reporter_id AS media_reporter_id,
              s.id AS source_id,
              s.display_name AS source_name,
              s.source_type,
              s.canonical_domain,
              dr.id AS direct_reporter_id,
              dr.display_name AS direct_reporter_name,
              r.display_name AS observation_reporter_name
            FROM claim_links AS cl
            JOIN reporter_observations AS o
              ON o.id = cl.reporter_observation_id
            LEFT JOIN media_items AS m
              ON m.id = o.media_item_id
            LEFT JOIN intelligence_reporters AS r
              ON r.id = o.reporter_id
            LEFT JOIN intelligence_sources AS s
              ON s.id = m.source_id
            LEFT JOIN intelligence_reporters AS dr
              ON dr.id = m.reporter_id
            WHERE cl.claim_id IN ({placeholders})
              AND cl.relationship_type = 'reports'
              AND cl.reporter_observation_id IS NOT NULL

            ORDER BY media_item_id, observation_kind, observation_id
            """,
            parameters,
        ).fetchall()
    ]


def _validated_claim_scope(
    conn,
    *,
    canonical_claim_id: str,
) -> tuple[dict[str, Any], list[str]]:
    claim = story_graph._validated_structured_claim(conn, canonical_claim_id)
    if conn.execute(
        """
        SELECT production_claim_id
        FROM claim_identity_mappings
        WHERE production_claim_id = ?
        """,
        (canonical_claim_id,),
    ).fetchone() is not None:
        raise story_graph.StoryClaimGraphMaterializationIntegrityError(
            "A canonical structured claim cannot act as a legacy mapping source."
        )

    legacy_ids = story_graph._validated_legacy_ids(conn, claim)
    if legacy_ids:
        placeholders = ",".join("?" for _ in legacy_ids)
        if conn.execute(
            f"""
            SELECT production_claim_id
            FROM claim_identity_mappings
            WHERE canonical_claim_id IN ({placeholders})
            LIMIT 1
            """,
            tuple(legacy_ids),
        ).fetchone() is not None:
            raise story_graph.StoryClaimGraphMaterializationIntegrityError(
                "Claim identity mapping chain or cycle is not allowed."
            )
    return claim, legacy_ids


def _validate_story_media(
    conn,
    *,
    story_id: str,
    qualifying_media_ids: set[str],
) -> None:
    rows = [
        dict(row)
        for row in conn.execute(
            """
            SELECT *
            FROM story_media_links
            WHERE story_id = ?
            ORDER BY media_item_id
            """,
            (story_id,),
        ).fetchall()
    ]
    persisted_ids: set[str] = set()
    for row in rows:
        media_id = _clean(row.get("media_item_id"), 128)
        try:
            confidence = float(row.get("confidence"))
        except (TypeError, ValueError) as error:
            raise story_graph.StoryClaimGraphMaterializationIntegrityError(
                "Canonical story media confidence is invalid."
            ) from error
        if (
            not media_id
            or _clean(row.get("relationship_type"), 64)
            != story_graph.STORY_MEDIA_RELATIONSHIP_TYPE
            or not math.isfinite(confidence)
            or abs(confidence - story_graph.STORY_MEDIA_STRUCTURAL_CONFIDENCE)
            > 1e-9
        ):
            raise story_graph.StoryClaimGraphMaterializationIntegrityError(
                "Canonical story media semantics are inconsistent."
            )
        persisted_ids.add(media_id)
    if persisted_ids != qualifying_media_ids:
        raise story_graph.StoryClaimGraphMaterializationIntegrityError(
            "Canonical reporting graph and story media graph are inconsistent."
        )


def build_claim_reporting_coverage(
    *,
    canonical_claim_id: str,
    connection_factory,
) -> dict[str, Any]:
    if connection_factory is None:
        raise ValueError("Reporting coverage requires database access.")
    requested_id = _clean(canonical_claim_id, 128)
    if not requested_id:
        raise ValueError("Reporting coverage canonical_claim_id is required.")

    conn = connection_factory()
    try:
        if conn.execute(
            "SELECT id FROM intelligence_claims WHERE id = ?",
            (requested_id,),
        ).fetchone() is None:
            return {
                "version": REPORTING_COVERAGE_VERSION,
                "status": "not_found",
                "canonical_claim_id": requested_id,
            }

        claim, legacy_ids = _validated_claim_scope(
            conn,
            canonical_claim_id=requested_id,
        )
        story = _validated_story(conn, claim=claim)
        rows = _coverage_rows(
            conn,
            claim_ids=[requested_id, *legacy_ids],
        )

        media_by_id: dict[str, dict[str, Any]] = {}
        for row in rows:
            if _clean(row.get("observation_subject_key"), 256) != _clean(
                claim.get("subject_key"), 256
            ):
                raise story_graph.StoryClaimGraphMaterializationIntegrityError(
                    "Claim-linked observation subject is inconsistent."
                )
            if not _clean(row.get("observation_media_item_id"), 128):
                continue
            media_id = _clean(row.get("media_item_id"), 128)
            if not media_id:
                raise story_graph.StoryClaimGraphMaterializationIntegrityError(
                    "Claim-linked reporting media item is missing."
                )
            observation_reporter_id = _clean(
                row.get("observation_reporter_id"), 128
            )
            if observation_reporter_id and observation_reporter_id != _clean(
                row.get("persisted_observation_reporter_id"), 128
            ):
                raise story_graph.StoryClaimGraphMaterializationIntegrityError(
                    "Claim-linked reporter identity is missing."
                )
            if _clean(row.get("media_source_id"), 128) and not _clean(
                row.get("source_id"), 128
            ):
                raise story_graph.StoryClaimGraphMaterializationIntegrityError(
                    "Persisted media source identity is missing."
                )
            if _clean(row.get("media_reporter_id"), 128) and not _clean(
                row.get("direct_reporter_id"), 128
            ):
                raise story_graph.StoryClaimGraphMaterializationIntegrityError(
                    "Persisted media reporter identity is missing."
                )

            observed_text = _clean(row.get("reporting_observed_at"), 128)
            observed_value = _aware_timestamp(
                observed_text,
                label="Reporting observation",
            )
            published_value = _optional_aware_timestamp(
                row.get("published_at"),
                label="Media publication",
            )
            item = media_by_id.setdefault(
                media_id,
                {
                    "media_item_id": media_id,
                    "mode": _clean(row.get("mode"), 64),
                    "title": _clean(row.get("title"), 1000),
                    "canonical_url": _clean(row.get("canonical_url"), 2048),
                    "published_at": _clean(row.get("published_at"), 128) or None,
                    "first_seen_at": _clean(row.get("first_seen_at"), 128),
                    "last_seen_at": _clean(row.get("last_seen_at"), 128),
                    "_published_value": published_value,
                    "_observations": [],
                    "_reporters": {},
                    "source": (
                        {
                            "source_id": _clean(row.get("source_id"), 128),
                            "display_name": _clean(row.get("source_name"), 512),
                            "source_type": _clean(row.get("source_type"), 64),
                            "canonical_domain": (
                                _clean(row.get("canonical_domain"), 512) or None
                            ),
                        }
                        if _clean(row.get("source_id"), 128)
                        else None
                    ),
                },
            )
            item["_observations"].append((observed_value, observed_text))

            direct_id = _clean(row.get("direct_reporter_id"), 128)
            if direct_id:
                item["_reporters"][direct_id] = {
                    "reporter_id": direct_id,
                    "display_name": _clean(row.get("direct_reporter_name"), 512),
                }
            if observation_reporter_id:
                item["_reporters"][observation_reporter_id] = {
                    "reporter_id": observation_reporter_id,
                    "display_name": _clean(
                        row.get("observation_reporter_name"), 512
                    ),
                }

        _validate_story_media(
            conn,
            story_id=_clean(story.get("id"), 128),
            qualifying_media_ids=set(media_by_id),
        )
    finally:
        conn.close()

    media = []
    all_observations: list[tuple[datetime, str]] = []
    source_ids: set[str] = set()
    reporter_ids: set[str] = set()
    for item in media_by_id.values():
        observations = item.pop("_observations")
        observations.sort(key=lambda value: value[0])
        all_observations.extend(observations)
        item["reporting_first_observed_at"] = observations[0][1]
        item["reporting_last_observed_at"] = observations[-1][1]
        reporters_by_id = item.pop("_reporters")
        reporters = sorted(
            reporters_by_id.values(),
            key=lambda reporter: (
                reporter["display_name"].casefold(),
                reporter["reporter_id"],
            ),
        )
        item["reporters"] = reporters
        reporter_ids.update(reporters_by_id)
        source = item.get("source")
        if isinstance(source, dict) and source.get("source_id"):
            source_ids.add(source["source_id"])
        media.append(item)

    media.sort(
        key=lambda item: (
            _aware_timestamp(
                item["reporting_first_observed_at"],
                label="Reporting observation",
            ),
            item["_published_value"] is None,
            item["_published_value"] or datetime.max.replace(
                tzinfo=_aware_timestamp(
                    item["reporting_first_observed_at"],
                    label="Reporting observation",
                ).tzinfo
            ),
            item["media_item_id"],
        )
    )
    for item in media:
        item.pop("_published_value")

    all_observations.sort(key=lambda value: value[0])
    return {
        "version": REPORTING_COVERAGE_VERSION,
        "status": "ok",
        "canonical_claim": {
            "id": requested_id,
            "canonical_text": _clean(claim.get("canonical_text"), 1000),
            "claim_type": _clean(claim.get("claim_type"), 64),
            "subject_key": _clean(claim.get("subject_key"), 256),
        },
        "story": {
            "id": _clean(story.get("id"), 128),
            "canonical_key": _clean(story.get("canonical_key")),
            "canonical_title": _clean(story.get("canonical_title"), 1000),
        },
        "coverage": {
            "media_items": len(media),
            "distinct_sources": len(source_ids),
            "distinct_reporters": len(reporter_ids),
            "first_observed_at": (
                all_observations[0][1] if all_observations else None
            ),
            "last_observed_at": (
                all_observations[-1][1] if all_observations else None
            ),
        },
        "media": media,
        "policy": {
            "reporting_coverage_only": True,
            "establishes_truth": False,
            "establishes_verification": False,
            "establishes_independence": False,
            "source_count_is_not_independence": True,
            "provider_call_performed": False,
        },
    }


__all__ = [
    "REPORTING_COVERAGE_VERSION",
    "build_claim_reporting_coverage",
]
