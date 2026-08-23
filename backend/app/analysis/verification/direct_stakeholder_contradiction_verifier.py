import hashlib
import json

from datetime import datetime
from typing import Any, Dict, Optional

from app.intelligence.evidence import record_evidence
from app.services.direct_authority_verifier import (
    DIRECT_AUTHORITY_ENTITY_VERIFIER_VERSION,
    build_direct_authority_entity_candidate,
)


DIRECT_STAKEHOLDER_CONTRADICTION_VERIFIER_VERSION = (
    "direct-stakeholder-contradiction-verifier-v1"
)

DIRECT_STAKEHOLDER_CONTRADICTION_BASIS = (
    "verified_direct_stakeholder_with_recorded_claim_contradiction"
)

DIRECT_STAKEHOLDER_CONTRADICTION_EVIDENCE_TYPE = (
    "direct_stakeholder_contradiction_reference"
)

DIRECT_STAKEHOLDER_CONTRADICTION_REFERENCE_PREFIX = (
    "direct-stakeholder-contradiction:"
)


def _clean(value: Any) -> str:
    return " ".join(str(value or "").split())


def _key(value: Any) -> str:
    return _clean(value).lower()


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def _timestamp(
    value: Any,
    *,
    label: str,
) -> datetime:
    text = _clean(value)

    if not text:
        raise ValueError(
            f"{label} is required."
        )

    if text.endswith("Z"):
        text = text[:-1] + "+00:00"

    try:
        parsed = datetime.fromisoformat(
            text
        )
    except ValueError as exc:
        raise ValueError(
            f"{label} must be ISO-8601."
        ) from exc

    if (
        parsed.tzinfo is None
        or parsed.utcoffset() is None
    ):
        raise ValueError(
            f"{label} must include timezone."
        )

    return parsed


def _load_context(
    *,
    claim_id: str,
    observation_id: str,
    connection_factory,
) -> Dict[str, Any]:
    conn = connection_factory()

    try:
        claim = conn.execute(
            """
            SELECT *
            FROM intelligence_claims
            WHERE id = ?
            """,
            (claim_id,),
        ).fetchone()

        observation = conn.execute(
            """
            SELECT *
            FROM source_observations
            WHERE id = ?
            """,
            (observation_id,),
        ).fetchone()

        links = conn.execute(
            """
            SELECT *
            FROM claim_links
            WHERE claim_id = ?
              AND source_observation_id = ?
            ORDER BY id
            """,
            (
                claim_id,
                observation_id,
            ),
        ).fetchall()

    finally:
        conn.close()

    if claim is None:
        raise ValueError(
            "Contradiction claim does not exist."
        )

    if observation is None:
        raise ValueError(
            "Contradiction source observation "
            "does not exist."
        )

    return {
        "claim": dict(claim),
        "observation": dict(observation),
        "links": [
            dict(row)
            for row in links
        ],
    }


def build_direct_stakeholder_contradiction_candidate(
    *,
    claim_id: str,
    observation_id: str,
    connection_factory,
    authority_candidate_builder=(
        build_direct_authority_entity_candidate
    ),
) -> Dict[str, Any]:
    normalized_claim_id = _clean(
        claim_id
    )
    normalized_observation_id = _clean(
        observation_id
    )

    if not normalized_claim_id:
        raise ValueError(
            "Contradiction verifier claim ID "
            "is required."
        )

    if not normalized_observation_id:
        raise ValueError(
            "Contradiction verifier observation "
            "ID is required."
        )

    if connection_factory is None:
        raise ValueError(
            "Contradiction verifier requires "
            "database access."
        )

    context = _load_context(
        claim_id=normalized_claim_id,
        observation_id=(
            normalized_observation_id
        ),
        connection_factory=(
            connection_factory
        ),
    )

    claim = context["claim"]
    observation = context["observation"]
    links = context["links"]

    if (
        _clean(
            observation.get(
                "subject_key"
            )
        )
        != _clean(
            claim.get(
                "subject_key"
            )
        )
    ):
        return {
            "version": (
                DIRECT_STAKEHOLDER_CONTRADICTION_VERIFIER_VERSION
            ),
            "status": "claim_subject_mismatch",
            "candidate": None,
        }

    contradiction_links = [
        row
        for row in links
        if _key(
            row.get(
                "relationship_type"
            )
        )
        == "contradicts"
    ]

    support_links = [
        row
        for row in links
        if _key(
            row.get(
                "relationship_type"
            )
        )
        == "supports"
    ]

    if not contradiction_links:
        return {
            "version": (
                DIRECT_STAKEHOLDER_CONTRADICTION_VERIFIER_VERSION
            ),
            "status": (
                "explicit_contradiction_not_recorded"
            ),
            "candidate": None,
        }

    if support_links:
        return {
            "version": (
                DIRECT_STAKEHOLDER_CONTRADICTION_VERIFIER_VERSION
            ),
            "status": (
                "same_observation_has_support_and_contradiction"
            ),
            "candidate": None,
        }

    source_id = _clean(
        observation.get(
            "source_id"
        )
    )

    if not source_id:
        raise ValueError(
            "Contradiction observation source "
            "identity is missing."
        )

    authority_result = (
        authority_candidate_builder(
            source_id=source_id,
            claim_id=(
                normalized_claim_id
            ),
            connection_factory=(
                connection_factory
            ),
        )
    )

    if not isinstance(
        authority_result,
        dict,
    ):
        raise ValueError(
            "Direct authority verifier returned "
            "invalid data."
        )

    if (
        _clean(
            authority_result.get(
                "version"
            )
        )
        != DIRECT_AUTHORITY_ENTITY_VERIFIER_VERSION
    ):
        raise ValueError(
            "Direct authority verifier version "
            "is unsupported."
        )

    if (
        authority_result.get(
            "status"
        )
        != "verified_direct_stakeholder"
    ):
        return {
            "version": (
                DIRECT_STAKEHOLDER_CONTRADICTION_VERIFIER_VERSION
            ),
            "status": (
                "direct_stakeholder_not_verified"
            ),
            "candidate": None,
            "authority_status": (
                authority_result.get(
                    "status"
                )
            ),
        }

    authority = authority_result.get(
        "candidate"
    )

    if not isinstance(
        authority,
        dict,
    ):
        raise ValueError(
            "Verified direct authority candidate "
            "is missing."
        )

    if (
        _key(
            authority.get(
                "source_role"
            )
        )
        != "primary_stakeholder"
        or _key(
            authority.get(
                "authority_class"
            )
        )
        != "direct"
    ):
        return {
            "version": (
                DIRECT_STAKEHOLDER_CONTRADICTION_VERIFIER_VERSION
            ),
            "status": (
                "direct_authority_contract_mismatch"
            ),
            "candidate": None,
        }

    entity = authority.get(
        "entity"
    )

    if not isinstance(
        entity,
        dict,
    ):
        raise ValueError(
            "Verified direct authority entity "
            "is missing."
        )

    entity_id = _clean(
        entity.get(
            "id"
        )
    )

    if not entity_id:
        raise ValueError(
            "Verified direct authority entity ID "
            "is missing."
        )

    observed_at = max(
        _timestamp(
            observation.get(
                "observed_at"
            ),
            label=(
                "Contradiction observation time"
            ),
        ),
        _timestamp(
            authority.get(
                "availability_at"
            ),
            label=(
                "Direct authority availability"
            ),
        ),
    ).isoformat()

    contradiction_link_ids = sorted(
        {
            _clean(
                row.get(
                    "id"
                )
            )
            for row
            in contradiction_links
            if _clean(
                row.get(
                    "id"
                )
            )
        }
    )

    authority_lineage = {
        "entity": entity,
        "source_binding_ids": sorted(
            authority.get(
                "source_binding_ids",
                [],
            )
        ),
        "claim_participant_ids": sorted(
            authority.get(
                "claim_participant_ids",
                [],
            )
        ),
        "source_evidence_ids": sorted(
            authority.get(
                "source_evidence_ids",
                [],
            )
        ),
        "participant_evidence_ids": sorted(
            authority.get(
                "participant_evidence_ids",
                [],
            )
        ),
    }

    return {
        "version": (
            DIRECT_STAKEHOLDER_CONTRADICTION_VERIFIER_VERSION
        ),
        "status": (
            "verified_direct_stakeholder_contradiction_lineage"
        ),
        "candidate": {
            "claim_id": (
                normalized_claim_id
            ),
            "observation_id": (
                normalized_observation_id
            ),
            "source_id": source_id,
            "entity_id": entity_id,
            "contradiction_link_ids": (
                contradiction_link_ids
            ),
            "observed_at": (
                observed_at
            ),
            "authority_confidence": float(
                authority.get(
                    "confidence",
                    0.0,
                )
            ),
            "basis": (
                DIRECT_STAKEHOLDER_CONTRADICTION_BASIS
            ),
            "authority_lineage": (
                authority_lineage
            ),
        },
        "policy": {
            "requires_persisted_claim": True,
            "requires_persisted_source_observation": True,
            "requires_explicit_contradiction_link": True,
            "requires_verified_direct_stakeholder_authority": True,
            "authority_is_machine_verified": True,
            "contradiction_semantics_are_not_truth_verification": True,
            "model_output_alone_never_changes_merit": True,
            "does_not_establish_claim_truth": True,
            "does_not_change_live_merit": True,
        },
    }


def persist_direct_stakeholder_contradiction_verification(
    *,
    claim_id: str,
    observation_id: str,
    connection_factory,
    recorded_at: Optional[str] = None,
    candidate_builder=(
        build_direct_stakeholder_contradiction_candidate
    ),
    evidence_recorder=record_evidence,
) -> Dict[str, Any]:
    result = candidate_builder(
        claim_id=claim_id,
        observation_id=observation_id,
        connection_factory=(
            connection_factory
        ),
    )

    if (
        result.get(
            "status"
        )
        != (
            "verified_direct_stakeholder_"
            "contradiction_lineage"
        )
    ):
        return {
            "version": (
                DIRECT_STAKEHOLDER_CONTRADICTION_VERIFIER_VERSION
            ),
            "status": result.get(
                "status"
            ),
            "persisted": False,
            "candidate": result,
            "evidence": None,
        }

    candidate = result[
        "candidate"
    ]

    identity = {
        "claim_id": candidate[
            "claim_id"
        ],
        "observation_id": candidate[
            "observation_id"
        ],
        "source_id": candidate[
            "source_id"
        ],
        "entity_id": candidate[
            "entity_id"
        ],
        "contradiction_link_ids": (
            candidate[
                "contradiction_link_ids"
            ]
        ),
        "basis": candidate[
            "basis"
        ],
    }

    reference_hash = hashlib.sha256(
        _canonical_json(
            identity
        ).encode(
            "utf-8"
        )
    ).hexdigest()

    evidence = evidence_recorder(
        evidence_type=(
            DIRECT_STAKEHOLDER_CONTRADICTION_EVIDENCE_TYPE
        ),
        subject_key=(
            "merit-negative-evidence|"
            + candidate[
                "claim_id"
            ]
        ),
        observed_at=(
            candidate[
                "observed_at"
            ]
        ),
        reference_key=(
            DIRECT_STAKEHOLDER_CONTRADICTION_REFERENCE_PREFIX
            + reference_hash
        ),
        verification_status="verified",
        recorded_at=recorded_at,
        metadata={
            "verifier_version": (
                DIRECT_STAKEHOLDER_CONTRADICTION_VERIFIER_VERSION
            ),
            "verification_scope": (
                "authority_and_persisted_"
                "relationship_lineage_only"
            ),
            "basis": candidate[
                "basis"
            ],
            "claim_id": candidate[
                "claim_id"
            ],
            "observation_id": (
                candidate[
                    "observation_id"
                ]
            ),
            "source_id": candidate[
                "source_id"
            ],
            "entity_id": candidate[
                "entity_id"
            ],
            "contradiction_link_ids": (
                candidate[
                    "contradiction_link_ids"
                ]
            ),
            "authority_lineage": (
                candidate[
                    "authority_lineage"
                ]
            ),
            "machine_verified_authority": True,
            "recorded_contradiction_relationship": True,
            "contradiction_semantics_verified": False,
            "claim_truth_established": False,
            "live_merit_changed": False,
        },
        connection_factory=(
            connection_factory
        ),
    )["evidence"]

    return {
        "version": (
            DIRECT_STAKEHOLDER_CONTRADICTION_VERIFIER_VERSION
        ),
        "status": (
            "persisted_verified_direct_stakeholder_"
            "contradiction_lineage"
        ),
        "persisted": True,
        "candidate": result,
        "evidence": evidence,
        "policy": {
            "append_only_verified_lineage_evidence": True,
            "verification_scope_is_limited": True,
            "contradiction_semantics_are_not_truth_verification": True,
            "claim_truth_established": False,
            "live_merit_changed": False,
        },
    }
