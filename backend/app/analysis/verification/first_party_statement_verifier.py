import hashlib
import json
import re

from datetime import datetime
from typing import Any, Dict, Optional
from urllib.parse import urlparse


from app.analysis.multi_evaluator_adjudication import (
    MULTI_EVALUATOR_FIELDS,
)

from app.analysis.trusted_validation import (
    VALIDATION_REFERENCE_BASIS_BY_FIELD,
)

from app.services.direct_authority_verifier import (
    DIRECT_AUTHORITY_ENTITY_VERIFIER_VERSION,
    build_direct_authority_entity_candidate,
)

from app.services.machine_verified_revision_runtime import (
    MACHINE_VERIFIED_REVISION_RUNTIME_VERSION,
    persist_machine_verified_reference_revision,
)


FIRST_PARTY_STATEMENT_VERIFIER_VERSION = (
    "first-party-statement-verifier-v1"
)

FIRST_PARTY_STATEMENT_PROOF_EVIDENCE_TYPE = (
    "claim_entity_participant_reference"
)

FIRST_PARTY_STATEMENT_PROOF_KIND = (
    "explicit_official_article_participation"
)

FIRST_PARTY_STATEMENT_PROOF_RELATIONSHIP = (
    "verifies_entity_participation"
)


# These are verifier-owned semantics.
# Callers never choose field values or basis classes.
FIRST_PARTY_FIXED_VALUES = {
    "source_role": "primary_stakeholder",
    "authority_class": "direct",
    "reliability_class": "not_applicable",
    "provenance_class": "direct_statement",
    "stance": "supports",
    "independence_status": "not_applicable",
}


FIRST_PARTY_FIXED_BASIS = {
    "source_role": "direct_authority_record",
    "authority_class": "direct_authority_record",
    "reliability_class": "deterministic_rule",
    "provenance_class": "structured_fact",
    "stance": "structured_fact",
    "independence_status": "deterministic_rule",
}


def _clean(value: Any) -> str:
    return " ".join(
        str(
            value or ""
        ).split()
    )


def _key(value: Any) -> str:
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

    if text.endswith("Z"):
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
            f"{label} must include timezone."
        )

    return parsed


def _confidence(
    value: Any,
    *,
    label: str,
) -> float:
    if isinstance(
        value,
        bool,
    ):
        raise ValueError(
            f"{label} must be numeric."
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
            f"{label} must be numeric."
        ) from exc

    if not (
        0.95
        <= result
        <= 1.0
    ):
        raise ValueError(
            f"{label} must be between 0.95 and 1.0."
        )

    return result


def _domain_for_url(
    value: str,
    normalize_url,
) -> str:
    normalized = _clean(
        normalize_url(
            value
        )
    )

    hostname = _key(
        urlparse(
            normalized
        ).hostname
    )

    if hostname.startswith(
        "www."
    ):
        hostname = hostname[4:]

    return hostname


def _decode_metadata(
    value: Any,
) -> Dict[str, Any]:
    try:
        parsed = json.loads(
            str(
                value or "{}"
            )
        )

    except Exception as exc:
        raise ValueError(
            "First-party proof metadata "
            "contains invalid JSON."
        ) from exc

    if not isinstance(
        parsed,
        dict,
    ):
        raise ValueError(
            "First-party proof metadata "
            "must be a dictionary."
        )

    return parsed


def _load_proof_context(
    *,
    source_id: str,
    claim_id: str,
    proof_evidence_id: str,
    normalize_url,
    connection_factory,
) -> Dict[str, Any]:
    conn = connection_factory()

    try:
        source_row = conn.execute(
            """
            SELECT *
            FROM intelligence_sources
            WHERE id = ?
            """,
            (
                source_id,
            ),
        ).fetchone()

        claim_row = conn.execute(
            """
            SELECT *
            FROM intelligence_claims
            WHERE id = ?
            """,
            (
                claim_id,
            ),
        ).fetchone()

        proof_row = conn.execute(
            """
            SELECT *
            FROM evidence_records
            WHERE id = ?
            """,
            (
                proof_evidence_id,
            ),
        ).fetchone()

        link_rows = conn.execute(
            """
            SELECT *
            FROM claim_links
            WHERE claim_id = ?
              AND evidence_id = ?
              AND relationship_type = ?
            ORDER BY id ASC
            """,
            (
                claim_id,
                proof_evidence_id,
                FIRST_PARTY_STATEMENT_PROOF_RELATIONSHIP,
            ),
        ).fetchall()

    finally:
        conn.close()

    if source_row is None:
        raise ValueError(
            "First-party semantic source "
            "does not exist."
        )

    if claim_row is None:
        raise ValueError(
            "First-party semantic claim "
            "does not exist."
        )

    if proof_row is None:
        raise ValueError(
            "First-party statement proof "
            "does not exist."
        )

    if len(
        link_rows
    ) != 1:
        raise ValueError(
            "First-party statement proof must "
            "have exactly one verified "
            "claim-participation link."
        )

    source = dict(
        source_row
    )

    claim = dict(
        claim_row
    )

    proof = dict(
        proof_row
    )

    link = dict(
        link_rows[0]
    )

    if (
        _key(
            proof.get(
                "verification_status"
            )
        )
        != "verified"
    ):
        raise ValueError(
            "First-party statement proof "
            "must be verified."
        )

    if (
        _key(
            proof.get(
                "evidence_type"
            )
        )
        != FIRST_PARTY_STATEMENT_PROOF_EVIDENCE_TYPE
    ):
        raise ValueError(
            "First-party statement proof "
            "evidence type is unsupported."
        )

    if (
        _clean(
            proof.get(
                "subject_key"
            )
        )
        != _clean(
            claim.get(
                "subject_key"
            )
        )
    ):
        raise ValueError(
            "First-party statement proof "
            "subject does not match claim."
        )

    canonical_url = _clean(
        proof.get(
            "canonical_url"
        )
    )

    if not canonical_url:
        raise ValueError(
            "First-party statement proof "
            "must preserve its canonical URL."
        )

    expected_domain = _key(
        source.get(
            "canonical_domain"
        )
    )

    actual_domain = (
        _domain_for_url(
            canonical_url,
            normalize_url,
        )
    )

    if (
        not expected_domain
        or actual_domain
        != expected_domain
    ):
        raise ValueError(
            "First-party statement proof URL "
            "does not belong to the verified source."
        )

    link_confidence = _confidence(
        link.get(
            "confidence"
        ),
        label=(
            "First-party statement proof link confidence"
        ),
    )

    metadata = _decode_metadata(
        proof.get(
            "metadata_json"
        )
    )

    return {
        "source": source,
        "claim": claim,
        "proof": proof,
        "link": link,
        "link_confidence": (
            link_confidence
        ),
        "metadata": metadata,
    }


def _validate_fixed_semantics() -> None:
    if (
        set(
            FIRST_PARTY_FIXED_VALUES
        )
        != set(
            MULTI_EVALUATOR_FIELDS
        )
    ):
        raise ValueError(
            "First-party semantic verifier "
            "does not cover all adjudication fields."
        )

    if (
        set(
            FIRST_PARTY_FIXED_BASIS
        )
        != set(
            MULTI_EVALUATOR_FIELDS
        )
    ):
        raise ValueError(
            "First-party semantic verifier "
            "basis coverage is incomplete."
        )

    for field in MULTI_EVALUATOR_FIELDS:
        basis = (
            FIRST_PARTY_FIXED_BASIS[
                field
            ]
        )

        if (
            basis
            not in (
                VALIDATION_REFERENCE_BASIS_BY_FIELD[
                    field
                ]
            )
        ):
            raise ValueError(
                "First-party semantic verifier "
                f"basis is invalid for {field}."
            )


def build_first_party_statement_semantic_candidate(
    *,
    source_id: str,
    claim_id: str,
    proof_evidence_id: str,
    normalize_url,
    connection_factory,
    authority_candidate_builder=(
        build_direct_authority_entity_candidate
    ),
) -> Dict[str, Any]:
    normalized_source_id = _clean(
        source_id
    )

    normalized_claim_id = _clean(
        claim_id
    )

    normalized_proof_id = _clean(
        proof_evidence_id
    )

    if not normalized_source_id:
        raise ValueError(
            "First-party semantic source ID "
            "is required."
        )

    if not normalized_claim_id:
        raise ValueError(
            "First-party semantic claim ID "
            "is required."
        )

    if not normalized_proof_id:
        raise ValueError(
            "First-party statement proof "
            "evidence ID is required."
        )

    if normalize_url is None:
        raise ValueError(
            "First-party semantic verifier "
            "requires URL normalization."
        )

    if connection_factory is None:
        raise ValueError(
            "First-party semantic verifier "
            "requires database access."
        )

    _validate_fixed_semantics()

    authority_result = (
        authority_candidate_builder(
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
    )

    if not isinstance(
        authority_result,
        dict,
    ):
        raise ValueError(
            "Direct-authority candidate "
            "returned invalid data."
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
            "Direct-authority candidate "
            "version is unsupported."
        )

    if (
        authority_result.get(
            "status"
        )
        != "verified_direct_stakeholder"
    ):
        return {
            "version": (
                FIRST_PARTY_STATEMENT_VERIFIER_VERSION
            ),
            "status": (
                authority_result.get(
                    "status"
                )
            ),
            "candidate": None,
            "authority_candidate": (
                authority_result
            ),
            "policy": {
                "fails_closed_without_unique_direct_stakeholder": True,
                "no_machine_reference_created": True,
                "does_not_establish_claim_truth": True,
                "does_not_change_live_merit": True,
            },
        }

    authority_candidate = (
        authority_result.get(
            "candidate"
        )
    )

    if not isinstance(
        authority_candidate,
        dict,
    ):
        raise ValueError(
            "Verified direct-authority "
            "candidate is missing."
        )

    participant_evidence_ids = {
        _clean(
            value
        )
        for value
        in authority_candidate.get(
            "participant_evidence_ids",
            [],
        )
        if _clean(
            value
        )
    }

    if (
        normalized_proof_id
        not in participant_evidence_ids
    ):
        raise ValueError(
            "First-party statement proof is "
            "not part of the verified "
            "claim-participation lineage."
        )

    context = (
        _load_proof_context(
            source_id=(
                normalized_source_id
            ),
            claim_id=(
                normalized_claim_id
            ),
            proof_evidence_id=(
                normalized_proof_id
            ),
            normalize_url=(
                normalize_url
            ),
            connection_factory=(
                connection_factory
            ),
        )
    )

    metadata = context[
        "metadata"
    ]

    entity = (
        authority_candidate[
            "entity"
        ]
    )

    entity_id = _clean(
        entity.get(
            "id"
        )
    )

    if (
        _key(
            metadata.get(
                "proof_kind"
            )
        )
        != FIRST_PARTY_STATEMENT_PROOF_KIND
    ):
        raise ValueError(
            "First-party statement proof kind "
            "is unsupported."
        )

    if (
        _clean(
            metadata.get(
                "entity_id"
            )
        )
        != entity_id
    ):
        raise ValueError(
            "First-party statement proof entity "
            "does not match verified authority entity."
        )

    if (
        metadata.get(
            "claim_truth_established"
        )
        is not False
    ):
        raise ValueError(
            "First-party semantic proof must "
            "explicitly preserve the distinction "
            "between source semantics and claim truth."
        )

    canonical_claim_text = _clean(
        context[
            "claim"
        ].get(
            "canonical_text"
        )
    )

    statement_title = _clean(
        metadata.get(
            "title"
        )
    )

    if not canonical_claim_text:
        raise ValueError(
            "First-party semantic claim text "
            "is missing."
        )

    # v1 is intentionally strict:
    # the independently captured first-party
    # statement title must be exactly the
    # canonical claim under validation.
    if (
        statement_title
        != canonical_claim_text
    ):
        raise ValueError(
            "First-party statement title does "
            "not exactly match the canonical claim."
        )

    content_sha256 = _key(
        metadata.get(
            "content_sha256"
        )
    )

    if not re.fullmatch(
        r"[0-9a-f]{64}",
        content_sha256,
    ):
        raise ValueError(
            "First-party statement proof "
            "content SHA256 is invalid."
        )

    authority_confidence = _confidence(
        authority_candidate.get(
            "confidence"
        ),
        label=(
            "Verified direct-authority confidence"
        ),
    )

    proof_confidence = min(
        authority_confidence,
        context[
            "link_confidence"
        ],
    )

    authority_available_at = (
        _timestamp(
            authority_candidate.get(
                "availability_at"
            ),
            label=(
                "Direct-authority availability time"
            ),
        )
    )

    proof_recorded_at = (
        _timestamp(
            context[
                "proof"
            ].get(
                "recorded_at"
            ),
            label=(
                "First-party proof recorded time"
            ),
        )
    )

    link_recorded_at = (
        _timestamp(
            context[
                "link"
            ].get(
                "recorded_at"
            ),
            label=(
                "First-party proof-link recorded time"
            ),
        )
    )

    availability_at = max(
        authority_available_at,
        proof_recorded_at,
        link_recorded_at,
    ).isoformat()

    field_verifications = [
        {
            "field": field,
            "value": (
                FIRST_PARTY_FIXED_VALUES[
                    field
                ]
            ),
            "confidence": (
                proof_confidence
            ),
            "basis_class": (
                FIRST_PARTY_FIXED_BASIS[
                    field
                ]
            ),
        }
        for field
        in MULTI_EVALUATOR_FIELDS
    ]

    return {
        "version": (
            FIRST_PARTY_STATEMENT_VERIFIER_VERSION
        ),
        "status": (
            "verified_first_party_statement"
        ),
        "source_id": (
            normalized_source_id
        ),
        "claim_id": (
            normalized_claim_id
        ),
        "proof_evidence_id": (
            normalized_proof_id
        ),
        "candidate": {
            "entity": entity,
            "canonical_url": (
                context[
                    "proof"
                ][
                    "canonical_url"
                ]
            ),
            "canonical_claim_text": (
                canonical_claim_text
            ),
            "content_sha256": (
                content_sha256
            ),
            "confidence": (
                proof_confidence
            ),
            "availability_at": (
                availability_at
            ),
            "source_binding_ids": (
                authority_candidate[
                    "source_binding_ids"
                ]
            ),
            "claim_participant_ids": (
                authority_candidate[
                    "claim_participant_ids"
                ]
            ),
            "source_evidence_ids": (
                authority_candidate[
                    "source_evidence_ids"
                ]
            ),
            "participant_evidence_ids": (
                authority_candidate[
                    "participant_evidence_ids"
                ]
            ),
            "field_verifications": (
                field_verifications
            ),
        },
        "policy": {
            "requires_verified_direct_stakeholder": True,
            "requires_verified_participation_evidence": True,
            "requires_exact_statement_claim_identity": True,
            "field_values_are_verifier_fixed": True,
            "field_basis_classes_are_verifier_fixed": True,
            "reliability_not_applicable_is_not_a_reliability_rating": True,
            "independence_not_applicable_is_not_independence_established": True,
            "direct_statement_does_not_establish_claim_truth": True,
            "supports_describes_source_stance_not_objective_truth": True,
            "does_not_establish_claim_truth": True,
            "does_not_change_live_merit": True,
        },
    }


def persist_first_party_statement_verified_revision(
    *,
    source_id: str,
    claim_id: str,
    proof_evidence_id: str,
    normalize_url,
    connection_factory,
    recorded_at: Optional[str] = None,
    candidate_builder=(
        build_first_party_statement_semantic_candidate
    ),
    revision_runner=(
        persist_machine_verified_reference_revision
    ),
) -> Dict[str, Any]:
    candidate_result = (
        candidate_builder(
            source_id=source_id,
            claim_id=claim_id,
            proof_evidence_id=(
                proof_evidence_id
            ),
            normalize_url=(
                normalize_url
            ),
            connection_factory=(
                connection_factory
            ),
        )
    )

    if not isinstance(
        candidate_result,
        dict,
    ):
        raise ValueError(
            "First-party semantic candidate "
            "returned invalid data."
        )

    if (
        _clean(
            candidate_result.get(
                "version"
            )
        )
        != FIRST_PARTY_STATEMENT_VERIFIER_VERSION
    ):
        raise ValueError(
            "First-party semantic candidate "
            "version is unsupported."
        )

    if (
        candidate_result.get(
            "status"
        )
        != "verified_first_party_statement"
    ):
        return {
            "version": (
                FIRST_PARTY_STATEMENT_VERIFIER_VERSION
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
            "revision": None,
            "policy": {
                "fails_closed_without_verified_first_party_statement": True,
                "no_machine_reference_created": True,
                "does_not_establish_claim_truth": True,
                "does_not_change_live_merit": True,
            },
        }

    candidate = (
        candidate_result[
            "candidate"
        ]
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
        "proof_evidence_id": (
            candidate_result[
                "proof_evidence_id"
            ]
        ),
        "content_sha256": (
            candidate[
                "content_sha256"
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

    runtime = (
        revision_runner(
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
                "canonical_url": (
                    candidate[
                        "canonical_url"
                    ]
                ),
                "reference_key": (
                    "first-party-statement-proof:"
                    + reference_hash
                ),
                "claim_summary": (
                    candidate[
                        "canonical_claim_text"
                    ]
                ),
                "metadata": {
                    "first_party_statement_verifier_version": (
                        FIRST_PARTY_STATEMENT_VERIFIER_VERSION
                    ),
                    "entity": (
                        candidate[
                            "entity"
                        ]
                    ),
                    "proof_evidence_id": (
                        candidate_result[
                            "proof_evidence_id"
                        ]
                    ),
                    "content_sha256": (
                        candidate[
                            "content_sha256"
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
                    "fixed_values": (
                        FIRST_PARTY_FIXED_VALUES
                    ),
                    "fixed_basis_classes": (
                        FIRST_PARTY_FIXED_BASIS
                    ),
                    "claim_truth_established": False,
                    "reliability_not_applicable_is_not_a_reliability_rating": True,
                    "independence_not_applicable_is_not_independence_established": True,
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
    )

    if not isinstance(
        runtime,
        dict,
    ):
        raise ValueError(
            "Machine-verified semantic runtime "
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
            "Machine-verified semantic runtime "
            "version is unsupported."
        )

    machine_fields = {}

    training_fields = set()

    for run in runtime.get(
        "machine_evaluator_runs",
        [],
    ):
        if (
            _key(
                run.get(
                    "derivation_mode"
                )
            )
            != "machine_verified"
        ):
            raise ValueError(
                "First-party semantic verifier "
                "produced a non-machine-verified run."
            )

        for judgment in run.get(
            "judgments",
            [],
        ):
            field = _key(
                judgment.get(
                    "field"
                )
            )

            if field in machine_fields:
                raise ValueError(
                    "First-party semantic verifier "
                    "produced duplicate fields."
                )

            machine_fields[
                field
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

            if (
                judgment.get(
                    "training_eligible"
                )
                is True
            ):
                training_fields.add(
                    field
                )

    expected_fields = {
        field: {
            "value": (
                FIRST_PARTY_FIXED_VALUES[
                    field
                ]
            ),
            "basis_class": (
                FIRST_PARTY_FIXED_BASIS[
                    field
                ]
            ),
        }
        for field
        in MULTI_EVALUATOR_FIELDS
    }

    if machine_fields != expected_fields:
        raise ValueError(
            "First-party semantic machine "
            "verification fields are inconsistent."
        )

    partition = _key(
        runtime.get(
            "partition"
        )
    )

    expected_training_fields = (
        {
            "authority_class",
        }
        if partition
        == "calibration"
        else set()
    )

    if (
        training_fields
        != expected_training_fields
    ):
        raise ValueError(
            "First-party semantic verifier "
            "changed the existing training-truth boundary."
        )

    return {
        "version": (
            FIRST_PARTY_STATEMENT_VERIFIER_VERSION
        ),
        "status": (
            "persisted_verified_first_party_semantics"
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
        "revision_runtime": (
            runtime
        ),
        "revision": (
            runtime.get(
                "revision"
            )
        ),
        "policy": {
            "all_six_fields_share_one_verified_trigger": True,
            "only_authority_class_can_train_on_calibration": True,
            "holdout_fields_are_never_training_eligible": True,
            "auto_gold_basis_map_is_not_expanded": True,
            "model_output_is_not_used_as_verification": True,
            "does_not_establish_claim_truth": True,
            "does_not_change_live_merit": True,
        },
    }
