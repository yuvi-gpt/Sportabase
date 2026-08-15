import hashlib
import json

from datetime import (
    datetime,
)

from typing import (
    Any,
    Dict,
    Optional,
)


from app.analysis.authority import (
    CLAIM_AUTHORITY_CLASSES,
    CLAIM_SOURCE_ROLES,
)

from app.intelligence.entity_bindings import (
    SOURCE_ENTITY_BINDING_TYPES,
    VERIFIED_ENTITY_MATCH_VERSION,
    load_verified_source_claim_entity_matches,
)

from app.services.machine_verified_revision_runtime import (
    MACHINE_VERIFIED_REVISION_RUNTIME_VERSION,
    persist_machine_verified_reference_revision,
)


DIRECT_AUTHORITY_ENTITY_VERIFIER_VERSION = (
    "direct-authority-entity-verifier-v1"
)


DIRECT_STAKEHOLDER_ENTITY_TYPES = (
    "player",
    "club",
    "team",
    "organization",
    "person",
)


DIRECT_STAKEHOLDER_PARTICIPANT_ROLES = (
    "subject",
    "actor",
    "counterparty",
    "origin",
    "destination",
    "affected_party",
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


def _timestamp(
    value: Any,
    *,
    label: str,
) -> datetime:
    text = _clean(
        value
    )

    if not text:
        raise ValueError(
            f"{label} is required."
        )

    if text.endswith(
        "Z"
    ):
        text = (
            text[:-1]
            + "+00:00"
        )

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
        or parsed.utcoffset()
        is None
    ):
        raise ValueError(
            f"{label} must include a timezone."
        )

    return parsed


def _confidence(
    value: Any,
) -> float:
    if isinstance(
        value,
        bool,
    ):
        raise ValueError(
            "Direct authority proof confidence "
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
            "Direct authority proof confidence "
            "must be numeric."
        ) from exc

    if not (
        0.95
        <= result
        <= 1.0
    ):
        raise ValueError(
            "Direct authority proof confidence "
            "must be between 0.95 and 1.0."
        )

    return result


def build_direct_authority_entity_candidate(
    *,
    source_id: str,
    claim_id: str,
    connection_factory,
    match_loader=(
        load_verified_source_claim_entity_matches
    ),
) -> Dict[str, Any]:
    normalized_source_id = _clean(
        source_id
    )

    normalized_claim_id = _clean(
        claim_id
    )

    if not normalized_source_id:
        raise ValueError(
            "Direct authority verifier source ID "
            "is required."
        )

    if not normalized_claim_id:
        raise ValueError(
            "Direct authority verifier claim ID "
            "is required."
        )

    if connection_factory is None:
        raise ValueError(
            "Direct authority verifier requires "
            "database access."
        )

    matches = match_loader(
        source_id=(
            normalized_source_id
        ),
        claim_id=(
            normalized_claim_id
        ),
        connection_factory=(
            connection_factory
        ),
    )

    if not isinstance(
        matches,
        dict,
    ):
        raise ValueError(
            "Verified entity matcher returned "
            "invalid data."
        )

    if (
        _clean(
            matches.get(
                "version"
            )
        )
        != VERIFIED_ENTITY_MATCH_VERSION
    ):
        raise ValueError(
            "Verified entity matcher version "
            "is unsupported."
        )

    raw_matches = matches.get(
        "matches",
        [],
    )

    if not isinstance(
        raw_matches,
        list,
    ):
        raise ValueError(
            "Verified entity matches "
            "must be a list."
        )

    eligible = []

    for row in raw_matches:
        if not isinstance(
            row,
            dict,
        ):
            raise ValueError(
                "Verified entity match "
                "must be a dictionary."
            )

        entity = row.get(
            "entity"
        )

        source_binding = row.get(
            "source_binding"
        )

        participant = row.get(
            "claim_participant"
        )

        if (
            not isinstance(
                entity,
                dict,
            )
            or not isinstance(
                source_binding,
                dict,
            )
            or not isinstance(
                participant,
                dict,
            )
        ):
            raise ValueError(
                "Verified entity match lineage "
                "is incomplete."
            )

        entity_type = _key(
            entity.get(
                "entity_type"
            )
        )

        binding_type = _key(
            source_binding.get(
                "binding_type"
            )
        )

        participant_role = _key(
            participant.get(
                "participant_role"
            )
        )

        if (
            entity_type
            not in DIRECT_STAKEHOLDER_ENTITY_TYPES
        ):
            continue

        if (
            participant_role
            not in DIRECT_STAKEHOLDER_PARTICIPANT_ROLES
        ):
            continue

        if (
            binding_type
            not in SOURCE_ENTITY_BINDING_TYPES
        ):
            raise ValueError(
                "Verified source binding type "
                "is unsupported."
            )

        source_confidence = _confidence(
            source_binding.get(
                "confidence"
            )
        )

        participant_confidence = _confidence(
            participant.get(
                "confidence"
            )
        )

        source_recorded_at = _timestamp(
            source_binding.get(
                "recorded_at"
            ),
            label=(
                "Source-entity binding recorded_at"
            ),
        )

        participant_recorded_at = _timestamp(
            participant.get(
                "recorded_at"
            ),
            label=(
                "Claim-entity participant recorded_at"
            ),
        )

        eligible.append(
            {
                **row,
                "_source_confidence": (
                    source_confidence
                ),
                "_participant_confidence": (
                    participant_confidence
                ),
                "_availability_at": max(
                    source_recorded_at,
                    participant_recorded_at,
                ),
            }
        )

    by_entity = {}

    for row in eligible:
        entity_id = _clean(
            row[
                "entity"
            ].get(
                "id"
            )
        )

        if not entity_id:
            raise ValueError(
                "Verified direct-authority entity "
                "ID is missing."
            )

        by_entity.setdefault(
            entity_id,
            [],
        ).append(
            row
        )

    entity_ids = sorted(
        by_entity
    )

    base_policy = {
        "uses_verified_source_entity_binding": True,
        "uses_verified_claim_entity_participation": True,
        "requires_same_canonical_entity": True,
        "aliases_are_not_authority_evidence": True,
        "no_fuzzy_resolution_in_authority_path": True,
        "source_role_is_verifier_fixed": True,
        "authority_class_is_verifier_fixed": True,
        "governing_bodies_are_not_direct_stakeholders_here": True,
        "competitions_are_not_direct_stakeholders_here": True,
        "does_not_establish_sports_claim_truth": True,
        "does_not_change_live_merit": True,
    }

    if not entity_ids:
        return {
            "version": (
                DIRECT_AUTHORITY_ENTITY_VERIFIER_VERSION
            ),
            "status": (
                "no_verified_direct_stakeholder_match"
            ),
            "source_id": (
                normalized_source_id
            ),
            "claim_id": (
                normalized_claim_id
            ),
            "candidate": None,
            "candidate_entity_ids": [],
            "policy": {
                **base_policy,
                "fails_closed_without_match": True,
            },
        }

    if len(
        entity_ids
    ) > 1:
        return {
            "version": (
                DIRECT_AUTHORITY_ENTITY_VERIFIER_VERSION
            ),
            "status": (
                "ambiguous_verified_direct_stakeholder_match"
            ),
            "source_id": (
                normalized_source_id
            ),
            "claim_id": (
                normalized_claim_id
            ),
            "candidate": None,
            "candidate_entity_ids": (
                entity_ids
            ),
            "policy": {
                **base_policy,
                "ambiguity_fails_closed": True,
            },
        }

    entity_id = entity_ids[0]

    rows = by_entity[
        entity_id
    ]

    entity = rows[0][
        "entity"
    ]

    source_binding_ids = sorted(
        {
            _clean(
                row[
                    "source_binding"
                ].get(
                    "id"
                )
            )
            for row in rows
        }
    )

    participant_ids = sorted(
        {
            _clean(
                row[
                    "claim_participant"
                ].get(
                    "id"
                )
            )
            for row in rows
        }
    )

    source_evidence_ids = sorted(
        {
            _clean(
                row[
                    "source_binding"
                ].get(
                    "evidence_id"
                )
            )
            for row in rows
        }
    )

    participant_evidence_ids = sorted(
        {
            _clean(
                row[
                    "claim_participant"
                ].get(
                    "evidence_id"
                )
            )
            for row in rows
        }
    )

    confidence = min(
        [
            row[
                "_source_confidence"
            ]
            for row in rows
        ]
        + [
            row[
                "_participant_confidence"
            ]
            for row in rows
        ]
    )

    availability_at = max(
        row[
            "_availability_at"
        ]
        for row in rows
    ).isoformat()

    if (
        "primary_stakeholder"
        not in CLAIM_SOURCE_ROLES
        or "direct"
        not in CLAIM_AUTHORITY_CLASSES
    ):
        raise ValueError(
            "Direct authority vocabulary "
            "is unavailable."
        )

    candidate = {
        "entity": {
            "id": entity_id,
            "entity_key": _clean(
                entity.get(
                    "entity_key"
                )
            ),
            "entity_type": _key(
                entity.get(
                    "entity_type"
                )
            ),
            "sport_key": _key(
                entity.get(
                    "sport_key"
                )
            ),
            "canonical_name": _clean(
                entity.get(
                    "canonical_name"
                )
            ),
        },
        "source_role": (
            "primary_stakeholder"
        ),
        "authority_class": "direct",
        "confidence": confidence,
        "availability_at": (
            availability_at
        ),
        "source_binding_ids": (
            source_binding_ids
        ),
        "claim_participant_ids": (
            participant_ids
        ),
        "source_evidence_ids": (
            source_evidence_ids
        ),
        "participant_evidence_ids": (
            participant_evidence_ids
        ),
        "field_verifications": [
            {
                "field": "source_role",
                "value": (
                    "primary_stakeholder"
                ),
                "confidence": confidence,
                "basis_class": (
                    "direct_authority_record"
                ),
            },
            {
                "field": (
                    "authority_class"
                ),
                "value": "direct",
                "confidence": confidence,
                "basis_class": (
                    "direct_authority_record"
                ),
            },
        ],
    }

    return {
        "version": (
            DIRECT_AUTHORITY_ENTITY_VERIFIER_VERSION
        ),
        "status": (
            "verified_direct_stakeholder"
        ),
        "source_id": (
            normalized_source_id
        ),
        "claim_id": (
            normalized_claim_id
        ),
        "candidate": candidate,
        "candidate_entity_ids": [
            entity_id
        ],
        "policy": {
            **base_policy,
            "machine_verifiable_basis": (
                "direct_authority_record"
            ),
        },
    }


def persist_direct_authority_verified_revision(
    *,
    source_id: str,
    claim_id: str,
    normalize_url,
    connection_factory,
    recorded_at: Optional[str] = None,
    candidate_builder=(
        build_direct_authority_entity_candidate
    ),
    revision_runner=(
        persist_machine_verified_reference_revision
    ),
) -> Dict[str, Any]:
    candidate_result = candidate_builder(
        source_id=source_id,
        claim_id=claim_id,
        connection_factory=(
            connection_factory
        ),
    )

    if not isinstance(
        candidate_result,
        dict,
    ):
        raise ValueError(
            "Direct authority candidate builder "
            "returned invalid data."
        )

    if (
        _clean(
            candidate_result.get(
                "version"
            )
        )
        != DIRECT_AUTHORITY_ENTITY_VERIFIER_VERSION
    ):
        raise ValueError(
            "Direct authority candidate version "
            "is unsupported."
        )

    if (
        candidate_result.get(
            "status"
        )
        != "verified_direct_stakeholder"
    ):
        return {
            "version": (
                DIRECT_AUTHORITY_ENTITY_VERIFIER_VERSION
            ),
            "status": (
                candidate_result.get(
                    "status"
                )
            ),
            "persisted": False,
            "candidate": (
                candidate_result
            ),
            "revision_runtime": None,
            "policy": {
                "fails_closed_without_unique_verified_match": True,
                "no_machine_reference_was_created": True,
                "does_not_change_live_merit": True,
            },
        }

    candidate = candidate_result.get(
        "candidate"
    )

    if not isinstance(
        candidate,
        dict,
    ):
        raise ValueError(
            "Verified direct authority candidate "
            "is missing."
        )

    proof_identity = {
        "source_id": _clean(
            source_id
        ),
        "claim_id": _clean(
            claim_id
        ),
        "entity_id": (
            candidate[
                "entity"
            ][
                "id"
            ]
        ),
        "source_binding_ids": (
            candidate[
                "source_binding_ids"
            ]
        ),
        "claim_participant_ids": (
            candidate[
                "claim_participant_ids"
            ]
        ),
    }

    reference_hash = hashlib.sha256(
        _canonical_json(
            proof_identity
        ).encode(
            "utf-8"
        )
    ).hexdigest()

    runtime = revision_runner(
        claim_id=(
            _clean(
                claim_id
            )
        ),
        verification_evidence={
            "observed_at": (
                candidate[
                    "availability_at"
                ]
            ),
            "reference_key": (
                "direct-authority-entity-proof:"
                + reference_hash
            ),
            "claim_summary": (
                "Verified source control and "
                "verified claim participation "
                "share one canonical entity."
            ),
            "metadata": {
                "direct_authority_verifier_version": (
                    DIRECT_AUTHORITY_ENTITY_VERIFIER_VERSION
                ),
                "entity": (
                    candidate[
                        "entity"
                    ]
                ),
                "source_binding_ids": (
                    candidate[
                        "source_binding_ids"
                    ]
                ),
                "claim_participant_ids": (
                    candidate[
                        "claim_participant_ids"
                    ]
                ),
                "source_evidence_ids": (
                    candidate[
                        "source_evidence_ids"
                    ]
                ),
                "participant_evidence_ids": (
                    candidate[
                        "participant_evidence_ids"
                    ]
                ),
                "proof_confidence": (
                    candidate[
                        "confidence"
                    ]
                ),
                "source_role": (
                    "primary_stakeholder"
                ),
                "authority_class": (
                    "direct"
                ),
                "claim_truth_established": False,
            },
        },
        field_verifications=(
            candidate[
                "field_verifications"
            ]
        ),
        normalize_url=(
            normalize_url
        ),
        connection_factory=(
            connection_factory
        ),
        recorded_at=(
            recorded_at
        ),
    )

    if not isinstance(
        runtime,
        dict,
    ):
        raise ValueError(
            "Machine-verified revision runtime "
            "returned invalid data."
        )

    if (
        _clean(
            runtime.get(
                "version"
            )
        )
        != MACHINE_VERIFIED_REVISION_RUNTIME_VERSION
    ):
        raise ValueError(
            "Machine-verified revision runtime "
            "version is unsupported."
        )

    machine_runs = runtime.get(
        "machine_evaluator_runs",
        [],
    )

    if not isinstance(
        machine_runs,
        list,
    ):
        raise ValueError(
            "Machine-verified evaluator runs "
            "must be a list."
        )

    verified_fields = {}

    for run in machine_runs:
        if (
            _key(
                run.get(
                    "derivation_mode"
                )
            )
            != "machine_verified"
        ):
            raise ValueError(
                "Direct authority verifier produced "
                "a non-machine-verified run."
            )

        for judgment in run.get(
            "judgments",
            [],
        ):
            verified_fields[
                _key(
                    judgment.get(
                        "field"
                    )
                )
            ] = {
                "value": _clean(
                    judgment.get(
                        "value"
                    )
                ),
                "basis_class": _key(
                    judgment.get(
                        "basis_class"
                    )
                ),
            }

    expected_fields = {
        "source_role": {
            "value": (
                "primary_stakeholder"
            ),
            "basis_class": (
                "direct_authority_record"
            ),
        },
        "authority_class": {
            "value": "direct",
            "basis_class": (
                "direct_authority_record"
            ),
        },
    }

    if verified_fields != expected_fields:
        raise ValueError(
            "Direct authority machine-verification "
            "fields are inconsistent."
        )

    return {
        "version": (
            DIRECT_AUTHORITY_ENTITY_VERIFIER_VERSION
        ),
        "status": (
            "persisted_verified_direct_authority"
            if runtime.get(
                "status"
            )
            == "persisted"
            else runtime.get(
                "status"
            )
        ),
        "persisted": True,
        "candidate": (
            candidate_result
        ),
        "revision_runtime": runtime,
        "revision": runtime.get(
            "revision"
        ),
        "policy": {
            "authority_values_are_verifier_fixed": True,
            "caller_cannot_choose_source_role": True,
            "caller_cannot_choose_authority_class": True,
            "basis_is_direct_authority_record": True,
            "machine_verified_revision_runtime_is_reused": True,
            "underlying_verified_binding_lineage_is_preserved": True,
            "does_not_establish_sports_claim_truth": True,
            "does_not_change_live_merit": True,
        },
    }