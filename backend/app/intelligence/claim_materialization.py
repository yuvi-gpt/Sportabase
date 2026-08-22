from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Mapping, Sequence

from app.intelligence.claims import identity as claim_identity
from app.intelligence.claims import repository as claim_repository
from app.intelligence.claims import router as claim_router
from app.intelligence.projection import (
    build_claim_projection,
    build_story_projection,
    build_subject_timeline,
)


CLAIM_MATERIALIZATION_VERSION = "canonical-claim-materialization-v1"
CLAIM_MATERIALIZATION_METADATA_VERSION = (
    "canonical-claim-materialization-metadata-v1"
)
_MAX_SPECIFIC_FINGERPRINTS = 128
_MAX_STORY_PROJECTIONS = 20


class ClaimMaterializationError(ValueError):
    pass


class ClaimMaterializationConflictError(ClaimMaterializationError):
    pass


def _clean(value: Any, maximum: int = 1000) -> str:
    return " ".join(str(value or "").split())[:maximum]


def _utc_timestamp(value: Any, *, label: str) -> str:
    text = _clean(value, 128)
    if not text:
        raise ClaimMaterializationError(label + " is required.")

    candidate = text[:-1] + "+00:00" if text.endswith("Z") else text
    try:
        parsed = datetime.fromisoformat(candidate)
    except ValueError as exc:
        raise ClaimMaterializationError(label + " must be ISO-8601.") from exc

    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ClaimMaterializationError(label + " must include a timezone.")

    return parsed.astimezone(timezone.utc).isoformat()


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


def _canonical_json(value: Mapping[str, Any]) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def _active_target(
    *,
    source_observation_id: str | None,
    reporter_observation_id: str | None,
    evidence_id: str | None,
) -> tuple[str, str] | None:
    targets = [
        (
            "source_observation",
            _clean(source_observation_id, 128),
        ),
        (
            "reporter_observation",
            _clean(reporter_observation_id, 128),
        ),
        (
            "evidence",
            _clean(evidence_id, 128),
        ),
    ]
    active = [(kind, value) for kind, value in targets if value]

    if len(active) > 1:
        raise ClaimMaterializationError(
            "Claim materialization accepts at most one link target."
        )

    return active[0] if active else None


def _merge_candidate(
    *,
    existing: Mapping[str, Any],
    incoming: Mapping[str, Any],
) -> dict[str, Any]:
    comparison = claim_identity.compare_canonical_claims(existing, incoming)

    if comparison["status"] == "different_core":
        raise ClaimMaterializationConflictError(
            "Existing structured claim metadata has a different core identity."
        )

    if comparison["status"] == "material_conflict":
        raise ClaimMaterializationConflictError(
            "Incoming structured claim conflicts with stored material semantics: "
            + ", ".join(comparison.get("material_conflicts") or [])
            + "."
        )

    left = claim_identity.normalize_canonical_claim(existing)
    right = claim_identity.normalize_canonical_claim(incoming)

    roles = dict(left["roles"])
    roles.update(right["roles"])
    facets = dict(left["facets"])
    facets.update(right["facets"])

    return claim_identity.normalize_canonical_claim(
        {
            "version": claim_identity.CANONICAL_CLAIM_CONTRACT_VERSION,
            "subject_key": left["subject_key"],
            "event_type": left["event_type"],
            "state": left["state"],
            "negated": left["negated"],
            "roles": roles,
            "facets": facets,
        }
    )


def _metadata_for_materialization(
    *,
    existing_metadata: Mapping[str, Any],
    candidate: Mapping[str, Any],
    core_fingerprint: str,
    specific_fingerprint: str,
    router_version: str,
) -> dict[str, Any]:
    metadata = dict(existing_metadata)

    previous_fingerprints = metadata.get("specific_fingerprints")
    if isinstance(previous_fingerprints, list):
        specific_fingerprints = {
            _clean(item, 128)
            for item in previous_fingerprints
            if _clean(item, 128)
        }
    else:
        specific_fingerprints = set()

    specific_fingerprints.add(_clean(specific_fingerprint, 128))
    ordered_fingerprints = sorted(specific_fingerprints)
    fingerprints_truncated = len(ordered_fingerprints) > _MAX_SPECIFIC_FINGERPRINTS
    ordered_fingerprints = ordered_fingerprints[:_MAX_SPECIFIC_FINGERPRINTS]

    metadata.update(
        {
            "materialization_version": CLAIM_MATERIALIZATION_METADATA_VERSION,
            "identity_contract_version": (
                claim_identity.CANONICAL_CLAIM_CONTRACT_VERSION
            ),
            "router_output_version": _clean(router_version, 128),
            "structured_claim": claim_identity.normalize_canonical_claim(candidate),
            "core_fingerprint": _clean(core_fingerprint, 128),
            "specific_fingerprints": ordered_fingerprints,
            "specific_fingerprints_truncated": fingerprints_truncated,
            "identity_source": "deterministic_structured_claim_core",
        }
    )

    return metadata


def _stored_structured_candidate(existing_row: Mapping[str, Any]) -> dict[str, Any] | None:
    metadata = _json_object(existing_row.get("metadata_json"))
    candidate = metadata.get("structured_claim")
    return dict(candidate) if isinstance(candidate, Mapping) else None


def _latest_seen_at(existing_value: Any, incoming_value: str) -> str:
    existing_text = _clean(existing_value, 128)
    if not existing_text:
        return incoming_value

    existing_candidate = (
        existing_text[:-1] + "+00:00"
        if existing_text.endswith("Z")
        else existing_text
    )

    try:
        existing_dt = datetime.fromisoformat(existing_candidate)
    except ValueError:
        return incoming_value

    if existing_dt.tzinfo is None or existing_dt.utcoffset() is None:
        return incoming_value

    incoming_dt = datetime.fromisoformat(incoming_value)
    return max(
        existing_dt.astimezone(timezone.utc),
        incoming_dt.astimezone(timezone.utc),
    ).isoformat()


def _claim_link_insert(
    *,
    conn,
    claim_id: str,
    target: tuple[str, str] | None,
    relationship_type: str,
    confidence: float | None,
    observed_at: str,
    recorded_at: str,
    core_fingerprint: str,
) -> dict[str, Any] | None:
    if target is None:
        return None

    normalized_relationship = _clean(relationship_type, 64).casefold()
    if not normalized_relationship:
        raise ClaimMaterializationError(
            "Claim materialization relationship_type is required when linking."
        )

    normalized_confidence = None
    if confidence is not None:
        try:
            normalized_confidence = float(confidence)
        except (TypeError, ValueError) as exc:
            raise ClaimMaterializationError(
                "Claim materialization confidence must be numeric."
            ) from exc
        if not 0.0 <= normalized_confidence <= 1.0:
            raise ClaimMaterializationError(
                "Claim materialization confidence must be between 0 and 1."
            )

    target_type, target_id = target
    keyword = {
        "source_observation": "source_observation_id",
        "reporter_observation": "reporter_observation_id",
        "evidence": "evidence_id",
    }[target_type]

    link_args = {
        "claim_id": claim_id,
        "relationship_type": normalized_relationship,
        "observed_at": observed_at,
        "confidence": normalized_confidence,
        "source_observation_id": None,
        "reporter_observation_id": None,
        "evidence_id": None,
    }
    link_args[keyword] = target_id

    link_id = claim_repository.claim_link_id_for_record(**link_args)

    columns = {
        "source_observation": (
            target_id,
            None,
            None,
        ),
        "reporter_observation": (
            None,
            target_id,
            None,
        ),
        "evidence": (
            None,
            None,
            target_id,
        ),
    }[target_type]

    metadata_json = _canonical_json(
        {
            "materialization_version": CLAIM_MATERIALIZATION_VERSION,
            "core_fingerprint": core_fingerprint,
        }
    )

    cursor = conn.execute(
        """
        INSERT INTO claim_links (
          id,
          claim_id,
          source_observation_id,
          reporter_observation_id,
          evidence_id,
          relationship_type,
          confidence,
          observed_at,
          recorded_at,
          metadata_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO NOTHING
        """,
        (
            link_id,
            claim_id,
            columns[0],
            columns[1],
            columns[2],
            normalized_relationship,
            normalized_confidence,
            observed_at,
            recorded_at,
            metadata_json,
        ),
    )

    return {
        "id": link_id,
        "created": cursor.rowcount == 1,
        "target_type": target_type,
        "target_id": target_id,
        "relationship_type": normalized_relationship,
        "confidence": normalized_confidence,
        "observed_at": observed_at,
    }


def materialize_canonical_claim(
    *,
    candidate: Mapping[str, Any],
    claim_text: str,
    observed_at: str,
    connection_factory,
    source_observation_id: str | None = None,
    reporter_observation_id: str | None = None,
    evidence_id: str | None = None,
    relationship_type: str = "reports",
    confidence: float | None = None,
    router_version: str = "",
    stale_after_days: int = 30,
    timeline_limit: int = 100,
) -> dict[str, Any]:
    if connection_factory is None:
        raise ClaimMaterializationError(
            "Claim materialization requires database access."
        )

    normalized_candidate = claim_identity.normalize_canonical_claim(candidate)
    normalized_observed_at = _utc_timestamp(
        observed_at,
        label="Claim materialization observed_at",
    )
    target = _active_target(
        source_observation_id=source_observation_id,
        reporter_observation_id=reporter_observation_id,
        evidence_id=evidence_id,
    )

    core_key = claim_identity.canonical_claim_core_key(normalized_candidate)
    core_fingerprint = claim_identity.canonical_claim_core_fingerprint(
        normalized_candidate
    )
    specific_fingerprint = claim_identity.canonical_claim_specific_fingerprint(
        normalized_candidate
    )
    claim_id = claim_repository.claim_id_for_canonical_key(core_key)
    canonical_text = _clean(claim_text, 4000)
    claim_type = "structured_" + _clean(
        normalized_candidate["event_type"],
        48,
    )

    conn = connection_factory()
    try:
        conn.execute("BEGIN IMMEDIATE")

        existing = conn.execute(
            "SELECT * FROM intelligence_claims WHERE canonical_key = ?",
            (core_key,),
        ).fetchone()
        existing_row = dict(existing) if existing is not None else None

        if existing_row is not None:
            if _clean(existing_row.get("subject_key"), 256) != normalized_candidate[
                "subject_key"
            ]:
                raise ClaimMaterializationConflictError(
                    "Existing canonical claim is assigned to a different subject."
                )

            stored_candidate = _stored_structured_candidate(existing_row)
            if stored_candidate is None:
                raise ClaimMaterializationConflictError(
                    "Existing structured claim cannot be safely merged because its "
                    "structured identity metadata is missing."
                )

            merged_candidate = _merge_candidate(
                existing=stored_candidate,
                incoming=normalized_candidate,
            )
            existing_metadata = _json_object(existing_row.get("metadata_json"))
            first_seen_at = _clean(existing_row.get("first_seen_at"), 128)
            last_seen_at = _latest_seen_at(
                existing_row.get("last_seen_at"),
                normalized_observed_at,
            )
            stored_text = _clean(existing_row.get("canonical_text"), 4000)
            canonical_text_to_store = stored_text or canonical_text
            created = False
        else:
            merged_candidate = normalized_candidate
            existing_metadata = {}
            first_seen_at = normalized_observed_at
            last_seen_at = normalized_observed_at
            canonical_text_to_store = canonical_text
            created = True

        merged_specific_fingerprint = (
            claim_identity.canonical_claim_specific_fingerprint(merged_candidate)
        )
        metadata = _metadata_for_materialization(
            existing_metadata=existing_metadata,
            candidate=merged_candidate,
            core_fingerprint=core_fingerprint,
            specific_fingerprint=specific_fingerprint,
            router_version=router_version,
        )
        metadata["merged_specific_fingerprint"] = merged_specific_fingerprint

        if existing_row is None:
            conn.execute(
                """
                INSERT INTO intelligence_claims (
                  id,
                  canonical_key,
                  subject_key,
                  canonical_text,
                  claim_type,
                  first_seen_at,
                  last_seen_at,
                  metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    claim_id,
                    core_key,
                    normalized_candidate["subject_key"],
                    canonical_text_to_store,
                    claim_type,
                    first_seen_at,
                    last_seen_at,
                    _canonical_json(metadata),
                ),
            )
        else:
            conn.execute(
                """
                UPDATE intelligence_claims
                SET
                  canonical_text = ?,
                  claim_type = ?,
                  last_seen_at = ?,
                  metadata_json = ?
                WHERE id = ?
                """,
                (
                    canonical_text_to_store,
                    claim_type,
                    last_seen_at,
                    _canonical_json(metadata),
                    existing_row["id"],
                ),
            )
            claim_id = _clean(existing_row["id"], 128)

        link = _claim_link_insert(
            conn=conn,
            claim_id=claim_id,
            target=target,
            relationship_type=relationship_type,
            confidence=confidence,
            observed_at=normalized_observed_at,
            recorded_at=normalized_observed_at,
            core_fingerprint=core_fingerprint,
        )

        stored = conn.execute(
            "SELECT * FROM intelligence_claims WHERE id = ?",
            (claim_id,),
        ).fetchone()

        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    if stored is None:
        raise RuntimeError("Canonical claim materialization failed.")

    claim_projection = build_claim_projection(
        claim_id=claim_id,
        connection_factory=connection_factory,
        stale_after_days=stale_after_days,
    )
    story_ids = [
        _clean(item.get("story_id"), 128)
        for item in claim_projection.get("stories") or []
        if _clean(item.get("story_id"), 128)
    ][:_MAX_STORY_PROJECTIONS]
    story_projections = [
        build_story_projection(
            story_id=story_id,
            connection_factory=connection_factory,
            stale_after_days=stale_after_days,
        )
        for story_id in story_ids
    ]
    subject_timeline = build_subject_timeline(
        subject_key=normalized_candidate["subject_key"],
        connection_factory=connection_factory,
        limit=timeline_limit,
    )

    return {
        "version": CLAIM_MATERIALIZATION_VERSION,
        "status": "materialized",
        "created": created,
        "claim": {
            "id": claim_id,
            "canonical_key": core_key,
            "subject_key": normalized_candidate["subject_key"],
            "claim_type": claim_type,
            "canonical_text": canonical_text_to_store,
            "first_seen_at": first_seen_at,
            "last_seen_at": last_seen_at,
        },
        "identity": {
            "candidate": merged_candidate,
            "core_key": core_key,
            "core_fingerprint": core_fingerprint,
            "incoming_specific_fingerprint": specific_fingerprint,
            "merged_specific_fingerprint": merged_specific_fingerprint,
            "specific_fingerprints": list(metadata["specific_fingerprints"]),
            "specific_fingerprints_truncated": bool(
                metadata["specific_fingerprints_truncated"]
            ),
        },
        "link": link,
        "projection": claim_projection,
        "story_projections": story_projections,
        "subject_timeline": subject_timeline,
        "policy": {
            "materialization_requires_complete_structured_identity": True,
            "same_core_material_conflicts_fail_closed": True,
            "claim_link_write_is_atomic_with_claim_materialization": True,
            "partial_semantics_are_not_persisted_as_claim_identity": True,
            "semantic_router_output_is_candidate_semantics_not_truth": True,
            "projection_is_operational_context_not_truth": True,
            "no_model_call_performed": True,
            "affects_live_merit": False,
        },
    }


def route_and_materialize_claim_semantics(
    *,
    router_output: Any,
    expected_subject_key: str,
    allowed_entity_keys: Sequence[str],
    claim_text: str,
    observed_at: str,
    connection_factory,
    source_observation_id: str | None = None,
    reporter_observation_id: str | None = None,
    evidence_id: str | None = None,
    relationship_type: str = "reports",
    confidence: float | None = None,
    stale_after_days: int = 30,
    timeline_limit: int = 100,
) -> dict[str, Any]:
    parsed = claim_router.parse_claim_semantic_extraction_router_output(
        router_output,
        expected_subject_key=expected_subject_key,
        allowed_entity_keys=allowed_entity_keys,
    )

    if parsed.get("route") != claim_router.ROUTE_FULL_IDENTITY:
        return {
            "version": CLAIM_MATERIALIZATION_VERSION,
            "status": "not_materialized",
            "router_status": parsed.get("status"),
            "route": parsed.get("route"),
            "reason": _clean(parsed.get("reason"), 500),
            "missing_identity_fields": list(
                parsed.get("missing_identity_fields") or []
            ),
            "claim": None,
            "projection": None,
            "story_projections": [],
            "subject_timeline": None,
            "policy": {
                "partial_semantics_are_not_persisted_as_claim_identity": True,
                "insufficient_semantics_are_not_persisted": True,
                "safe_exclusion_does_not_create_claim_identity": True,
                "no_model_call_performed": True,
                "affects_live_merit": False,
            },
        }

    result = materialize_canonical_claim(
        candidate=parsed["candidate"],
        claim_text=claim_text,
        observed_at=observed_at,
        connection_factory=connection_factory,
        source_observation_id=source_observation_id,
        reporter_observation_id=reporter_observation_id,
        evidence_id=evidence_id,
        relationship_type=relationship_type,
        confidence=confidence,
        router_version=parsed.get("version") or "",
        stale_after_days=stale_after_days,
        timeline_limit=timeline_limit,
    )
    result["router_status"] = parsed.get("status")
    result["route"] = parsed.get("route")
    result["router_reason"] = _clean(parsed.get("reason"), 500)
    return result


__all__ = [
    "CLAIM_MATERIALIZATION_VERSION",
    "CLAIM_MATERIALIZATION_METADATA_VERSION",
    "ClaimMaterializationError",
    "ClaimMaterializationConflictError",
    "materialize_canonical_claim",
    "route_and_materialize_claim_semantics",
]
