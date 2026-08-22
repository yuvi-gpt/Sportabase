from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

from app.intelligence.claim_materialization import (
    ClaimMaterializationConflictError,
    materialize_canonical_claim,
)
from app.intelligence.claims import identity as claim_identity
from app.intelligence.entity_resolution_runtime import (
    resolve_entity_mentions,
)


STRUCTURED_CLAIM_INGESTION_VERSION = (
    "structured-claim-ingestion-runtime-v1"
)
CLAIM_IDENTITY_MAPPING_VERSION = (
    "claim-identity-mapping-v1"
)

_MAX_CAPTURE_TEXT = 16000
_MAX_ENTITIES = 32

_MAPPING_SCHEMA = """
CREATE TABLE IF NOT EXISTS claim_identity_mappings (
  production_claim_id TEXT PRIMARY KEY,
  canonical_claim_id TEXT NOT NULL,
  subject_key TEXT NOT NULL,
  mapping_status TEXT NOT NULL,
  mapping_basis TEXT NOT NULL,
  first_seen_at TEXT NOT NULL,
  last_seen_at TEXT NOT NULL,
  metadata_json TEXT NOT NULL DEFAULT '{}',
  CHECK (mapping_status = 'verified_equivalent'),
  FOREIGN KEY(production_claim_id)
    REFERENCES intelligence_claims(id)
    ON DELETE CASCADE,
  FOREIGN KEY(canonical_claim_id)
    REFERENCES intelligence_claims(id)
    ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_claim_identity_mappings_canonical
ON claim_identity_mappings(canonical_claim_id);

CREATE INDEX IF NOT EXISTS idx_claim_identity_mappings_subject
ON claim_identity_mappings(subject_key);
"""


def _clean(value: Any, maximum: int = 1000) -> str:
    return " ".join(str(value or "").split())[:maximum]


def _json(value: Mapping[str, Any]) -> str:
    return json.dumps(
        dict(value),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def _capture_text(value: Any, *, maximum: int = _MAX_CAPTURE_TEXT) -> str:
    pieces: list[str] = []
    used = 0

    preferred_keys = {
        "title",
        "headline",
        "body",
        "text",
        "caption",
        "description",
        "transcript",
        "ocr",
        "alt",
        "alt_text",
        "display_name",
        "name",
    }

    def add(raw: Any) -> None:
        nonlocal used
        text = _clean(raw, maximum)
        if not text or used >= maximum:
            return
        remaining = maximum - used
        clipped = text[:remaining]
        if clipped:
            pieces.append(clipped)
            used += len(clipped) + 1

    def visit(raw: Any, depth: int = 0) -> None:
        if depth > 6 or used >= maximum:
            return

        if isinstance(raw, Mapping):
            preferred = []
            remaining = []
            for key, item in raw.items():
                normalized = _clean(key, 64).casefold()
                if normalized in preferred_keys:
                    preferred.append(item)
                else:
                    remaining.append(item)

            for item in preferred:
                if isinstance(item, str):
                    add(item)
                else:
                    visit(item, depth + 1)

            for item in remaining[:80]:
                if isinstance(item, (Mapping, list, tuple)):
                    visit(item, depth + 1)

        elif isinstance(raw, (list, tuple)):
            for item in list(raw)[:80]:
                visit(item, depth + 1)

        elif isinstance(raw, str):
            add(raw)

    visit(value)
    return "\n".join(pieces)[:maximum]


def _subject_record(
    *,
    subject_key: str,
    connection_factory,
) -> dict[str, Any] | None:
    conn = connection_factory()
    try:
        row = conn.execute(
            """
            SELECT id, entity_key, entity_type, canonical_name
            FROM canonical_entities
            WHERE entity_key = ?
            LIMIT 1
            """,
            (_clean(subject_key, 256),),
        ).fetchone()
    finally:
        conn.close()

    return dict(row) if row is not None else None


def build_structured_claim_allowlist(
    *,
    subject_key: str,
    left_capture: Mapping[str, Any],
    right_capture: Mapping[str, Any],
    connection_factory,
    max_entities: int = _MAX_ENTITIES,
    resolver=resolve_entity_mentions,
) -> dict[str, Any]:
    """Build a bounded canonical-entity allowlist from exact alias matches.

    The verified subject is always retained. Other entities are candidate-only
    exact alias matches from the two captures. Ambiguous aliases are excluded.
    Failure to inspect aliases degrades to a subject-only allowlist instead of
    breaking the existing multimodal path.
    """

    subject = _clean(subject_key, 256).casefold()
    if not subject:
        raise ValueError("Structured claim ingestion requires a subject key.")
    if connection_factory is None:
        raise ValueError("Structured claim ingestion requires database access.")

    try:
        limit = int(max_entities)
    except (TypeError, ValueError) as exc:
        raise ValueError("Structured claim entity limit must be an integer.") from exc

    if limit < 1 or limit > 100:
        raise ValueError("Structured claim entity limit must be between 1 and 100.")

    record = _subject_record(
        subject_key=subject,
        connection_factory=connection_factory,
    )
    if record is None:
        raise ValueError(
            "Structured claim subject is not backed by a canonical entity."
        )

    entities: dict[str, dict[str, str]] = {
        subject: {
            "entity_key": subject,
            "canonical_name": _clean(record.get("canonical_name"), 256),
            "entity_type": _clean(record.get("entity_type"), 64).casefold(),
        }
    }

    combined_text = "\n".join(
        value
        for value in (
            _capture_text(left_capture),
            _capture_text(right_capture),
        )
        if value
    )[:_MAX_CAPTURE_TEXT]

    resolution_status = "subject_only"
    resolution_error_type = ""
    ambiguous_count = 0

    if combined_text:
        try:
            resolved = resolver(
                text=combined_text,
                connection_factory=connection_factory,
                max_entities=limit,
            )
            resolution_status = _clean(resolved.get("status"), 64)
            ambiguous_count = int(
                (resolved.get("counts") or {}).get("ambiguous") or 0
            )
            for row in resolved.get("resolved") or []:
                if not isinstance(row, Mapping):
                    continue
                entity_key = _clean(row.get("entity_key"), 256).casefold()
                if not entity_key or entity_key in entities:
                    continue
                entities[entity_key] = {
                    "entity_key": entity_key,
                    "canonical_name": _clean(row.get("canonical_name"), 256),
                    "entity_type": _clean(row.get("entity_type"), 64).casefold(),
                }
                if len(entities) >= limit:
                    break
        except Exception as error:
            # Existing installations and focused unit schemas may not yet have
            # the alias table. Subject-only structured extraction remains safe.
            resolution_status = "subject_only"
            resolution_error_type = type(error).__name__

    ordered = {
        key: entities[key]
        for key in sorted(entities)
    }

    return {
        "version": STRUCTURED_CLAIM_INGESTION_VERSION,
        "status": "ready",
        "resolution_status": resolution_status,
        "resolution_error_type": resolution_error_type,
        "subject_key": subject,
        "allowed_entity_keys": list(ordered),
        "allowed_entities": ordered,
        "counts": {
            "entities": len(ordered),
            "ambiguous_aliases_excluded": max(0, ambiguous_count),
        },
        "policy": {
            "verified_subject_always_included": True,
            "additional_entities_require_exact_alias_resolution": True,
            "ambiguous_aliases_fail_closed": True,
            "no_fuzzy_entity_guessing": True,
            "allowlist_is_candidate_context_only": True,
            "allowlist_does_not_establish_authority": True,
            "provider_call_performed": False,
            "affects_live_merit": False,
        },
    }


def _shadow_row(
    report: Mapping[str, Any] | None,
    candidate_id: str,
) -> dict[str, Any] | None:
    if not isinstance(report, Mapping):
        return None

    target = _clean(candidate_id, 256)
    if not target:
        return None

    matches = []
    for raw in report.get("candidate_rows") or []:
        if not isinstance(raw, Mapping):
            continue
        row = dict(raw)
        if _clean(row.get("candidate_id"), 256) == target:
            matches.append(row)

    return matches[0] if len(matches) == 1 else None


def _full_candidate(row: Mapping[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(row, Mapping):
        return None
    if _clean(row.get("shadow_status"), 64).casefold() != "evaluated":
        return None
    if _clean(row.get("route"), 64).casefold() != "full_identity":
        return None
    if row.get("identity_complete") is not True:
        return None
    candidate = row.get("candidate")
    if not isinstance(candidate, Mapping):
        return None
    return claim_identity.normalize_canonical_claim(candidate)


def _observation_rows(
    *,
    observation_ids: tuple[str, str],
    production_claim_id: str,
    connection_factory,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]] | None:
    left_id = _clean(observation_ids[0], 128)
    right_id = _clean(observation_ids[1], 128)
    production_id = _clean(production_claim_id, 128)

    if not left_id or not right_id or left_id == right_id or not production_id:
        return None

    conn = connection_factory()
    try:
        claim = conn.execute(
            """
            SELECT id, subject_key, canonical_text, first_seen_at, last_seen_at
            FROM intelligence_claims
            WHERE id = ?
            LIMIT 1
            """,
            (production_id,),
        ).fetchone()
        rows = conn.execute(
            """
            SELECT id, subject_key, observed_at
            FROM source_observations
            WHERE id IN (?, ?)
            ORDER BY id
            """,
            (left_id, right_id),
        ).fetchall()
    finally:
        conn.close()

    if claim is None or len(rows) != 2:
        return None

    by_id = {str(row["id"]): dict(row) for row in rows}
    if left_id not in by_id or right_id not in by_id:
        return None

    return dict(claim), by_id[left_id], by_id[right_id]


def _ensure_mapping_schema(conn) -> None:
    conn.executescript(_MAPPING_SCHEMA)


def _persist_mapping(
    *,
    production_claim_id: str,
    canonical_claim_id: str,
    subject_key: str,
    observed_at: str,
    compatibility: Mapping[str, Any],
    connection_factory,
) -> dict[str, Any]:
    production_id = _clean(production_claim_id, 128)
    canonical_id = _clean(canonical_claim_id, 128)
    subject = _clean(subject_key, 256).casefold()
    seen_at = _clean(observed_at, 128)

    metadata = {
        "version": CLAIM_IDENTITY_MAPPING_VERSION,
        "compatibility_status": _clean(compatibility.get("status"), 64),
        "core_fingerprint": _clean(
            compatibility.get("left_core_fingerprint"), 128
        ),
        "left_specific_fingerprint": _clean(
            compatibility.get("left_specific_fingerprint"), 128
        ),
        "right_specific_fingerprint": _clean(
            compatibility.get("right_specific_fingerprint"), 128
        ),
        "truth_established": False,
        "authority_established": False,
        "independence_established": False,
        "affects_live_merit": False,
    }

    conn = connection_factory()
    try:
        conn.execute("BEGIN IMMEDIATE")
        _ensure_mapping_schema(conn)

        existing = conn.execute(
            """
            SELECT *
            FROM claim_identity_mappings
            WHERE production_claim_id = ?
            """,
            (production_id,),
        ).fetchone()

        if existing is not None:
            existing_row = dict(existing)
            if (
                _clean(existing_row.get("canonical_claim_id"), 128)
                != canonical_id
                or _clean(existing_row.get("subject_key"), 256).casefold()
                != subject
            ):
                raise ClaimMaterializationConflictError(
                    "Legacy claim identity is already mapped to a different canonical claim."
                )

        conn.execute(
            """
            INSERT INTO claim_identity_mappings (
              production_claim_id,
              canonical_claim_id,
              subject_key,
              mapping_status,
              mapping_basis,
              first_seen_at,
              last_seen_at,
              metadata_json
            ) VALUES (?, ?, ?, 'verified_equivalent', ?, ?, ?, ?)
            ON CONFLICT(production_claim_id)
            DO UPDATE SET
              last_seen_at = excluded.last_seen_at,
              metadata_json = excluded.metadata_json
            """,
            (
                production_id,
                canonical_id,
                subject,
                "dual_structured_full_identity_same_core",
                seen_at,
                seen_at,
                _json(metadata),
            ),
        )

        row = conn.execute(
            """
            SELECT *
            FROM claim_identity_mappings
            WHERE production_claim_id = ?
            """,
            (production_id,),
        ).fetchone()
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    if row is None:
        raise RuntimeError("Claim identity mapping persistence failed.")

    return dict(row)


def materialize_selected_structured_claim(
    *,
    production_claim_id: str,
    subject_key: str,
    left_candidate_id: str,
    right_candidate_id: str,
    left_shadow_report: Mapping[str, Any] | None,
    right_shadow_report: Mapping[str, Any] | None,
    left_source_observation_id: str,
    right_source_observation_id: str,
    connection_factory,
    materializer=materialize_canonical_claim,
) -> dict[str, Any]:
    """Promote dual full structured shadow outputs into canonical identity.

    Automatic materialization requires both already-selected exact-claim sides
    to independently yield complete structured identities with the same core
    and no material conflict. Partial or insufficient outputs remain read-only.
    """

    production_id = _clean(production_claim_id, 128)
    subject = _clean(subject_key, 256).casefold()

    left_row = _shadow_row(left_shadow_report, left_candidate_id)
    right_row = _shadow_row(right_shadow_report, right_candidate_id)
    left_candidate = _full_candidate(left_row)
    right_candidate = _full_candidate(right_row)

    base = {
        "version": STRUCTURED_CLAIM_INGESTION_VERSION,
        "production_claim_id": production_id,
        "subject_key": subject,
        "canonical_claim_id": "",
        "mapping_status": "",
        "policy": {
            "dual_full_identity_required": True,
            "same_core_required": True,
            "material_conflict_fails_closed": True,
            "partial_semantics_never_mint_identity": True,
            "insufficient_semantics_never_mint_identity": True,
            "source_observation_links_are_preserved": True,
            "additional_provider_call_performed": False,
            "model_output_does_not_establish_truth": True,
            "model_output_does_not_establish_authority": True,
            "model_output_does_not_establish_independence": True,
            "affects_live_merit": False,
        },
    }

    if not production_id or not subject:
        return {**base, "status": "not_materialized", "reason": "scope_missing"}

    if left_candidate is None or right_candidate is None:
        return {
            **base,
            "status": "not_materialized",
            "reason": "dual_full_identity_unavailable",
            "left_route": _clean((left_row or {}).get("route"), 64),
            "right_route": _clean((right_row or {}).get("route"), 64),
        }

    if (
        left_candidate["subject_key"] != subject
        or right_candidate["subject_key"] != subject
    ):
        return {
            **base,
            "status": "conflict",
            "reason": "structured_subject_changed",
        }

    compatibility = claim_identity.compare_canonical_claims(
        left_candidate,
        right_candidate,
    )

    if compatibility["status"] in {"different_core", "material_conflict"}:
        return {
            **base,
            "status": "conflict",
            "reason": _clean(compatibility["status"], 64),
            "compatibility": compatibility,
        }

    scoped = _observation_rows(
        observation_ids=(
            left_source_observation_id,
            right_source_observation_id,
        ),
        production_claim_id=production_id,
        connection_factory=connection_factory,
    )
    if scoped is None:
        return {
            **base,
            "status": "not_materialized",
            "reason": "persisted_observation_scope_unavailable",
            "compatibility": compatibility,
        }

    production_claim, left_observation, right_observation = scoped
    if (
        _clean(production_claim.get("subject_key"), 256).casefold() != subject
        or _clean(left_observation.get("subject_key"), 256).casefold() != subject
        or _clean(right_observation.get("subject_key"), 256).casefold() != subject
    ):
        return {
            **base,
            "status": "conflict",
            "reason": "persisted_subject_scope_changed",
            "compatibility": compatibility,
        }

    claim_text = _clean(production_claim.get("canonical_text"), 4000)
    observed_at = max(
        _clean(left_observation.get("observed_at"), 128),
        _clean(right_observation.get("observed_at"), 128),
        _clean(production_claim.get("last_seen_at"), 128),
    )

    left_result = materializer(
        candidate=left_candidate,
        claim_text=claim_text,
        observed_at=observed_at,
        connection_factory=connection_factory,
        source_observation_id=_clean(left_observation.get("id"), 128),
        relationship_type="reports",
        router_version="structured-claim-shadow-bridge-v1",
    )
    right_result = materializer(
        candidate=right_candidate,
        claim_text=claim_text,
        observed_at=observed_at,
        connection_factory=connection_factory,
        source_observation_id=_clean(right_observation.get("id"), 128),
        relationship_type="reports",
        router_version="structured-claim-shadow-bridge-v1",
    )

    left_id = _clean((left_result.get("claim") or {}).get("id"), 128)
    right_id = _clean((right_result.get("claim") or {}).get("id"), 128)
    if not left_id or left_id != right_id:
        raise ClaimMaterializationConflictError(
            "Dual structured claim materialization produced different canonical identities."
        )

    mapping = _persist_mapping(
        production_claim_id=production_id,
        canonical_claim_id=left_id,
        subject_key=subject,
        observed_at=observed_at,
        compatibility=compatibility,
        connection_factory=connection_factory,
    )

    return {
        **base,
        "status": "materialized",
        "reason": "dual_full_identity_same_core",
        "canonical_claim_id": left_id,
        "mapping_status": _clean(mapping.get("mapping_status"), 64),
        "compatibility": compatibility,
        "links": {
            "left": left_result.get("link"),
            "right": right_result.get("link"),
        },
        "canonical_projection": right_result.get("projection"),
        "story_projections": right_result.get("story_projections") or [],
        "subject_timeline": right_result.get("subject_timeline"),
    }


def materialize_selected_structured_claim_safely(**kwargs) -> dict[str, Any]:
    try:
        return materialize_selected_structured_claim(**kwargs)
    except ClaimMaterializationConflictError as error:
        return {
            "version": STRUCTURED_CLAIM_INGESTION_VERSION,
            "status": "conflict",
            "reason": "materialization_conflict",
            "error_type": type(error).__name__,
            "canonical_claim_id": "",
            "policy": {
                "failure_is_advisory": True,
                "additional_provider_call_performed": False,
                "affects_live_merit": False,
            },
        }
    except Exception as error:
        return {
            "version": STRUCTURED_CLAIM_INGESTION_VERSION,
            "status": "unavailable",
            "reason": "materialization_runtime_failure",
            "error_type": type(error).__name__,
            "canonical_claim_id": "",
            "policy": {
                "failure_is_advisory": True,
                "error_message_not_exposed": True,
                "additional_provider_call_performed": False,
                "affects_live_merit": False,
            },
        }


def load_claim_identity_mapping(
    *,
    production_claim_id: str,
    connection_factory,
) -> dict[str, Any]:
    claim_id = _clean(production_claim_id, 128)
    if not claim_id:
        raise ValueError("Production claim ID is required.")

    conn = connection_factory()
    try:
        _ensure_mapping_schema(conn)
        row = conn.execute(
            """
            SELECT *
            FROM claim_identity_mappings
            WHERE production_claim_id = ?
            """,
            (claim_id,),
        ).fetchone()
        conn.commit()
    finally:
        conn.close()

    if row is None:
        return {
            "version": CLAIM_IDENTITY_MAPPING_VERSION,
            "status": "not_found",
            "production_claim_id": claim_id,
        }

    record = dict(row)
    return {
        "version": CLAIM_IDENTITY_MAPPING_VERSION,
        "status": "ok",
        "production_claim_id": _clean(record.get("production_claim_id"), 128),
        "canonical_claim_id": _clean(record.get("canonical_claim_id"), 128),
        "subject_key": _clean(record.get("subject_key"), 256),
        "mapping_status": _clean(record.get("mapping_status"), 64),
        "mapping_basis": _clean(record.get("mapping_basis"), 128),
        "first_seen_at": _clean(record.get("first_seen_at"), 128),
        "last_seen_at": _clean(record.get("last_seen_at"), 128),
        "policy": {
            "mapping_is_identity_equivalence_only": True,
            "mapping_does_not_establish_truth": True,
            "mapping_does_not_establish_authority": True,
            "mapping_does_not_establish_independence": True,
            "affects_live_merit": False,
        },
    }


__all__ = [
    "STRUCTURED_CLAIM_INGESTION_VERSION",
    "CLAIM_IDENTITY_MAPPING_VERSION",
    "build_structured_claim_allowlist",
    "materialize_selected_structured_claim",
    "materialize_selected_structured_claim_safely",
    "load_claim_identity_mapping",
]
