import hashlib
import json

from datetime import (
    datetime,
    timezone,
)

from typing import (
    Any,
    Dict,
    List,
    Optional,
)


VERIFIED_ENTITY_BINDING_VERSION = (
    "verified-entity-binding-v1"
)

VERIFIED_ENTITY_MATCH_VERSION = (
    "verified-source-claim-entity-match-v1"
)

VERIFIED_ENTITY_BINDING_MIN_CONFIDENCE = (
    0.95
)


SOURCE_ENTITY_BINDING_TYPES = (
    "official_site",
    "official_publication",
    "official_channel",
    "official_account",
    "controlled_domain",
)


CLAIM_ENTITY_PARTICIPANT_ROLES = (
    "subject",
    "actor",
    "counterparty",
    "origin",
    "destination",
    "affected_party",
    "governing_body",
    "competition",
    "other_party",
)


def _clean(
    value: Any,
) -> str:
    return " ".join(
        str(
            value or ""
        ).split()
    )


def _key(
    value: Any,
) -> str:
    return _clean(
        value
    ).lower()


def _canonical_json(
    value: Any,
) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def _now() -> str:
    return datetime.now(
        timezone.utc
    ).isoformat()


def _confidence(
    value: Any,
) -> float:
    if isinstance(
        value,
        bool,
    ):
        raise ValueError(
            "Verified entity binding confidence "
            "must be numeric."
        )

    try:
        result = float(
            value
        )

    except (
        TypeError,
        ValueError,
    ) as exc:
        raise ValueError(
            "Verified entity binding confidence "
            "must be numeric."
        ) from exc

    if not (
        VERIFIED_ENTITY_BINDING_MIN_CONFIDENCE
        <= result
        <= 1.0
    ):
        raise ValueError(
            "Verified entity binding confidence "
            "must be between 0.95 and 1.0."
        )

    return result


def _require_verified_evidence(
    *,
    evidence_id: str,
    connection_factory,
) -> Dict[str, Any]:
    normalized_id = _clean(
        evidence_id
    )

    if not normalized_id:
        raise ValueError(
            "Verified entity binding evidence ID "
            "is required."
        )

    conn = connection_factory()

    try:
        row = conn.execute(
            """
            SELECT *
            FROM evidence_records
            WHERE id = ?
            """,
            (
                normalized_id,
            ),
        ).fetchone()

    finally:
        conn.close()

    if row is None:
        raise ValueError(
            "Verified entity binding evidence "
            "does not exist."
        )

    result = dict(
        row
    )

    if (
        _key(
            result.get(
                "verification_status"
            )
        )
        != "verified"
    ):
        raise ValueError(
            "Entity binding requires evidence "
            "whose verification status is verified."
        )

    return result


def _require_entity(
    *,
    entity_id: str,
    connection_factory,
) -> Dict[str, Any]:
    normalized_id = _clean(
        entity_id
    )

    if not normalized_id:
        raise ValueError(
            "Canonical entity ID is required."
        )

    conn = connection_factory()

    try:
        row = conn.execute(
            """
            SELECT *
            FROM canonical_entities
            WHERE id = ?
            """,
            (
                normalized_id,
            ),
        ).fetchone()

    finally:
        conn.close()

    if row is None:
        raise ValueError(
            "Canonical entity does not exist."
        )

    return dict(
        row
    )


def _require_source(
    *,
    source_id: str,
    connection_factory,
) -> Dict[str, Any]:
    normalized_id = _clean(
        source_id
    )

    if not normalized_id:
        raise ValueError(
            "Intelligence source ID is required."
        )

    conn = connection_factory()

    try:
        row = conn.execute(
            """
            SELECT *
            FROM intelligence_sources
            WHERE id = ?
            """,
            (
                normalized_id,
            ),
        ).fetchone()

    finally:
        conn.close()

    if row is None:
        raise ValueError(
            "Intelligence source does not exist."
        )

    return dict(
        row
    )


def _require_claim(
    *,
    claim_id: str,
    connection_factory,
) -> Dict[str, Any]:
    normalized_id = _clean(
        claim_id
    )

    if not normalized_id:
        raise ValueError(
            "Intelligence claim ID is required."
        )

    conn = connection_factory()

    try:
        row = conn.execute(
            """
            SELECT *
            FROM intelligence_claims
            WHERE id = ?
            """,
            (
                normalized_id,
            ),
        ).fetchone()

    finally:
        conn.close()

    if row is None:
        raise ValueError(
            "Intelligence claim does not exist."
        )

    return dict(
        row
    )


def verified_source_entity_binding_id_for_record(
    *,
    source_id: str,
    entity_id: str,
    binding_type: str,
    evidence_id: str,
    confidence: float,
    observed_at: str,
) -> str:
    normalized_source = _clean(
        source_id
    )

    normalized_entity = _clean(
        entity_id
    )

    normalized_binding_type = _key(
        binding_type
    )

    normalized_evidence = _clean(
        evidence_id
    )

    normalized_observed_at = _clean(
        observed_at
    )

    normalized_confidence = _confidence(
        confidence
    )

    if not normalized_source:
        raise ValueError(
            "Source ID is required."
        )

    if not normalized_entity:
        raise ValueError(
            "Entity ID is required."
        )

    if (
        normalized_binding_type
        not in SOURCE_ENTITY_BINDING_TYPES
    ):
        raise ValueError(
            "Source-entity binding type "
            "is unsupported."
        )

    if not normalized_evidence:
        raise ValueError(
            "Source-entity binding evidence "
            "ID is required."
        )

    if not normalized_observed_at:
        raise ValueError(
            "Source-entity binding observed_at "
            "is required."
        )

    identity = {
        "source_id": normalized_source,
        "entity_id": normalized_entity,
        "binding_type": (
            normalized_binding_type
        ),
        "evidence_id": (
            normalized_evidence
        ),
        "confidence": (
            normalized_confidence
        ),
        "observed_at": (
            normalized_observed_at
        ),
    }

    return hashlib.sha256(
        (
            "verified-source-entity-binding|"
            + _canonical_json(
                identity
            )
        ).encode(
            "utf-8"
        )
    ).hexdigest()


def verified_claim_entity_participant_id_for_record(
    *,
    claim_id: str,
    entity_id: str,
    participant_role: str,
    evidence_id: str,
    confidence: float,
    observed_at: str,
) -> str:
    normalized_claim = _clean(
        claim_id
    )

    normalized_entity = _clean(
        entity_id
    )

    normalized_role = _key(
        participant_role
    )

    normalized_evidence = _clean(
        evidence_id
    )

    normalized_observed_at = _clean(
        observed_at
    )

    normalized_confidence = _confidence(
        confidence
    )

    if not normalized_claim:
        raise ValueError(
            "Claim ID is required."
        )

    if not normalized_entity:
        raise ValueError(
            "Entity ID is required."
        )

    if (
        normalized_role
        not in CLAIM_ENTITY_PARTICIPANT_ROLES
    ):
        raise ValueError(
            "Claim-entity participant role "
            "is unsupported."
        )

    if not normalized_evidence:
        raise ValueError(
            "Claim-entity participant evidence "
            "ID is required."
        )

    if not normalized_observed_at:
        raise ValueError(
            "Claim-entity participant observed_at "
            "is required."
        )

    identity = {
        "claim_id": normalized_claim,
        "entity_id": normalized_entity,
        "participant_role": (
            normalized_role
        ),
        "evidence_id": (
            normalized_evidence
        ),
        "confidence": (
            normalized_confidence
        ),
        "observed_at": (
            normalized_observed_at
        ),
    }

    return hashlib.sha256(
        (
            "verified-claim-entity-participant|"
            + _canonical_json(
                identity
            )
        ).encode(
            "utf-8"
        )
    ).hexdigest()


def record_verified_source_entity_binding(
    *,
    source_id: str,
    entity_id: str,
    binding_type: str,
    evidence_id: str,
    confidence: float,
    observed_at: str,
    recorded_at: Optional[str] = None,
    metadata: Optional[
        Dict[str, Any]
    ] = None,
    connection_factory=None,
) -> Dict[str, Any]:
    if connection_factory is None:
        raise ValueError(
            "Verified source-entity binding "
            "requires database access."
        )

    normalized_source = _clean(
        source_id
    )

    normalized_entity = _clean(
        entity_id
    )

    normalized_type = _key(
        binding_type
    )

    normalized_evidence = _clean(
        evidence_id
    )

    normalized_observed_at = _clean(
        observed_at
    )

    normalized_confidence = _confidence(
        confidence
    )

    if (
        normalized_type
        not in SOURCE_ENTITY_BINDING_TYPES
    ):
        raise ValueError(
            "Source-entity binding type "
            "is unsupported."
        )

    if not normalized_observed_at:
        raise ValueError(
            "Source-entity binding observed_at "
            "is required."
        )

    if (
        metadata is not None
        and not isinstance(
            metadata,
            dict,
        )
    ):
        raise ValueError(
            "Source-entity binding metadata "
            "must be a dictionary."
        )

    source = _require_source(
        source_id=normalized_source,
        connection_factory=(
            connection_factory
        ),
    )

    entity = _require_entity(
        entity_id=normalized_entity,
        connection_factory=(
            connection_factory
        ),
    )

    evidence = _require_verified_evidence(
        evidence_id=normalized_evidence,
        connection_factory=(
            connection_factory
        ),
    )

    binding_id = (
        verified_source_entity_binding_id_for_record(
            source_id=normalized_source,
            entity_id=normalized_entity,
            binding_type=normalized_type,
            evidence_id=normalized_evidence,
            confidence=normalized_confidence,
            observed_at=(
                normalized_observed_at
            ),
        )
    )

    normalized_recorded_at = (
        _clean(
            recorded_at
        )
        or _now()
    )

    metadata_json = json.dumps(
        metadata or {},
        ensure_ascii=False,
        sort_keys=True,
    )

    conn = connection_factory()

    try:
        cursor = conn.execute(
            """
            INSERT INTO verified_source_entity_bindings (
              id,
              source_id,
              entity_id,
              binding_type,
              evidence_id,
              verification_status,
              confidence,
              observed_at,
              recorded_at,
              metadata_json
            )
            VALUES (?, ?, ?, ?, ?, 'verified', ?, ?, ?, ?)
            ON CONFLICT(id)
            DO NOTHING
            """,
            (
                binding_id,
                normalized_source,
                normalized_entity,
                normalized_type,
                normalized_evidence,
                normalized_confidence,
                normalized_observed_at,
                normalized_recorded_at,
                metadata_json,
            ),
        )

        created = (
            cursor.rowcount == 1
        )

        row = conn.execute(
            """
            SELECT *
            FROM verified_source_entity_bindings
            WHERE id = ?
            """,
            (
                binding_id,
            ),
        ).fetchone()

        conn.commit()

    finally:
        conn.close()

    if row is None:
        raise RuntimeError(
            "Verified source-entity binding "
            "persistence failed."
        )

    return {
        "version": (
            VERIFIED_ENTITY_BINDING_VERSION
        ),
        "binding": dict(
            row
        ),
        "source": source,
        "entity": entity,
        "evidence": evidence,
        "created": created,
        "policy": {
            "requires_verified_evidence": True,
            "minimum_confidence": (
                VERIFIED_ENTITY_BINDING_MIN_CONFIDENCE
            ),
            "append_only_identity": True,
            "alias_match_is_not_sufficient": True,
            "binding_alone_does_not_establish_claim_participation": True,
            "binding_alone_does_not_assign_authority_class": True,
            "does_not_change_live_merit": True,
        },
    }


def record_verified_claim_entity_participant(
    *,
    claim_id: str,
    entity_id: str,
    participant_role: str,
    evidence_id: str,
    confidence: float,
    observed_at: str,
    recorded_at: Optional[str] = None,
    metadata: Optional[
        Dict[str, Any]
    ] = None,
    connection_factory=None,
) -> Dict[str, Any]:
    if connection_factory is None:
        raise ValueError(
            "Verified claim-entity participant "
            "requires database access."
        )

    normalized_claim = _clean(
        claim_id
    )

    normalized_entity = _clean(
        entity_id
    )

    normalized_role = _key(
        participant_role
    )

    normalized_evidence = _clean(
        evidence_id
    )

    normalized_observed_at = _clean(
        observed_at
    )

    normalized_confidence = _confidence(
        confidence
    )

    if (
        normalized_role
        not in CLAIM_ENTITY_PARTICIPANT_ROLES
    ):
        raise ValueError(
            "Claim-entity participant role "
            "is unsupported."
        )

    if not normalized_observed_at:
        raise ValueError(
            "Claim-entity participant observed_at "
            "is required."
        )

    if (
        metadata is not None
        and not isinstance(
            metadata,
            dict,
        )
    ):
        raise ValueError(
            "Claim-entity participant metadata "
            "must be a dictionary."
        )

    claim = _require_claim(
        claim_id=normalized_claim,
        connection_factory=(
            connection_factory
        ),
    )

    entity = _require_entity(
        entity_id=normalized_entity,
        connection_factory=(
            connection_factory
        ),
    )

    evidence = _require_verified_evidence(
        evidence_id=normalized_evidence,
        connection_factory=(
            connection_factory
        ),
    )

    participant_id = (
        verified_claim_entity_participant_id_for_record(
            claim_id=normalized_claim,
            entity_id=normalized_entity,
            participant_role=(
                normalized_role
            ),
            evidence_id=normalized_evidence,
            confidence=(
                normalized_confidence
            ),
            observed_at=(
                normalized_observed_at
            ),
        )
    )

    normalized_recorded_at = (
        _clean(
            recorded_at
        )
        or _now()
    )

    metadata_json = json.dumps(
        metadata or {},
        ensure_ascii=False,
        sort_keys=True,
    )

    conn = connection_factory()

    try:
        cursor = conn.execute(
            """
            INSERT INTO verified_claim_entity_participants (
              id,
              claim_id,
              entity_id,
              participant_role,
              evidence_id,
              verification_status,
              confidence,
              observed_at,
              recorded_at,
              metadata_json
            )
            VALUES (?, ?, ?, ?, ?, 'verified', ?, ?, ?, ?)
            ON CONFLICT(id)
            DO NOTHING
            """,
            (
                participant_id,
                normalized_claim,
                normalized_entity,
                normalized_role,
                normalized_evidence,
                normalized_confidence,
                normalized_observed_at,
                normalized_recorded_at,
                metadata_json,
            ),
        )

        created = (
            cursor.rowcount == 1
        )

        row = conn.execute(
            """
            SELECT *
            FROM verified_claim_entity_participants
            WHERE id = ?
            """,
            (
                participant_id,
            ),
        ).fetchone()

        conn.commit()

    finally:
        conn.close()

    if row is None:
        raise RuntimeError(
            "Verified claim-entity participant "
            "persistence failed."
        )

    return {
        "version": (
            VERIFIED_ENTITY_BINDING_VERSION
        ),
        "participant": dict(
            row
        ),
        "claim": claim,
        "entity": entity,
        "evidence": evidence,
        "created": created,
        "policy": {
            "requires_verified_evidence": True,
            "minimum_confidence": (
                VERIFIED_ENTITY_BINDING_MIN_CONFIDENCE
            ),
            "append_only_identity": True,
            "claim_participation_is_explicit": True,
            "claim_participation_does_not_prove_source_control": True,
            "claim_participation_does_not_assign_authority_class": True,
            "does_not_change_live_merit": True,
        },
    }


def load_verified_source_claim_entity_matches(
    *,
    source_id: str,
    claim_id: str,
    connection_factory=None,
) -> Dict[str, Any]:
    if connection_factory is None:
        raise ValueError(
            "Verified entity matching requires "
            "database access."
        )

    normalized_source = _clean(
        source_id
    )

    normalized_claim = _clean(
        claim_id
    )

    if not normalized_source:
        raise ValueError(
            "Source ID is required."
        )

    if not normalized_claim:
        raise ValueError(
            "Claim ID is required."
        )

    _require_source(
        source_id=normalized_source,
        connection_factory=(
            connection_factory
        ),
    )

    _require_claim(
        claim_id=normalized_claim,
        connection_factory=(
            connection_factory
        ),
    )

    conn = connection_factory()

    try:
        rows = [
            dict(
                row
            )
            for row
            in conn.execute(
                """
                SELECT
                  e.id AS entity_id,
                  e.entity_key,
                  e.entity_type,
                  e.sport_key,
                  e.canonical_name,

                  sb.id AS source_binding_id,
                  sb.binding_type,
                  sb.evidence_id AS source_evidence_id,
                  sb.confidence AS source_confidence,
                  sb.observed_at AS source_observed_at,
                  sb.recorded_at AS source_recorded_at,

                  cp.id AS participant_id,
                  cp.participant_role,
                  cp.evidence_id AS participant_evidence_id,
                  cp.confidence AS participant_confidence,
                  cp.observed_at AS participant_observed_at,
                  cp.recorded_at AS participant_recorded_at

                FROM verified_source_entity_bindings AS sb

                JOIN verified_claim_entity_participants AS cp
                  ON cp.entity_id = sb.entity_id

                JOIN canonical_entities AS e
                  ON e.id = sb.entity_id

                WHERE
                  sb.source_id = ?
                  AND cp.claim_id = ?
                  AND sb.verification_status = 'verified'
                  AND cp.verification_status = 'verified'

                ORDER BY
                  e.entity_type,
                  e.sport_key,
                  e.canonical_name,
                  e.id,
                  sb.id,
                  cp.id
                """,
                (
                    normalized_source,
                    normalized_claim,
                ),
            ).fetchall()
        ]

    finally:
        conn.close()

    matches = []

    for row in rows:
        matches.append(
            {
                "entity": {
                    "id": row[
                        "entity_id"
                    ],
                    "entity_key": row[
                        "entity_key"
                    ],
                    "entity_type": row[
                        "entity_type"
                    ],
                    "sport_key": row[
                        "sport_key"
                    ],
                    "canonical_name": row[
                        "canonical_name"
                    ],
                },
                "source_binding": {
                    "id": row[
                        "source_binding_id"
                    ],
                    "binding_type": row[
                        "binding_type"
                    ],
                    "evidence_id": row[
                        "source_evidence_id"
                    ],
                    "confidence": row[
                        "source_confidence"
                    ],
                    "observed_at": row[
                        "source_observed_at"
                    ],
                    "recorded_at": row[
                        "source_recorded_at"
                    ],
                },
                "claim_participant": {
                    "id": row[
                        "participant_id"
                    ],
                    "participant_role": row[
                        "participant_role"
                    ],
                    "evidence_id": row[
                        "participant_evidence_id"
                    ],
                    "confidence": row[
                        "participant_confidence"
                    ],
                    "observed_at": row[
                        "participant_observed_at"
                    ],
                    "recorded_at": row[
                        "participant_recorded_at"
                    ],
                },
            }
        )

    return {
        "version": (
            VERIFIED_ENTITY_MATCH_VERSION
        ),
        "source_id": normalized_source,
        "claim_id": normalized_claim,
        "matches": matches,
        "match_count": len(
            matches
        ),
        "policy": {
            "source_entity_binding_is_verified": True,
            "claim_entity_participation_is_verified": True,
            "common_entity_is_required": True,
            "alias_match_is_not_used_as_trust": True,
            "match_is_authority_candidate_only": True,
            "authority_class": "",
            "authority_not_adjudicated_here": True,
            "does_not_change_live_merit": True,
        },
    }