import hashlib
import json
import re

from datetime import datetime
from typing import Any, Dict, Optional
from urllib.parse import urlparse


from app.analysis.canonical_outcome import (
    CANONICAL_OUTCOME_CONTRACT_VERSION,
    CANONICAL_TENURE_OUTCOME_CONTRACT_VERSION,
    compare_canonical_claim_to_outcome,
)

from app.intelligence.canonical_claims import (
    normalize_canonical_claim,
)

from app.services.direct_authority_verifier import (
    DIRECT_AUTHORITY_ENTITY_VERIFIER_VERSION,
    build_direct_authority_entity_candidate,
)

from app.services.machine_verified_revision_runtime import (
    MACHINE_VERIFIED_REVISION_RUNTIME_VERSION,
    persist_machine_verified_reference_revision,
)


CANONICAL_OUTCOME_RESOLUTION_VERIFIER_VERSION = (
    "canonical-outcome-resolution-verifier-v1"
)

CANONICAL_OUTCOME_PROOF_EVIDENCE_TYPE = (
    "canonical_outcome_reference"
)

CANONICAL_OUTCOME_PROOF_RELATIONSHIP = (
    "verifies_canonical_outcome"
)

CANONICAL_OUTCOME_PROOF_KIND = (
    "explicit_official_canonical_outcome"
)


def _clean(value: Any) -> str:
    return " ".join(
        str(value or "").split()
    )


def _key(value: Any) -> str:
    return _clean(value).lower()


def _metadata(value: Any) -> Dict[str, Any]:
    try:
        parsed = json.loads(
            str(value or "{}")
        )
    except Exception as exc:
        raise ValueError(
            "Canonical outcome metadata "
            "contains invalid JSON."
        ) from exc

    if not isinstance(
        parsed,
        dict,
    ):
        raise ValueError(
            "Canonical outcome metadata "
            "must be a dictionary."
        )

    return parsed


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
        or parsed.utcoffset() is None
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
        result = float(value)
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
            f"{label} must be between "
            "0.95 and 1.0."
        )

    return result


def _domain_for_url(
    value: str,
    normalize_url,
) -> str:
    normalized = _clean(
        normalize_url(value)
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


def _fail(
    status: str,
    *,
    claim_id: str,
    source_id: str,
    proof_evidence_id: str,
    authority_candidate=None,
    canonical_resolution=None,
) -> Dict[str, Any]:
    return {
        "version": (
            CANONICAL_OUTCOME_RESOLUTION_VERIFIER_VERSION
        ),
        "status": status,
        "claim_id": claim_id,
        "source_id": source_id,
        "proof_evidence_id": (
            proof_evidence_id
        ),
        "candidate": None,
        "authority_candidate": (
            authority_candidate
        ),
        "canonical_resolution": (
            canonical_resolution
        ),
        "policy": {
            "fails_closed": True,
            "requires_persisted_structured_claim": True,
            "requires_verified_outcome_proof": True,
            "requires_verified_direct_stakeholder": True,
            "requires_deterministic_canonical_resolution": True,
            "claim_truth_established": False,
            "numeric_negative_penalty_authorized": False,
            "live_negative_merit_authorized": False,
            "does_not_change_live_merit": True,
        },
    }


def _load_context(
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
            ORDER BY id
            """,
            (
                claim_id,
                proof_evidence_id,
                CANONICAL_OUTCOME_PROOF_RELATIONSHIP,
            ),
        ).fetchall()

    finally:
        conn.close()

    if source_row is None:
        raise ValueError(
            "Canonical outcome source "
            "does not exist."
        )

    if claim_row is None:
        raise ValueError(
            "Canonical outcome claim "
            "does not exist."
        )

    if proof_row is None:
        raise ValueError(
            "Canonical outcome proof "
            "does not exist."
        )

    if len(link_rows) != 1:
        raise ValueError(
            "Canonical outcome proof must "
            "have exactly one canonical-"
            "outcome claim link."
        )

    source = dict(source_row)
    claim = dict(claim_row)
    proof = dict(proof_row)
    link = dict(link_rows[0])

    if (
        _key(
            proof.get(
                "verification_status"
            )
        )
        != "verified"
    ):
        raise ValueError(
            "Canonical outcome proof "
            "must be verified."
        )

    if (
        _key(
            proof.get(
                "evidence_type"
            )
        )
        != CANONICAL_OUTCOME_PROOF_EVIDENCE_TYPE
    ):
        raise ValueError(
            "Canonical outcome proof "
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
            "Canonical outcome proof subject "
            "does not match the claim."
        )

    canonical_url = _clean(
        proof.get(
            "canonical_url"
        )
    )

    if not canonical_url:
        raise ValueError(
            "Canonical outcome proof must "
            "preserve its canonical URL."
        )

    expected_domain = _key(
        source.get(
            "canonical_domain"
        )
    )

    actual_domain = _domain_for_url(
        canonical_url,
        normalize_url,
    )

    if (
        not expected_domain
        or actual_domain
        != expected_domain
    ):
        raise ValueError(
            "Canonical outcome proof URL "
            "does not belong to the "
            "verified source."
        )

    return {
        "source": source,
        "claim": claim,
        "proof": proof,
        "link": link,
        "claim_metadata": _metadata(
            claim.get(
                "metadata_json"
            )
        ),
        "proof_metadata": _metadata(
            proof.get(
                "metadata_json"
            )
        ),
    }


def build_canonical_outcome_resolution_candidate(
    *,
    source_id: str,
    claim_id: str,
    proof_evidence_id: str,
    normalize_url,
    connection_factory,
    authority_candidate_builder=(
        build_direct_authority_entity_candidate
    ),
    resolution_builder=(
        compare_canonical_claim_to_outcome
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
            "Canonical outcome source ID "
            "is required."
        )

    if not normalized_claim_id:
        raise ValueError(
            "Canonical outcome claim ID "
            "is required."
        )

    if not normalized_proof_id:
        raise ValueError(
            "Canonical outcome proof ID "
            "is required."
        )

    if normalize_url is None:
        raise ValueError(
            "Canonical outcome verifier "
            "requires URL normalization."
        )

    if connection_factory is None:
        raise ValueError(
            "Canonical outcome verifier "
            "requires database access."
        )

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
            "Canonical outcome authority "
            "candidate returned invalid data."
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
            "Canonical outcome authority "
            "candidate version is unsupported."
        )

    if (
        authority_result.get(
            "status"
        )
        != "verified_direct_stakeholder"
    ):
        return _fail(
            str(
                authority_result.get(
                    "status"
                )
                or "direct_stakeholder_not_verified"
            ),
            claim_id=(
                normalized_claim_id
            ),
            source_id=(
                normalized_source_id
            ),
            proof_evidence_id=(
                normalized_proof_id
            ),
            authority_candidate=(
                authority_result
            ),
        )

    authority = authority_result.get(
        "candidate"
    )

    if not isinstance(
        authority,
        dict,
    ):
        raise ValueError(
            "Verified direct authority "
            "candidate is missing."
        )

    participant_evidence_ids = {
        _clean(value)
        for value
        in authority.get(
            "participant_evidence_ids",
            [],
        )
        if _clean(value)
    }

    if (
        normalized_proof_id
        not in participant_evidence_ids
    ):
        raise ValueError(
            "Canonical outcome proof is "
            "not part of verified claim-"
            "participant authority lineage."
        )

    context = _load_context(
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

    proof_metadata = context[
        "proof_metadata"
    ]

    claim_metadata = context[
        "claim_metadata"
    ]

    entity = authority.get(
        "entity"
    )

    if not isinstance(
        entity,
        dict,
    ):
        raise ValueError(
            "Canonical outcome authority "
            "entity is missing."
        )

    entity_id = _clean(
        entity.get(
            "id"
        )
    )

    if (
        _key(
            proof_metadata.get(
                "proof_kind"
            )
        )
        != CANONICAL_OUTCOME_PROOF_KIND
    ):
        raise ValueError(
            "Canonical outcome proof kind "
            "is unsupported."
        )

    if (
        _clean(
            proof_metadata.get(
                "source_id"
            )
        )
        != normalized_source_id
    ):
        raise ValueError(
            "Canonical outcome proof source "
            "identity does not match."
        )

    if (
        _clean(
            proof_metadata.get(
                "claim_id"
            )
        )
        != normalized_claim_id
    ):
        raise ValueError(
            "Canonical outcome proof claim "
            "identity does not match."
        )

    if (
        _clean(
            proof_metadata.get(
                "entity_id"
            )
        )
        != entity_id
    ):
        raise ValueError(
            "Canonical outcome proof entity "
            "does not match verified authority."
        )

    if (
        proof_metadata.get(
            "claim_truth_established"
        )
        is not False
    ):
        raise ValueError(
            "Canonical outcome proof must "
            "preserve the claim-truth boundary."
        )

    content_sha256 = _key(
        proof_metadata.get(
            "content_sha256"
        )
    )

    if not re.fullmatch(
        r"[0-9a-f]{64}",
        content_sha256,
    ):
        raise ValueError(
            "Canonical outcome proof "
            "content SHA256 is invalid."
        )

    claim_candidate = (
        claim_metadata.get(
            "canonical_claim_candidate"
        )
    )

    if not isinstance(
        claim_candidate,
        dict,
    ):
        return _fail(
            "canonical_claim_structure_unavailable",
            claim_id=(
                normalized_claim_id
            ),
            source_id=(
                normalized_source_id
            ),
            proof_evidence_id=(
                normalized_proof_id
            ),
            authority_candidate=(
                authority_result
            ),
        )

    outcome_candidate = (
        proof_metadata.get(
            "outcome_candidate"
        )
    )

    if not isinstance(
        outcome_candidate,
        dict,
    ):
        raise ValueError(
            "Canonical outcome proof "
            "structured outcome is missing."
        )

    normalized_claim = (
        normalize_canonical_claim(
            claim_candidate
        )
    )

    normalized_outcome = (
        normalize_canonical_claim(
            outcome_candidate
        )
    )

    claim_observed_at = _clean(
        context[
            "claim"
        ].get(
            "first_seen_at"
        )
    )

    outcome_observed_at = _clean(
        context[
            "proof"
        ].get(
            "observed_at"
        )
    )

    resolution = resolution_builder(
        claim_candidate=(
            normalized_claim
        ),
        outcome_candidate=(
            normalized_outcome
        ),
        claim_observed_at=(
            claim_observed_at
        ),
        outcome_observed_at=(
            outcome_observed_at
        ),
    )

    if not isinstance(
        resolution,
        dict,
    ):
        raise ValueError(
            "Canonical outcome comparison "
            "returned invalid data."
        )

    if (
        _clean(
            resolution.get(
                "version"
            )
        )
        not in {
            CANONICAL_OUTCOME_CONTRACT_VERSION,
            CANONICAL_TENURE_OUTCOME_CONTRACT_VERSION,
        }
    ):
        raise ValueError(
            "Canonical outcome comparison "
            "version is unsupported."
        )

    if (
        resolution.get(
            "status"
        )
        != (
            "resolution_against_claim_candidate"
        )
        or resolution.get(
            "direction"
        )
        != "against_claim"
    ):
        return _fail(
            "canonical_outcome_not_against_claim",
            claim_id=(
                normalized_claim_id
            ),
            source_id=(
                normalized_source_id
            ),
            proof_evidence_id=(
                normalized_proof_id
            ),
            authority_candidate=(
                authority_result
            ),
            canonical_resolution=(
                resolution
            ),
        )

    link_confidence = _confidence(
        context[
            "link"
        ].get(
            "confidence"
        ),
        label=(
            "Canonical outcome proof "
            "link confidence"
        ),
    )

    authority_confidence = _confidence(
        authority.get(
            "confidence"
        ),
        label=(
            "Canonical outcome authority "
            "confidence"
        ),
    )

    proof_confidence = min(
        link_confidence,
        authority_confidence,
    )

    availability_at = max(
        _timestamp(
            authority.get(
                "availability_at"
            ),
            label=(
                "Direct authority "
                "availability time"
            ),
        ),
        _timestamp(
            context[
                "proof"
            ].get(
                "recorded_at"
            ),
            label=(
                "Canonical outcome proof "
                "recorded time"
            ),
        ),
        _timestamp(
            context[
                "link"
            ].get(
                "recorded_at"
            ),
            label=(
                "Canonical outcome link "
                "recorded time"
            ),
        ),
    ).isoformat()

    return {
        "version": (
            CANONICAL_OUTCOME_RESOLUTION_VERIFIER_VERSION
        ),
        "status": (
            "verified_canonical_outcome_against_claim"
        ),
        "claim_id": (
            normalized_claim_id
        ),
        "source_id": (
            normalized_source_id
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
            "content_sha256": (
                content_sha256
            ),
            "claim_candidate": (
                normalized_claim
            ),
            "outcome_candidate": (
                normalized_outcome
            ),
            "canonical_resolution": (
                resolution
            ),
            "rule_id": (
                resolution.get(
                    "rule_id"
                )
            ),
            "confidence": (
                proof_confidence
            ),
            "availability_at": (
                availability_at
            ),
            "source_binding_ids": (
                authority.get(
                    "source_binding_ids",
                    [],
                )
            ),
            "claim_participant_ids": (
                authority.get(
                    "claim_participant_ids",
                    [],
                )
            ),
            "source_evidence_ids": (
                authority.get(
                    "source_evidence_ids",
                    [],
                )
            ),
            "participant_evidence_ids": (
                authority.get(
                    "participant_evidence_ids",
                    [],
                )
            ),
        },
        "authority_candidate": (
            authority_result
        ),
        "canonical_resolution": (
            resolution
        ),
        "policy": {
            "persisted_structured_claim_required": True,
            "verified_outcome_proof_required": True,
            "verified_direct_stakeholder_required": True,
            "proof_must_be_in_authority_lineage": True,
            "canonical_url_must_match_verified_source": True,
            "content_hash_required": True,
            "canonical_resolution_is_deterministic": True,
            "canonical_resolution_is_machine_verifiable": True,
            "resolution_against_claim_verified": True,
            "claim_truth_established": False,
            "resolution_is_not_permanent_objective_truth": True,
            "numeric_negative_penalty_authorized": False,
            "live_negative_merit_authorized": False,
            "does_not_change_live_merit": True,
        },
    }


def persist_canonical_outcome_resolution_verified_revision(
    *,
    source_id: str,
    claim_id: str,
    proof_evidence_id: str,
    normalize_url,
    connection_factory,
    recorded_at: Optional[str] = None,
    candidate_builder=(
        build_canonical_outcome_resolution_candidate
    ),
    revision_runner=(
        persist_machine_verified_reference_revision
    ),
) -> Dict[str, Any]:
    candidate_result = candidate_builder(
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

    if not isinstance(
        candidate_result,
        dict,
    ):
        raise ValueError(
            "Canonical outcome resolution "
            "candidate returned invalid data."
        )

    if (
        _clean(
            candidate_result.get(
                "version"
            )
        )
        != (
            CANONICAL_OUTCOME_RESOLUTION_VERIFIER_VERSION
        )
    ):
        raise ValueError(
            "Canonical outcome resolution "
            "candidate version is unsupported."
        )

    if (
        candidate_result.get(
            "status"
        )
        != (
            "verified_canonical_outcome_against_claim"
        )
    ):
        return {
            "version": (
                CANONICAL_OUTCOME_RESOLUTION_VERIFIER_VERSION
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
                "fails_closed_without_verified_resolution": True,
                "claim_truth_established": False,
                "numeric_negative_penalty_authorized": False,
                "live_negative_merit_authorized": False,
                "does_not_change_live_merit": True,
            },
        }

    candidate = candidate_result[
        "candidate"
    ]

    proof_identity = {
        "source_id": _clean(
            source_id
        ),
        "claim_id": _clean(
            claim_id
        ),
        "proof_evidence_id": (
            candidate_result[
                "proof_evidence_id"
            ]
        ),
        "entity_id": (
            candidate[
                "entity"
            ][
                "id"
            ]
        ),
        "content_sha256": (
            candidate[
                "content_sha256"
            ]
        ),
        "rule_id": (
            candidate[
                "rule_id"
            ]
        ),
        "outcome_candidate": (
            candidate[
                "outcome_candidate"
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
            "canonical_url": (
                candidate[
                    "canonical_url"
                ]
            ),
            "reference_key": (
                "canonical-outcome-resolution-proof:"
                + reference_hash
            ),
            "claim_summary": (
                "Machine-verified canonical "
                "outcome resolution against "
                "the earlier claim."
            ),
            "metadata": {
                "canonical_outcome_resolution_verifier_version": (
                    CANONICAL_OUTCOME_RESOLUTION_VERIFIER_VERSION
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
                "claim_candidate": (
                    candidate[
                        "claim_candidate"
                    ]
                ),
                "outcome_candidate": (
                    candidate[
                        "outcome_candidate"
                    ]
                ),
                "canonical_resolution": (
                    candidate[
                        "canonical_resolution"
                    ]
                ),
                "canonical_outcome_resolution_verified": True,
                "resolved_against_claim": True,
                "claim_truth_established": False,
                "live_merit_changed": False,
            },
        },
        field_verifications=[
            {
                "field": "stance",
                "value": "contradicts",
                "confidence": (
                    candidate[
                        "confidence"
                    ]
                ),
                "basis_class": (
                    "canonical_resolution"
                ),
            }
        ],
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
            "Canonical outcome machine "
            "revision returned invalid data."
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
            "Canonical outcome machine "
            "revision version is unsupported."
        )

    matching = []

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
                "Canonical outcome verifier "
                "produced a non-machine run."
            )

        for judgment in run.get(
            "judgments",
            [],
        ):
            if (
                _key(
                    judgment.get(
                        "field"
                    )
                )
                == "stance"
            ):
                matching.append(
                    judgment
                )

    if len(matching) != 1:
        raise ValueError(
            "Canonical outcome verifier must "
            "produce exactly one machine "
            "stance judgment."
        )

    judgment = matching[0]

    if (
        _key(
            judgment.get(
                "value"
            )
        )
        != "contradicts"
        or _key(
            judgment.get(
                "basis_class"
            )
        )
        != "canonical_resolution"
    ):
        raise ValueError(
            "Canonical outcome machine stance "
            "does not match the verified "
            "resolution contract."
        )

    runtime_status = _clean(
        runtime.get(
            "status"
        )
    )

    return {
        "version": (
            CANONICAL_OUTCOME_RESOLUTION_VERIFIER_VERSION
        ),
        "status": (
            "persisted_verified_canonical_outcome_resolution"
            if runtime_status
            == "persisted"
            else runtime_status
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
        "resolution_evidence_id": (
            (
                runtime.get(
                    "evidence"
                )
                or {}
            ).get(
                "id"
            )
        ),
        "policy": {
            "canonical_resolution_machine_verified": True,
            "machine_stance": "contradicts",
            "machine_basis_class": (
                "canonical_resolution"
            ),
            "resolved_against_claim": True,
            "claim_truth_established": False,
            "resolution_is_not_permanent_objective_truth": True,
            "numeric_negative_penalty_authorized": False,
            "live_negative_merit_authorized": False,
            "does_not_change_live_merit": True,
        },
    }
