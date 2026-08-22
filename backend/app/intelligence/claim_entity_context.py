from __future__ import annotations

from typing import Any

from app.intelligence.entity_resolution_runtime import (
    resolve_entity_mentions,
)


CLAIM_ENTITY_CONTEXT_VERSION = "claim-entity-context-v1"


def _clean(value: Any, maximum: int = 512) -> str:
    return " ".join(str(value or "").split())[:maximum]


def _entity_row(row: Any) -> dict[str, str]:
    value = dict(row)
    return {
        "entity_id": _clean(value.get("id"), 128),
        "entity_key": _clean(value.get("entity_key"), 256).casefold(),
        "entity_type": _clean(value.get("entity_type"), 64),
        "sport_key": _clean(value.get("sport_key"), 64),
        "canonical_name": _clean(value.get("canonical_name"), 256),
    }


def build_claim_entity_context(
    *,
    claim_text: str,
    subject_key: str,
    connection_factory,
    sport_key: str = "",
    max_entities: int = 24,
) -> dict[str, Any]:
    """Build a bounded allowlist for structured claim extraction.

    The explicit subject key must already exist in the canonical entity store.
    Other entities come only from deterministic exact-alias mention resolution.
    Ambiguous aliases are reported but never admitted to the allowlist.
    """

    if connection_factory is None:
        raise ValueError("Claim entity context requires database access.")

    normalized_subject = _clean(subject_key, 256).casefold()
    source_text = _clean(claim_text)
    normalized_sport = _clean(sport_key, 64).casefold()

    if not normalized_subject:
        raise ValueError("Claim entity context subject_key is required.")
    if not source_text:
        raise ValueError("Claim entity context claim_text is required.")

    conn = connection_factory()
    try:
        subject_row = conn.execute(
            """
            SELECT
              id,
              entity_key,
              entity_type,
              sport_key,
              canonical_name
            FROM canonical_entities
            WHERE entity_key = ?
            """,
            (normalized_subject,),
        ).fetchone()
    finally:
        conn.close()

    if subject_row is None:
        return {
            "version": CLAIM_ENTITY_CONTEXT_VERSION,
            "status": "subject_unresolved",
            "subject_key": normalized_subject,
            "allowed_entities": {},
            "resolved_mentions": [],
            "ambiguous_mentions": [],
            "counts": {
                "allowed_entities": 0,
                "resolved_mentions": 0,
                "ambiguous_mentions": 0,
            },
            "policy": {
                "canonical_subject_required": True,
                "exact_alias_mentions_only": True,
                "ambiguous_mentions_excluded": True,
                "fuzzy_guessing_used": False,
                "candidate_semantics_only": True,
                "establishes_truth": False,
                "establishes_authority": False,
                "establishes_independence": False,
                "affects_live_merit": False,
            },
        }

    subject = _entity_row(subject_row)
    effective_sport = normalized_sport or subject["sport_key"]

    resolution = resolve_entity_mentions(
        text=source_text,
        connection_factory=connection_factory,
        sport_key=effective_sport,
        max_entities=max_entities,
    )

    allowed: dict[str, dict[str, str]] = {
        subject["entity_key"]: subject,
    }

    resolved_mentions = []
    for item in resolution.get("resolved") or []:
        entity_key = _clean(item.get("entity_key"), 256).casefold()
        if not entity_key:
            continue

        context_row = {
            "entity_id": _clean(item.get("entity_id"), 128),
            "entity_key": entity_key,
            "entity_type": _clean(item.get("entity_type"), 64),
            "sport_key": _clean(item.get("sport_key"), 64),
            "canonical_name": _clean(item.get("canonical_name"), 256),
        }
        allowed[entity_key] = context_row
        resolved_mentions.append({
            **context_row,
            "matched_alias": _clean(item.get("matched_alias"), 256),
            "alias_type": _clean(item.get("alias_type"), 64),
        })

    ambiguous_mentions = []
    for item in resolution.get("ambiguous") or []:
        ambiguous_mentions.append({
            "matched_alias": _clean(item.get("matched_alias"), 256),
            "candidate_count": int(item.get("candidate_count") or 0),
            "candidates": [
                {
                    "entity_id": _clean(candidate.get("entity_id"), 128),
                    "entity_type": _clean(candidate.get("entity_type"), 64),
                    "sport_key": _clean(candidate.get("sport_key"), 64),
                    "canonical_name": _clean(candidate.get("canonical_name"), 256),
                }
                for candidate in (item.get("candidates") or [])
                if isinstance(candidate, dict)
            ],
        })

    status = (
        "partial_ambiguity"
        if ambiguous_mentions
        else "ready"
    )

    return {
        "version": CLAIM_ENTITY_CONTEXT_VERSION,
        "status": status,
        "subject_key": normalized_subject,
        "subject_entity": subject,
        "allowed_entities": {
            key: allowed[key]
            for key in sorted(allowed)
        },
        "resolved_mentions": sorted(
            resolved_mentions,
            key=lambda item: (
                item["entity_type"],
                item["canonical_name"].casefold(),
                item["entity_id"],
            ),
        ),
        "ambiguous_mentions": ambiguous_mentions,
        "counts": {
            "allowed_entities": len(allowed),
            "resolved_mentions": len(resolved_mentions),
            "ambiguous_mentions": len(ambiguous_mentions),
        },
        "resolution_version": resolution.get("version", ""),
        "policy": {
            "canonical_subject_required": True,
            "subject_key_resolved_by_canonical_key": True,
            "exact_alias_mentions_only": True,
            "ambiguous_mentions_excluded": True,
            "fuzzy_guessing_used": False,
            "candidate_semantics_only": True,
            "verified_participant_binding_required_for_claim_identity_provenance": True,
            "establishes_truth": False,
            "establishes_authority": False,
            "establishes_independence": False,
            "affects_live_merit": False,
        },
    }


__all__ = [
    "CLAIM_ENTITY_CONTEXT_VERSION",
    "build_claim_entity_context",
]
