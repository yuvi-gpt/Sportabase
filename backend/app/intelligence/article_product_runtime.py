from __future__ import annotations

import json
from collections import Counter
from typing import Any, Mapping

from app.intelligence.projection import (
    build_claim_projection,
    build_story_projection,
)
from app.services.content_resolution import normalized_analysis_url


ARTICLE_PRODUCT_INTELLIGENCE_VERSION = (
    "article-product-intelligence-runtime-v1"
)
ARTICLE_PRODUCT_INTELLIGENCE_ATTACHMENT_VERSION = (
    "article-product-intelligence-attachment-v1"
)

_MAX_CLAIMS = 16
_MAX_STORIES = 16


def _clean(value: Any, maximum: int = 1000) -> str:
    return " ".join(str(value or "").split())[:maximum]


def _json_object(value: Any) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)

    text = str(value or "").strip()
    if not text:
        return {}

    try:
        parsed = json.loads(text)
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}

    return dict(parsed) if isinstance(parsed, dict) else {}


def _media_record(
    *,
    url: str,
    connection_factory,
) -> tuple[str, dict[str, Any] | None]:
    canonical_url = _clean(normalized_analysis_url(url), 2048)
    if not canonical_url:
        raise ValueError("Article intelligence runtime requires a valid URL.")

    conn = connection_factory()
    try:
        row = conn.execute(
            """
            SELECT
              id,
              canonical_url,
              mode,
              source_id,
              reporter_id,
              title,
              published_at,
              first_seen_at,
              last_seen_at,
              metadata_json
            FROM media_items
            WHERE canonical_url = ?
            LIMIT 1
            """,
            (canonical_url,),
        ).fetchone()
    finally:
        conn.close()

    return canonical_url, (dict(row) if row is not None else None)


def _claim_ids_for_media(
    *,
    media_item_id: str,
    connection_factory,
) -> tuple[list[str], bool]:
    conn = connection_factory()
    try:
        rows = conn.execute(
            """
            SELECT DISTINCT claim_id
            FROM (
              SELECT cl.claim_id AS claim_id
              FROM claim_links AS cl
              JOIN source_observations AS source_observation
                ON source_observation.id = cl.source_observation_id
              WHERE source_observation.media_item_id = ?

              UNION

              SELECT cl.claim_id AS claim_id
              FROM claim_links AS cl
              JOIN reporter_observations AS reporter_observation
                ON reporter_observation.id = cl.reporter_observation_id
              WHERE reporter_observation.media_item_id = ?

              UNION

              SELECT cl.claim_id AS claim_id
              FROM claim_links AS cl
              JOIN evidence_links AS evidence_link
                ON evidence_link.evidence_id = cl.evidence_id
              WHERE evidence_link.media_item_id = ?

              UNION

              SELECT story_claim.claim_id AS claim_id
              FROM story_media_links AS story_media
              JOIN story_claim_links AS story_claim
                ON story_claim.story_id = story_media.story_id
              WHERE story_media.media_item_id = ?
            )
            WHERE claim_id IS NOT NULL AND claim_id != ''
            ORDER BY claim_id
            """,
            (
                media_item_id,
                media_item_id,
                media_item_id,
                media_item_id,
            ),
        ).fetchall()
    finally:
        conn.close()

    ids = [
        _clean(row["claim_id"], 128)
        for row in rows
        if _clean(row["claim_id"], 128)
    ]
    truncated = len(ids) > _MAX_CLAIMS
    return ids[:_MAX_CLAIMS], truncated


def _direct_story_ids_for_media(
    *,
    media_item_id: str,
    connection_factory,
) -> list[str]:
    conn = connection_factory()
    try:
        rows = conn.execute(
            """
            SELECT story_id
            FROM story_media_links
            WHERE media_item_id = ?
            ORDER BY story_id
            """,
            (media_item_id,),
        ).fetchall()
    finally:
        conn.close()

    return [
        _clean(row["story_id"], 128)
        for row in rows
        if _clean(row["story_id"], 128)
    ]


def _claim_identity_metadata(
    *,
    claim_ids: list[str],
    connection_factory,
) -> dict[str, dict[str, Any]]:
    if not claim_ids:
        return {}

    placeholders = ",".join("?" for _ in claim_ids)
    conn = connection_factory()
    try:
        rows = conn.execute(
            f"""
            SELECT id, metadata_json
            FROM intelligence_claims
            WHERE id IN ({placeholders})
            """,
            tuple(claim_ids),
        ).fetchall()
    finally:
        conn.close()

    result: dict[str, dict[str, Any]] = {}
    for row in rows:
        claim_id = _clean(row["id"], 128)
        metadata = _json_object(row["metadata_json"])
        structured = metadata.get("structured_claim")
        result[claim_id] = {
            "structured_identity": isinstance(structured, Mapping),
            "identity_source": _clean(metadata.get("identity_source"), 128),
            "core_fingerprint": _clean(metadata.get("core_fingerprint"), 128),
            "structured_claim": (
                dict(structured)
                if isinstance(structured, Mapping)
                else None
            ),
        }

    return result


def _compact_claim_projection(
    projection: Mapping[str, Any],
    identity: Mapping[str, Any],
) -> dict[str, Any]:
    claim = projection.get("claim")
    claim = dict(claim) if isinstance(claim, Mapping) else {}
    state = projection.get("claim_state")
    state = dict(state) if isinstance(state, Mapping) else {}
    support = state.get("support")
    support = dict(support) if isinstance(support, Mapping) else {}
    evidence = state.get("evidence")
    evidence = dict(evidence) if isinstance(evidence, Mapping) else {}
    evidence_counts = evidence.get("counts")
    evidence_counts = (
        dict(evidence_counts)
        if isinstance(evidence_counts, Mapping)
        else {}
    )
    freshness = projection.get("freshness")
    freshness = (
        dict(freshness)
        if isinstance(freshness, Mapping)
        else {}
    )
    adjudication = projection.get("adjudication")
    adjudication = (
        dict(adjudication)
        if isinstance(adjudication, Mapping)
        else {}
    )

    return {
        "claim_id": _clean(claim.get("id"), 128),
        "subject_key": _clean(claim.get("subject_key"), 256),
        "claim_type": _clean(claim.get("claim_type"), 64),
        "canonical_text": _clean(claim.get("canonical_text"), 1000),
        "projection_state": _clean(
            projection.get("projection_state"),
            128,
        ),
        "claim_state": _clean(state.get("claim_state"), 128),
        "support_state": _clean(state.get("support_state"), 128),
        "freshness": {
            "state": _clean(freshness.get("state"), 64),
            "last_activity_at": _clean(
                freshness.get("last_activity_at"),
                128,
            ),
            "age_days": freshness.get("age_days"),
        },
        "support": {
            "observations": int(support.get("observation_count") or 0),
            "distinct_sources": int(support.get("distinct_sources") or 0),
            "distinct_reporters": int(support.get("distinct_reporters") or 0),
            "verified_independent_pairs": int(
                support.get("verified_independent_pairs") or 0
            ),
            "dependency_pairs": int(support.get("dependency_pairs") or 0),
        },
        "evidence": {
            "verified_supporting": int(
                evidence_counts.get("verified_supporting") or 0
            ),
            "verified_conflicting": int(
                evidence_counts.get("verified_conflicting") or 0
            ),
            "verified_total": int(
                evidence_counts.get("verified_total") or 0
            ),
            "unverified_total": int(
                evidence_counts.get("unverified_total") or 0
            ),
        },
        "adjudication_status": _clean(adjudication.get("status"), 64),
        "structured_identity": bool(identity.get("structured_identity")),
        "identity_source": _clean(identity.get("identity_source"), 128),
        "core_fingerprint": _clean(identity.get("core_fingerprint"), 128),
        "structured_claim": identity.get("structured_claim"),
        "conflict_signal_count": len(state.get("conflict_signals") or []),
    }


def _compact_story_projection(
    projection: Mapping[str, Any],
) -> dict[str, Any]:
    story = projection.get("story")
    story = dict(story) if isinstance(story, Mapping) else {}
    counts = projection.get("counts")
    counts = dict(counts) if isinstance(counts, Mapping) else {}

    return {
        "story_id": _clean(story.get("id"), 128),
        "canonical_key": _clean(story.get("canonical_key"), 512),
        "canonical_title": _clean(story.get("canonical_title"), 1000),
        "story_status": _clean(story.get("status"), 64),
        "projection_state": _clean(
            projection.get("projection_state"),
            128,
        ),
        "claims": int(counts.get("claims") or 0),
        "conflict_claims": int(counts.get("conflict_claims") or 0),
        "stale_claims": int(counts.get("stale_claims") or 0),
        "media_items": int(counts.get("media_items") or 0),
        "direct_story_evidence": int(
            counts.get("direct_story_evidence") or 0
        ),
    }


def build_article_product_intelligence(
    *,
    url: str,
    connection_factory,
    stale_after_days: int = 30,
) -> dict[str, Any]:
    if connection_factory is None:
        return {
            "version": ARTICLE_PRODUCT_INTELLIGENCE_VERSION,
            "status": "disabled",
            "reason": "database_unavailable",
            "policy": {
                "read_only": True,
                "provider_call_performed": False,
                "affects_live_merit": False,
            },
        }

    canonical_url, media = _media_record(
        url=url,
        connection_factory=connection_factory,
    )

    if media is None:
        return {
            "version": ARTICLE_PRODUCT_INTELLIGENCE_VERSION,
            "status": "no_media_record",
            "canonical_url": canonical_url,
            "counts": {
                "claims": 0,
                "stories": 0,
                "structured_claims": 0,
                "conflict_claims": 0,
                "stale_claims": 0,
            },
            "claims": [],
            "stories": [],
            "policy": {
                "read_only": True,
                "provider_call_performed": False,
                "no_media_record_is_not_an_error": True,
                "affects_live_merit": False,
            },
        }

    media_item_id = _clean(media.get("id"), 128)
    claim_ids, claim_ids_truncated = _claim_ids_for_media(
        media_item_id=media_item_id,
        connection_factory=connection_factory,
    )
    identity_metadata = _claim_identity_metadata(
        claim_ids=claim_ids,
        connection_factory=connection_factory,
    )

    claim_projections = []
    for claim_id in claim_ids:
        projection = build_claim_projection(
            claim_id=claim_id,
            connection_factory=connection_factory,
            stale_after_days=stale_after_days,
        )
        if projection.get("status") == "ok":
            claim_projections.append(
                _compact_claim_projection(
                    projection,
                    identity_metadata.get(claim_id, {}),
                )
            )

    story_ids = set(
        _direct_story_ids_for_media(
            media_item_id=media_item_id,
            connection_factory=connection_factory,
        )
    )
    for claim_id in claim_ids:
        projection = build_claim_projection(
            claim_id=claim_id,
            connection_factory=connection_factory,
            stale_after_days=stale_after_days,
        )
        for story in projection.get("stories") or []:
            if isinstance(story, Mapping):
                story_id = _clean(story.get("story_id"), 128)
                if story_id:
                    story_ids.add(story_id)

    ordered_story_ids = sorted(story_ids)
    stories_truncated = len(ordered_story_ids) > _MAX_STORIES
    ordered_story_ids = ordered_story_ids[:_MAX_STORIES]

    story_projections = []
    for story_id in ordered_story_ids:
        projection = build_story_projection(
            story_id=story_id,
            connection_factory=connection_factory,
            stale_after_days=stale_after_days,
        )
        if projection.get("status") == "ok":
            story_projections.append(_compact_story_projection(projection))

    state_counts = Counter(
        _clean(item.get("projection_state"), 128) or "unknown"
        for item in claim_projections
    )
    structured_claims = sum(
        1 for item in claim_projections if item.get("structured_identity")
    )
    conflict_claims = sum(
        1
        for item in claim_projections
        if item.get("conflict_signal_count", 0) > 0
        or item.get("projection_state")
        in {"claim_conflict_present", "adjudication_history_conflict"}
    )
    stale_claims = sum(
        1
        for item in claim_projections
        if (item.get("freshness") or {}).get("state") == "stale"
    )

    if conflict_claims:
        runtime_state = "claim_conflicts_present"
    elif structured_claims:
        runtime_state = "structured_claim_context_ready"
    elif claim_projections:
        runtime_state = "claim_context_ready"
    else:
        runtime_state = "no_claim_context"

    return {
        "version": ARTICLE_PRODUCT_INTELLIGENCE_VERSION,
        "status": "ready",
        "runtime_state": runtime_state,
        "media": {
            "id": media_item_id,
            "canonical_url": canonical_url,
            "mode": _clean(media.get("mode"), 64),
            "source_id": _clean(media.get("source_id"), 128),
            "reporter_id": _clean(media.get("reporter_id"), 128),
            "title": _clean(media.get("title"), 1000),
            "published_at": _clean(media.get("published_at"), 128),
            "first_seen_at": _clean(media.get("first_seen_at"), 128),
            "last_seen_at": _clean(media.get("last_seen_at"), 128),
        },
        "counts": {
            "claims": len(claim_projections),
            "stories": len(story_projections),
            "structured_claims": structured_claims,
            "conflict_claims": conflict_claims,
            "stale_claims": stale_claims,
        },
        "claim_projection_states": dict(sorted(state_counts.items())),
        "claims": claim_projections,
        "stories": story_projections,
        "truncated": {
            "claims": claim_ids_truncated,
            "stories": stories_truncated,
        },
        "policy": {
            "read_only": True,
            "provider_call_performed": False,
            "projection_is_context_not_truth": True,
            "structured_identity_is_not_truth": True,
            "verified_evidence_is_not_claim_truth": True,
            "source_count_is_not_independence": True,
            "different_claims_do_not_corroborate_each_other": True,
            "cached_analysis_can_receive_fresh_intelligence_context": True,
            "analysis_snapshot_is_not_rewritten": True,
            "affects_live_merit": False,
        },
    }


def attach_article_product_intelligence(
    *,
    response,
    url: str,
    connection_factory,
    stale_after_days: int = 30,
):
    try:
        runtime = build_article_product_intelligence(
            url=url,
            connection_factory=connection_factory,
            stale_after_days=stale_after_days,
        )
    except Exception as error:
        runtime = {
            "version": ARTICLE_PRODUCT_INTELLIGENCE_VERSION,
            "status": "unavailable",
            "reason": "runtime_exception",
            "error_type": type(error).__name__,
            "policy": {
                "fail_open": True,
                "provider_call_performed": False,
                "affects_live_merit": False,
            },
        }

    attachment_summary = {
        "version": ARTICLE_PRODUCT_INTELLIGENCE_ATTACHMENT_VERSION,
        "status": _clean(runtime.get("status"), 64),
        "runtime_state": _clean(runtime.get("runtime_state"), 128),
        "counts": dict(runtime.get("counts") or {}),
    }

    if isinstance(response, dict):
        intelligence = response.get("intelligence")
        intelligence = dict(intelligence) if isinstance(intelligence, Mapping) else {}
        intelligence["runtime"] = runtime
        response["intelligence"] = intelligence

        debug = response.get("debug")
        debug = dict(debug) if isinstance(debug, Mapping) else {}
        debug["intelligence_runtime"] = attachment_summary
        response["debug"] = debug
        return response

    intelligence = getattr(response, "intelligence", None)
    intelligence = dict(intelligence) if isinstance(intelligence, Mapping) else {}
    intelligence["runtime"] = runtime
    setattr(response, "intelligence", intelligence)

    debug = getattr(response, "debug", None)
    debug = dict(debug) if isinstance(debug, Mapping) else {}
    debug["intelligence_runtime"] = attachment_summary
    setattr(response, "debug", debug)
    return response


__all__ = [
    "ARTICLE_PRODUCT_INTELLIGENCE_VERSION",
    "ARTICLE_PRODUCT_INTELLIGENCE_ATTACHMENT_VERSION",
    "build_article_product_intelligence",
    "attach_article_product_intelligence",
]
